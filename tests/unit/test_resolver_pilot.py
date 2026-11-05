"""Resolver typing pilot readings (session A2b): static rows, receivers, trace readings, summary."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from ril.bench.resolver_pilot import (
    PILOTS,
    _trace_reading,
    dynamic_rows,
    receiver_census,
    static_rows,
    summary,
)
from ril.evaluation.edge_recovery import DynamicPairs
from tests.unit.test_resolver_options import FILES


def _def_line(rel: str, name: str) -> int:
    lines = FILES[rel].splitlines()
    return next(i for i, ln in enumerate(lines, 1) if ln.lstrip().startswith(f"def {name}("))


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    for rel, text in FILES.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    return tmp_path


def test_static_rows_one_per_pilot_over_the_same_sites(repo: Path) -> None:
    rows = static_rows(str(repo), "acme/opts")
    assert [r["options"] for r in rows] == [p.label() for p in PILOTS]
    assert len({r["invoke_sites"] for r in rows}) == 1
    assert rows[-1]["invoke_resolved"] > rows[0]["invoke_resolved"]
    assert rows[-1]["unknown_receiver_sites"] < rows[0]["unknown_receiver_sites"]


def test_receiver_census_names_the_kind_of_untyped_receiver(repo: Path) -> None:
    stored = receiver_census(str(repo), "acme/opts", PILOTS[0])
    combined = receiver_census(str(repo), "acme/opts", PILOTS[-1])
    assert stored["call result"] > combined.get("call result", 0)
    assert stored["local: unannotated parameter"] == 1  # g's parameter, typed by its default later
    assert "local: unannotated parameter" not in combined


def _trace() -> dict[str, Any]:
    use, models = "pkg/use.py", "pkg/models.py"
    f, g, start = _def_line(use, "f"), _def_line(use, "g"), _def_line(models, "start")
    return {
        "entered": [[use, f, "f", 1], [use, g, "g", 1], [models, start, "start", 1]],
        "pairs_py": [[use, f, "f", models, start, "start", 1]],
        "pairs_ext_py": [],
        "pairs_c": [],
    }


def test_dynamic_rows_read_each_added_pair_against_the_trace(repo: Path) -> None:
    rows = {r["options"]: r for r in dynamic_rows(str(repo), "acme/opts", _trace())}
    assert rows["stored"]["added_vs_stored"] == 0
    readings = {
        (p["caller"].split("::")[1], p["trace"])
        for p in rows["infer_returns+merge_locals+param_defaults"]["added_pairs"]
        if p["callee"].endswith("Engine.start")
    }
    assert ("f", "executed") in readings  # merged local, and the suite ran it
    assert ("g", "caller executed, pair not seen") in readings
    assert ("a", "caller not executed") in readings
    assert all(r["removed_vs_stored"] == 0 for r in rows.values())


def test_class_target_is_read_apart() -> None:
    dp = DynamicPairs({}, set(), set(), set(), {"m::caller"}, Counter())
    assert _trace_reading("m::caller", "m::Cls", dp, "class").startswith("class target")
    assert _trace_reading("m::other", "m::Cls", dp, "class") == "caller not executed"


def test_summary_totals_and_shares() -> None:
    def row(options: str, resolved: int, unknown: int, secs: float) -> dict[str, Any]:
        return {
            "options": options,
            "invoke_sites": 100,
            "invoke_resolved": resolved,
            "unknown_receiver_sites": unknown,
            "graph_build_seconds": secs,
        }

    static = {
        "static": [
            *(row("stored", 40, 20, 1.0), row("all", 44, 15, 1.1)),
            *(row("stored", 10, 0, 1.0), row("all", 10, 0, 1.0)),
        ],
        "untyped_receivers_combined_options": {
            "x/y": {
                "attribute chain on self": 1,
                "attribute chain on another object": 2,
                "call result": 1,
            }
        },
    }
    breakdown = {
        "repositories": [
            {
                "invoke_by_status_and_rule": {
                    "resolved|name:function": 6,
                    "ambiguous|unknown-receiver:name-match": 3,
                    "unresolved|name:undefined-name": 1,
                }
            }
        ]
    }
    out = summary(breakdown, static, None)
    assert out["invoke_breakdown"] == {
        "invoke_sites": 10,
        "ambiguous_or_unresolved": 4,
        "unknown_receiver_among_them": 3,
        "unknown_receiver_share_pct": 75.0,
    }
    s = out["static_totals_over_repositories"]
    assert s["stored"]["invoke_resolved"] == 50
    assert (s["all"]["resolved_gain"], s["all"]["resolved_gain_pct"]) == (4, 8.0)
    assert s["all"]["unknown_receiver_change_pct"] == -25.0
    assert s["all"]["graph_build_change_pct"] == 5.0
    assert out["untyped_receivers_combined_options"]["attribute_chain_pct"] == 75.0
    assert "dynamic" not in out
