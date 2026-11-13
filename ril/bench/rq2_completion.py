"""Completion check of the RQ2 final training runs (read-only, no torch).

Implements ``docs/RQ2_LAUNCH_PLAN.md`` section 11 and the post-launch step: for every
planned run the result directory exists, the stored configuration hash equals the registered one,
the training record shows the planned update count and ``finished``, the leakage record of the
launch commit passed, and (for the retained mined family, D142) the retained model folder exists
with a manifest naming the same configuration hash. A missing or short run marks that cell
incomplete; it never stops the others.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

Record = dict[str, Any]


@dataclass(frozen=True)
class RunCheck:
    """One planned run and what was found for it."""

    run_id: str
    cell: str
    seed: int
    account: str
    optimizer_updates: int | None
    planned_updates: int
    train_loop_gpu_hours: float | None
    result_dir: str | None
    retained: str  # "present", "absent" or "not retained by design"
    problems: tuple[str, ...] = field(default_factory=tuple)

    @property
    def complete(self) -> bool:
        return not self.problems


def _load(path: Path) -> Record | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _find_result(root: Path, cell: str, hash8: str) -> list[Path]:
    base = root / f"rq2f_{cell}"
    if not base.is_dir():
        return []
    return sorted(
        p for p in base.iterdir() if p.name.endswith(f"_{hash8}") and (p / "results.json").is_file()
    )


def check_run(
    run: Mapping[str, Any],
    *,
    results_root: Path,
    retained_root: Path | None,
    leakage_passed: bool,
) -> RunCheck:
    """Check one registered run (a row of ``resolve_summary.json``) against its stored outputs."""
    run_id = str(run["run_id"])
    registered = str(run["config_hash"])
    planned = int(run["optimizer_updates"])
    problems: list[str] = []
    found = _find_result(results_root, str(run["cell"]), registered[:8])
    result: Record | None = None
    if not found:
        problems.append("no result directory with the registered configuration hash")
    else:
        if len(found) > 1:
            problems.append(f"{len(found)} result directories carry this hash")
        result = _load(found[-1] / "results.json")
    training: Record = (result or {}).get("training", {}) or {}
    updates: int | None = None
    gpu_hours: float | None = None
    if result is not None:
        if training.get("config_hash") != registered:
            problems.append("stored configuration hash differs from the registered one")
        budget = training.get("budget", {}) or {}
        updates = budget.get("optimizer_updates")
        gpu_hours = budget.get("gpu_hours_train_loop")
        if updates != planned:
            problems.append(f"update count {updates} against planned {planned}")
        if training.get("finished") is not True:
            problems.append("training record is not marked finished")
        if training.get("seed") != run["seed"]:
            problems.append("seed in the training record differs from the registered seed")
        if training.get("teacher_equals_base") is True:
            problems.append("quality-signal encoder equals the encoder being trained")
    if not leakage_passed:
        problems.append("leakage record of the launch commit did not pass")
    retained = "not retained by design"
    if run.get("retain_final"):
        retained = "absent"
        folder = training.get("retained", {}).get("folder") if training else None
        manifest = (
            _load(retained_root / folder / "manifest.json") if retained_root and folder else None
        )
        if manifest is None:
            problems.append("retained model folder or manifest is missing")
        elif manifest.get("config_hash") != registered:
            problems.append("retained manifest names another configuration hash")
        else:
            retained = "present"
    return RunCheck(
        run_id,
        str(run["cell"]),
        int(run["seed"]),
        str(run["account"]),
        updates if isinstance(updates, int) else None,
        planned,
        float(gpu_hours) if isinstance(gpu_hours, (int, float)) else None,
        found[-1].name if found else None,
        retained,
        tuple(problems),
    )


def check_all(
    runs: Sequence[Mapping[str, Any]],
    *,
    results_roots: Mapping[str, Path],
    retained_roots: Mapping[str, Path | None],
    leakage: Mapping[str, Mapping[str, Any]],
    excluded_run_ids: frozenset[str] = frozenset(),
) -> list[RunCheck]:
    """Check every planned run on its account; ``excluded_run_ids`` are runs not in this launch."""
    out: list[RunCheck] = []
    for run in runs:
        if str(run["run_id"]) in excluded_run_ids:
            continue
        acct = str(run["account"])
        rec = leakage.get(acct, {})
        ok = rec.get("failed") == 0 and int(rec.get("passed", 0)) > 0
        out.append(
            check_run(
                run,
                results_root=results_roots[acct],
                retained_root=retained_roots.get(acct),
                leakage_passed=bool(ok),
            )
        )
    return out
