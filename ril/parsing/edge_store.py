"""The stored graph: a versioned, deterministic, hashed edge-list directory (session A2c).

Decision D16 fixes the read structure of the first stored graph: a typed edge-list file read into an
in-memory adjacency, no graph database. This module is that file format:

    <dir>/manifest.json   format version, schema and resolver versions, repository, snapshot commit,
                          config hash, unit-set hash, counts per family and status, and the
                          SHA-256 and byte size of every data file
    <dir>/nodes.jsonl.gz  one canonical JSON object per node, sorted by id
    <dir>/edges.jsonl.gz  one canonical JSON object per edge, in the canonical edge order

The data files are the canonical bytes of :class:`ril.parsing.repo_graph.RepoGraph`, gzip-compressed
with a fixed header (no file name, time 0), so the same graph always writes the same bytes. A load
checks the format version, every file hash and the counts before returning the graph; any mismatch
raises :class:`EdgeStoreError` instead of returning a partly wrong graph. ``deep=True`` also
recomputes the graph digest from the parsed graph (a check of the reader itself, about twice the
cost of the load); ``verify=False`` skips the file hashes. The cost of each level is measured by
``ril.bench.edge_store_measure``.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
from collections import Counter
from typing import Any

from ril.parsing.repo_graph import Edge, RepoGraph, canonical_json

EDGE_STORE_FORMAT = "ril-edge-store"
EDGE_STORE_VERSION = 1
"""Bumped on any change to the files or the manifest; a reader refuses versions it does not know."""

_FILES = ("nodes.jsonl.gz", "edges.jsonl.gz")
_GZIP_LEVEL = 6


class EdgeStoreError(ValueError):
    """The directory is not a readable edge store of a known version, or it fails a check."""


def _gzip(data: bytes) -> bytes:
    buf = io.BytesIO()
    with gzip.GzipFile(
        filename="", mode="wb", fileobj=buf, compresslevel=_GZIP_LEVEL, mtime=0
    ) as f:
        f.write(data)
    return buf.getvalue()


def _counts(graph: RepoGraph) -> dict[str, dict[str, int]]:
    table: dict[str, Counter[str]] = {}
    for e in graph.edges:
        table.setdefault(e.type, Counter())[e.status] += 1
    return {t: dict(sorted(c.items())) for t, c in sorted(table.items())}


def write_store(graph: RepoGraph, path: str) -> dict[str, Any]:
    """Write ``graph`` to the directory ``path`` (created if needed); return the manifest.

    The graph is put in canonical edge order first, so the bytes do not depend on how it was built.
    """
    graph.sort()
    os.makedirs(path, exist_ok=True)
    payloads = {
        "nodes.jsonl.gz": _gzip(graph.nodes_jsonl()),
        "edges.jsonl.gz": _gzip(graph.edges_jsonl()),
    }
    manifest: dict[str, Any] = {
        "format": EDGE_STORE_FORMAT,
        "format_version": EDGE_STORE_VERSION,
        "graph_meta": graph.meta,
        "n_nodes": len(graph.nodes),
        "n_edges": len(graph.edges),
        "edge_counts": _counts(graph),
        "graph_digest": graph.digest(),
        "files": {
            name: {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
            for name, data in sorted(payloads.items())
        },
    }
    for name, data in payloads.items():
        with open(os.path.join(path, name), "wb") as handle:
            handle.write(data)
    with open(os.path.join(path, "manifest.json"), "w", encoding="utf-8") as handle:
        handle.write(canonical_json(manifest) + "\n")
    return manifest


def read_manifest(path: str) -> dict[str, Any]:
    """The manifest of the store at ``path``, after the format and version checks."""
    try:
        with open(os.path.join(path, "manifest.json"), encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise EdgeStoreError(f"no readable manifest in {path}: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("format") != EDGE_STORE_FORMAT:
        raise EdgeStoreError(f"{path} is not an edge store")
    if manifest.get("format_version") != EDGE_STORE_VERSION:
        raise EdgeStoreError(
            f"edge store version {manifest.get('format_version')!r} in {path}; "
            f"this reader knows version {EDGE_STORE_VERSION}"
        )
    return manifest


def load_store(path: str, *, verify: bool = True, deep: bool = False) -> RepoGraph:
    """Read the store at ``path`` into a :class:`RepoGraph`.

    Always checked: format version, node and edge counts, per-family counts. ``verify`` adds the
    file hashes; ``deep`` adds the graph digest recomputed from the parsed graph.
    """
    manifest = read_manifest(path)
    raw: dict[str, bytes] = {}
    for name in _FILES:
        try:
            with open(os.path.join(path, name), "rb") as handle:
                raw[name] = handle.read()
        except OSError as exc:
            raise EdgeStoreError(f"missing data file {name} in {path}") from exc
        if verify:
            want = manifest["files"][name]["sha256"]
            if hashlib.sha256(raw[name]).hexdigest() != want:
                raise EdgeStoreError(f"{name} in {path} does not match its manifest hash")
    try:
        node_lines = gzip.decompress(raw["nodes.jsonl.gz"]).decode("utf-8").splitlines()
        edge_lines = gzip.decompress(raw["edges.jsonl.gz"]).decode("utf-8").splitlines()
    except (OSError, EOFError, UnicodeDecodeError) as exc:
        raise EdgeStoreError(f"corrupt data file in {path}: {exc}") from exc
    nodes: dict[str, tuple[str, str]] = {}
    for line in node_lines:
        d = json.loads(line)
        nodes[d["id"]] = (d["kind"], d["path"])
    edges = [Edge.from_dict(json.loads(line)) for line in edge_lines]
    graph = RepoGraph(meta=manifest["graph_meta"], nodes=nodes, edges=edges)
    if len(nodes) != manifest["n_nodes"] or len(edges) != manifest["n_edges"]:
        raise EdgeStoreError(f"node or edge count in {path} differs from its manifest")
    if _counts(graph) != manifest["edge_counts"]:
        raise EdgeStoreError(f"per-family edge counts in {path} differ from its manifest")
    if deep and graph.digest() != manifest["graph_digest"]:
        raise EdgeStoreError(f"graph digest of {path} differs from its manifest")
    return graph


__all__ = [
    "EDGE_STORE_FORMAT",
    "EDGE_STORE_VERSION",
    "EdgeStoreError",
    "load_store",
    "read_manifest",
    "write_store",
]
