"""Unit tests: hop-decay expansion, the two scored lists, the chance controls, the recency prior."""

from __future__ import annotations

import numpy as np
import pytest

from ril.retrieval.graph_expansion import (
    FamilyGraph,
    bfs_distances,
    combine_uniform,
    expand_weighted,
    list_variant_ranks,
    random_same_files,
    random_whole,
    rrf_graph_list,
    rrf_ranks,
    select_expansion,
)
from ril.retrieval.recency import ages_in_days, blend, parse_utc, recency_prior


def chain() -> FamilyGraph:
    # units 0..5; 6 is a traversal-only node (a directory)
    return FamilyGraph.from_pairs(
        6,
        {
            "invoke": [(0, 1), (1, 2), (2, 3)],
            "contain": [(0, 6), (6, 4), (6, 5)],
        },
    )


def test_bfs_distances_respects_hops_and_families() -> None:
    g = chain()
    assert bfs_distances(g, ["invoke"], 0, 1) == {1: 1}
    assert bfs_distances(g, ["invoke"], 0, 3) == {1: 1, 2: 2, 3: 3}
    assert bfs_distances(g, ["contain"], 0, 2) == {6: 1, 4: 2, 5: 2}
    assert bfs_distances(g, ["invoke", "contain"], 0, 2) == {1: 1, 6: 1, 2: 2, 4: 2, 5: 2}
    assert bfs_distances(g, ["tests"], 0, 2) == {}  # unknown family: nothing reached


def test_combine_uniform_takes_max_over_seeds() -> None:
    d0 = {1: 1, 2: 2}
    d3 = {2: 1}
    out = combine_uniform([d0, d3], [1.0, 0.8], 0.5, 2)
    assert out[1] == pytest.approx(0.5)
    assert out[2] == pytest.approx(0.4)  # 0.8 * 0.5 beats 1.0 * 0.25
    assert combine_uniform([d0], [1.0], 0.5, 1) == {1: 0.5}  # hop limit
    with pytest.raises(ValueError):
        combine_uniform([d0], [1.0, 2.0], 0.5, 1)


def test_weighted_expansion_equals_uniform_for_equal_weights() -> None:
    g = chain()
    fams = ["invoke", "contain"]
    dist = bfs_distances(g, fams, 0, 2)
    uni = combine_uniform([dist], [0.9], 0.6, 2)
    wtd = expand_weighted(g, {"invoke": 0.6, "contain": 0.6}, [0], [0.9], 2)
    assert set(uni) == set(wtd)
    for k in uni:
        assert wtd[k] == pytest.approx(uni[k])


def test_weighted_expansion_uses_family_weights_and_zero_removes_a_family() -> None:
    g = chain()
    out = expand_weighted(g, {"invoke": 0.9, "contain": 0.1}, [0], [1.0], 2)
    assert out[1] == pytest.approx(0.9)
    assert out[6] == pytest.approx(0.1)
    assert out[4] == pytest.approx(0.01)
    none = expand_weighted(g, {"invoke": 0.0, "contain": 0.0}, [0], [1.0], 2)
    assert none == {}


def test_select_expansion_drops_seeds_nodes_and_orders_by_score_then_position() -> None:
    position = np.array([3, 0, 2, 1, 4, 5], dtype=np.int64)
    scores = {0: 0.9, 1: 0.5, 2: 0.5, 3: 0.4, 6: 0.99}
    out = select_expansion(scores, seed_units=[0], position=position, n_units=6, cap=10)
    # 6 is not a unit, 0 is a seed; 1 and 2 tie on score: position 0 (unit 1) before 2 (unit 2)
    assert out == [1, 2, 3]
    assert select_expansion(scores, [0], position, 6, cap=2) == [1, 2]


def test_list_variant_ranks_seeds_then_expansion_then_rest() -> None:
    # retrieval positions 0..9; seeds 0,1; expansion 7,4
    ranks = list_variant_ranks([0, 1, 7, 4, 2, 3, 5, 9], [0, 1], [7, 4])
    assert ranks[:4] == [1, 2, 3, 4]
    # rest in retrieval order without 0,1,7,4: positions 2,3,5,6,8,9 take ranks 5..10
    assert ranks[4:] == [5, 6, 7, 10]
    with pytest.raises(ValueError):
        list_variant_ranks([0], [0, 1], [1])


def test_list_variant_without_expansion_is_the_baseline() -> None:
    gold = [0, 3, 8]
    assert list_variant_ranks(gold, [0, 1], []) == [1, 4, 9]
    assert list_variant_ranks(gold, [], []) == [1, 4, 9]


def test_rrf_ranks_promote_graph_units_and_keep_ties_in_retrieval_order() -> None:
    n = 200
    assert rrf_ranks(n, [0, 5, 100], []) == [1, 6, 101]
    # unit at retrieval position 150 is graph rank 1: it outranks retrieval positions 1..
    r = rrf_ranks(n, [150, 0], [150])
    assert r[0] < 150
    assert r[1] >= 1
    with pytest.raises(ValueError):
        rrf_ranks(n, [0], [3, 3])


def test_rrf_graph_list_orders_seeds_and_expansion_by_score() -> None:
    glist = rrf_graph_list([0, 1], [1.0, 0.4], [9, 7], [0.5, 0.5])
    assert glist == [0, 7, 9, 1]  # 0.5 ties go to the earlier retrieval position


def test_random_controls_size_exclusion_and_determinism() -> None:
    n = 50
    rng = np.random.default_rng(0)
    a = random_whole(rng, n, 10, [0, 1, 2])
    assert len(a) == 10 and len(set(a)) == 10 and not set(a) & {0, 1, 2}
    b = random_whole(np.random.default_rng(0), n, 10, [0, 1, 2])
    assert a == b
    assert len(random_whole(rng, 5, 10, [0])) == 4  # cannot exceed what exists
    files = np.array([0] * 5 + [1] * 5 + [2] * 40, dtype=np.int64)
    same = random_same_files(np.random.default_rng(1), files, [0], 3)
    assert len(same) == 3 and all(files[p] == 0 and p != 0 for p in same)
    topped = random_same_files(np.random.default_rng(1), files, [0], 9)
    assert len(topped) == 9 and len(set(topped)) == 9 and 0 not in topped
    assert sum(files[p] == 0 for p in topped) == 4  # all of the seed's file, rest from elsewhere


def test_ages_prior_and_blend() -> None:
    snap = parse_utc("2024-03-10T00:00:00Z")
    ages = ages_in_days(["2024-03-09T00:00:00Z", "", "2023-03-10T00:00:00Z"], snap)
    assert ages[0] == pytest.approx(1.0)
    assert np.isinf(ages[1])
    assert ages[2] == pytest.approx(366.0)
    prior = recency_prior(ages, 30.0)
    assert prior[1] == 0.0 and prior[0] > prior[2] > 0
    scores = np.array([2.0, 4.0, 0.0])
    out = blend(scores, prior, 0.5)
    assert out[1] == pytest.approx(1.0 + 0.0)
    assert out[0] == pytest.approx(0.5 + 0.5 * prior[0])
    zero = blend(np.zeros(3), prior, 0.5)
    assert zero[0] == pytest.approx(0.5 * prior[0])
    with pytest.raises(ValueError):
        recency_prior(ages, 0.0)


def test_future_last_modified_is_a_leak() -> None:
    snap = parse_utc("2024-03-10T00:00:00Z")
    with pytest.raises(ValueError, match="leak"):
        ages_in_days(["2024-03-11T00:00:00Z"], snap)
