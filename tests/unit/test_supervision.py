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
