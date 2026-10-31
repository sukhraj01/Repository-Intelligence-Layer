"""Does a teacher's K-rank separate injected from clean pairs? (E-PILOT-NOISE gate N0.)

Reads the example caches, a teacher's stored per-function scores and the E-POOL-RANKS feature
table. Per teacher, seed and rate it reports the AUC of the pair's K-rank (the minimum over its
positives) for injected against clean pairs, and the share of injected and of clean pairs a FILTER
at K would drop (every positive of the pair ranked beyond K, the rule of ``KRankThreshold`` at
``level: positive``), plus the same shares per positive. Gate (brief, session N0): an AUC below 0.6
means the filter has nothing to find. A reproduction check compares the ranks recomputed from the
stored scores for the true positives with the feature table's (same definition, same teacher).

Kept compatible with Python 3.10.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from ril.training import noise
from ril.training.pool_reader import FeatureTable, PoolExample

Record = dict[str, Any]
N0_TABLES_VERSION = "n0-tables/v1"
GATE_AUC = 0.6


def reproduction(
    examples: Sequence[PoolExample],
    store: Mapping[str, np.ndarray],
    table: FeatureTable,
    teacher: str,
) -> Record:
    """Ranks of the true positives recomputed from stored scores against the feature table's."""
    same = total = missing = 0
    worst = 0
    for ex in examples:
        s = store.get(ex.instance_id)
        if s is None:
            missing += 1
            continue
        for row in noise.noisy_ranks(ex, ex, s):
            ref = table.rank(ex.instance_id, str(row["positive"]), teacher)
            if ref is None:
                continue
            total += 1
            same += int(ref == row["rank"])
            worst = max(worst, abs(int(ref) - int(row["rank"])))
    return {
        "teacher": teacher,
        "positives_compared": total,
        "identical": same,
        "identical_share": same / total if total else float("nan"),
        "max_abs_difference": worst,
        "directories_without_scores": missing,
    }


def separation(
    examples: Sequence[PoolExample],
    store: Mapping[str, np.ndarray],
    teacher: str,
    rate: float,
    seed: int,
    k: int = 20,
) -> Record:
    """AUC and drop shares of one teacher on one noise realisation."""
    noised, ledger = noise.inject(examples, rate, seed)
    sig = noise.noisy_signal(examples, noised, store, teacher)
    inj_pair: list[int] = []
    cln_pair: list[int] = []
    inj_pos: list[int] = []
    cln_pos: list[int] = []
    for ex in noised:
        ranks = [sig.positive_rank(ex, p) for p in ex.positive_ids]
        if ledger.is_injected(ex.instance_id):
            inj_pair.append(min(ranks))
            inj_pos += ranks
        else:
            cln_pair.append(min(ranks))
            cln_pos += ranks

    def beyond(xs: Sequence[int]) -> float:
        return float(np.mean([x > k for x in xs])) if xs else float("nan")

    return {
        "teacher": teacher,
        "rate": rate,
        "seed": seed,
        "k": k,
        "pairs": len(noised),
        "injected": len(inj_pair),
        "auc_pair": noise.auc_injected_vs_clean(inj_pair, cln_pair),
        "auc_positive": noise.auc_injected_vs_clean(inj_pos, cln_pos),
        "injected_pairs_dropped": beyond(inj_pair),
        "clean_pairs_dropped": beyond(cln_pair),
        "injected_positives_beyond_k": beyond(inj_pos),
        "clean_positives_beyond_k": beyond(cln_pos),
        "median_pair_rank_injected": float(np.median(inj_pair)) if inj_pair else float("nan"),
        "median_pair_rank_clean": float(np.median(cln_pair)) if cln_pair else float("nan"),
        "ledger_digest": ledger.digest(),
        "gate_auc_below": GATE_AUC,
        "gate_fails": bool(noise.auc_injected_vs_clean(inj_pair, cln_pair) < GATE_AUC),
    }
