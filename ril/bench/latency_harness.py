"""Per-commit latency and throughput harness.

Implements specs/latency_harness.md and docs/07_latency_and_profiling.md: a fixed, versioned query
set; per-stage p50/p95/p99 computed from raw samples (never a mean); warmup calls discarded and
recorded; cold and warm rows kept apart; batch size 1; GPU sections bracketed by
``torch.cuda.synchronize()`` when a GPU exists; hardware spec captured automatically; append-only
CSV output; a regression check that exits non-zero past a configured threshold.

A real component becomes a timed stage with one line::

    REGISTRY.register("bm25", my_bm25_search, reset=my_bm25.clear_cache)

Stage names come from a closed taxonomy (``LATENCY_STAGES`` / ``THROUGHPUT_STAGES``) so a rename
cannot silently change the sourcing-versus-ranking split.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime

try:
    from datetime import UTC
except ImportError:  # Python 3.10 (cluster nodes)
    from datetime import timezone

    UTC = timezone.utc  # noqa: UP017
from pathlib import Path
from typing import Any

import yaml

from ril.config.paths import configs_dir, repo_root, results_dir
from ril.util.log import get_logger
from ril.util.seed import set_seed

log = get_logger("bench")

# Query path: the stages of one interactive retrieval call (docs/07; spec "Stages").
LATENCY_STAGES: tuple[str, ...] = (
    "query_encode",
    "bm25",
    "dense_search",
    "graph_expansion",
    "graph_expand_1hop",
    "graph_expand_2hop",
    "rrf_fusion",
    "same_file_expansion",
    "recency_prior",
    "cross_encoder_rerank",
    "assemble",
    "end_to_end",
)
# Offline stages, reported as units per second in the throughput log.
THROUGHPUT_STAGES: tuple[str, ...] = ("parse", "graph_build", "dense_encode", "train_step")

CACHE_STATES: tuple[str, ...] = ("cold", "warm")

ENV_COLUMNS: tuple[str, ...] = (
    "timestamp_utc",
    "commit",
    "dirty",
    "branch",
    "host",
    "cpu_model",
    "cpu_cores",
    "ram_gb",
    "gpu_name",
    "gpu_driver",
    "cuda_version",
    "python",
    "torch",
    "config_hash",
)
LATENCY_COLUMNS: tuple[str, ...] = (
    *ENV_COLUMNS,
    "query_set_id",
    "n_queries",
    "warmup_n",
    "cache_state",
    "stage",
    "p50_ms",
    "p95_ms",
    "p99_ms",
    "n",
)
THROUGHPUT_COLUMNS: tuple[str, ...] = (
    *ENV_COLUMNS,
    "workload_id",
    "stage",
    "units",
    "seconds",
    "units_per_s",
)
# Rows are comparable only when all of these agree (spec "Regression check").
COMPARABLE_KEYS: tuple[str, ...] = (
    "cpu_model",
    "cpu_cores",
    "ram_gb",
    "gpu_name",
    "query_set_id",
    "cache_state",
    "stage",
)

Row = dict[str, str | int | float]


# --------------------------------------------------------------------------- configuration


@dataclass(frozen=True)
class RegressionThreshold:
    """When a stage counts as regressed. Provisional (Q33): the engineer sets the values."""

    rel_threshold: float
    abs_floor_ms: float


@dataclass(frozen=True)
class BenchConfig:
    """Harness configuration, loaded from ``configs/bench/latency.yaml``."""

    seed: int
    query_set: str
    warmup_n: int
    repeats: int
    throughput_repeats: int
    regression: RegressionThreshold

    def config_hash(self) -> str:
        """Stable SHA-256 of the canonical JSON form."""
        canonical = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def default_config_path() -> Path:
    """Return ``configs/bench/latency.yaml``."""
    return configs_dir() / "bench" / "latency.yaml"


def load_bench_config(path: Path) -> BenchConfig:
    """Load and validate a ``BenchConfig``; unknown keys and bad values are rejected."""
    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected a mapping at the top level")
    regression = RegressionThreshold(**raw.pop("regression"))
    config = BenchConfig(regression=regression, **raw)
    if config.warmup_n < 0 or config.repeats < 1 or config.throughput_repeats < 1:
        raise ValueError("warmup_n must be >= 0; repeats and throughput_repeats must be >= 1")
    if regression.rel_threshold < 0 or regression.abs_floor_ms < 0:
        raise ValueError("regression thresholds must be non-negative")
    return config


def load_query_set(query_set_id: str) -> list[str]:
    """Return the queries of a versioned set (``configs/bench/query_sets/<id>.txt``).

    A set is immutable by convention: changing its content means a new id, because rows are not
    comparable across ids.
    """
    path = configs_dir() / "bench" / "query_sets" / f"{query_set_id}.txt"
    lines = path.read_text(encoding="utf-8").splitlines()
    queries = [line.strip() for line in lines]
    if not queries or any(not q for q in queries):
        raise ValueError(f"{path}: query set must be non-empty with no blank lines")
    return queries


# --------------------------------------------------------------------------- statistics


def percentile(samples: Sequence[float], p: float) -> float:
    """Nearest-rank percentile of raw samples (an observed value, never an interpolated mean)."""
    if not samples:
        raise ValueError("percentile of an empty sample")
    if not 0 < p <= 100:
        raise ValueError("p must be in (0, 100]")
    ordered = sorted(samples)
    rank = math.ceil(p / 100 * len(ordered))
    return ordered[rank - 1]


# --------------------------------------------------------------------------- stage registry


@dataclass(frozen=True)
class LatencyStage:
    """A query-path stage: ``fn(query)`` is timed with batch size 1.

    ``reset`` drops the stage's own caches; it is called before every call of a cold run. (The OS
    page cache cannot be dropped portably; a cold row means stage-level caches were cleared.)
    """

    name: str
    fn: Callable[[str], object]
    reset: Callable[[], None] | None = None


@dataclass(frozen=True)
class ThroughputStage:
    """An offline stage: ``fn()`` does one full workload and returns the number of units done."""

    name: str
    fn: Callable[[], int]


class StageRegistry:
    """Holds the registered stages; names are checked against the closed taxonomy."""

    def __init__(self) -> None:
        self.latency: dict[str, LatencyStage] = {}
        self.throughput: dict[str, ThroughputStage] = {}

    def register(
        self, name: str, fn: Callable[[str], object], reset: Callable[[], None] | None = None
    ) -> None:
        """Register a query-path stage under a taxonomy name."""
        if name not in LATENCY_STAGES:
            raise ValueError(f"unknown latency stage {name!r}; known: {LATENCY_STAGES}")
        self.latency[name] = LatencyStage(name, fn, reset)

    def register_throughput(self, name: str, fn: Callable[[], int]) -> None:
        """Register an offline stage under a taxonomy name."""
        if name not in THROUGHPUT_STAGES:
            raise ValueError(f"unknown throughput stage {name!r}; known: {THROUGHPUT_STAGES}")
        self.throughput[name] = ThroughputStage(name, fn)


REGISTRY = StageRegistry()


# --------------------------------------------------------------------------- timing


def _cuda_module() -> Any | None:
    """Return ``torch.cuda`` if torch is installed and a GPU is usable, else ``None``."""
    try:
        torch = importlib.import_module("torch")
    except ImportError:
        return None
    cuda = torch.cuda
    return cuda if cuda.is_available() else None


def cuda_synchronize() -> None:
    """``torch.cuda.synchronize()`` when a GPU exists; a no-op on a CPU-only box."""
    cuda = _cuda_module()
    if cuda is not None:
        cuda.synchronize()


def time_call_ms(fn: Callable[[str], object], query: str) -> float:
    """Time one call in milliseconds, with a device synchronize before and after."""
    cuda_synchronize()
    start = time.perf_counter_ns()
    fn(query)
    cuda_synchronize()
    return (time.perf_counter_ns() - start) / 1e6


def measure_warm(
    stage: LatencyStage, queries: Sequence[str], warmup_n: int, repeats: int
) -> list[float]:
    """Warm samples: ``repeats`` passes over the set; the first ``warmup_n`` calls are discarded."""
    calls = [q for _ in range(repeats) for q in queries]
    if warmup_n >= len(calls):
        raise ValueError("warmup_n discards every call; lower it or add repeats")
    for query in calls[:warmup_n]:
        stage.fn(query)
    cuda_synchronize()
    return [time_call_ms(stage.fn, query) for query in calls[warmup_n:]]


def measure_cold(stage: LatencyStage, queries: Sequence[str]) -> list[float]:
    """Cold samples: one pass over the set, stage caches reset before every call, no warmup."""
    samples: list[float] = []
    for query in queries:
        if stage.reset is not None:
            stage.reset()
        samples.append(time_call_ms(stage.fn, query))
    return samples


# --------------------------------------------------------------------------- environment


def _run(cmd: Sequence[str], cwd: Path | None = None) -> str:
    """Run a command and return stripped stdout, or ``""`` when it cannot run or fails."""
    try:
        done = subprocess.run(
            list(cmd), capture_output=True, text=True, timeout=10, check=False, cwd=cwd
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


def _cpu_model() -> str:
    if sys.platform == "darwin":
        return _run(["sysctl", "-n", "machdep.cpu.brand_string"]) or platform.processor()
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        for line in cpuinfo.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.lower().startswith("model name"):
                return line.split(":", 1)[1].strip()
    return platform.processor() or platform.machine()


def _ram_gb() -> float:
    if sys.platform == "darwin":
        total = _run(["sysctl", "-n", "hw.memsize"])
        return round(int(total) / 2**30, 1) if total.isdigit() else 0.0
    try:
        return round(os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / 2**30, 1)
    except (ValueError, OSError, AttributeError):
        return 0.0


def _gpu_info() -> tuple[str, str, str]:
    """Return (name, driver, cuda version); ``none`` / empty strings on a CPU-only box."""
    cuda = _cuda_module()
    if cuda is None:
        return "none", "", ""
    torch = importlib.import_module("torch")
    driver = _run(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"])
    return (
        str(cuda.get_device_name(0)),
        driver.splitlines()[0] if driver else "",
        str(torch.version.cuda or ""),
    )


def _torch_version() -> str:
    try:
        return str(importlib.import_module("torch").__version__)
    except ImportError:
        return "none"


def capture_environment(config_hash: str, root: Path | None = None) -> Row:
    """Capture the hardware spec, git state and software versions for one run.

    ``dirty`` is 1 when tracked files differ from HEAD (the row then does not describe a clean
    commit); ``commit`` is the HEAD the working tree is based on.
    """
    root = root or repo_root()
    gpu_name, gpu_driver, cuda_version = _gpu_info()
    status = _run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=root)
    commit = _run(["git", "rev-parse", "--short", "HEAD"], cwd=root)
    # a copy of the package without .git (the cluster) names its commit in the environment
    return {
        "timestamp_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": commit or os.environ.get("RIL_COMMIT", "none"),
        "dirty": 1 if status else int(os.environ.get("RIL_DIRTY", "0")),
        "branch": _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root)
        or os.environ.get("RIL_BRANCH", "none"),
        "host": platform.node(),
        "cpu_model": _cpu_model(),
        "cpu_cores": os.cpu_count() or 0,
        "ram_gb": _ram_gb(),
        "gpu_name": gpu_name,
        "gpu_driver": gpu_driver,
        "cuda_version": cuda_version,
        "python": platform.python_version(),
        "torch": _torch_version(),
        "config_hash": config_hash,
    }


# --------------------------------------------------------------------------- running


def run_latency(
    registry: StageRegistry, config: BenchConfig, queries: Sequence[str], env: Row
) -> list[Row]:
    """Measure every registered query-path stage, cold and warm; return CSV rows."""
    rows: list[Row] = []
    for name in LATENCY_STAGES:
        stage = registry.latency.get(name)
        if stage is None:
            continue
        for state in CACHE_STATES:
            if state == "warm":
                samples = measure_warm(stage, queries, config.warmup_n, config.repeats)
                warmup = config.warmup_n
            else:
                samples = measure_cold(stage, queries)
                warmup = 0
            rows.append(
                {
                    **env,
                    "query_set_id": config.query_set,
                    "n_queries": len(queries),
                    "warmup_n": warmup,
                    "cache_state": state,
                    "stage": name,
                    "p50_ms": round(percentile(samples, 50), 4),
                    "p95_ms": round(percentile(samples, 95), 4),
                    "p99_ms": round(percentile(samples, 99), 4),
                    "n": len(samples),
                }
            )
    return rows


def run_throughput(registry: StageRegistry, config: BenchConfig, env: Row) -> list[Row]:
    """Time each offline stage over its whole workload; return CSV rows (units per second)."""
    rows: list[Row] = []
    for name in THROUGHPUT_STAGES:
        stage = registry.throughput.get(name)
        if stage is None:
            continue
        units = 0
        start = time.perf_counter_ns()
        for _ in range(config.throughput_repeats):
            units += stage.fn()
        seconds = (time.perf_counter_ns() - start) / 1e9
        rows.append(
            {
                **env,
                "workload_id": config.query_set,
                "stage": name,
                "units": units,
                "seconds": round(seconds, 6),
                "units_per_s": round(units / seconds, 2) if seconds > 0 else 0.0,
            }
        )
    return rows


# --------------------------------------------------------------------------- CSV (append-only)


def append_rows(path: Path, columns: Sequence[str], rows: Sequence[Row]) -> None:
    """Append rows to a CSV; existing content is never rewritten.

    A new file gets the header. An existing file must already carry exactly this header,
    otherwise the append is refused rather than the file being migrated.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and path.stat().st_size > 0
    if exists:
        with path.open("r", encoding="utf-8", newline="") as handle:
            header = next(csv.reader(handle), [])
        if header != list(columns):
            raise ValueError(f"{path}: header differs from the contract; refusing to append")
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), lineterminator="\n")
        if not exists:
            writer.writeheader()
        for row in rows:
            writer.writerow({c: row[c] for c in columns})


def read_rows(path: Path) -> list[dict[str, str]]:
    """Read a CSV log as string dicts; a missing file is an empty history."""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


# --------------------------------------------------------------------------- regression


@dataclass(frozen=True)
class Regression:
    """One stage metric that got slower than the comparable previous row allows."""

    stage: str
    cache_state: str
    metric: str
    previous_ms: float
    current_ms: float
    previous_commit: str


def find_regressions(
    new_rows: Sequence[Row], history: Sequence[dict[str, str]], threshold: RegressionThreshold
) -> tuple[list[Regression], int]:
    """Compare each new row with the most recent comparable row in ``history``.

    Comparable = same hardware spec, query_set_id, cache_state and stage. p50 and p95 are checked
    (p99 at this sample size is the maximum and too noisy to gate on; it is still logged). A metric
    regresses when it grows by more than ``rel_threshold`` and by more than ``abs_floor_ms``.
    Returns the regressions and the number of rows that had a comparable predecessor; with no
    predecessor a row passes.
    """
    found: list[Regression] = []
    compared = 0
    for row in new_rows:
        key = {k: str(row[k]) for k in COMPARABLE_KEYS}
        previous = next(
            (h for h in reversed(history) if all(h.get(k) == v for k, v in key.items())), None
        )
        if previous is None:
            continue
        compared += 1
        for metric in ("p50_ms", "p95_ms"):
            old, new = float(previous[metric]), float(row[metric])
            if new > old * (1 + threshold.rel_threshold) and new - old > threshold.abs_floor_ms:
                found.append(
                    Regression(
                        str(row["stage"]),
                        str(row["cache_state"]),
                        metric,
                        old,
                        new,
                        previous.get("commit", ""),
                    )
                )
    return found, compared


# --------------------------------------------------------------------------- CLI


def default_registry(seed: int) -> StageRegistry:
    """Registry the command line measures: synthetic stub stages until real ones register."""
    from ril.bench.stub_stages import build_stub_registry  # local: stubs depend on this module

    return build_stub_registry(seed)


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point: ``run`` appends rows; ``check`` also fails on a regression."""
    parser = argparse.ArgumentParser(prog="bench", description=__doc__.split("\n")[0])
    parser.add_argument("command", choices=("run", "check"))
    parser.add_argument("--seed", type=int, default=None, help="overrides the config seed")
    parser.add_argument("--config", type=Path, default=default_config_path())
    parser.add_argument("--log-dir", type=Path, default=results_dir() / "latency")
    parser.add_argument("--no-append", action="store_true", help="measure and compare only")
    parser.add_argument(
        "--append-on-fail",
        action="store_true",
        help="check: also append rows when a regression is found (default: do not)",
    )
    args = parser.parse_args(argv)

    config = load_bench_config(args.config)
    seed = config.seed if args.seed is None else args.seed
    set_seed(seed)
    queries = load_query_set(config.query_set)
    env = capture_environment(config.config_hash())
    registry = default_registry(seed)

    latency_rows = run_latency(registry, config, queries, env)
    throughput_rows = run_throughput(registry, config, env)
    latency_path = args.log_dir / "latency_log.csv"
    throughput_path = args.log_dir / "throughput_log.csv"

    for row in latency_rows:
        log.info(
            "%-22s %-4s p50=%8.3f p95=%8.3f p99=%8.3f ms (n=%d)",
            row["stage"],
            row["cache_state"],
            row["p50_ms"],
            row["p95_ms"],
            row["p99_ms"],
            row["n"],
        )
    for row in throughput_rows:
        log.info("%-22s %s units/s (%s units)", row["stage"], row["units_per_s"], row["units"])

    failed = False
    if args.command == "check":
        regressions, compared = find_regressions(
            latency_rows, read_rows(latency_path), config.regression
        )
        if compared == 0:
            log.info("regression check: no comparable previous row; passing")
        for r in regressions:
            log.error(
                "REGRESSION %s/%s %s: %.3f ms -> %.3f ms (previous commit %s)",
                r.stage,
                r.cache_state,
                r.metric,
                r.previous_ms,
                r.current_ms,
                r.previous_commit,
            )
        failed = bool(regressions)
        if not failed and compared:
            log.info("regression check: %d comparable rows, no regression", compared)

    if not args.no_append and (not failed or args.append_on_fail):
        append_rows(latency_path, LATENCY_COLUMNS, latency_rows)
        append_rows(throughput_path, THROUGHPUT_COLUMNS, throughput_rows)
        log.info(
            "appended %d latency and %d throughput rows", len(latency_rows), len(throughput_rows)
        )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
