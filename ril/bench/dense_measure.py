"""Latency, throughput and memory of the dense stages (query encoding, flat exact search, encoding).

Implements ``specs/latency_harness.md`` for the real stages ``query_encode`` and ``dense_search``
and
the offline stage ``dense_encode`` (``ril.retrieval.dense_encoder``, ``provisional: ADR-006``):

* ``query_encode``: one issue-like query through the encoder, batch size 1 (template applied);
* ``dense_search``: inner product of one precomputed query vector with every unit vector of a
  snapshot and selection of the 100 best (``FlatIndex.search``; on a GPU node a torch variant with
  the matrix on the device is measured under its own query-set id);
* ``dense_encode``: a fixed seeded sample of unit texts encoded in batches (units per second).

Query set: queries built from a snapshot's own identifiers (no benchmark text), whose word counts
are drawn from the word counts of the development issues (numbers only), so that the encoded
length resembles an issue. One query-set id per encoder and cut (``qenc-<encoder>-t<cut>-v1``);
the files share their content, the id keeps rows of different encoders out of one comparison.
Search rows: ``dsearch-<encoder>-<scale>[-torch]-v1``. Scales: a development snapshot's real unit
vectors, and the django scale (35,860 units, the parsed django snapshot of the first graph build)
filled with real development unit vectors drawn with replacement (search cost depends on the row
count and dimension only).

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from ril.bench.latency_harness import (
    BenchConfig,
    RegressionThreshold,
    Row,
    StageRegistry,
    capture_environment,
    run_latency,
    run_throughput,
)
from ril.bench.retrieval_measure import words_of
from ril.retrieval.dense_encoder import FlatIndex

DJANGO_UNITS = 35_860
TOP_K = 100
N_QUERIES = 100


def build_issue_like_queries(
    identifiers: Sequence[str], word_counts: Sequence[int], n: int, seed: int
) -> list[str]:
    """``n`` queries of identifier words whose lengths follow ``word_counts`` (drawn, seeded)."""
    rng = random.Random(seed)
    words = [w for ident in identifiers for w in words_of(ident)]
    if not words or not word_counts:
        raise ValueError("identifiers and word counts must be non-empty")
    out: list[str] = []
    for _ in range(n):
        target = max(3, int(rng.choice(list(word_counts))))
        start = rng.randrange(len(words))
        picked = [words[(start + i) % len(words)] for i in range(target)]
        out.append(" ".join(picked))
    return out


def bench_config(query_set: str, seed: int) -> BenchConfig:
    """Harness configuration of these rows (thresholds provisional: Q33)."""
    return BenchConfig(
        seed=seed,
        query_set=query_set,
        warmup_n=5,
        repeats=3,
        throughput_repeats=1,
        regression=RegressionThreshold(rel_threshold=0.5, abs_floor_ms=0.5),
    )


def scale_matrix(vectors: np.ndarray[Any, Any], rows: int, seed: int) -> np.ndarray[Any, Any]:
    """``rows`` vectors drawn from ``vectors`` with replacement (seeded); all rows if equal."""
    if rows == len(vectors):
        return np.asarray(vectors, dtype=np.float32)
    rng = np.random.default_rng(seed)
    return np.asarray(vectors[rng.integers(0, len(vectors), size=rows)], dtype=np.float32)


def query_encode_rows(encoder: Any, queries: Sequence[str], query_set: str, seed: int) -> list[Row]:
    """``query_encode`` rows (cold and warm) for one encoder and cut."""
    reg = StageRegistry()
    reg.register("query_encode", encoder.encode_query)
    cfg = bench_config(query_set, seed)
    return run_latency(reg, cfg, queries, capture_environment(cfg.config_hash()))


def search_rows(
    matrix: np.ndarray[Any, Any],
    query_vectors: dict[str, np.ndarray[Any, Any]],
    query_set: str,
    seed: int,
    *,
    device: str = "cpu",
) -> list[Row]:
    """``dense_search`` rows over ``matrix`` with precomputed query vectors (looked up by text)."""
    fn: Callable[[str], object]
    if device == "cpu":
        index = FlatIndex(matrix)

        def fn(q: str) -> object:
            return index.search(query_vectors[q], TOP_K)

    else:
        import torch  # type: ignore[import-not-found,unused-ignore]

        mat = torch.from_numpy(np.ascontiguousarray(matrix, dtype=np.float32)).to(device)
        qv = {
            k: torch.from_numpy(v.astype(np.float32)).to(device) for k, v in query_vectors.items()
        }
        k = min(TOP_K, int(mat.shape[0]))

        def fn(q: str) -> object:
            return torch.topk(mat @ qv[q], k)

    reg = StageRegistry()
    reg.register("dense_search", fn)
    cfg = bench_config(query_set, seed)
    return run_latency(reg, cfg, list(query_vectors), capture_environment(cfg.config_hash()))


def encode_throughput_rows(
    encoder: Any, texts: Sequence[str], workload: str, batch_size: int, seed: int
) -> list[Row]:
    """``dense_encode`` row: the sample encoded once, units per second."""
    reg = StageRegistry()
    reg.register_throughput(
        "dense_encode", lambda: int(encoder.encode_documents(texts, batch_size).shape[0])
    )
    cfg = bench_config(workload, seed)
    return run_throughput(reg, cfg, capture_environment(cfg.config_hash()))


def write_query_set(path: Path, queries: Sequence[str]) -> list[str]:
    """Write the set if it does not exist; return the set as stored (immutable once written)."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(queries) + "\n", encoding="utf-8")
    return path.read_text(encoding="utf-8").splitlines()


def vm_hwm_kb() -> int | None:
    """Peak resident memory of this process (``VmHWM``; Linux only)."""
    try:
        with open("/proc/self/status", encoding="ascii") as handle:
            for line in handle:
                if line.startswith("VmHWM:"):
                    return int(line.split()[1])
    except OSError:
        return None
    return None
