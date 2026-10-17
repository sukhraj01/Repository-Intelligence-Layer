"""Binary-gain ranking metrics from relevant-document ranks, and the bootstrap helpers."""

from __future__ import annotations

import math

import numpy as np
import pytest

from ril.evaluation.metrics import (
    drop_from_ranking,
    first_rank,
    mean_ci,
    ndcg_at_k,
    paired_diff_ci,
    recall_at_k,
)


def test_ndcg_known_values() -> None:
    assert ndcg_at_k([1], 10) == pytest.approx(1.0)
    assert ndcg_at_k([2], 10) == pytest.approx(1 / math.log2(3))
    # two relevant, found at 1 and 3: dcg = 1 + 0.5, idcg = 1 + 1/log2(3)
    assert ndcg_at_k([1, 3], 10) == pytest.approx(1.5 / (1 + 1 / math.log2(3)))
    assert ndcg_at_k([11], 10) == 0.0 and ndcg_at_k([None], 10) == 0.0


def test_ideal_list_is_capped_at_k_and_missing_positives_count_in_the_denominator() -> None:
    ranks = list(range(1, 11))  # 10 relevant all in the top 10, 20 relevant in total
    assert ndcg_at_k(ranks, 10, n_relevant=20) == pytest.approx(1.0)
    assert recall_at_k(ranks, 100, n_relevant=20) == 0.5
    assert recall_at_k([], 100, n_relevant=0) == 0.0


def test_first_rank_and_drop_from_ranking() -> None:
    assert first_rank([None, 7, 3]) == 3 and first_rank([None]) is None
    # a removed document above a kept one moves the kept one up; one below does not
    assert drop_from_ranking([5, 12, None], [2, 9, 40, None]) == [4, 10, None]
    assert drop_from_ranking([1], []) == [1]


def test_bootstrap_is_seeded_and_brackets_the_mean() -> None:
    v = np.linspace(0, 1, 50)
    a = mean_ci(v, draws=500, seed=3)
    assert a == mean_ci(v, draws=500, seed=3)
    assert a[1] <= a[0] <= a[2]
    assert all(math.isnan(x) for x in mean_ci([], draws=10))


def test_paired_difference_uses_the_same_queries_and_rejects_unequal_lengths() -> None:
    x = [0.2, 0.4, 0.6, 0.8]
    d = paired_diff_ci(x, [0.1, 0.3, 0.5, 0.7], draws=200, seed=0)
    assert d[0] == pytest.approx(0.1) and d[1] == pytest.approx(0.1) and d[2] == pytest.approx(0.1)
    with pytest.raises(ValueError):
        paired_diff_ci([1.0], [1.0, 2.0])
