"""Synthetic stage workloads for the latency harness.

Implements specs/latency_harness.md ("until then the harness runs against stubs"). These stages do
real numpy/Python work of roughly the right shape so the CSV contract, cold/warm separation and
regression check are exercised end to end. They are NOT measurements of any retrieval component and
their numbers must never be quoted as such; a real component replaces a stub with one
``REGISTRY.register(...)`` line and a different ``query_set_id``.
"""

from __future__ import annotations

import ast
import zlib

import numpy as np
import numpy.typing as npt

from ril.bench.latency_harness import StageRegistry

_DIM = 64
_N_UNITS = 4000
_N_TERMS = 512
_TOP = 100
_RRF_K = 60  # stub-local; the real fusion constant belongs to the frozen configuration
_N_SEEDS = 20
_DEGREE = 8
_PARSE_FILES = 120
_GRAPH_EDGES = 40000

Floats = npt.NDArray[np.float32]
Ints = npt.NDArray[np.int64]


def _top_ids(scores: Floats, k: int) -> Ints:
    ids = np.argpartition(-scores, k)[:k]
    return np.asarray(ids[np.argsort(-scores[ids], kind="stable")], dtype=np.int64)


def _source(i: int) -> str:
    funcs = "\n".join(f"def f{i}_{j}(x):\n    return x + {j}\n" for j in range(5))
    return f"class C{i}:\n    def m(self):\n        return {i}\n\n{funcs}"


def build_stub_registry(seed: int) -> StageRegistry:
    """Build a registry whose stages are deterministic synthetic workloads for ``seed``."""
    rng = np.random.default_rng(seed)
    corpus = rng.standard_normal((_N_UNITS, _DIM)).astype(np.float32)
    proj = (rng.standard_normal((_DIM, _DIM)) / _DIM**0.5).astype(np.float32)
    postings = rng.random((_N_UNITS, _N_TERMS)).astype(np.float32)
    neighbours = rng.integers(0, _N_UNITS, size=(_N_UNITS, _DEGREE), dtype=np.int64)
    sources = [_source(i) for i in range(_PARSE_FILES)]
    edges = rng.integers(0, _N_UNITS, size=(_GRAPH_EDGES, 2), dtype=np.int64)
    cache: dict[str, Floats] = {}

    def encode(query: str) -> Floats:
        hit = cache.get(query)
        if hit is not None:
            return hit
        vec = np.random.default_rng(zlib.crc32(query.encode())).standard_normal(_DIM)
        out = vec.astype(np.float32)
        for _ in range(8):
            out = np.tanh(proj @ out)
        cache[query] = out
        return out

    def bm25(query: str) -> Ints:
        cols = [zlib.crc32(t.encode()) % _N_TERMS for t in query.split()]
        return _top_ids(postings[:, cols].sum(axis=1), _TOP)

    def dense(query: str) -> Ints:
        return _top_ids(corpus @ encode(query), _TOP)

    def seeds(query: str) -> Ints:
        return np.random.default_rng(zlib.crc32(query.encode())).integers(
            0, _N_UNITS, size=_N_SEEDS, dtype=np.int64
        )

    def hop1(query: str) -> Ints:
        return np.unique(neighbours[seeds(query)])

    def hop2(query: str) -> Ints:
        return np.unique(neighbours[hop1(query)])

    def rrf(query: str) -> list[int]:
        scores: dict[int, float] = {}
        for ranked in (bm25(query), dense(query)):
            for rank, unit in enumerate(ranked.tolist(), start=1):
                scores[unit] = scores.get(unit, 0.0) + 1.0 / (_RRF_K + rank)
        return sorted(scores, key=lambda u: (-scores[u], u))

    def same_file(query: str) -> Ints:
        return np.unique(neighbours[seeds(query)][:_TOP])

    def recency(query: str) -> Ints:
        scores = corpus @ encode(query)
        prior = np.exp(-np.arange(_N_UNITS) / 30.0).astype(np.float32)
        return _top_ids(scores + np.float32(0.2) * prior, _TOP)

    def rerank(query: str) -> Ints:
        candidates = corpus[_top_ids(corpus @ encode(query), _TOP)]
        hidden = candidates
        for _ in range(12):
            hidden = np.tanh(hidden @ proj)
        return _top_ids(hidden @ encode(query), 10)

    def assemble(query: str) -> str:
        return "\n".join(f"unit {u}: " + "x" * 80 for u in rrf(query)[:50])

    def end_to_end(query: str) -> str:
        hop2(query)
        return assemble(query)

    def parse() -> int:
        return sum(
            sum(isinstance(n, ast.FunctionDef | ast.ClassDef) for n in ast.walk(ast.parse(s)))
            for s in sources
        )

    def graph_build() -> int:
        adjacency: dict[int, list[int]] = {}
        for src, dst in edges.tolist():
            adjacency.setdefault(src, []).append(dst)
        return int(sum(len(v) for v in adjacency.values()))

    registry = StageRegistry()
    reset = cache.clear
    registry.register("query_encode", encode, reset=reset)
    registry.register("bm25", bm25, reset=reset)
    registry.register("dense_search", dense, reset=reset)
    registry.register("graph_expansion", hop1, reset=reset)
    registry.register("graph_expand_1hop", hop1, reset=reset)
    registry.register("graph_expand_2hop", hop2, reset=reset)
    registry.register("rrf_fusion", rrf, reset=reset)
    registry.register("same_file_expansion", same_file, reset=reset)
    registry.register("recency_prior", recency, reset=reset)
    registry.register("cross_encoder_rerank", rerank, reset=reset)
    registry.register("assemble", assemble, reset=reset)
    registry.register("end_to_end", end_to_end, reset=reset)
    registry.register_throughput("parse", parse)
    registry.register_throughput("graph_build", graph_build)
    registry.register_throughput(
        "dense_encode", lambda: int(np.stack([encode(s) for s in sources]).shape[0])
    )
    # stand-in for one training update per source: encode, score against all, no real model
    registry.register_throughput(
        "train_step",
        lambda: int(
            (
                np.stack([encode(s) for s in sources]) @ np.stack([encode(s) for s in sources]).T
            ).shape[0]
        ),
    )
    return registry
