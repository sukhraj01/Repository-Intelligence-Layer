"""Edge subsets, hop distances and the random controls of the reach pilot."""

from __future__ import annotations

import json

import numpy as np

from ril.analysis.reach_tables import compare
from ril.evaluation.graph_reach import (
    SUBSETS,
    adjacency,
    control_pools,
    control_shares,
    distances,
    draw_sets,
    edge_pairs,
    min_distance,
    observed_shares,
    stable_rng,
)
from ril.parsing.code_unit import CodeUnit
from ril.parsing.repo_graph import Edge

SPEC = {s.name: s for s in SUBSETS}


def _edge(kind: str, a: str, b: str, status: str = "resolved") -> Edge:
    if status == "resolved":
        return Edge(kind, a, b, "resolved", "t")
    return Edge(kind, a, "", status, "t", (b,) if status == "ambiguous" else ())


def test_only_resolved_edges_count_and_self_loops_are_dropped() -> None:
    pairs = edge_pairs(
        [
            _edge("invoke", "a", "b"),
            _edge("invoke", "a", "c", "ambiguous"),
            _edge("invoke", "a", "x", "external"),
            _edge("invoke", "d", "d"),
        ]
    )
    assert pairs == {"invoke": [("a", "b")]}


def test_directed_and_undirected_invoke_subsets() -> None:
    pairs = edge_pairs([_edge("invoke", "a", "b"), _edge("invoke", "b", "c")])
    both = distances(adjacency(pairs, SPEC["invoke_both"]), {"b"})
    fwd = distances(adjacency(pairs, SPEC["invoke_fwd"]), {"b"})
    rev = distances(adjacency(pairs, SPEC["invoke_rev"]), {"b"})
    assert both == {"b": 0, "a": 1, "c": 1}
    assert fwd == {"b": 0, "c": 1}
    assert rev == {"b": 0, "a": 1}


def test_inherit_subset_includes_override_and_all_adds_the_exploratory_families() -> None:
    pairs = edge_pairs([_edge("override", "m2", "m1"), _edge("tests", "t", "m1")])
    assert distances(adjacency(pairs, SPEC["inherit"]), {"m1"}) == {"m1": 0, "m2": 1}
    assert "t" not in distances(adjacency(pairs, SPEC["core"]), {"m1"})
    assert distances(adjacency(pairs, SPEC["all"]), {"m1"})["t"] == 1
    assert SPEC["tests"].exploratory and not SPEC["core"].exploratory


def test_co_change_families_are_keyed_by_support() -> None:
    cc2 = [Edge("co_change", "f1", "f2", "resolved", "r")]
    pairs = edge_pairs([], {2: cc2, 3: []})
    assert distances(adjacency(pairs, SPEC["co_change_n2"]), {"f1"}) == {"f1": 0, "f2": 1}
    assert distances(adjacency(pairs, SPEC["co_change_n3"]), {"f1"}) == {"f1": 0}


def test_min_distance_and_unreachable() -> None:
    dist = {"a": 0, "b": 2, "c": 5}
    assert min_distance(dist, ["c", "b"]) == 2
    assert min_distance(dist, ["z"]) is None
    assert observed_shares(None)["unreachable"] == 1.0
    assert observed_shares(2) == {"le1": 0.0, "le2": 1.0, "le3": 1.0, "unreachable": 0.0}


def _unit(path: str, name: str, utype: str = "function", is_test: bool = False) -> CodeUnit:
    return CodeUnit(
        id=f"{path}::{name}",
        repo_id="acme/x",
        file=path,
        language="python",
        unit_type=utype,
        name=name,
        qualified_name=name,
        signature="",
        docstring=None,
        source="",
        start_line=1,
        end_line=2,
        loc=1,
        calls=[],
        called_by=[],
        tests=[],
        configs=[],
        last_modified="",
        is_test=is_test,
    )


def test_control_pools_exclude_the_l2_units_and_stratify_by_kind() -> None:
    units = [_unit("a.py", "f"), _unit("a.py", "g"), _unit("t/test_a.py", "test_f", is_test=True)]
    pools = control_pools(units, {"a.py::f"})
    assert pools.by_file == {"a.py": ["a.py::g"], "t/test_a.py": ["t/test_a.py::test_f"]}
    assert pools.whole == ["a.py::g", "t/test_a.py::test_f"]
    assert pools.by_kind == {"function": ["a.py::g"], "function+test": ["t/test_a.py::test_f"]}


def test_draws_are_deterministic_and_a_small_pool_is_taken_whole() -> None:
    pool = [f"u{i}" for i in range(20)]
    a = draw_sets(pool, 3, 5, stable_rng(0, "inst", "c1", "whole_repo"))
    b = draw_sets(pool, 3, 5, stable_rng(0, "inst", "c1", "whole_repo"))
    c = draw_sets(pool, 3, 5, stable_rng(0, "inst", "c2", "whole_repo"))
    assert a == b and a != c and all(len(s) == 3 for s in a)
    assert draw_sets(["only"], 4, 3, stable_rng(1)) == [("only",)] * 3
    assert draw_sets([], 2, 3, stable_rng(1)) == []
    assert control_shares([], {}) is None


def test_control_shares_match_the_hand_count() -> None:
    sets = [("a",), ("b",), ("c",), ("z",)]
    dist = {"a": 1, "b": 2, "c": 3}
    got = control_shares(sets, dist)
    assert got == {"le1": 0.25, "le2": 0.5, "le3": 0.75, "unreachable": 0.25}


def test_compare_reports_excess_over_chance_with_intervals() -> None:
    rng = np.random.default_rng(0)
    obs = np.array([1.0] * 18 + [0.0] * 2)
    ctrl = np.full(20, 0.5)
    cluster = np.array(["i1"] * 10 + ["i2"] * 10)
    out = compare(obs, ctrl, cluster, rng, 500)
    assert out["obs_share"] == 0.9 and out["chance_share"] == 0.5
    assert out["difference"] == 0.4 and out["ratio"] == 1.8
    assert out["diff_lo"] <= 0.4 <= out["diff_hi"]
    assert out["ratio_lo"] <= 1.8 <= out["ratio_hi"]
    assert out["n_instances"] == 2 and "diff_cluster_lo" in out
    zero = compare(np.zeros(4), np.zeros(4), np.array(["a", "a", "b", "b"]), rng, 100)
    assert zero["ratio"] is None
    assert compare(np.array([]), np.array([]), np.array([]), rng, 10) == {"n": 0}


def test_run_log_states_whether_two_runs_agree_apart_from_timing() -> None:
    from ril.analysis.reach_tables import comparable, run_log

    doc = {
        "pilot": "p",
        "config_hash": "h",
        "seed": 0,
        "draws": 5,
        "hardware": {"host": "a", "python": "3"},
        "git": "g",
        "repos": [],
        "failures": [],
        "instances": [{"instance": "i", "repo_id": "r/x", "build_seconds": 1.0, "positives": []}],
    }
    other = json.loads(json.dumps(doc))
    other["instances"][0]["build_seconds"] = 9.0
    other["hardware"]["host"] = "b"
    assert comparable(doc) == comparable(other)
    log = run_log(doc, records_sha256="x", rerun=other, tables={}, extras={})
    assert log["determinism"] == {"second_run_identical_apart_from_timing_and_host": True}
    other["instances"][0]["positives"] = [{"level": "L2"}]
    log = run_log(doc, records_sha256="x", rerun=other, tables={}, extras={})
    assert log["determinism"] == {"second_run_identical_apart_from_timing_and_host": False}
    assert run_log(doc, records_sha256="x", rerun=None, tables={}, extras={})["determinism"] is None
