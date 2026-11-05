"""Edge store: round trip, byte-identical writes, and refusal of damaged or unknown stores."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from ril.parsing.build import BuildConfig, build_repository
from ril.parsing.edge_store import EdgeStoreError, load_store, read_manifest, write_store
from ril.parsing.repo_graph import RepoGraph


def _graph(mini_repo: Path) -> RepoGraph:
    config = BuildConfig(repo_id="acme/mini", with_history=False)
    return build_repository(str(mini_repo), config, exploratory=False).graph


def test_round_trip_returns_the_same_graph(mini_repo: Path, tmp_path: Path) -> None:
    graph = _graph(mini_repo)
    manifest = write_store(graph, str(tmp_path / "g"))
    loaded = load_store(str(tmp_path / "g"), deep=True)
    assert loaded.digest() == graph.digest() == manifest["graph_digest"]
    assert loaded.adjacency() == graph.adjacency()
    assert manifest["n_edges"] == len(graph.edges)


def test_the_same_graph_writes_the_same_bytes(mini_repo: Path, tmp_path: Path) -> None:
    graph = _graph(mini_repo)
    write_store(graph, str(tmp_path / "a"))
    shuffled = RepoGraph(meta=graph.meta, nodes=graph.nodes, edges=list(reversed(graph.edges)))
    write_store(shuffled, str(tmp_path / "b"))
    for name in ("manifest.json", "nodes.jsonl.gz", "edges.jsonl.gz"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


def test_a_changed_data_file_is_refused(mini_repo: Path, tmp_path: Path) -> None:
    store = tmp_path / "g"
    write_store(_graph(mini_repo), str(store))
    lines = gzip.decompress((store / "edges.jsonl.gz").read_bytes()).decode().splitlines()
    (store / "edges.jsonl.gz").write_bytes(gzip.compress(("\n".join(lines[1:]) + "\n").encode()))
    with pytest.raises(EdgeStoreError, match="hash"):
        load_store(str(store))
    with pytest.raises(EdgeStoreError, match="count"):  # still caught without hash checks
        load_store(str(store), verify=False)


def test_an_unknown_version_or_a_foreign_directory_is_refused(
    mini_repo: Path, tmp_path: Path
) -> None:
    store = tmp_path / "g"
    write_store(_graph(mini_repo), str(store))
    manifest = read_manifest(str(store))
    manifest["format_version"] = 99
    (store / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(EdgeStoreError, match="version"):
        load_store(str(store))
    with pytest.raises(EdgeStoreError, match="manifest"):
        load_store(str(tmp_path / "missing"))
