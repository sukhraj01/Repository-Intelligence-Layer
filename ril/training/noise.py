"""Injected label noise at a known rate, and the teacher ranks of the noised positives.

Implements ``docs/EXPERIMENTS.md`` E-PILOT-NOISE (decisions D45 to D48). The question: when a share
``r`` of the training pairs carries a wrong positive set, do FILTER and WEIGHT recover what RAW
loses? That needs the noise to be plausible, known and identical across the arms being compared.

* **Injection** (:func:`inject`): each pair, independently with probability ``r``, has its positive
  set replaced by the same number of functions drawn uniformly from the other functions of the
  snapshot (the snapshot is one repository), so the replacement is same-repository, plausible and
  exactly known. The true positives become masked (neither positive nor negative), as in the NOISE
  control (D38). One uniform draw ``u`` per pair, keyed by the seed and the instance id, decides
  ``u < r``: the realisation does not depend on the order of the pool, is the same for every cell
  of a seed, and is nested across rates (the pairs noised at 0.2 are also noised at 0.4).
* **Sibling kind** (``kind="sibling"``, E-PILOT-NOISE-SIB, D54): the replacement comes from the
  neighbourhood of the true positives, as a real mislabel does (the edited function is next to the
  one the issue is about). Per pair the first level that holds at least as many non-positive
  functions as there are positives is used: the file(s) of the true positives, then their class,
  then their directory, then the whole snapshot (the uniform draw above). The class level is a
  subset of the file level, so it is only reached if the file level is empty, which it never is for
  a pair whose positives share a file; its share is reported anyway. The pairs noised are the same
  as under the uniform kind (same uniform draw ``u``), only the replacement differs.
* **Ledger** (:class:`NoiseLedger`): the per-pair indicator. It lives outside the examples, so no
  arm can read it; only the ORACLE-CLEAN control and the analysis get it.
* **Ranks** (:func:`noisy_signal`): the K-rank of a (possibly replaced) positive is 1 + the
  number of functions that are not positives *of the pair as the arm sees it* scored strictly
  higher; this is the published definition (``ril.training.pool_ranks.positive_ranks``) applied
  to the noised positive set, from per-function scores stored by
  :func:`ril.training.train_jobs.score_job`. The true positives are ordinary competitors for a
  replacement, as they would be for a real mislabel.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

import numpy as np

from ril.training import pool_ranks as pr
from ril.training.pool_reader import PoolExample
from ril.training.supervision import MappingKRank, QualitySignal, rng_for

NOISE_VERSION = "noise-dose/v1"
SIBLING_VERSION = "noise-sibling/v1"
KINDS = ("uniform", "sibling")
SIBLING_LEVELS = ("file", "class", "directory", "uniform")
SCHEME_KINDS = {"same_snapshot_uniform": "uniform", "sibling_same_file": "sibling"}
PROVISIONAL = "provisional: ADR-002"
Record = dict[str, Any]


@dataclass(frozen=True)
class NoiseLedger:
    """Which pairs were noised in one realisation (rate, seed): never visible to an arm."""

    rate: float
    seed: int
    injected: Mapping[str, bool]
    replaced_ids: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    uninjectable: int = 0
    text_duplicates: int = 0
    kind: str = "uniform"
    levels: Mapping[str, str] = field(default_factory=dict)

    def is_injected(self, instance_id: str) -> bool:
        return bool(self.injected.get(instance_id, False))

    def clean_count(self) -> int:
        return sum(1 for v in self.injected.values() if not v)

    def injected_count(self) -> int:
        return sum(1 for v in self.injected.values() if v)

    def digest(self) -> str:
        """SHA-256 of the realisation (rate, seed, indicator, replacements)."""
        parts: list[Any] = [
            self.rate,
            self.seed,
            sorted(self.injected.items()),
            sorted(self.replaced_ids.items()),
        ]
        if self.kind != "uniform":  # the uniform digest is the one logged in Wave 7
            parts += [self.kind, sorted(self.levels.items())]
        return hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()

    def level_shares(self) -> dict[str, float]:
        """Share of the injected pairs per sibling level (empty for the uniform kind)."""
        if self.kind != "sibling" or not self.levels:
            return {}
        n = len(self.levels)
        return {lv: sum(1 for v in self.levels.values() if v == lv) / n for lv in SIBLING_LEVELS}

    def summary(self) -> Record:
        n = len(self.injected)
        k = self.injected_count()
        extra: Record = {}
        if self.kind == "sibling":
            extra = {"kind": self.kind, "level_shares": self.level_shares()}
        return {
            **extra,
            "version": SIBLING_VERSION if self.kind == "sibling" else NOISE_VERSION,
            "rate": self.rate,
            "seed": self.seed,
            "pairs": n,
            "injected": k,
            "clean": n - k,
            "injected_share": k / n if n else float("nan"),
            "uninjectable": self.uninjectable,
            "replacement_text_equals_true_positive": self.text_duplicates,
            "digest": self.digest(),
        }


def split_function_id(fid: str) -> tuple[str, str, str | None]:
    """``(directory, file, class or None)`` of a pool function id ``dir/file.py/Class/name``."""
    segs = fid.split("/")
    cut = next((i for i, g in enumerate(segs) if g.endswith(".py")), max(len(segs) - 1, 0))
    rest = segs[cut + 1 :]
    return "/".join(segs[:cut]), "/".join(segs[: cut + 1]), ("/".join(rest[:-1]) or None)


def sibling_pools(ex: PoolExample) -> dict[str, list[int]]:
    """Candidate indices of ``ex`` per sibling level (all non-positives of the pair)."""
    pos = [split_function_id(p) for p in ex.positive_ids]
    dirs = {d for d, _, _ in pos}
    files = {f for _, f, _ in pos}
    classes = {(f, c) for _, f, c in pos if c is not None}
    pools: dict[str, list[int]] = {lv: [] for lv in SIBLING_LEVELS}
    for i, cid in enumerate(ex.candidate_ids):
        d, f, c = split_function_id(cid)
        if f in files:
            pools["file"].append(i)
        if c is not None and (f, c) in classes:
            pools["class"].append(i)
        if d in dirs:
            pools["directory"].append(i)
        pools["uniform"].append(i)
    return pools


def _draw(
    ex: PoolExample, rate: float, seed: int, kind: str = "uniform"
) -> tuple[str, list[int], str]:
    """``("clean"|"hit"|"uninjectable", candidate indices replacing the positives, level)``."""
    n = len(ex.positive_ids)
    u = float(rng_for(seed, "noise-dose", "u", ex.instance_id).random())
    if not u < rate:
        return "clean", [], ""
    if len(ex.candidate_ids) <= n:
        return "uninjectable", [], ""  # a snapshot too small to draw a replacement from
    if kind == "uniform":
        pick = rng_for(seed, "noise-dose", "pick", ex.instance_id).choice(
            len(ex.candidate_ids), size=n, replace=False
        )
        return "hit", sorted(int(i) for i in pick), ""
    pools = sibling_pools(ex)
    level = next(lv for lv in SIBLING_LEVELS if len(pools[lv]) >= n)
    pool = pools[level]
    pick = rng_for(seed, "noise-sibling", "pick", ex.instance_id).choice(
        len(pool), size=n, replace=False
    )
    return "hit", sorted(pool[int(i)] for i in pick), level


def inject(
    examples: Sequence[PoolExample], rate: float, seed: int, kind: str = "uniform"
) -> tuple[list[PoolExample], NoiseLedger]:
    """Noise the pairs at ``rate`` (0 = the identity: the same objects, an all-clean ledger)."""
    if not 0.0 <= rate <= 1.0:
        raise ValueError("rate must be in [0, 1]")
    if kind not in KINDS:
        raise ValueError(f"unknown noise kind {kind!r}")
    out: list[PoolExample] = []
    injected: dict[str, bool] = {}
    replaced: dict[str, tuple[str, ...]] = {}
    levels: dict[str, str] = {}
    uninjectable = 0
    duplicates = 0
    for ex in examples:
        if rate == 0.0:
            out.append(ex)
            injected[ex.instance_id] = False
            continue
        status, pick, level = _draw(ex, rate, seed, kind)
        if status != "hit":
            uninjectable += status == "uninjectable"
            out.append(ex)
            injected[ex.instance_id] = False
            continue
        chosen = set(pick)
        new_ids = tuple(ex.candidate_ids[i] for i in pick)
        new_texts = tuple(ex.candidate_texts[i] for i in pick)
        duplicates += sum(1 for t in new_texts if t in set(ex.positive_texts))
        out.append(
            replace(
                ex,
                positive_ids=new_ids,
                positive_texts=new_texts,
                candidate_ids=tuple(c for i, c in enumerate(ex.candidate_ids) if i not in chosen),
                candidate_texts=tuple(
                    t for i, t in enumerate(ex.candidate_texts) if i not in chosen
                ),
                masked_ids=ex.masked_ids + ex.positive_ids,
            )
        )
        injected[ex.instance_id] = True
        replaced[ex.instance_id] = new_ids
        if kind == "sibling":
            levels[ex.instance_id] = level
    ledger = NoiseLedger(rate, seed, injected, replaced, uninjectable, duplicates, kind, levels)
    return out, ledger


# --------------------------------------------------------------------------- score store


def encode_scores(scores: Iterable[float]) -> str:
    """Scores as base64 of little-endian float32 (exact for the ranks computed from them)."""
    return base64.b64encode(np.asarray(list(scores), dtype="<f4").tobytes()).decode("ascii")


def decode_scores(blob: str) -> np.ndarray:
    return np.frombuffer(base64.b64decode(blob), dtype="<f4").astype(np.float64)


def read_score_store(path: str) -> dict[str, np.ndarray]:
    """``{instance_id: scores}`` in the order ``positives + candidates`` of the original pair."""
    return {str(r["dir"]): decode_scores(r["scores"]) for r in pr.read_jsonl(path)}


def noisy_ranks(original: PoolExample, noised: PoolExample, scores: np.ndarray) -> list[Record]:
    """Rank rows of ``noised``'s positives from the scores of ``original``'s function order."""
    ids = original.ids
    if scores.shape[0] != len(ids):
        raise ValueError(
            f"{original.instance_id}: {scores.shape[0]} scores for {len(ids)} functions"
        )
    return pr.positive_ranks(ids, scores, noised.positive_ids)


def noisy_signal(
    originals: Sequence[PoolExample],
    noised: Sequence[PoolExample],
    store: Mapping[str, np.ndarray],
    teacher: str,
) -> QualitySignal:
    """K-rank signal of a teacher over a noised pool, from stored per-function scores."""
    ranks: dict[tuple[str, str], int] = {}
    for orig, new in zip(originals, noised, strict=True):
        if orig.instance_id != new.instance_id:
            raise ValueError("originals and noised pool are not aligned")
        s = store.get(orig.instance_id)
        if s is None:
            raise KeyError(f"{orig.instance_id}: no stored {teacher} scores")
        for row in noisy_ranks(orig, new, s):
            ranks[(new.instance_id, str(row["positive"]))] = int(row["rank"])
    return MappingKRank(ranks, teacher)


# --------------------------------------------------------------------------- separation


def auc_injected_vs_clean(rank_injected: Sequence[float], rank_clean: Sequence[float]) -> float:
    """P(an injected pair has a larger K-rank than a clean one) + half the ties (Mann-Whitney)."""
    a = np.asarray(rank_injected, dtype=np.float64)
    b = np.asarray(rank_clean, dtype=np.float64)
    if a.size == 0 or b.size == 0:
        return float("nan")
    allv = np.concatenate([a, b])
    order = np.argsort(allv, kind="stable")
    ranks = np.empty(allv.size)
    sorted_v = allv[order]
    i = 0
    while i < allv.size:  # average ranks over ties
        j = i
        while j + 1 < allv.size and sorted_v[j + 1] == sorted_v[i]:
            j += 1
        ranks[order[i : j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    u = ranks[: a.size].sum() - a.size * (a.size + 1) / 2.0
    return float(u / (a.size * b.size))
