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

from ril.evaluation.stats import (
    bootstrap_means as bootstrap_means,
)
from ril.evaluation.stats import (
    mean_ci as mean_ci,
)
from ril.evaluation.stats import (
    paired_diff_ci as paired_diff_ci,
)

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
