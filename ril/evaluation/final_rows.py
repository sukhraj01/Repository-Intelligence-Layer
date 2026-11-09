"""Rows of the RQ2 final analysis from the scoring results (the converter between the two halves).

Implements ``docs/RQ2_LAUNCH_PLAN.md`` section 10.6 (the converter item of the checklist) and the
row format of ``ril.analysis.rq2_final``: one row per run, cell, seed, evaluation set, level,
repository and query (``run_id, cell, seed, eval_set, level, repo, query_id, n_positives, ndcg10,
recall100``, fractions), plus one diagnostics row per run (``RUN_COLUMNS``).

Two sources, one row format:

* ``final_rows``: the eight repositories and the executable 377, scored once from the retained
  models (``ril.evaluation.final_sets``). It refuses to run without the id of the finished dev
  analysis and calls the shared guard (:func:`ril.evaluation.sealed.require_dev_analysis`) before
  it opens a single result file; the index reader then checks that every result names that id.
* ``dev_rows``: the dev evaluation each training job wrote next to its record (the same
  ``query_rows.csv`` and ``results.json`` as the pilots; never sealed).

The value read is the dense column under the primary gold reading ``units_all_nomod`` (D18), as
``ril.analysis.rq2_final_pilot`` reads the pilots. A query with no gold under the reading has an
empty cell and no row (undefined, not zero). ``n_positives`` is not recorded per query by the
scoring and stays empty. No torch.
"""

from __future__ import annotations

import csv
import json
import os
import re
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from ril.evaluation import final_sets, sealed

READING = "units_all_nomod"
ROW_FIELDS: tuple[str, ...] = (
    "run_id",
    "cell",
    "seed",
    "eval_set",
    "level",
    "repo",
    "query_id",
    "n_positives",
    "ndcg10",
    "recall100",
)
RUN_FIELDS: tuple[str, ...] = (
    "run_id",
    "cell",
    "seed",
    "config_hash",
    "optimizer_updates",
    "examples_seen",
    "distinct_directories_seen",
    "pool_examples",
)
_RUN_ID = re.compile(r"^(?P<cell>[a-z0-9_]+)_u(?P<updates>\d+)_s(?P<seed>\d+)$")
Record = dict[str, Any]


def parse_run_id(run_id: str) -> tuple[str, int, int]:
    """``(cell, updates, seed)`` of ``mined_raw_u100_s100``."""
    m = _RUN_ID.match(run_id)
    if m is None:
        raise ValueError(f"not a final run id: {run_id!r}")
    return m["cell"], int(m["updates"]), int(m["seed"])


def rows_from_query_csv(path: str, *, run_id: str, eval_set: str) -> list[Record]:
    """The analysis rows of one ``query_rows.csv`` (dense column, reading ``units_all_nomod``)."""
    cell, _, seed = parse_run_id(run_id)
    ndcg, rec = f"{READING}:ndcg10", f"{READING}:recall100"
    out: list[Record] = []
    seen: set[tuple[str, str]] = set()
    with open(path, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if not str(row["name"]).startswith("dense:"):
                continue
            if row[ndcg] == "" or row[rec] == "":
                continue  # no gold under the reading
            key = (row["instance"], row["level"])
            if key in seen:
                raise ValueError(f"{path}: two dense rows for {key}")
            seen.add(key)
            out.append(
                {
                    "run_id": run_id,
                    "cell": cell,
                    "seed": seed,
                    "eval_set": eval_set,
                    "level": row["level"],
                    "repo": row["repo"],
                    "query_id": row["instance"],
                    "n_positives": None,
                    "ndcg10": float(row[ndcg]),
                    "recall100": float(row[rec]),
                }
            )
    return out


def final_rows(
    index_path: str, dev_analysis_id: str | None, *, docs_root: Path | None = None
) -> list[Record]:
    """Rows of every scored (model, part) of the final sets, only after the dev analysis.

    Refuses without the dev-analysis id before reading anything, then reads the index only for
    that id. A result directory without ``query_rows.csv`` is an error, never skipped.
    """
    entry = sealed.require_dev_analysis(dev_analysis_id, docs_root)
    index = final_sets.read_final_sets(index_path, entry)
    base = os.path.dirname(index_path)
    out: list[Record] = []
    for item in index:
        result_dir = str(item["result_dir"])
        if not os.path.isabs(result_dir):
            result_dir = os.path.join(base, result_dir)
        path = os.path.join(result_dir, "query_rows.csv")
        if not os.path.isfile(path):
            raise FileNotFoundError(f"{item['run_id']} {item['set']}/{item['part']}: no {path}")
        out += rows_from_query_csv(path, run_id=str(item["run_id"]), eval_set=str(item["set"]))
    return out


def run_record(result_dir: str) -> Record:
    """The diagnostics row of one training run from its ``results.json``."""
    with open(os.path.join(result_dir, "results.json"), encoding="utf-8") as handle:
        rec = json.load(handle)
    tr = rec["training"]
    budget = tr["budget"]
    cell = str(tr["exp_id"]).removeprefix("rq2f_")
    run_id = f"{cell}_u{int(budget['optimizer_updates'])}_s{int(tr['seed'])}"
    return {
        "run_id": run_id,
        "cell": cell,
        "seed": int(tr["seed"]),
        "config_hash": str(tr["config_hash"]),
        "optimizer_updates": int(budget["optimizer_updates"]),
        "examples_seen": int(budget["examples_seen"]),
        "distinct_directories_seen": int(budget["unique_examples_seen"]),
        "pool_examples": int(budget["pool_examples"]),
    }


def dev_rows(result_dirs: Iterable[str]) -> tuple[list[Record], list[Record]]:
    """``(rows, runs)`` of the dev evaluation of finished training runs (``eval_set`` ``dev``)."""
    rows: list[Record] = []
    runs: list[Record] = []
    for d in sorted(result_dirs):
        run = run_record(d)
        runs.append(run)
        rows += rows_from_query_csv(
            os.path.join(d, "query_rows.csv"), run_id=str(run["run_id"]), eval_set="dev"
        )
    return rows, runs


def write_csv(path: str, fields: Sequence[str], rows: Iterable[Record]) -> int:
    """Write rows in the analysis module's column order; empty for ``None``; returns the count."""
    n = 0
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=list(fields))
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r[k] is None else r[k]) for k in fields})
            n += 1
    return n
