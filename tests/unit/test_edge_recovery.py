"""Unit tests for ril.evaluation.edge_recovery on a synthetic repository and trace."""

from pathlib import Path

from ril.evaluation.edge_recovery import UnitIndex, map_trace, recovery_report, terminal_name
from ril.parsing.call_graph import GraphBuilder
from ril.parsing.repository_parser import parse_repository


def _trace() -> dict[str, object]:
    # (file, first line, code name) of the units in tests/conftest.py's mini repository
    return {
        "entered": [
            ["pkg/core.py", 19, "__init__", 1],
            ["pkg/core.py", 25, "run", 1],
        ],
        "pairs_py": [
            # Engine.run (line 25) called Base.hook (line 11): recovered (self.hook())
            ["pkg/core.py", 25, "run", "pkg/core.py", 11, "hook", 1],
            # a comprehension code object called from run: excluded, not an edge
            ["pkg/core.py", 25, "run", "pkg/core.py", 27, "<listcomp>", 1],
            # run called util.other directly: static graph has no such edge (it goes through Helper)
            ["pkg/core.py", 25, "run", "pkg/util.py", 6, "other", 1],
        ],
        "pairs_ext_py": [],
        "pairs_c": [["pkg/core.py", 25, "run", "posix", "getcwd", 1]],
        "outcomes": {"call:passed": 1},
        "pytest_exit_code": 0,
        "python": "3.10",
    }


def test_terminal_name() -> None:
    assert terminal_name("self.helper.go") == "go"
    assert terminal_name("f(x).g") == "g"
    assert terminal_name("os.path.join") == "join"


def test_unit_index_maps_own_nested_and_module_code(mini_repo: Path) -> None:
    parsed = parse_repository(str(mini_repo), "acme/mini")
    idx = UnitIndex.build(parsed.units)
    hook = parsed.unit_by_id()["pkg/core.py::Base.hook"]
    assert idx.locate("pkg/core.py", hook.start_line, "hook") == (hook.id, "own")
    assert idx.locate("pkg/core.py", 1, "<module>") == ("pkg/core.py::<module>", "module")
    inner = idx.locate("pkg/core.py", hook.start_line + 1, "<listcomp>")
    assert inner == (hook.id, "comp")
    assert idx.locate("missing.py", 1, "f") is None


def test_recovery_counts_hits_misses_and_exclusions(mini_repo: Path) -> None:
    parsed = parse_repository(str(mini_repo), "acme/mini")
    builder = GraphBuilder(parsed)
    graph = builder.build()
    units = parsed.unit_by_id()
    run, hook, other = (
        units["pkg/core.py::Engine.run"],
        units["pkg/core.py::Base.hook"],
        units["pkg/util.py::other"],
    )
    trace = _trace()
    trace["pairs_py"] = [  # use the real first lines of this fixture
        ["pkg/core.py", run.start_line, "run", "pkg/core.py", hook.start_line, "hook", 1],
        ["pkg/core.py", run.start_line, "run", "pkg/core.py", run.start_line + 1, "<listcomp>", 1],
        ["pkg/core.py", run.start_line, "run", "pkg/util.py", other.start_line, "other", 1],
    ]
    trace["pairs_c"] = [["pkg/core.py", run.start_line, "run", "posix", "getcwd", 1]]
    trace["entered"] = [["pkg/core.py", run.start_line, "run", 1]]
    dp = map_trace(trace, UnitIndex.build(parsed.units))
    assert set(dp.pairs) == {(run.id, hook.id), (run.id, other.id)}
    assert dp.excluded["callee-comprehension"] == 1
    report = recovery_report(parsed, graph, builder, trace)
    view = report["recall_in_repo_callees"][0]
    assert view["n_pairs"] == 2
    assert view["recovered_resolved"] == 1  # self.hook() resolves; run -> other has no such site
    assert view["recall_resolved"] == 0.5
    both = report["recall_including_builtin_and_external_callees"]
    assert both["n_pairs"] == 3 and both["builtin_c"]["matched_by_terminal_name"] == 1
    prec = report["precision_among_edges_whose_caller_executed"]
    assert prec["caller_executed"] >= 1
