"""Training throughput and device memory per batch shape (stage ``train_step``, throughput log).

Implements the training row of ``specs/latency_harness.md`` (throughput: training samples per
second, a separate log from per-query latency) for the RQ2 training stack. For each batch shape of
a configuration (batch size, hard negatives and positives per example, token cut) it builds the
shared training path exactly as a run does (arm hooks, batch planner, encoder, AdamW), runs
``warmup`` updates, then times ``timed`` updates (synchronised on a GPU) and records examples per
second and peak device memory. A shape that does not fit is recorded as ``oom`` and the next one
is tried; which shape RQ2 holds is ``provisional: ADR-002`` and not chosen here.

The measurement updates a throwaway copy of the model and writes no checkpoint.
Kept compatible with Python 3.10.
"""

from __future__ import annotations

import copy
import gc
import json
import os
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ril.bench.latency_harness import (
    THROUGHPUT_COLUMNS,
    BenchConfig,
    RegressionThreshold,
    StageRegistry,
    append_rows,
    capture_environment,
    run_throughput,
)
from ril.training.encoders import build_encoder
from ril.training.negatives import Mined
from ril.training.pool_reader import PoolExample
from ril.training.supervision import QualitySignal
from ril.training.training import Updater, config_hash, make_planner, prepare_arm

Record = dict[str, Any]


def workload_id(cfg: Mapping[str, Any]) -> str:
    """Throughput workload name of one batch shape (precision, checkpointing when not default)."""
    m, b = cfg["model"], cfg["batch"]
    enc = m.get("encoder", m["kind"])
    extra = ""
    if cfg["optimizer"].get("precision", "fp32") != "fp32":
        extra += f"-{cfg['optimizer']['precision']}"
    if m.get("gradient_checkpointing"):
        extra += "-gc"
    return (
        f"train-{enc}-b{b['batch_size']}-n{b['negatives_per_example']}-p{b['max_positives']}"
        f"-t{m['max_tokens']}{extra}-v1"
    )


def shape_config(
    cfg: Mapping[str, Any],
    batch_size: int,
    negatives: int,
    positives: int,
    max_tokens: int,
    *,
    precision: str | None = None,
    gradient_checkpointing: bool | None = None,
) -> Record:
    """The configuration with one batch shape substituted (everything else unchanged)."""
    out = copy.deepcopy(dict(cfg))
    if precision is not None:
        out["optimizer"] = {**out["optimizer"], "precision": precision}
    if gradient_checkpointing is not None:
        out["model"] = {**out["model"], "gradient_checkpointing": gradient_checkpointing}
    out["batch"] = {
        **out["batch"],
        "batch_size": batch_size,
        "negatives_per_example": negatives,
        "max_positives": positives,
    }
    out["model"] = {**out["model"], "max_tokens": max_tokens}
    return out


def measure_shape(
    cfg: Mapping[str, Any],
    examples: Sequence[PoolExample],
    *,
    device: str,
    warmup: int,
    timed: int,
    signals: Mapping[str, QualitySignal] | None = None,
    mined: Mapping[str, Mined] | None = None,
) -> tuple[Record, list[Record]]:
    """Time ``timed`` updates after ``warmup`` of one shape; returns (summary, throughput rows)."""
    import torch

    cuda = device.startswith("cuda")
    arm, kept, weights, _ = prepare_arm(cfg, examples, signals or {})
    planner = make_planner(cfg, arm, kept, weights, mined)
    batches = list(planner.batches(warmup + timed))
    enc = build_encoder(cfg["model"], device=device, seed=int(cfg["seed"]))
    enc.module.train()
    upd = Updater(enc, cfg, warmup + timed, device)
    state = {"i": 0}

    def step() -> int:
        b = batches[state["i"]]
        state["i"] += 1
        upd.step(b)
        return len(b.queries)

    summary: Record = {"workload_id": workload_id(cfg), "status": "ok"}
    try:
        for _ in range(warmup):
            step()
        if cuda:
            torch.cuda.synchronize()
            torch.cuda.reset_peak_memory_stats()

        def timed_steps() -> int:
            n = sum(step() for _ in range(timed))
            if cuda:
                torch.cuda.synchronize()
            return n

        reg = StageRegistry()
        reg.register_throughput("train_step", timed_steps)
        bc = BenchConfig(
            seed=int(cfg["seed"]),
            query_set=workload_id(cfg),
            warmup_n=warmup,
            repeats=1,
            throughput_repeats=1,
            regression=RegressionThreshold(rel_threshold=0.5, abs_floor_ms=0.5),
        )
        rows = run_throughput(reg, bc, capture_environment(config_hash(cfg)))
        summary.update(
            examples_per_s=rows[0]["units_per_s"],
            seconds_per_update=float(rows[0]["seconds"]) / timed,
            docs_per_update=len(batches[-1].docs),
        )
        if cuda:
            summary["peak_gpu_mem_mb"] = round(torch.cuda.max_memory_allocated() / 2**20, 1)
        return summary, rows
    except torch.cuda.OutOfMemoryError as exc:
        summary["status"] = "oom"
        summary["error"] = str(exc)[:300]
        if cuda:
            summary["peak_gpu_mem_mb"] = round(torch.cuda.max_memory_allocated() / 2**20, 1)
        return summary, []
    finally:
        batches.clear()
        if cuda:
            torch.cuda.empty_cache()


def measure_job(
    config_path: str,
    cache_path: str,
    shapes: Sequence[tuple[int, int, int, int]],
    out_log: str,
    log_dir: str,
    *,
    device: str,
    warmup: int = 3,
    timed: int = 10,
    precision: str | None = None,
    gradient_checkpointing: bool | None = None,
) -> Record:
    """Measure every shape ``(batch, negatives, positives, tokens)``; rows to ``log_dir``."""
    from ril.training.pool_reader import read_cache
    from ril.training.training import hardware_info, load_train_config
    from ril.util.gpu import cuda_gate

    cfg = load_train_config(config_path)
    gate = cuda_gate() if device.startswith("cuda") else None
    examples = read_cache(cache_path)
    out: Record = {
        "config_hash": config_hash(cfg),
        "gate": gate,
        "hardware": hardware_info(device),
        "warmup": warmup,
        "timed": timed,
        "shapes": [],
    }
    for b, n, p, t in shapes:
        t0 = time.perf_counter()
        sc = shape_config(
            cfg, b, n, p, t, precision=precision, gradient_checkpointing=gradient_checkpointing
        )
        summary, rows = measure_shape(sc, examples, device=device, warmup=warmup, timed=timed)
        summary["wall_seconds"] = round(time.perf_counter() - t0, 1)
        gc.collect()
        out["shapes"].append(summary)
        if rows:
            append_rows(Path(log_dir) / "throughput_log.csv", THROUGHPUT_COLUMNS, rows)
        os.makedirs(os.path.dirname(out_log) or ".", exist_ok=True)
        with open(out_log, "w", encoding="utf-8") as handle:
            json.dump(out, handle, indent=1, sort_keys=True, default=str)
    return out
