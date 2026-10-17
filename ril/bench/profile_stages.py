"""Per-stage profiling: where the time inside a stage goes.

Implements specs/latency_harness.md ("Use cProfile/py-spy for CPU attribution and torch.profiler for
GPU") and docs/07_latency_and_profiling.md. Wall-clock percentiles say how long a stage takes; this
module says which functions inside it take the time, so optimisation is planned where the time goes.
``py-spy`` is an external sampler and is run from the shell against ``scripts/bench.py``.
"""

from __future__ import annotations

import argparse
import cProfile
import importlib
import io
import pstats
import sys
from collections.abc import Sequence
from pathlib import Path

from ril.bench.latency_harness import (
    LatencyStage,
    _cuda_module,
    default_config_path,
    default_registry,
    load_bench_config,
    load_query_set,
)
from ril.util.seed import set_seed


def profile_cpu(stage: LatencyStage, queries: Sequence[str], top: int = 15) -> str:
    """Profile one pass of ``stage`` over ``queries`` with cProfile; return the top functions by
    cumulative time as text."""
    profiler = cProfile.Profile()
    profiler.enable()
    for query in queries:
        stage.fn(query)
    profiler.disable()
    out = io.StringIO()
    pstats.Stats(profiler, stream=out).sort_stats("cumulative").print_stats(top)
    return out.getvalue()


def profile_gpu(stage: LatencyStage, queries: Sequence[str], top: int = 15) -> str | None:
    """Profile with ``torch.profiler`` (CPU and CUDA activities); ``None`` when no GPU exists."""
    if _cuda_module() is None:
        return None
    profiler_mod = importlib.import_module("torch.profiler")
    with profiler_mod.profile(
        activities=[profiler_mod.ProfilerActivity.CPU, profiler_mod.ProfilerActivity.CUDA]
    ) as prof:
        for query in queries:
            stage.fn(query)
    return str(prof.key_averages().table(sort_by="cuda_time_total", row_limit=top))


def main(argv: Sequence[str] | None = None) -> int:
    """Profile one registered stage and write the report to stdout."""
    parser = argparse.ArgumentParser(prog="profile_stages")
    parser.add_argument("--stage", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--config", type=Path, default=default_config_path())
    parser.add_argument("--top", type=int, default=15)
    args = parser.parse_args(argv)

    set_seed(args.seed)
    config = load_bench_config(args.config)
    registry = default_registry(args.seed)
    stage = registry.latency.get(args.stage)
    if stage is None:
        parser.error(f"stage {args.stage!r} is not registered; have {sorted(registry.latency)}")
    queries = load_query_set(config.query_set)
    sys.stdout.write(profile_cpu(stage, queries, args.top))
    gpu = profile_gpu(stage, queries, args.top)
    sys.stdout.write(gpu if gpu is not None else "torch.profiler: no GPU available, skipped\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
