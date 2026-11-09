"""Tests for the batch planner: distinct examples, masks, determinism, exposure counts."""

from __future__ import annotations

from dataclasses import replace

import pytest

from ril.training.data_loader import BatchPlanner, BatchSpec
from ril.training.negatives import RandomRepoLocal
from ril.training.supervision import RandomOrder
from tests.unit._training_fixtures import synthetic_examples


def _planner(exs, spec=None, seed=1):  # type: ignore[no-untyped-def]
    spec = spec or BatchSpec(4, 3, 2)
    return BatchPlanner(exs, [1.0] * len(exs), RandomOrder(), RandomRepoLocal(), spec, seed)


def test_batches_are_distinct_deterministic_and_counted() -> None:
    exs = synthetic_examples(repos=2, prs=3)  # 6 examples, batch 4: passes overlap batches
    a = [b.fingerprint() for b in _planner(exs).batches(9)]
    b = [b.fingerprint() for b in _planner(exs).batches(9)]
    assert a == b and len(set(a)) == 9
    p = _planner(exs)
    batches = list(p.batches(9))
    for bt in batches:
        assert len(set(bt.instance_ids)) == 4
        assert bt.pos_mask.any(axis=1).all() and not (bt.pos_mask & ~bt.valid_mask).any()
        assert int(bt.pos_mask.sum(axis=1).max()) <= 2
    c = p.counts.to_dict()
    assert c["examples_seen"] == 36 and c["unique_examples_seen"] == 6
    assert c["effective_epochs"] == pytest.approx(6.0)
    assert c["positives_seen"] == int(sum(bt.pos_mask.sum() for bt in batches))
    assert [bt.fingerprint() for bt in _planner(exs, seed=2).batches(9)] != a


def test_same_function_across_examples_is_masked() -> None:
    exs = synthetic_examples(repos=1, prs=4)
    # make example 1 carry example 0's first positive as a candidate (same repository and id)
    e0, e1 = exs[0], exs[1]
    shared = e0.positive_ids[0]
    if shared not in e1.candidate_ids:
        pytest.skip("fixture layout changed")
    bt = next(_planner(exs[:4], spec=BatchSpec(4, 30, 3)).batches(1))
    i0 = bt.instance_ids.index(e0.instance_id)
    for j, (_, fid) in enumerate(bt.doc_ids):
        if fid == shared and bt.owner[j] != i0:
            assert not bt.valid_mask[i0, j]
    assert e1.instance_id in bt.instance_ids


def test_masked_ids_never_enter_the_softmax() -> None:
    exs = synthetic_examples(repos=1, prs=4)
    e0 = exs[0]
    other = next(c for c in exs[1].positive_ids if c in e0.candidate_ids)
    i = e0.candidate_ids.index(other)
    exs[0] = replace(
        e0,
        candidate_ids=e0.candidate_ids[:i] + e0.candidate_ids[i + 1 :],
        candidate_texts=e0.candidate_texts[:i] + e0.candidate_texts[i + 1 :],
        masked_ids=(other,),
    )
    bt = next(_planner(exs, spec=BatchSpec(4, 2, 3)).batches(1))
    i0 = bt.instance_ids.index(e0.instance_id)
    for j, (_, fid) in enumerate(bt.doc_ids):
        if fid == other:
            assert not bt.valid_mask[i0, j]


def test_planner_refuses_bad_inputs() -> None:
    exs = synthetic_examples(repos=1, prs=3)
    with pytest.raises(ValueError):
        _planner(exs)  # 3 examples < batch 4
    with pytest.raises(ValueError):
        BatchPlanner(exs, [1.0], RandomOrder(), RandomRepoLocal(), BatchSpec(2, 1, 1), 0)
    with pytest.raises(ValueError):
        BatchPlanner(exs, [1.0, -1.0, 1.0], RandomOrder(), RandomRepoLocal(), BatchSpec(2, 1, 1), 0)


def test_small_pool_is_cycled_in_a_fresh_seeded_order_per_pass() -> None:
    """D131: an arm with a pool smaller than its visits cycles it, one fresh shuffle per pass.

    Every example is seen before any is repeated, passes differ, the order is a function of the seed
    alone, and the stored diagnostic reports how many distinct examples the arm saw.
    """
    exs = synthetic_examples(repos=2, prs=4)  # 8 examples
    spec = BatchSpec(2, 1, 1)
    p = _planner(exs, spec, seed=100)
    stream = [i for bt in p.batches(12) for i in bt.instance_ids]  # 24 visits = 3 passes
    first, second, third = (stream[k * 8 : (k + 1) * 8] for k in range(3))
    assert sorted(first) == sorted(second) == sorted(third) == sorted(e.instance_id for e in exs)
    assert len({tuple(first), tuple(second), tuple(third)}) == 3
    again = [i for bt in _planner(exs, spec, seed=100).batches(12) for i in bt.instance_ids]
    other = [i for bt in _planner(exs, spec, seed=101).batches(12) for i in bt.instance_ids]
    assert again == stream and other != stream
    c = p.counts.to_dict()
    assert c["unique_examples_seen"] == 8 and c["examples_seen"] == 24
    assert c["effective_epochs"] == pytest.approx(3.0)
    short = _planner(exs, spec, seed=100)
    list(short.batches(2))  # 4 visits of a pool of 8: no repeat, diagnostic equals the visits
    assert short.counts.to_dict()["unique_examples_seen"] == 4
