"""Negative policies for retriever training, and the teacher mining they read.

Implements the negative side of ``docs/08_experimental_design.md`` "The four supervision arms". The
negative policy is **held identical across the RQ2 arms** (wave decision answering pushback (2);
Q46): it is a component of the stack, not one of the three arm hooks of
``ril.training.supervision``. Which policy the frozen configuration uses is open (Q46,
``provisional: ADR-002``); every policy here is an option, none is chosen:

* ``random_repo`` — uniform over the snapshot's non-positive functions (repository-local random
  negatives, as the CORE-Bench fine-tune draws them from a per-query pool;
  ``knowledge/papers/core-bench-2606.11864.md``).
* ``teacher_top_m`` — uniform over the teacher's top-``m`` non-positive functions (SweRank mines
  hard negatives from a base retriever's top ``M``; ``knowledge/papers/swerank-2505.07849.md``).
* ``teacher_top_m_poscut`` — as ``teacher_top_m`` after removing candidates scored too close to the
  positive: ``ratio`` keeps ``s < value * ref``, ``margin`` keeps ``s < ref - value``, where ``ref``
  is a stated aggregate of the positives' teacher scores (``min``, ``max`` or ``mean``; with several
  positives the reference positive must be stated, Q46). The positive-aware rule of
  ``knowledge/papers/nv-retriever-2407.15831.md`` (single positive, text retrieval; untested on
  code).
* ``structural`` — functions sharing a file or a class with a positive, read from the pool ids
  (``path.py/Class/name``). **A separate pilot factor only** (E-PILOT-NEG); never inside the four
  arms.

Selection is deterministic given the generator passed in; the caller derives that generator from
(seed, instance, visit), so dropping one example (FILTER) never shifts another example's draws.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import gzip
import json
import os
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np

from ril.training.pool_reader import PoolExample

PROVISIONAL = "provisional: ADR-002 (Q46)"
POLICIES = ("random_repo", "teacher_top_m", "teacher_top_m_poscut", "structural")
PILOT_ONLY = frozenset({"structural"})
"""Policies that may only appear in a pilot configuration, never in an RQ2 arm run."""
Record = dict[str, Any]
Rng = np.random.Generator


# --------------------------------------------------------------------------- mining


@dataclass(frozen=True)
class Mined:
    """Teacher scores of one instance: every positive, and the top candidates (ids, best first)."""

    teacher: str
    positive_scores: tuple[float, ...]
    top_ids: tuple[str, ...]
    top_scores: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.top_ids) != len(self.top_scores):
            raise ValueError("top ids and scores differ in length")
        if any(a < b for a, b in zip(self.top_scores, self.top_scores[1:], strict=False)):
            raise ValueError("top scores must be in descending order")


ScoreFn = Callable[[PoolExample, Sequence[str]], Sequence[float]]
"""``(example, texts) -> one teacher score per text`` (the query is the example's)."""


def mine(example: PoolExample, teacher: str, score_fn: ScoreFn, keep: int) -> Mined:
    """Teacher scores of the positives and the ``keep`` best non-positive candidates.

    Ties among candidates are broken by the lower candidate index (the snapshot order), as the
    flat index and BM25 break them.
    """
    if keep < 1:
        raise ValueError("keep must be at least 1")
    texts = list(example.positive_texts) + list(example.candidate_texts)
    s = np.asarray(score_fn(example, texts), dtype=np.float64)
    if s.shape[0] != len(texts):
        raise ValueError("one teacher score per text expected")
    npos = len(example.positive_ids)
    cand = s[npos:]
    order = np.lexsort((np.arange(len(cand)), -cand))[:keep]
    return Mined(
        teacher=teacher,
        positive_scores=tuple(float(x) for x in s[:npos]),
        top_ids=tuple(example.candidate_ids[int(i)] for i in order),
        top_scores=tuple(float(cand[int(i)]) for i in order),
    )


def write_mined(path: str, rows: Mapping[str, Mined]) -> None:
    """Mined scores to a gzip JSON-lines file (ids and scores only, no text)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.tmp"
    with gzip.open(tmp, "wt", encoding="utf-8") as handle:
        for inst in sorted(rows):
            m = rows[inst]
            handle.write(
                json.dumps(
                    {
                        "instance_id": inst,
                        "teacher": m.teacher,
                        "positive_scores": list(m.positive_scores),
                        "top_ids": list(m.top_ids),
                        "top_scores": list(m.top_scores),
                    }
                )
                + "\n"
            )
    os.replace(tmp, path)


def read_mined(path: str) -> dict[str, Mined]:
    """Inverse of :func:`write_mined`."""
    out: dict[str, Mined] = {}
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                r = json.loads(line)
                out[str(r["instance_id"])] = Mined(
                    teacher=str(r["teacher"]),
                    positive_scores=tuple(float(x) for x in r["positive_scores"]),
                    top_ids=tuple(r["top_ids"]),
                    top_scores=tuple(float(x) for x in r["top_scores"]),
                )
    return out


# --------------------------------------------------------------------------- pool id structure


def file_of(fid: str) -> str:
    """File part of a pool function id (``a/b.py/C/f`` -> ``a/b.py``); the id itself if none."""
    parts = fid.split("/")
    for i, p in enumerate(parts):
        if p.endswith(".py"):
            return "/".join(parts[: i + 1])
    return fid


def class_of(fid: str) -> str | None:
    """``file/Class`` of a method id (``a/b.py/C/f`` -> ``a/b.py/C``); ``None`` for a function."""
    f = file_of(fid)
    rest = fid[len(f) + 1 :].split("/") if fid != f else []
    return f"{f}/{rest[0]}" if len(rest) >= 2 else None


# --------------------------------------------------------------------------- policies


class NegativePolicy(Protocol):
    """Picks hard-negative candidates for one example (indices into ``candidate_ids``)."""

    name: str

    def eligible(self, example: PoolExample, mined: Mined | None) -> list[int]: ...

    def select(self, example: PoolExample, mined: Mined | None, n: int, rng: Rng) -> list[int]: ...


class _Uniform:
    """Shared selection: ``n`` uniformly without replacement from the eligible list (all if
    fewer)."""

    name = "base"

    def eligible(self, example: PoolExample, mined: Mined | None) -> list[int]:
        raise NotImplementedError

    def select(self, example: PoolExample, mined: Mined | None, n: int, rng: Rng) -> list[int]:
        pool = self.eligible(example, mined)
        if n <= 0 or not pool:
            return []
        if len(pool) <= n:
            return list(pool)
        pick = rng.choice(len(pool), size=n, replace=False)
        return [pool[int(i)] for i in sorted(pick)]


class RandomRepoLocal(_Uniform):
    """Uniform over every non-positive function of the snapshot."""

    name = "random_repo"

    def eligible(self, example: PoolExample, mined: Mined | None) -> list[int]:
        return list(range(len(example.candidate_ids)))


def _index_of(example: PoolExample) -> dict[str, int]:
    return {cid: i for i, cid in enumerate(example.candidate_ids)}


def _need(mined: Mined | None, example: PoolExample) -> Mined:
    if mined is None:
        raise ValueError(f"{example.instance_id}: this policy needs mined teacher scores")
    return mined


class TeacherTopM(_Uniform):
    """Uniform over the teacher's top-``m`` non-positive candidates."""

    name = "teacher_top_m"

    def __init__(self, m: int) -> None:
        if m < 1:
            raise ValueError("m must be at least 1")
        self.m = m

    def eligible(self, example: PoolExample, mined: Mined | None) -> list[int]:
        mm = _need(mined, example)
        idx = _index_of(example)
        return [idx[c] for c in mm.top_ids[: self.m]]


class TeacherTopMPositiveCut(_Uniform):
    """Top-``m`` after removing candidates whose teacher score is too close to the positive's."""

    name = "teacher_top_m_poscut"

    def __init__(self, m: int, mode: str, value: float, reference: str) -> None:
        if m < 1:
            raise ValueError("m must be at least 1")
        if mode not in ("ratio", "margin"):
            raise ValueError("mode must be 'ratio' or 'margin'")
        if reference not in ("min", "max", "mean"):
            raise ValueError("reference must be 'min', 'max' or 'mean'")
        self.m, self.mode, self.value, self.reference = m, mode, float(value), reference

    def threshold(self, mined: Mined) -> float:
        """Candidates scoring at or above this value are dropped."""
        ps = np.asarray(mined.positive_scores, dtype=np.float64)
        if self.reference == "min":
            ref = float(ps.min())
        elif self.reference == "max":
            ref = float(ps.max())
        else:
            ref = float(ps.mean())
        return ref * self.value if self.mode == "ratio" else ref - self.value

    def eligible(self, example: PoolExample, mined: Mined | None) -> list[int]:
        mm = _need(mined, example)
        cut = self.threshold(mm)
        idx = _index_of(example)
        kept = [idx[c] for c, s in zip(mm.top_ids, mm.top_scores, strict=True) if s < cut]
        return kept[: self.m]


class Structural(_Uniform):
    """Functions sharing a file (``same_file``) or a class (``same_class``) with a positive."""

    name = "structural"

    def __init__(self, relation: str) -> None:
        if relation not in ("same_file", "same_class"):
            raise ValueError("relation must be 'same_file' or 'same_class'")
        self.relation = relation

    def eligible(self, example: PoolExample, mined: Mined | None) -> list[int]:
        key: Callable[[str], str | None] = file_of if self.relation == "same_file" else class_of
        targets = {key(p) for p in example.positive_ids} - {None}
        return [i for i, c in enumerate(example.candidate_ids) if key(c) in targets]


def make_policy(cfg: Mapping[str, Any], *, pilot: bool = False) -> NegativePolicy:
    """Policy from a configuration mapping (``name`` plus its parameters).

    ``structural`` is refused unless ``pilot`` is true (it is a separate pilot factor only).
    """
    name = str(cfg["name"])
    if name in PILOT_ONLY and not pilot:
        raise ValueError(f"negative policy {name!r} is a pilot factor only (E-PILOT-NEG)")
    if name == "random_repo":
        return RandomRepoLocal()
    if name == "teacher_top_m":
        return TeacherTopM(int(cfg["m"]))
    if name == "teacher_top_m_poscut":
        return TeacherTopMPositiveCut(
            int(cfg["m"]), str(cfg["mode"]), float(cfg["value"]), str(cfg["reference"])
        )
    if name == "structural":
        return Structural(str(cfg["relation"]))
    raise ValueError(f"unknown negative policy {name!r}; options: {POLICIES}")


def needs_mining(policy: NegativePolicy) -> bool:
    """Whether the policy reads teacher scores."""
    return isinstance(policy, TeacherTopM | TeacherTopMPositiveCut)


def bm25_score_fn(example: PoolExample, texts: Sequence[str]) -> Sequence[float]:
    """BM25 teacher (reference form of ``ril.retrieval.bm25_index``; CPU, used in tests)."""
    from ril.training.pool_ranks import bm25_scores

    return [float(x) for x in bm25_scores(texts, example.query)]


def mine_all(
    examples: Iterable[PoolExample], teacher: str, score_fn: ScoreFn, keep: int
) -> dict[str, Mined]:
    """Mine every example (CPU teachers; the dense teachers run in the cluster job)."""
    return {ex.instance_id: mine(ex, teacher, score_fn, keep) for ex in examples}


def dense_score_fn(encoder: Any, batch_size: int) -> ScoreFn:
    """Dense teacher (a ``DenseEncoder``): inner products, snapshot vectors cached per repository.

    Pool snapshots of one repository repeat most function texts, so the X3 per-repository vector
    cache is reused (examples should be visited grouped by repository).
    """
    from ril.training.pool_ranks import RepoVectorCache

    cache = RepoVectorCache()

    def score(example: PoolExample, texts: Sequence[str]) -> Sequence[float]:
        q = encoder.encode_query(example.query)
        s, _ = cache.scores(example.repo, texts, q, encoder, batch_size)
        return [float(x) for x in s]

    return score
