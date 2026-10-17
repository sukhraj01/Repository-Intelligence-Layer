"""Unit tests for ril.parsing.call_graph and ril.parsing.repo_graph (specs/repo_graph.md)."""

from pathlib import Path

import pytest

from ril.parsing.call_graph import apply_projections, build_graph
from ril.parsing.repo_graph import Edge, RepoGraph
from ril.parsing.repository_parser import parse_repository


@pytest.fixture
def graph(mini_repo: Path) -> RepoGraph:
    parsed = parse_repository(str(mini_repo), "acme/mini")
    return build_graph(parsed, snapshot_commit="abc")


def invokes(graph: RepoGraph, src: str) -> list[Edge]:
    return [e for e in graph.edges if e.type == "invoke" and e.src == src]


def by_text(edges: list[Edge], text: str) -> Edge:
    found = [e for e in edges if e.target_text == text]
    assert len(found) == 1, (text, [e.target_text for e in edges])
    return found[0]


def test_every_edge_has_a_valid_status_and_resolved_edges_have_dst(graph: RepoGraph) -> None:
    for e in graph.edges:
        assert e.status in ("resolved", "ambiguous", "unresolved", "external")
        assert bool(e.dst) == (e.status == "resolved")


def test_self_method_super_and_attribute_type_resolution(graph: RepoGraph) -> None:
    edges = invokes(graph, "pkg/core.py::Engine.run")
    assert by_text(edges, "super().run").dst == "pkg/core.py::Base.run"
    assert by_text(edges, "self.hook").dst == "pkg/core.py::Base.hook"
    assert by_text(edges, "fmt").dst == "pkg/util.py::fmt"
    assert by_text(edges, "os.getcwd").status == "external"
    # self.helper was assigned Helper() in __init__, so go() resolves through the attribute type
    assert by_text(edges, "self.helper.go").dst == "pkg/core.py::Helper.go"


def test_module_alias_call_and_instantiation(graph: RepoGraph) -> None:
    assert (
        by_text(invokes(graph, "pkg/core.py::Helper.go"), "util.other").dst == "pkg/util.py::other"
    )
    test_edges = invokes(graph, "tests/test_core.py::test_run")
    assert by_text(test_edges, "Engine").dst == "pkg/core.py::Engine"  # instantiation
    assert by_text(test_edges, "Engine().run").dst == "pkg/core.py::Engine.run"


def test_dynamic_calls_are_unresolved_not_dropped(graph: RepoGraph) -> None:
    dyn = invokes(graph, "pkg/core.py::Engine.dyn")
    getattr_call = [e for e in dyn if e.derivation == "expr:dynamic-getattr"]
    assert len(getattr_call) == 1 and getattr_call[0].status == "unresolved"
    assert getattr_call[0].dst == ""
    # the getattr call itself and the call through a parameter are both counted
    make = invokes(graph, "pkg/core.py::Engine.make")
    assert by_text(make, "factory").status == "unresolved"
    assert by_text(make, "factory").derivation == "name:call-through-local-name"


def test_nested_definition_calls_fold_into_the_parent(graph: RepoGraph) -> None:
    edges = invokes(graph, "pkg/core.py::helper")
    inner = by_text(edges, "inner")
    assert inner.status == "resolved" and inner.dst == "pkg/core.py::helper"
    assert inner.derivation == "name:nested-def"


def test_multiple_definitions_make_an_ambiguous_edge(graph: RepoGraph) -> None:
    uses = by_text(invokes(graph, "pkg/core.py::uses"), "twice")
    assert uses.status == "ambiguous"
    assert uses.candidates == ("pkg/core.py::twice", "pkg/core.py::twice#2")


def test_inherit_override_contain_and_import_edges(graph: RepoGraph) -> None:
    inherit = [e for e in graph.edges if e.type == "inherit" and e.src == "pkg/core.py::Engine"]
    assert [(e.dst, e.status) for e in inherit] == [("pkg/core.py::Base", "resolved")]
    override = {(e.src, e.dst) for e in graph.edges if e.type == "override"}
    assert ("pkg/core.py::Engine.run", "pkg/core.py::Base.run") in override
    contain = {(e.src, e.dst) for e in graph.edges if e.type == "contain"}
    assert ("pkg/", "pkg/core.py::<module>") in contain
    assert ("pkg/core.py::<module>", "pkg/core.py::Engine") in contain
    assert ("pkg/core.py::Engine", "pkg/core.py::Engine.run") in contain
    imports = [e for e in graph.edges if e.type == "import" and e.src == "pkg/core.py::<module>"]
    texts = {e.target_text: e for e in imports}
    assert texts["os"].status == "external"
    assert texts[".util:fmt"].dst == "pkg/util.py::fmt"
    assert texts["fastjson"].status == "external"
    # re-export: pkg imports Engine from .core
    init_imports = [
        e for e in graph.edges if e.type == "import" and e.src == "pkg/__init__.py::<module>"
    ]
    assert {e.dst for e in init_imports} == {"pkg/core.py::Engine", "pkg/core.py::helper"}


def test_projections_hold_resolved_ids_only(mini_repo: Path) -> None:
    parsed = parse_repository(str(mini_repo), "acme/mini")
    graph = build_graph(parsed)
    apply_projections(parsed.units, graph)
    units = parsed.unit_by_id()
    run = units["pkg/core.py::Engine.run"]
    assert "pkg/core.py::Base.run" in run.calls
    assert all(c in units for c in run.calls)
    assert "pkg/core.py::Engine.run" in units["pkg/core.py::Base.run"].called_by
    # nested-definition self calls are not projected
    assert "pkg/core.py::helper" not in units["pkg/core.py::helper"].calls
    assert run.tests == [] and run.configs == []


def test_status_table_counts_every_site(graph: RepoGraph) -> None:
    table = graph.status_table()
    n_invoke = sum(1 for e in graph.edges if e.type == "invoke")
    assert sum(table["invoke"].values()) == n_invoke
    assert set(table["invoke"]) == {"resolved", "ambiguous", "unresolved", "external"}


def test_edge_validation() -> None:
    with pytest.raises(ValueError):
        Edge("invoke", "a", "", "resolved", "r")
    with pytest.raises(ValueError):
        Edge("invoke", "a", "b", "external", "r")
    with pytest.raises(ValueError):
        Edge("invoke", "a", "", "ambiguous", "r")
    with pytest.raises(ValueError):
        Edge("nope", "a", "b", "resolved", "r")
