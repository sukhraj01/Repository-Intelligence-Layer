"""Readers of the call-site buckets: interval, outcome labels, stratified draw, oracle report."""

from __future__ import annotations

from pathlib import Path

import pytest

from ril.evaluation.policy_readers import (
    STRATA,
    draw_policy_sites,
    jedi_outcome,
    oracle_policy_report,
    wilson,
)
from ril.parsing.ambiguity_policy import ambiguous_sites
from ril.parsing.call_graph import GraphBuilder
from ril.parsing.repo_graph import Edge
from ril.parsing.repository_parser import parse_repository


def test_wilson() -> None:
    assert wilson(0, 0) is None
    lo, hi = wilson(5, 10) or (0.0, 0.0)
    assert lo < 0.5 < hi and lo == pytest.approx(0.2366, abs=1e-3)
    lo, hi = wilson(10, 10) or (0.0, 0.0)
    assert hi == 1.0 and lo > 0.69


def test_jedi_outcome_labels() -> None:
    amb = Edge("invoke", "a", "", "ambiguous", "r", ("b", "c"), "p:1:0", "x.f")
    res = Edge("invoke", "a", "b", "resolved", "r", (), "p:2:0", "f")
    assert jedi_outcome("ambiguous_le3", amb, ("b",), 1, "") == "jedi-in-repo-in-set"
    assert jedi_outcome("ambiguous_le3", amb, ("b", "z"), 2, "") == "jedi-in-repo-overlaps-set"
    assert jedi_outcome("ambiguous_gt3", amb, ("z",), 1, "") == "jedi-in-repo-outside-set"
    assert jedi_outcome("ambiguous_evidence", amb, (), 2, "") == "jedi-external-only"
    assert jedi_outcome("external", amb, (), 0, "") == "jedi-nothing"
    assert jedi_outcome("resolved", res, ("b",), 1, "") == "jedi-in-repo-same"
    assert jedi_outcome("resolved", res, (), 0, "jedi-error:X") == "jedi-no-answer"


def test_draw_is_seeded_and_fills_short_strata(mini_repo: Path) -> None:
    parsed = parse_repository(str(mini_repo), "acme/mini")
    graph = GraphBuilder(parsed).build()
    amb = {s.site + "|" + s.target_text: s for s in ambiguous_sites(parsed, graph)}
    a = draw_policy_sites(graph, amb, 12, 0, "mini")
    b = draw_policy_sites(graph, amb, 12, 0, "mini")
    assert a == b and {s for s, _ in a} <= set(STRATA)
    invokes = sum(1 for e in graph.edges if e.type == "invoke")
    assert len(a) == min(12, invokes)  # a short stratum's quota is taken up elsewhere


def test_oracle_report_on_a_synthetic_trace(mini_repo: Path) -> None:
    parsed = parse_repository(str(mini_repo), "acme/mini")
    builder = GraphBuilder(parsed)
    graph = builder.build()
    # Engine.run calls Base.run (super), Engine.hook... record one observed pair
    trace = {
        "entered": [["pkg/core.py", 26, "run", 1], ["pkg/core.py", 9, "run", 1]],
        "pairs_py": [["pkg/core.py", 26, "run", "pkg/core.py", 8, "run", 1]],
        "pairs_ext_py": [],
        "pairs_c": [],
    }
    coverage = {"files": {"pkg/core.py": {"executed_lines": list(range(1, 60))}}}
    report = oracle_policy_report(parsed, graph, builder, trace, coverage)
    assert set(report["policies"]) == {"keep", "drop", "rebucket", "max3"}
    keep, drop = report["policies"]["keep"], report["policies"]["drop"]
    assert keep["edges"]["pairs"] >= drop["edges"]["pairs"]
    assert drop["ambiguous_pairs_added"]["pairs"] == 0
    assert report["dynamic_in_repo_pairs"] <= 1
