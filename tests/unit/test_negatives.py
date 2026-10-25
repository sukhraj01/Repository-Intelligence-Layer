"""Tests for the negative policies and the teacher mining."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from ril.training.negatives import (
    Mined,
    RandomRepoLocal,
    Structural,
    TeacherTopM,
    TeacherTopMPositiveCut,
    bm25_score_fn,
    class_of,
    file_of,
    make_policy,
    mine,
    read_mined,
    write_mined,
)
from ril.training.pool_reader import PoolExample


def _example() -> PoolExample:
    cand = ("a.py/f", "a.py/K/g", "b.py/h", "b.py/K/i", "c.py/j")
    return PoolExample(
        "o__r-1",
        "o/r",
        1,
        "q",
        ("a.py/K/p",),
        ("def p(): pass",),
        cand,
        tuple(f"def {c[-1]}(): pass" for c in cand),
    )


def _mined() -> Mined:
    return Mined("t", (0.8,), ("b.py/h", "a.py/f", "c.py/j", "a.py/K/g"), (0.9, 0.77, 0.5, 0.1))


def test_id_structure() -> None:
    assert file_of("pkg/a.py/K/f") == "pkg/a.py" and class_of("pkg/a.py/K/f") == "pkg/a.py/K"
    assert class_of("pkg/a.py/f") is None and file_of("weird") == "weird"


def test_random_policy_is_seeded_and_bounded() -> None:
    ex = _example()
    pol = RandomRepoLocal()
    a = pol.select(ex, None, 3, np.random.default_rng(1))
    b = pol.select(ex, None, 3, np.random.default_rng(1))
    assert a == b and len(set(a)) == 3
    assert sorted(pol.select(ex, None, 10, np.random.default_rng(0))) == list(range(5))
    assert pol.select(ex, None, 0, np.random.default_rng(0)) == []


def test_teacher_policies_and_positive_cut() -> None:
    ex, m = _example(), _mined()
    idx = {c: i for i, c in enumerate(ex.candidate_ids)}
    assert TeacherTopM(2).eligible(ex, m) == [idx["b.py/h"], idx["a.py/f"]]
    # ratio 0.95 of the positive's 0.8 = 0.76: drops 0.9 and 0.77
    cut = TeacherTopMPositiveCut(2, "ratio", 0.95, "min")
    assert cut.eligible(ex, m) == [idx["c.py/j"], idx["a.py/K/g"]]
    margin = TeacherTopMPositiveCut(5, "margin", 0.05, "max")
    assert margin.eligible(ex, m) == [idx["c.py/j"], idx["a.py/K/g"]]
    with pytest.raises(ValueError):
        TeacherTopM(2).eligible(ex, None)


def test_structural_is_pilot_only() -> None:
    ex = _example()
    assert Structural("same_file").eligible(ex, None) == [0, 1]
    assert Structural("same_class").eligible(ex, None) == [1]
    with pytest.raises(ValueError):
        make_policy({"name": "structural", "relation": "same_file"})
    assert make_policy({"name": "structural", "relation": "same_file"}, pilot=True).name
    with pytest.raises(ValueError):
        make_policy({"name": "nope"})


def test_mine_orders_by_score_and_round_trips(tmp_path: Path) -> None:
    cand = ("x.py/a", "x.py/b", "x.py/c")
    ex = PoolExample(
        "o__r-2",
        "o/r",
        2,
        "parse config",
        ("x.py/p",),
        ("def parse(config): 1",),
        cand,
        ("def parse(): 1", "def render(): 1", "def config(): 1"),
    )
    m = mine(ex, "bm25", bm25_score_fn, keep=2)
    assert len(m.top_ids) == 2 and m.top_scores[0] >= m.top_scores[1]
    assert m.positive_scores[0] > 0 and "x.py/b" not in m.top_ids
    p = str(tmp_path / "m.jsonl.gz")
    write_mined(p, {ex.instance_id: m})
    assert read_mined(p) == {ex.instance_id: m}
    with pytest.raises(ValueError):
        Mined("t", (1.0,), ("a", "b"), (0.1, 0.2))
