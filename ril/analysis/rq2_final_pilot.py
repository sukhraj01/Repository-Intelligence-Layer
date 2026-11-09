"""Stored pilot rows as input of ``ril.analysis.rq2_final`` (exploratory, never a headline).

Reads the per-query rows kept under ``results/rq2/<condition>/`` (the dense column of the primary
gold reading ``units_all_nomod``, nDCG@10 and Recall@100) and the budget record of each run, and
returns the rows and run diagnostics the final analysis takes. Used only to check that the module
reproduces the pilot summaries (``tests/unit/test_rq2_final_pilot.py``); every output of the module
built from these rows carries ``source_kind = "pilot"``.

Implements docs/experiments/B.md "E-RQ2-ANALYSIS".
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from ril.analysis import t2_tables as tt

READING = "units_all_nomod"
EVAL_SET = "dev"
CURVE_SEEDS = {"70f4195c": 0, "6c520027": 1}
"""Seed of each learning-curve run by its config hash prefix (E-PILOT-CURVE header)."""


def pilot_inputs(
    results_root: str, cells: Mapping[str, str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """``(rows, runs)`` for ``cells`` = ``{final-style cell id: stored condition id}``."""
    rows: list[dict[str, Any]] = []
    runs: list[dict[str, Any]] = []
    for cell, cond in cells.items():
        for run in tt.load_condition(results_root, cond):
            run_id = os.path.basename(run.result_dir)
            col = tt.column(run, "dense")
            budget = run.record["training"]["budget"]
            runs.append(
                {
                    "run_id": run_id,
                    "cell": cell,
                    "seed": run.seed,
                    "config_hash": run.config_hash,
                    "optimizer_updates": budget["optimizer_updates"],
                    "examples_seen": budget["examples_seen"],
                    "distinct_directories_seen": budget["unique_examples_seen"],
                    "pool_examples": budget["pool_examples"],
                }
            )
            queries = {(i, lv) for (i, lv, n, _k) in run.values if n == col}
            for inst, level in sorted(queries):
                got = {
                    m: run.values.get((inst, level, col, f"{READING}:{m}"))
                    for m in ("ndcg10", "recall100")
                }
                if any(v is None for v in got.values()):
                    continue  # no gold under the reading: undefined, not zero
                rows.append(
                    {
                        "run_id": run_id,
                        "cell": cell,
                        "seed": run.seed,
                        "eval_set": EVAL_SET,
                        "level": level,
                        "repo": run.repo_of[(inst, level)],
                        "query_id": inst,
                        "n_positives": None,
                        **got,
                    }
                )
    return rows, runs


def curve_inputs(
    results_root: str, steps: tuple[int, ...] = (0, 100)
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Rows of the learning-curve pilot (E-PILOT-CURVE): cell ``curve_<step>``, both seeds.

    A query enters a step only when it has the dense metrics under the reading in that step; the
    cells are then intersected by the analysis (``intersect=True``), as the pilot's own table does.
    """
    from ril.analysis import t3_tables

    rows: list[dict[str, Any]] = []
    base = os.path.join(results_root, "rq2", "t3_curve_raw")
    for name in sorted(os.listdir(base)):
        d = os.path.join(base, name)
        if not os.path.exists(os.path.join(d, "results.json")):
            continue  # the cancelled first attempt holds step 0 only
        seed = CURVE_SEEDS[name.rsplit("_", 1)[-1]]
        for step, path in t3_tables.step_dirs(d).items():
            if step not in steps:
                continue
            q = t3_tables.read_step(path)
            for (inst, level, kind), vals in sorted(q.items()):
                if kind != "dense":
                    continue
                repo = next(iter(q[(inst, level, "_repo")])).removeprefix("repo_")
                got = [vals.get(f"{READING}:{m}") for m in ("ndcg10", "recall100")]
                if any(v is None for v in got):
                    continue
                rows.append(
                    {
                        "run_id": f"{name}_{step}",
                        "cell": f"curve_{step}",
                        "seed": seed,
                        "eval_set": EVAL_SET,
                        "level": level,
                        "repo": repo,
                        "query_id": inst,
                        "n_positives": None,
                        "ndcg10": got[0],
                        "recall100": got[1],
                    }
                )
    return rows, []
