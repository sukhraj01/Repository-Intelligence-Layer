"""Retrieval-versus-reasoning breakdown (E-RQ3-BREAKDOWN): classes, failures, explained gain."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ril.analysis import rq3_breakdown as bd

GOLD = {"a": ["x.py"], "b": ["x.py", "y.py"], "c": ["z.py"]}


def _row(inst: str, resolved: bool, outcome: str = "", **kw: Any) -> dict[str, Any]:
    base = {"input_tokens": 100, "output_tokens": 10, "cost_usd": 0.01, "calls": 1}
    return {"instance_id": inst, "resolved": resolved, "outcome": outcome, **base, **kw}


def test_gold_class() -> None:
    assert bd.gold_class(["x.py"], ["x.py", "q.py"]) == "all"
    assert bd.gold_class(["x.py", "y.py"], ["x.py"]) == "some"
    assert bd.gold_class(["x.py"], ["q.py"]) == "none"
    assert bd.gold_class([], ["q.py"]) == "none"


def test_breakdown_counts_failures_by_class() -> None:
    files = {"a": ["x.py"], "b": ["x.py"], "c": []}
    rows = [
        _row("a", True),
        _row("a", False, "executed_unresolved"),
        _row("b", False, "apply_failed:no_match"),
        _row("c", False, "unusable"),
        _row("zz", True),  # not in the instance list: ignored
    ]
    out = bd.breakdown(rows, ["a", "b", "c"], GOLD, files)
    assert out["runs"] == 4 and out["failed_runs"] == 3
    assert out["classes"]["all"] == {
        "instances": 1,
        "runs": 2,
        "resolved": 1,
        "resolved_share": 0.5,
        "outcomes": {"executed_unresolved": 1, "resolved": 1},
    }
    assert out["classes"]["some"]["outcomes"] == {"apply_failed": 1}
    assert out["failed_share_all_gold_present"] == pytest.approx(1 / 3)
    assert out["failed_share_no_gold_present"] == pytest.approx(1 / 3)


def test_explained_gain_uses_the_baseline_rates_per_class() -> None:
    def arm(n_all: int, n_none: int, r_all: float, r_none: float) -> dict[str, Any]:
        return {
            "instances": 10,
            "classes": {
                "all": {"instances": n_all, "resolved_share": r_all},
                "some": {"instances": 10 - n_all - n_none, "resolved_share": 0.0},
                "none": {"instances": n_none, "resolved_share": r_none},
            },
        }

    out = bd.expected_retrieval_gain(arm(7, 3, 0.9, 0.9), arm(5, 5, 0.5, 0.1))
    assert out["instance_shift"] == {"all": 2, "some": 0, "none": -2}
    assert out["explained_gain_points"] == pytest.approx(100 * (2 * 0.5 - 2 * 0.1) / 10)


def test_attempt_cost_and_gap() -> None:
    rows = [_row("a", True), _row("a", False, output_tokens=30, cost_usd=0.03, calls=2)]
    c = bd.attempt_cost(rows, ["a"])
    assert (c["runs"], c["calls"], c["tokens_per_run"]) == (2, 3, 120.0)
    assert c["usd_per_run"] == pytest.approx(0.02)
    assert bd.gap_closed(0.4, 0.1, 0.5) == pytest.approx(0.75)


def test_attempt_cost_splits_cached_and_thought_tokens() -> None:
    rows = [
        _row("a", True, cached_tokens=40, thought_tokens=3),
        _row("a", False, cached_tokens=10, thought_tokens=0),
    ]
    c = bd.attempt_cost(rows, ["a"])
    assert c["cached_prompt_tokens"] == 50
    assert c["uncached_prompt_tokens"] == c["prompt_tokens"] - 50
    assert c["thought_tokens"] == 3
    assert c["cached_share"] == pytest.approx(50 / c["prompt_tokens"])
    assert bd.attempt_cost([], ["a"])["cached_share"] is None


def test_python_tokens_skips_git_and_other_files(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "m.py").write_text("def f(x):\n    return x\n")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "h.py").write_text("ignored = 1\n")
    (tmp_path / "README.md").write_text("words words\n")
    assert bd.python_tokens(str(tmp_path)) == {"python_files": 1, "approx_tokens": 10}


def test_outcome_of_reads_the_registered_reading() -> None:
    assert bd.outcome_of(_row("a", True, "apply_failed:no_match")) == "resolved"
    assert bd.outcome_of(_row("a", False, "apply_failed:no_match")) == "apply_failed"
    assert bd.outcome_of(_row("a", False, "executed_unresolved")) == "executed_unresolved"
    assert bd.outcome_of(_row("a", False, "something_new")) == "other"
