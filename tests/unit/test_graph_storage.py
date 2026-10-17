"""Unit tests for ril.bench.graph_storage: every backend answers expansions identically."""

from pathlib import Path

import pytest

from ril.bench import graph_storage as gs
from ril.parsing.call_graph import build_graph
from ril.parsing.repo_graph import RepoGraph
from ril.parsing.repository_parser import parse_repository


@pytest.fixture
def graph(mini_repo: Path) -> RepoGraph:
    return build_graph(parse_repository(str(mini_repo), "acme/mini"))


def test_reference_expansion_matches_manual_bfs(graph: RepoGraph) -> None:
    pairs = gs.core_pairs(graph)
    adj = gs._undirected_adj(pairs)
    seed = "pkg/core.py::Engine"
    one = gs._bfs(lambda n: adj.get(n, ()), [seed], 1)
    assert "pkg/core.py::Engine.run" in one  # contain
    assert "pkg/core.py::Base" in one  # inherit
    two = gs._bfs(lambda n: adj.get(n, ()), [seed], 2)
    assert one < two


@pytest.mark.parametrize("backend", gs.BACKENDS)
def test_backends_agree_with_the_reference(graph: RepoGraph, tmp_path: Path, backend: str) -> None:
    adj = gs._undirected_adj(gs.core_pairs(graph))
    seeds = ["pkg/core.py::Engine.run", "pkg/util.py::fmt"]
    gs.preimport(backend)
    store_dir = str(tmp_path / backend)
    gs.writer(backend)(graph, store_dir)
    store = gs.loader(backend)(store_dir)
    for hops in (1, 2):
        expected = gs._bfs(lambda n: adj.get(n, ()), seeds, hops)
        assert store.expand(seeds, hops) == expected, (backend, hops)
    store.reset()
    assert store.expand(seeds, 1) == gs._bfs(lambda n: adj.get(n, ()), seeds, 1)
    assert gs.dir_size(store_dir) > 0


def test_query_set_is_seeded_and_uses_code_units(graph: RepoGraph) -> None:
    a = gs.build_query_set(graph, 5, seed=1)
    b = gs.build_query_set(graph, 5, seed=1)
    c = gs.build_query_set(graph, 5, seed=2)
    assert a == b and a != c
    for q in a:
        ids = q.split("|")
        assert len(ids) == gs.SEEDS_PER_QUERY
        assert all(i in graph.nodes and graph.nodes[i][0] != "directory" for i in ids)
