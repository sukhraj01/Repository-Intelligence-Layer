"""The three supervision hooks through which the RQ2 arms differ, and the K-rank quality signal.

Implements ``docs/08_experimental_design.md`` "The four supervision arms" and "The quality signal".
An arm is exactly three hooks; everything else in the training path is shared code configured
identically for every arm (``ril.training.training``; the held-identical block of the design is
not changed here):

* **filter** (FILTER): which training examples or positives are kept. Identity: keep all.
* **weigher** (WEIGHT): one loss weight per example. Identity: weight 1.
* **ordering** (CURRICULUM): the order in which kept examples are visited in each pass. Identity:
  a seeded random permutation per pass.

RAW is the three identities. The quality signal is SweRank's K-rank: the rank of a positive among
the snapshot's non-positive functions under a **separately pretrained** teacher (never the model
being trained), read from the E-POOL-RANKS feature table; an example's K-rank is the minimum over
its positives (the best-ranked positive). Which teacher, which K, whether FILTER acts on positives
or on whole examples, and the weight form are open (ADR-002, E-PILOT-K): every such choice is a
parameter here, marked ``provisional: ADR-002``, with no default that could pass for a decision.

Design property the arms test relies on: every non-identity hook reduces to the identity at its
limit (FILTER at K = infinity keeps everything; a weight form whose weights are all 1; a curriculum
whose difficulty is constant is a stable sort of the identity permutation), so the code path outside
the hooks can be shown identical across arms.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, Protocol

import numpy as np

from ril.training.pool_reader import FeatureTable, PoolExample

PROVISIONAL = "provisional: ADR-002"
ARM_NAMES = ("RAW", "FILTER", "WEIGHT", "CURRICULUM", "NOISE", "RAW_SUBSAMPLE")
Record = dict[str, Any]


def rng_for(seed: int, *parts: object) -> np.random.Generator:
    """Generator keyed by the seed and a purpose path (independent of call order)."""
    digest = hashlib.sha256(":".join([str(seed), *map(str, parts)]).encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], "big"))


# --------------------------------------------------------------------------- quality signal


class QualitySignal(Protocol):
    """K-rank of a positive and of an example (lower = easier, more consistent)."""

    @property
    def teacher(self) -> str: ...

    def positive_rank(self, example: PoolExample, positive_id: str) -> int: ...

    def example_rank(self, example: PoolExample) -> int: ...


@dataclass(frozen=True)
class TableKRank:
    """K-rank from a feature table under one teacher; a missing rank raises (no silent default)."""

    table: FeatureTable
    teacher: str

    def __post_init__(self) -> None:
        if self.teacher not in self.table.teachers:
            raise ValueError(f"teacher {self.teacher!r} not in the table {self.table.teachers}")

    def positive_rank(self, example: PoolExample, positive_id: str) -> int:
        r = self.table.rank(example.instance_id, positive_id, self.teacher)
        if r is None:
            raise KeyError(f"{example.instance_id}: no {self.teacher} rank for a positive")
        return r

    def example_rank(self, example: PoolExample) -> int:
        return min(self.positive_rank(example, p) for p in example.positive_ids)


@dataclass(frozen=True)
class MappingKRank:
    """K-rank from an in-memory ``{(instance, positive id): rank}`` mapping (mined on the fly)."""

    ranks: Mapping[tuple[str, str], int]
    teacher: str

    def positive_rank(self, example: PoolExample, positive_id: str) -> int:
        return int(self.ranks[(example.instance_id, positive_id)])

    def example_rank(self, example: PoolExample) -> int:
        return min(self.positive_rank(example, p) for p in example.positive_ids)


# --------------------------------------------------------------------------- hook 1: filter


@dataclass
class FilterReport:
    """What a filter removed (recorded per run; FILTER's drop rate is reported)."""

    examples_in: int = 0
    examples_out: int = 0
    positives_in: int = 0
    positives_out: int = 0

    def to_dict(self) -> Record:
        return {
            "examples_in": self.examples_in,
            "examples_out": self.examples_out,
            "positives_in": self.positives_in,
            "positives_out": self.positives_out,
            "examples_kept_share": self.examples_out / self.examples_in
            if self.examples_in
            else math.nan,
            "positives_kept_share": self.positives_out / self.positives_in
            if self.positives_in
            else math.nan,
        }


class ExampleFilter(Protocol):
    name: str

    def apply(self, examples: Sequence[PoolExample]) -> tuple[list[PoolExample], FilterReport]: ...


def _report(before: Sequence[PoolExample], after: Sequence[PoolExample]) -> FilterReport:
    return FilterReport(
        examples_in=len(before),
        examples_out=len(after),
        positives_in=sum(len(e.positive_ids) for e in before),
        positives_out=sum(len(e.positive_ids) for e in after),
    )


class KeepAll:
    """Identity filter."""

    name = "keep_all"

    def apply(self, examples: Sequence[PoolExample]) -> tuple[list[PoolExample], FilterReport]:
        out = list(examples)
        return out, _report(examples, out)


class KRankThreshold:
    """Keep what ranks within the top ``k`` under the teacher (``k = None``: infinity).

    ``level='positive'``: drop the positives ranked above ``k`` (a dropped positive becomes neither
    positive nor negative), then drop examples left without a positive (SweRank's construction
    treats each positive as its own instance). ``level='example'``: keep an example if its best
    positive is within ``k`` (a pull-request-level rule). Which level is ADR-002's.
    """

    name = "krank_threshold"

    def __init__(self, signal: QualitySignal, k: int | None, level: str) -> None:
        if level not in ("positive", "example"):
            raise ValueError("level must be 'positive' or 'example'")
        if k is not None and k < 1:
            raise ValueError("k must be at least 1")
        self.signal, self.k, self.level = signal, k, level

    def _ok(self, rank: int) -> bool:
        return self.k is None or rank <= self.k

    def apply(self, examples: Sequence[PoolExample]) -> tuple[list[PoolExample], FilterReport]:
        out: list[PoolExample] = []
        for ex in examples:
            if self.level == "example":
                if self._ok(self.signal.example_rank(ex)):
                    out.append(ex)
                continue
            keep = [
                i
                for i, p in enumerate(ex.positive_ids)
                if self._ok(self.signal.positive_rank(ex, p))
            ]
            if not keep:
                continue
            if len(keep) == len(ex.positive_ids):
                out.append(ex)
                continue
            out.append(
                replace(
                    ex,
                    positive_ids=tuple(ex.positive_ids[i] for i in keep),
                    positive_texts=tuple(ex.positive_texts[i] for i in keep),
                    masked_ids=ex.masked_ids
                    + tuple(p for i, p in enumerate(ex.positive_ids) if i not in keep),
                )
            )
        return out, _report(examples, out)


class NoisePositives:
    """Negative control (D38): each example's positives are replaced by random functions of the
    same repository; query, count of positives, negatives and everything else stay as in RAW.

    The replacement is drawn from the example's non-positive functions (the snapshot is one
    repository) with a generator keyed by the seed and the instance id, so it does not depend on
    the order of examples. The true positives become masked: they are neither positive nor
    negative for this example. The question it answers is how much of a gain is adaptation to the
    format of the data (issue-style queries, function text, prefix, length) and not supervision.
    """

    name = "noise_positives"

    def __init__(self, seed: int) -> None:
        self.seed = seed

    def apply(self, examples: Sequence[PoolExample]) -> tuple[list[PoolExample], FilterReport]:
        out: list[PoolExample] = []
        for ex in examples:
            n = len(ex.positive_ids)
            if len(ex.candidate_ids) <= n:
                continue  # too small a snapshot to draw a replacement without exhausting it
            pick = sorted(
                int(i)
                for i in rng_for(self.seed, "noise", ex.instance_id).choice(
                    len(ex.candidate_ids), size=n, replace=False
                )
            )
            chosen = set(pick)
            out.append(
                replace(
                    ex,
                    positive_ids=tuple(ex.candidate_ids[i] for i in pick),
                    positive_texts=tuple(ex.candidate_texts[i] for i in pick),
                    candidate_ids=tuple(
                        c for i, c in enumerate(ex.candidate_ids) if i not in chosen
                    ),
                    candidate_texts=tuple(
                        t for i, t in enumerate(ex.candidate_texts) if i not in chosen
                    ),
                    masked_ids=ex.masked_ids + ex.positive_ids,
                )
            )
        return out, _report(examples, out)


class RandomSubset:
    """Size-matched control for FILTER (D43): a random subset of ``size`` examples.

    The draw is keyed by the seed and ``draw`` (a purpose path, so independent draws of one seed
    are independent of each other and of the batch plan) and made over the examples sorted by
    instance id, so it does not depend on the order the pool was read in. The kept examples keep
    their pool order. Positives, negatives and every other property of an example are untouched.
    """

    name = "random_subset"

    def __init__(self, size: int, seed: int, draw: int = 0) -> None:
        if size < 1:
            raise ValueError("size must be at least 1")
        if draw < 0:
            raise ValueError("draw must be non-negative")
        self.size, self.seed, self.draw = size, seed, draw

    def apply(self, examples: Sequence[PoolExample]) -> tuple[list[PoolExample], FilterReport]:
        if self.size > len(examples):
            raise ValueError(f"subset of {self.size} asked from a pool of {len(examples)}")
        by_id = sorted(range(len(examples)), key=lambda i: examples[i].instance_id)
        pick = rng_for(self.seed, "subsample", self.draw).choice(
            len(examples), size=self.size, replace=False
        )
        keep = sorted(by_id[int(i)] for i in pick)
        out = [examples[i] for i in keep]
        return out, _report(examples, out)


# --------------------------------------------------------------------------- hook 2: weights


class ExampleWeigher(Protocol):
    name: str

    def weight(self, example: PoolExample) -> float: ...


class UnitWeight:
    """Identity weigher."""

    name = "unit"

    def weight(self, example: PoolExample) -> float:
        return 1.0


WEIGHT_FORMS = ("power", "sigmoid")


class KRankWeight:
    """Soft weight from the example's K-rank (the same signal as FILTER, as a weight).

    ``power``: ``min(1, (k / rank) ** p)``, 1 inside the top ``k``, decaying outside;
    ``sigmoid``: ``1 / (1 + exp((rank - k) / s))``. A floor keeps every example in the loss.
    The form and its parameters are ADR-002's (E-PILOT-K); none is a recommendation.
    """

    name = "krank_weight"

    def __init__(
        self, signal: QualitySignal, form: str, k: float, param: float, floor: float = 0.0
    ) -> None:
        if form not in WEIGHT_FORMS:
            raise ValueError(f"form must be one of {WEIGHT_FORMS}")
        if k <= 0 or param <= 0 or not 0.0 <= floor <= 1.0:
            raise ValueError("k and param must be positive, floor in [0, 1]")
        self.signal, self.form, self.k, self.param, self.floor = signal, form, k, param, floor

    def weight(self, example: PoolExample) -> float:
        r = float(self.signal.example_rank(example))
        if self.form == "power":
            w = min(1.0, (self.k / r) ** self.param)
        else:
            z = (r - self.k) / self.param
            w = 1.0 / (1.0 + math.exp(min(z, 700.0)))
        return float(max(self.floor, w))


# --------------------------------------------------------------------------- hook 3: ordering


class Ordering(Protocol):
    name: str

    def order(self, examples: Sequence[PoolExample], seed: int, epoch: int) -> list[int]: ...


class RandomOrder:
    """Identity ordering: a seeded random permutation per pass."""

    name = "random"

    def order(self, examples: Sequence[PoolExample], seed: int, epoch: int) -> list[int]:
        return [int(i) for i in rng_for(seed, "order", epoch).permutation(len(examples))]


class Curriculum:
    """Easy to hard by a difficulty key, as a stable sort of the identity permutation.

    Difficulty defaults to the example's K-rank (low rank = easy). ``buckets`` > 0 sorts by the
    bucket of the difficulty quantile instead of its exact value (examples inside a bucket keep the
    random order). Every pass repeats the schedule over a fresh permutation. Pacing beyond this is
    ADR-002's.
    """

    name = "curriculum"

    def __init__(
        self,
        difficulty: Callable[[PoolExample], float],
        buckets: int = 0,
        reverse: bool = False,
    ) -> None:
        if buckets < 0:
            raise ValueError("buckets must be non-negative")
        self.difficulty, self.buckets, self.reverse = difficulty, buckets, reverse
        if reverse:
            self.name = "curriculum_reversed"

    def order(self, examples: Sequence[PoolExample], seed: int, epoch: int) -> list[int]:
        base = RandomOrder().order(examples, seed, epoch)
        d = np.asarray([float(self.difficulty(examples[i])) for i in base])
        if self.buckets > 0 and len(d):
            ranks = np.argsort(np.argsort(d, kind="stable"), kind="stable")
            d = np.floor(ranks * self.buckets / len(d))
        if self.reverse:
            d = -d  # hard to easy (the reversed-order control, D37)
        perm = np.argsort(d, kind="stable")
        return [base[int(i)] for i in perm]


# --------------------------------------------------------------------------- the arm


@dataclass(frozen=True)
class Arm:
    """An RQ2 arm: a name and exactly the three hooks."""

    name: str
    filter: ExampleFilter
    weigher: ExampleWeigher
    ordering: Ordering

    def describe(self) -> Record:
        return {
            "name": self.name,
            "filter": self.filter.name,
            "weigher": self.weigher.name,
            "ordering": self.ordering.name,
        }


ARM_HOOK_FIELDS = ("filter", "weigher", "ordering")


@dataclass(frozen=True)
class AgreementKRank:
    """Agreement of several teachers: a positive's rank is the worst (largest) of their ranks.

    Inside the top ``k`` under this signal means inside the top ``k`` under every teacher (the
    "agreement of two teachers" cell of E-PILOT-K); its name is the teachers joined by ``+``.
    """

    parts: tuple[QualitySignal, ...]

    @property
    def teacher(self) -> str:
        return "+".join(p.teacher for p in self.parts)

    def positive_rank(self, example: PoolExample, positive_id: str) -> int:
        return max(p.positive_rank(example, positive_id) for p in self.parts)

    def example_rank(self, example: PoolExample) -> int:
        return min(self.positive_rank(example, p) for p in example.positive_ids)


def _signal(cfg: Mapping[str, Any], signals: Mapping[str, QualitySignal]) -> QualitySignal:
    """The quality signal a hook names: one teacher, or ``a+b`` for the agreement of teachers."""
    t = str(cfg["teacher"])
    if t in signals:
        return signals[t]
    parts = t.split("+")
    if len(parts) > 1 and all(p in signals for p in parts):
        return AgreementKRank(tuple(signals[p] for p in parts))
    raise KeyError(f"no quality signal for teacher {t!r}")


def arm_from_config(
    cfg: Mapping[str, Any], signals: Mapping[str, QualitySignal], seed: int = 0
) -> Arm:
    """Build an arm from the configuration's ``arm`` section.

    ``{name, filter: {...}|null, weight: {...}|null, ordering: {...}|null}``; a missing or null
    hook is the identity. ``signals`` maps teacher names to quality signals. ``seed`` keys the
    NOISE control's and the subsample's draw (``RAW_SUBSAMPLE``: ``subsample: {size, draw}``).
    NOISE takes no hook section; ``ordering.reverse: true`` reverses the
    CURRICULUM order.
    """
    name = str(cfg["name"])
    if name not in ARM_NAMES:
        raise ValueError(f"unknown arm {name!r}; arms: {ARM_NAMES}")
    f: ExampleFilter = KeepAll()
    w: ExampleWeigher = UnitWeight()
    o: Ordering = RandomOrder()
    fc, wc, oc = cfg.get("filter"), cfg.get("weight"), cfg.get("ordering")
    if name == "NOISE":
        if fc or wc or oc:
            raise ValueError("the NOISE control takes no filter, weight or ordering section")
        f = NoisePositives(seed)
    sc = cfg.get("subsample")
    if name == "RAW_SUBSAMPLE":
        if fc or wc or oc or not sc:
            raise ValueError("RAW_SUBSAMPLE takes a 'subsample' section and no other hook")
        f = RandomSubset(int(sc["size"]), seed, int(sc.get("draw", 0)))
    elif sc:
        raise ValueError("a 'subsample' section belongs to the RAW_SUBSAMPLE arm")
    if fc:
        k = fc.get("k")
        f = KRankThreshold(_signal(fc, signals), None if k is None else int(k), str(fc["level"]))
    if wc:
        w = KRankWeight(
            _signal(wc, signals),
            str(wc["form"]),
            float(wc["k"]),
            float(wc["param"]),
            float(wc.get("floor", 0.0)),
        )
    if oc:
        sig = _signal(oc, signals)
        o = Curriculum(
            lambda ex: float(sig.example_rank(ex)),
            int(oc.get("buckets", 0)),
            bool(oc.get("reverse", False)),
        )
    return Arm(name=name, filter=f, weigher=w, ordering=o)
