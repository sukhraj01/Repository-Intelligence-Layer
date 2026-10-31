"""Tests for the three arm hooks and the K-rank quality signal."""

from __future__ import annotations

import math

import pytest

from ril.training.supervision import (
    Curriculum,
    KeepAll,
    KRankThreshold,
    KRankWeight,
    MappingKRank,
    RandomOrder,
    UnitWeight,
    arm_from_config,
)
from tests.unit._training_fixtures import synthetic_examples


def _signal(rank_of: dict[str, int] | None = None) -> MappingKRank:
    exs = synthetic_examples(repos=2, prs=3)
    ranks = {}
    for i, e in enumerate(exs):
        for j, p in enumerate(e.positive_ids):
            ranks[(e.instance_id, p)] = (rank_of or {}).get(p, 1 + 10 * i + j)
    return MappingKRank(ranks, "t")


def test_filter_levels_and_identity_limit() -> None:
    exs = synthetic_examples(repos=2, prs=3)
    sig = _signal()
    out, rep = KeepAll().apply(exs)
    assert out == exs and rep.examples_out == rep.examples_in
    inf, _ = KRankThreshold(sig, None, "positive").apply(exs)
    assert inf == exs  # K = infinity is the identity
    pos, rp = KRankThreshold(sig, 12, "positive").apply(exs)
    ex_level, re_ = KRankThreshold(sig, 12, "example").apply(exs)
    assert rp.positives_out < rp.positives_in and re_.examples_out >= rp.examples_out
    for e in pos:
        assert all(sig.positive_rank(e, p) <= 12 for p in e.positive_ids)
        orig = next(x for x in exs if x.instance_id == e.instance_id)
        assert set(e.masked_ids) == set(orig.positive_ids) - set(e.positive_ids)
    with pytest.raises(ValueError):
        KRankThreshold(sig, 0, "positive")


def test_weights_forms_and_identity_limit() -> None:
    exs = synthetic_examples(repos=2, prs=3)
    sig = _signal()
    assert all(UnitWeight().weight(e) == 1.0 for e in exs)
    big = KRankWeight(sig, "power", 1e9, 1.0)
    assert all(big.weight(e) == 1.0 for e in exs)
    w = KRankWeight(sig, "power", 5, 1.0, floor=0.1)
    vals = [w.weight(e) for e in exs]
    assert max(vals) == 1.0 and min(vals) >= 0.1
    s = KRankWeight(sig, "sigmoid", 5, 2.0)
    assert 0 < s.weight(exs[-1]) < s.weight(exs[0]) <= 1.0
    assert math.isfinite(KRankWeight(sig, "sigmoid", 1, 1e-6).weight(exs[-1]))


def test_curriculum_easy_to_hard_and_constant_is_random_order() -> None:
    exs = synthetic_examples(repos=2, prs=3)
    sig = _signal()
    order = Curriculum(lambda e: float(sig.example_rank(e))).order(exs, 7, 0)
    ranks = [sig.example_rank(exs[i]) for i in order]
    assert ranks == sorted(ranks) and sorted(order) == list(range(len(exs)))
    flat = Curriculum(lambda e: 1.0).order(exs, 7, 3)
    assert flat == RandomOrder().order(exs, 7, 3)
    assert RandomOrder().order(exs, 7, 0) != RandomOrder().order(exs, 7, 1)
    b = Curriculum(lambda e: float(sig.example_rank(e)), buckets=2).order(exs, 7, 0)
    half = len(exs) // 2
    assert {sig.example_rank(exs[i]) for i in b[:half]} == set(sorted(ranks)[:half])


def test_arm_from_config() -> None:
    sig = _signal()
    raw = arm_from_config({"name": "RAW"}, {})
    assert raw.describe() == {
        "name": "RAW",
        "filter": "keep_all",
        "weigher": "unit",
        "ordering": "random",
    }
    f = arm_from_config(
        {"name": "FILTER", "filter": {"teacher": "t", "k": 20, "level": "positive"}}, {"t": sig}
    )
    assert f.filter.name == "krank_threshold"
    c = arm_from_config({"name": "CURRICULUM", "ordering": {"teacher": "t"}}, {"t": sig})
    assert c.ordering.name == "curriculum"
    with pytest.raises(KeyError):
        arm_from_config(
            {"name": "WEIGHT", "weight": {"teacher": "z", "form": "power", "k": 1, "param": 1}},
            {"t": sig},
        )
    with pytest.raises(ValueError):
        arm_from_config({"name": "OTHER"}, {})


def test_agreement_signal_is_the_worst_rank_of_its_teachers() -> None:
    from ril.training.supervision import AgreementKRank

    exs = synthetic_examples(repos=2, prs=3)
    a = _signal()
    ranks_b = {k: (v * 3) % 17 + 1 for k, v in a.ranks.items()}
    b = MappingKRank(ranks_b, "u")
    ag = AgreementKRank((a, b))
    assert ag.teacher == "t+u"
    for e in exs:
        for p in e.positive_ids:
            assert ag.positive_rank(e, p) == max(a.positive_rank(e, p), b.positive_rank(e, p))
        assert ag.example_rank(e) == min(ag.positive_rank(e, p) for p in e.positive_ids)
    arm = arm_from_config(
        {"name": "FILTER", "filter": {"teacher": "t+u", "k": 10, "level": "positive"}},
        {"t": a, "u": b},
    )
    kept, _ = arm.filter.apply(exs)
    for e in kept:
        assert all(ag.positive_rank(e, p) <= 10 for p in e.positive_ids)
    with pytest.raises(KeyError):
        arm_from_config(
            {"name": "FILTER", "filter": {"teacher": "t+v", "k": 10, "level": "positive"}},
            {"t": a, "u": b},
        )


def test_noise_control_replaces_positives_inside_the_repository() -> None:
    exs = synthetic_examples(repos=2, prs=3)
    arm = arm_from_config({"name": "NOISE"}, {}, seed=3)
    out, rep = arm.filter.apply(exs)
    again, _ = arm_from_config({"name": "NOISE"}, {}, seed=3).filter.apply(exs)
    other, _ = arm_from_config({"name": "NOISE"}, {}, seed=4).filter.apply(exs)
    assert out == again and out != other  # keyed by the seed and the instance, not by order
    assert out == arm.filter.apply(list(reversed(exs)))[0][::-1]
    assert rep.examples_out == rep.examples_in
    for a, b in zip(exs, out, strict=True):
        assert len(b.positive_ids) == len(a.positive_ids) and b.query == a.query
        assert not set(b.positive_ids) & set(a.positive_ids)  # none of the true positives
        assert set(a.positive_ids) <= set(b.masked_ids)  # and they never serve as negatives
        assert set(b.positive_ids) <= set(a.candidate_ids)  # same snapshot
        assert not set(b.positive_ids) & set(b.candidate_ids)
        assert len(b.candidate_ids) == len(a.candidate_ids) - len(b.positive_ids)
    with pytest.raises(ValueError):
        bad = {"teacher": "t", "k": 1, "level": "positive"}
        arm_from_config({"name": "NOISE", "filter": bad}, {}, 0)


def test_reversed_curriculum_is_hard_to_easy() -> None:
    exs = synthetic_examples(repos=2, prs=3)
    sig = _signal()
    fwd = Curriculum(lambda e: float(sig.example_rank(e))).order(exs, 7, 0)
    rev = Curriculum(lambda e: float(sig.example_rank(e)), reverse=True).order(exs, 7, 0)
    key = [sig.example_rank(exs[i]) for i in rev]
    assert key == sorted(key, reverse=True) and sorted(rev) == sorted(fwd)
    arm = arm_from_config(
        {"name": "CURRICULUM", "ordering": {"teacher": "t", "buckets": 4, "reverse": True}},
        {"t": sig},
    )
    assert arm.ordering.name == "curriculum_reversed"


def test_random_subset_is_deterministic_sized_and_order_independent() -> None:
    exs = synthetic_examples(repos=3, prs=4)
    arm = arm_from_config({"name": "RAW_SUBSAMPLE", "subsample": {"size": 7, "draw": 0}}, {}, 5)
    out, rep = arm.filter.apply(exs)
    assert len(out) == 7 and rep.examples_in == len(exs) and rep.examples_out == 7
    assert len({e.instance_id for e in out}) == 7
    positions = [exs.index(e) for e in out]
    assert positions == sorted(positions)  # pool order kept
    again, _ = arm_from_config(
        {"name": "RAW_SUBSAMPLE", "subsample": {"size": 7, "draw": 0}}, {}, 5
    ).filter.apply(exs)
    assert [e.instance_id for e in again] == [e.instance_id for e in out]
    shuffled, _ = arm.filter.apply(list(reversed(exs)))  # the draw does not depend on read order
    assert {e.instance_id for e in shuffled} == {e.instance_id for e in out}


def test_random_subset_draws_and_seeds_are_independent() -> None:
    exs = synthetic_examples(repos=3, prs=4)

    def ids(seed: int, draw: int) -> set[str]:
        a = arm_from_config(
            {"name": "RAW_SUBSAMPLE", "subsample": {"size": 6, "draw": draw}}, {}, seed
        )
        return {e.instance_id for e in a.filter.apply(exs)[0]}

    assert ids(0, 0) != ids(0, 1) and ids(0, 0) != ids(1, 0)
    full, _ = arm_from_config(
        {"name": "RAW_SUBSAMPLE", "subsample": {"size": len(exs)}}, {}, 0
    ).filter.apply(exs)
    assert full == exs  # the limit is the identity


def test_random_subset_refuses_bad_configurations() -> None:
    exs = synthetic_examples(repos=1, prs=3)
    with pytest.raises(ValueError):
        arm_from_config({"name": "RAW_SUBSAMPLE"}, {}, 0)
    with pytest.raises(ValueError):
        arm_from_config({"name": "RAW", "subsample": {"size": 2}}, {}, 0)
    with pytest.raises(ValueError):
        arm_from_config(
            {
                "name": "RAW_SUBSAMPLE",
                "subsample": {"size": 2},
                "filter": {"teacher": "t", "level": "positive"},
            },
            {"t": _signal()},
            0,
        )
    with pytest.raises(ValueError):
        arm_from_config(
            {"name": "RAW_SUBSAMPLE", "subsample": {"size": len(exs) + 1}}, {}, 0
        ).filter.apply(exs)
