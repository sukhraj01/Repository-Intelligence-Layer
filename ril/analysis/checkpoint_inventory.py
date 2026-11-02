"""Inventory of training checkpoints against the evaluation outputs kept in the repository.

Joins three things, none of which loads a weight: the run directories under ``results/rq2/``
(``results.json`` records the checkpoint root the job used and the config hash), the job scripts
under ``scripts/ada/`` (whether the node-local work directory is removed at exit), and a listing
of the shared storage taken with read-only commands (``results/logs/checkpoint_listing_*.json``).
A checkpoint is *retained* only if the listing contains it; a node-local root is *gone* when the
job script removes it at exit. Paths are written with neutral tokens (no login names, no home
paths).

Implements docs/experiments/B.md "E-STORED-ANALYSIS" (checkpoint inventory).
"""

from __future__ import annotations

import csv
import glob
import json
import os
import re
from typing import Any

Record = dict[str, Any]
INVENTORY_VERSION = "checkpoint-inventory/v1"
FIELDS = (
    "run_id",
    "config_hash8",
    "kind",
    "seed",
    "step_or_updates",
    "checkpoint_root_pattern",
    "storage",
    "retained",
    "retained_bytes",
    "evidence",
    "eval_outputs_in_repo",
)
CURVE_STEPS = ("step_00000", "step_00100", "step_00300", "step_01000", "step_02000")
CURVE_SCRIPT = "scripts/ada/t3_curve.sbatch"


def neutral(path: str) -> str:
    """A path with job ids and home prefixes replaced by tokens."""
    p = re.sub(r"^/home[0-9]*/[^/]+/", "<home>/", path)
    p = re.sub(r"^/home/[^/]+/", "<home>/", p)
    p = re.sub(r"^\[?<?[A-Za-z_]*>?\]?", lambda m: m.group(0), p)
    return re.sub(r"(ril_[a-z0-9]+_)[0-9]+", r"\1<job>", p)


def script_removes_work_dir(script: str) -> bool:
    """Whether the job script removes the node-local work directory (``rm -rf "$CK"``)."""
    with open(script, encoding="utf-8") as fh:
        return 'rm -rf "$CK"' in fh.read()


def _script_for(exp_id: str) -> str:
    stem = exp_id.split("_")[0]
    if exp_id.startswith("t5"):
        return "scripts/ada/t5_runs.sbatch"
    if exp_id.startswith("t4"):
        return "scripts/ada/t4_runs.sbatch"
    if exp_id.startswith("n1"):
        return "scripts/ada/n1_runs.sbatch"
    if exp_id.startswith("n8"):
        return "scripts/ada/n8_runs.sbatch"
    if exp_id.startswith("t2"):
        return "scripts/ada/t2_runs.sbatch"
    if exp_id.startswith("t1_validate_cre"):
        return "scripts/ada/t1_validate.sbatch"
    if exp_id.startswith("t3"):
        return CURVE_SCRIPT
    return f"scripts/ada/{stem}_runs.sbatch"


def build(results_root: str, listing_path: str, repo_root: str = ".") -> list[Record]:
    """One row per run (and per curve step, and per retained checkpoint directory)."""
    with open(listing_path, encoding="utf-8") as fh:
        listing = json.load(fh)
    retained: dict[str, list[Record]] = {r["config_hash8"]: [] for r in listing["retained"]}
    for r in listing["retained"]:
        retained[r["config_hash8"]].append(r)
    rows: list[Record] = []
    for rpath in sorted(glob.glob(os.path.join(results_root, "*", "*", "results.json"))):
        d = os.path.dirname(rpath)
        exp_id = os.path.basename(os.path.dirname(d))
        h8 = os.path.basename(d).split("_")[-1]
        with open(rpath, encoding="utf-8") as fh:
            res = json.load(fh)
        if "curve" in res:
            for step in CURVE_STEPS:
                if not os.path.isdir(os.path.join(d, step)):
                    continue
                rows.append(
                    _row(
                        exp_id,
                        h8,
                        "curve step",
                        "",
                        step,
                        "/tmp/ril_t3_seed<seed>/ckpt",
                        repo_root,
                        CURVE_SCRIPT,
                        [],
                        os.path.exists(os.path.join(d, step, "query_rows.csv")),
                    )
                )
            continue
        t = res.get("training")
        if not t:
            continue
        rows.append(
            _row(
                exp_id,
                h8,
                "training run",
                str(t.get("seed", "")),
                str(t.get("updates_this_process", "")),
                str(t.get("checkpoint_root", "")),
                repo_root,
                _script_for(exp_id),
                retained.get(h8, []),
                os.path.exists(os.path.join(d, "query_rows.csv")) or "evaluation" in res,
            )
        )
    # curve directories that hold step rows only (no results.json): the untrained full-set job
    for sd in sorted(glob.glob(os.path.join(results_root, "t3_curve_raw", "*", "step_00000"))):
        run = os.path.dirname(sd)
        if os.path.exists(os.path.join(run, "results.json")):
            continue
        rows.append(
            _row(
                "t3_curve_raw",
                os.path.basename(run).split("_")[-1],
                "curve step",
                "",
                "step_00000",
                "(untrained encoder; no checkpoint written)",
                repo_root,
                CURVE_SCRIPT,
                [],
                os.path.exists(os.path.join(sd, "query_rows.csv")),
            )
        )
    return rows


def _row(
    run_id: str,
    h8: str,
    kind: str,
    seed: str,
    step: str,
    root: str,
    repo_root: str,
    script: str,
    kept: list[Record],
    eval_in_repo: bool,
) -> Record:
    pattern = neutral(root)
    if kept:
        step = "final;" + ";".join(str(k["step"]) for k in kept if k["step"] != "final")
    local = root.startswith(("/tmp", "/ssd_scratch")) or "node-local" in root
    removed = (
        script_removes_work_dir(os.path.join(repo_root, script))
        if os.path.exists(os.path.join(repo_root, script))
        else False
    )
    if kept:
        storage, ev, size = (
            "shared storage (account A)",
            "listed on the shared storage",
            sum(int(k["bytes"]) for k in kept),
        )
    elif step == "step_00000" and "untrained" in root:
        storage, ev, size = "none written", "untrained encoder", 0
    elif local and removed:
        storage, ev, size = "node-local, gone", f"{script} removes the work directory at exit", 0
    elif local:
        storage, ev, size = (
            "node-local, gone (presumed)",
            f"{script} does not remove it; node-local storage is not shared",
            0,
        )
    else:
        storage, ev, size = (
            "shared path recorded, not found in the listing",
            "absent from the listing",
            0,
        )
    return {
        "run_id": run_id,
        "config_hash8": h8,
        "kind": kind,
        "seed": seed,
        "step_or_updates": step,
        "checkpoint_root_pattern": pattern,
        "storage": storage,
        "retained": "yes" if kept else "no",
        "retained_bytes": size,
        "evidence": ev,
        "eval_outputs_in_repo": "yes" if eval_in_repo else "no",
    }


def write(rows: list[Record], path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def summarise(rows: list[Record], listing_path: str) -> Record:
    """Counts by storage class, retained bytes, and the disk figures of the listing."""
    with open(listing_path, encoding="utf-8") as fh:
        listing = json.load(fh)
    by: dict[str, int] = {}
    for r in rows:
        by[r["storage"]] = by.get(r["storage"], 0) + 1
    return {
        "version": INVENTORY_VERSION,
        "rows": len(rows),
        "by_storage": by,
        "retained_runs": sorted({r["run_id"] for r in rows if r["retained"] == "yes"}),
        "retained_bytes": sum(int(r["retained_bytes"]) for r in rows),
        "listing_retained_dirs": len(listing["retained"]),
        "listing_retained_bytes": sum(int(k["bytes"]) for k in listing["retained"]),
        "disk": listing["disk"],
        "all_rows_have_eval_outputs": sum(r["eval_outputs_in_repo"] == "yes" for r in rows),
    }
