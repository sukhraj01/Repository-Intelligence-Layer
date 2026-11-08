"""Cost of the edge store (session A2c): write time, size, load time with and without checks.

For each checkout the graph is built once (history off), written with ``write_store`` and read back
``repeats`` times at three check levels (``fast``: counts only; ``verify``: plus file hashes, the
default; ``deep``: plus the recomputed graph digest); the in-memory adjacency of decision D16 is
built from each load and timed separately. Times are wall clock in one process with a warm file
cache, nearest-rank percentiles over the repeats; the round trip must reproduce the graph digest.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import os
import shutil
import time
from typing import Any

from ril.bench.latency_harness import percentile
from ril.parsing.build import BuildConfig, build_repository
from ril.parsing.edge_store import EDGE_STORE_VERSION, load_store, write_store


def _pcts(values: list[float]) -> dict[str, float]:
    return {f"p{p}": round(percentile(values, p), 4) for p in (50, 95, 99)}


def measure_repository(root: str, repo_id: str, work: str, repeats: int = 7) -> dict[str, Any]:
    """Write, load and adjacency times for one checkout; the store goes to ``work``."""
    config = BuildConfig(repo_id=repo_id, with_history=False)
    graph = build_repository(root, config, exploratory=False).graph
    raw_bytes = len(graph.nodes_jsonl()) + len(graph.edges_jsonl())
    store = os.path.join(work, repo_id.replace("/", "__"))
    shutil.rmtree(store, ignore_errors=True)
    t0 = time.perf_counter()
    manifest = write_store(graph, store)
    write_s = time.perf_counter() - t0
    timings: dict[str, list[float]] = {
        "load_fast": [],
        "load_verify": [],
        "load_deep": [],
        "adjacency": [],
    }
    equal = True
    for _ in range(repeats):
        for key, verify, deep in (
            ("load_fast", False, False),
            ("load_verify", True, False),
            ("load_deep", True, True),
        ):
            t0 = time.perf_counter()
            loaded = load_store(store, verify=verify, deep=deep)
            timings[key].append(time.perf_counter() - t0)
            equal = equal and loaded.digest() == graph.digest()
        t0 = time.perf_counter()
        loaded.adjacency()
        timings["adjacency"].append(time.perf_counter() - t0)
    return {
        "repo_id": repo_id,
        "format_version": EDGE_STORE_VERSION,
        "config_hash": config.config_hash(),
        "n_nodes": manifest["n_nodes"],
        "n_edges": manifest["n_edges"],
        "raw_jsonl_bytes": raw_bytes,
        "store_bytes": sum(f["bytes"] for f in manifest["files"].values()),
        "write_seconds": round(write_s, 4),
        "round_trip_equal": equal,
        "repeats": repeats,
        **{f"{k}_seconds": _pcts(v) for k, v in timings.items()},
    }
