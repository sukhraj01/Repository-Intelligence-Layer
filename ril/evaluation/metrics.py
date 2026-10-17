"""Ranking metrics with binary gain, computed from the ranks of the relevant documents.

Implements the metric definitions of the benchmark's collector (``docs/06_core_bench.md``):
binary gain, ``nDCG@k = DCG@k / IDCG@k`` with the ideal list holding ``min(#relevant, k)``
hits, ``Recall@k = hits in the top k / #relevant``. Working from the ranks of the relevant
documents (1-based, ``None`` for a relevant document that was not retrieved) is exact for binary
gain, keeps run records tiny, and lets one record be re-scored under any label set (E2).

The interval helpers are percentile bootstraps over queries with a seeded generator; a
paired interval resamples the same queries for both conditions.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
import numpy.typing as npt

Rank = int | None


def ndcg_at_k(ranks: Sequence[Rank], k: int, n_relevant: int | None = None) -> float:
    """nDCG@k with binary gain. ``n_relevant`` defaults to ``len(ranks)``."""
    n = len(ranks) if n_relevant is None else n_relevant
    if n <= 0:
        return 0.0
    dcg = sum(1.0 / math.log2(r + 1) for r in ranks if r is not None and r <= k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(min(n, k)))
    return dcg / idcg


def recall_at_k(ranks: Sequence[Rank], k: int, n_relevant: int | None = None) -> float:
    """Share of the relevant documents ranked in the top ``k``."""
    n = len(ranks) if n_relevant is None else n_relevant
    if n <= 0:
        return 0.0
    return sum(1 for r in ranks if r is not None and r <= k) / n


def first_rank(ranks: Sequence[Rank]) -> Rank:
    """Rank of the best-placed relevant document (``None`` when none was retrieved)."""
    found = [r for r in ranks if r is not None]
    return min(found) if found else None


def drop_from_ranking(kept: Sequence[Rank], removed: Sequence[Rank]) -> list[Rank]:
    """Ranks of ``kept`` documents after the ``removed`` documents leave the ranked list.

    A removed document that stood above a kept one moves the kept one up by one place. A
    removed document that was never retrieved changes nothing.
    """
    gone = sorted(r for r in removed if r is not None)
    out: list[Rank] = []
    for r in kept:
        if r is None:
            out.append(None)
        else:
            out.append(r - sum(1 for g in gone if g < r))
    return out


def bootstrap_means(
    values: npt.ArrayLike, *, draws: int = 2000, seed: int = 0
) -> npt.NDArray[np.float64]:
    """Means of ``draws`` resamples (with replacement) of ``values``."""
    v = np.asarray(values, dtype=np.float64)
    if v.size == 0:
        return np.full(draws, np.nan)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, v.size, size=(draws, v.size))
    return np.asarray(v[idx].mean(axis=1), dtype=np.float64)


def mean_ci(
    values: npt.ArrayLike, *, draws: int = 2000, seed: int = 0, level: float = 0.95
) -> tuple[float, float, float]:
    """``(mean, low, high)``: the sample mean and its percentile-bootstrap interval."""
    v = np.asarray(values, dtype=np.float64)
    if v.size == 0:
        return (math.nan, math.nan, math.nan)
    means = bootstrap_means(v, draws=draws, seed=seed)
    a = (1.0 - level) / 2.0
    lo, hi = np.quantile(means, [a, 1.0 - a])
    return (float(v.mean()), float(lo), float(hi))


def paired_diff_ci(
    a: npt.ArrayLike, b: npt.ArrayLike, *, draws: int = 2000, seed: int = 0, level: float = 0.95
) -> tuple[float, float, float]:
    """``(mean(a - b), low, high)`` with the same queries resampled for both conditions."""
    x = np.asarray(a, dtype=np.float64)
    y = np.asarray(b, dtype=np.float64)
    if x.shape != y.shape:
        raise ValueError(f"paired samples differ in length: {x.shape} vs {y.shape}")
    return mean_ci(x - y, draws=draws, seed=seed, level=level)
