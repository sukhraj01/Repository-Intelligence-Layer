"""Per-commit graph update cost: incremental update against a full rebuild, with an equality check.

For one repository checkout and its last ``n`` first-parent commits that touch Python files (oldest
first), the first commit is built in full; then for every later commit the checkout moves to it,
the previous state is updated incrementally (``ril.parsing.incremental``) and the same commit is
built from scratch with ``ril.parsing.build.build_repository``. The two must agree byte for byte
(graph digest and unit bytes); a disagreement is recorded, never skipped. Wall times are per
commit, single process, warm file cache; percentiles are nearest-rank (an observed value).

The checkout is moved with ``git checkout --detach`` and returned to its original commit at the end.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import hashlib
import subprocess
import time
from dataclasses import asdict
from typing import Any

from ril.bench.latency_harness import percentile
from ril.parsing.build import BuildConfig, build_repository, git_head
from ril.parsing.code_unit import units_to_jsonl
from ril.parsing.incremental import INCREMENTAL_VERSION, full_state, state_digest, update_state


def _git(root: str, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", root, *args], capture_output=True, text=True, check=True, timeout=600
    )
    return done.stdout


def python_commits(root: str, n: int, ref: str = "HEAD") -> list[str]:
    """The last ``n`` first-parent commits up to ``ref`` that touch a ``.py`` file, oldest first."""
    out = _git(root, "log", "--first-parent", "--format=%H", f"-n{n}", ref, "--", "*.py")
    return list(reversed(out.split()))


def _pcts(values: list[float]) -> dict[str, float]:
    return {f"p{p}": round(percentile(values, p), 4) for p in (50, 95, 99)}


def measure_repository(root: str, repo_id: str, n_commits: int) -> dict[str, Any]:
    """Run the comparison over ``n_commits`` commits (the first is the base build)."""
    start_commit = git_head(root)
    commits = python_commits(root, n_commits)
    config = BuildConfig(repo_id=repo_id, with_history=True)
    rows: list[dict[str, Any]] = []
    try:
        _git(root, "checkout", "-q", "--detach", commits[0])
        t0 = time.perf_counter()
        state = full_state(root, config)
        base_seconds = time.perf_counter() - t0
        for commit in commits[1:]:
            _git(root, "checkout", "-q", "--detach", commit)
            t0 = time.perf_counter()
            state, stats = update_state(state)
            inc = time.perf_counter() - t0
            t0 = time.perf_counter()
            ref = build_repository(root, config, exploratory=False)
            full = time.perf_counter() - t0
            ref_digest = (
                ref.graph.digest(),
                hashlib.sha256(units_to_jsonl(ref.parsed.units)).hexdigest(),
            )
            rows.append(
                {
                    "commit": commit,
                    "equal": state_digest(state) == ref_digest,
                    "incremental_seconds": round(inc, 4),
                    "full_seconds": round(full, 4),
                    "full_stage_seconds": {k: round(v, 4) for k, v in ref.seconds.items()},
                    "n_units": len(ref.parsed.units),
                    "n_edges": len(ref.graph.edges),
                    **{k: v for k, v in asdict(stats).items() if k != "commit"},
                }
            )
    finally:
        _git(root, "checkout", "-q", "--detach", start_commit)
    inc_s = [r["incremental_seconds"] for r in rows]
    full_s = [r["full_seconds"] for r in rows]
    speedups = [f / i for f, i in zip(full_s, inc_s, strict=True) if i > 0]
    reresolved = [r["files_reresolved"] / max(1, r["files_total"]) for r in rows]
    return {
        "repo_id": repo_id,
        "updater": INCREMENTAL_VERSION,
        "config_hash": config.config_hash(),
        "n_updates": len(rows),
        "equal_updates": sum(1 for r in rows if r["equal"]),
        "base_commit": commits[0],
        "base_build_seconds": round(base_seconds, 4),
        "files_total_last": rows[-1]["files_total"] if rows else 0,
        "n_units_last": rows[-1]["n_units"] if rows else 0,
        "incremental_seconds": _pcts(inc_s) if rows else {},
        "full_seconds": _pcts(full_s) if rows else {},
        "speedup_p50": round(percentile(speedups, 50), 2) if speedups else None,
        "speedup_min": round(min(speedups), 2) if speedups else None,
        "reresolved_share": _pcts(reresolved) if rows else {},
        "rows": rows,
    }
