"""Sharded, resumable gold-patch runs over the instance specifications.

Implements ``docs/RQ3_PILOT.md`` ("Can resolved rate be measured on the cluster?") and D106:
every instance is evaluated with its gold patch twice (independent builds, same caches), one
JSON line per (instance, run) under the run directory, and a restart skips what is finished.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import threading
import time
from collections.abc import Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ril.evaluation.executor.envbuild import EnvBuilder
from ril.evaluation.executor.runner import EXECUTOR_VERSION, ExecConfig, ExecResult, evaluate
from ril.evaluation.executor.spec import InstanceSpec
from ril.util.log import get_logger

log = get_logger("executor.jobs")

RESULT_FILE = "results.jsonl"
META_FILE = "meta.json"
STOP_FILE = "STOPPED_DISK_FULL"
MIN_FREE_GB = 4.0
EXIT_DISK_FULL = 75
NAMED_FAILURE_CAP = 40


def shard_of(specs: Sequence[InstanceSpec], index: int, count: int) -> list[InstanceSpec]:
    """Contiguous slice ``index`` of ``count``; the list is sorted by environment, so a shard's
    instances mostly share packages."""
    if not 0 <= index < count:
        raise ValueError(f"shard {index} of {count}")
    n = len(specs)
    lo, hi = n * index // count, n * (index + 1) // count
    return list(specs[lo:hi])


def result_record(
    spec: InstanceSpec,
    run_index: int,
    res: ExecResult,
    cfg_hash: str,
    node: str,
    policy: str = "latest",
) -> dict[str, Any]:
    """The small JSON row kept per (instance, run); failing named tests are listed, capped."""
    bad = sorted(t for t, s in res.statuses.items() if s not in ("PASSED", "XFAIL"))
    return {
        "instance_id": spec.instance_id,
        "repo": spec.repo,
        "version": spec.version,
        "run": run_index,
        "config_hash": cfg_hash,
        "env_policy": policy,
        "node": node,
        "built": res.built,
        "failure_stage": res.failure_stage,
        "failure_detail": res.failure_detail[-400:],
        "patch_applied": res.patch_applied,
        "tests_ran": res.tests_ran,
        "timed_out": res.timed_out,
        "f2p": [res.f2p_passed, res.f2p_total],
        "p2p": [res.p2p_passed, res.p2p_total],
        "resolved": res.resolved,
        "outcome_digest": res.outcome_digest(),
        "not_passing": bad[:NAMED_FAILURE_CAP],
        "n_not_passing": len(bad),
        "seconds": res.seconds,
        "peak_rss_mb": res.peak_rss_mb,
        "departures": res.departures,
        "skipped_commands": res.skipped_commands,
    }


def read_done(path: Path) -> set[tuple[str, int]]:
    done: set[tuple[str, int]] = set()
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                done.add((row["instance_id"], int(row["run"])))
    return done


def hardware_meta() -> dict[str, Any]:
    mem_gb = 0.0
    try:
        with open("/proc/meminfo") as f:
            mem_gb = round(int(f.readline().split()[1]) / 1024 / 1024, 1)
    except (OSError, ValueError):
        pass
    cpu = ""
    try:
        with open("/proc/cpuinfo") as f:
            cpu = next((x.split(":", 1)[1].strip() for x in f if x.startswith("model name")), "")
    except OSError:
        pass
    return {
        "node": platform.node(),
        "platform": platform.platform(),
        "cpu": cpu,
        "cpu_count": os.cpu_count(),
        "mem_gb": mem_gb,
    }


def _tool_version(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


@dataclass
class ShardStats:
    done: int = 0
    skipped: int = 0
    stopped_disk: bool = False


def run_shard(
    specs: Iterable[InstanceSpec],
    gold: Mapping[str, str],
    run_dir: Path,
    config: ExecConfig,
    *,
    runs: int = 2,
    workers: int = 1,
    commit: str = "",
    builder: EnvBuilder | None = None,
) -> ShardStats:
    """Evaluate each spec's gold patch ``runs`` times; append one row per run; resumable."""
    run_dir.mkdir(parents=True, exist_ok=True)
    config.work_root.mkdir(parents=True, exist_ok=True)
    result_path = run_dir / RESULT_FILE
    done = read_done(result_path)
    cfg_hash = config.config_hash()
    hw = hardware_meta()
    (run_dir / META_FILE).write_text(
        json.dumps(
            {
                "executor": EXECUTOR_VERSION,
                "config_hash": cfg_hash,
                "env_policy": config.env_policy,
                "commit": commit,
                "uv": _tool_version(["uv", "--version"]),
                "git": _tool_version(["git", "--version"]),
                "hardware": hw,
                "runs": runs,
                "workers": workers,
                "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
            indent=1,
            sort_keys=True,
        )
        + "\n"
    )
    lock = threading.Lock()
    stats = ShardStats()
    stop = threading.Event()
    todo = [s for s in specs if any((s.instance_id, r) not in done for r in range(1, runs + 1))]
    stats.skipped = sum(1 for s in specs if s not in todo)

    def one(spec: InstanceSpec) -> None:
        for run_index in range(1, runs + 1):
            if stop.is_set():
                return
            if (spec.instance_id, run_index) in done:
                continue
            free = shutil.disk_usage(config.work_root).free / 1e9
            if free < MIN_FREE_GB:
                stop.set()
                (run_dir / STOP_FILE).write_text(f"{hw['node']} free {free:.1f} GB\n")
                stats.stopped_disk = True
                return
            res = evaluate(spec, gold[spec.instance_id], config, builder=builder)
            row = result_record(spec, run_index, res, cfg_hash, str(hw["node"]), config.env_policy)
            if res.failure_detail:
                fail_dir = run_dir / "fail_logs"
                fail_dir.mkdir(exist_ok=True)
                (fail_dir / f"{spec.instance_id}_run{run_index}.log").write_text(res.failure_detail)
            with lock:
                with result_path.open("a") as out:
                    out.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
                stats.done += 1
            log.info(
                "%s run %d built=%s stage=%s resolved=%s %.0fs",
                spec.instance_id,
                run_index,
                res.built,
                res.failure_stage or "-",
                res.resolved,
                res.seconds.get("total", 0.0),
            )

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, todo))
    return stats
