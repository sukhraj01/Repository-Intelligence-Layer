"""Tables of E-ASSEMBLY: gold in the assembled context by budget and first stage.

Implements ``docs/experiments/B.md`` E-ASSEMBLY. Reads the per-instance JSON files written by
``ril.assembly.measure`` and writes one row per (group, level, reading, first stage, budget) with
the mean over queries and two 95% intervals from the same 2,000 bootstrap draws (seed 0): query
level (``q``) and repository-clustered (``cl``), as in the other tables (decision D17). Shares are
in points. A query is one (instance, level); a query whose gold set under the reading is empty is
left out of that reading's rows (``queries`` is stated). BM25 and the fused first stage are
compared on the queries that have both (``matched``); ``bm25_all`` is BM25 on every query.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import glob
import json
import os
from typing import Any

import numpy as np

from ril.analysis.e3_tables import Boot

Record = dict[str, Any]
GROUPS = {"dev": "dev", "test": "verified_six"}
METRICS = ("file_share", "unit_share", "unit_intact_share", "no_gold_file", "tokens", "n_included")
POINTS = ("file_share", "unit_share", "unit_intact_share", "no_gold_file")


def load_rows(out_dir: str) -> tuple[list[Record], list[Record]]:
    """All rows of an output directory and one coverage record per instance."""
    rows: list[Record] = []
    coverage: list[Record] = []
    for path in sorted(glob.glob(os.path.join(out_dir, "instances", "*.json"))):
        with open(path, encoding="utf-8") as handle:
            doc = json.load(handle)
        rows += doc["rows"]
        coverage.append(
            {
                "instance": doc["instance"],
                "units": doc["units"],
                "has_dense": doc["has_dense"],
                "rows": len(doc["rows"]),
            }
        )
    return rows, coverage


def _values(r: Record) -> list[float]:
    n_units, n_files = float(r["n_gold_units"]), float(r["n_gold_files"])
    return [
        100.0 * r["files_in"] / n_files,
        100.0 * r["units_in"] / n_units,
        100.0 * r["units_intact"] / n_units,
        100.0 * (1.0 if r["files_in"] == 0 else 0.0),
        float(r["tokens"]),
        float(r["n_included"]),
    ]


def summary_rows(rows: list[Record], seed: int = 0) -> list[Record]:
    """The table rows (see the module docstring); deterministic for a given seed."""
    out: list[Record] = []
    keys = sorted({(r["role"], r["level"], r["reading"]) for r in rows})
    for role, level, reading in keys:
        sel = [r for r in rows if (r["role"], r["level"], r["reading"]) == (role, level, reading)]
        sel = [r for r in sel if r["n_gold_units"] > 0 and r["n_gold_files"] > 0]
        by_stage: dict[str, dict[str, dict[int, Record]]] = {}
        for r in sel:
            by_stage.setdefault(r["first_stage"], {}).setdefault(r["instance"], {})[
                int(r["budget"])
            ] = r
        stages = sorted(by_stage)
        if not stages:
            continue
        matched = set.intersection(*(set(by_stage[s]) for s in stages))
        views: list[tuple[str, str, list[str]]] = [(s, "matched", sorted(matched)) for s in stages]
        for s in stages:
            allq = sorted(by_stage[s])
            if len(allq) != len(matched):
                views.append((s, "all", allq))
        for stage, scope, queries in views:
            if not queries:
                continue
            repos = [_repo_of(by_stage[stage][q]) for q in queries]
            boot = Boot(repos, seed)
            for budget in sorted({b for q in queries for b in by_stage[stage][q]}):
                d = np.asarray([_values(by_stage[stage][q][budget]) for q in queries])
                mean, qlo, qhi = boot.summarize(d, "micro")
                _, clo, chi = boot.summarize(d, "cluster")
                row: Record = {
                    "group": GROUPS.get(role, role),
                    "level": level,
                    "reading": reading,
                    "first_stage": stage,
                    "scope": scope,
                    "budget": budget,
                    "queries": len(queries),
                    "repositories": len(set(repos)),
                }
                for j, m in enumerate(METRICS):
                    digits = 1 if m in POINTS else 0
                    row[m] = round(float(mean[j]), 2 if m in POINTS else 1)
                    row[f"{m}_q"] = f"[{qlo[j]:.{digits}f}, {qhi[j]:.{digits}f}]"
                    row[f"{m}_cl"] = f"[{clo[j]:.{digits}f}, {chi[j]:.{digits}f}]"
                out.append(row)
    return out


def _repo_of(by_budget: dict[int, Record]) -> str:
    return str(next(iter(by_budget.values()))["repo_id"])


def coverage_rows(coverage: list[Record], rows: list[Record]) -> list[Record]:
    """Instances and queries with and without stored dense scores, per role."""
    role_of = {r["instance"]: r["role"] for r in rows}
    out: list[Record] = []
    for role in sorted(set(role_of.values())):
        inst = [c for c in coverage if role_of.get(c["instance"]) == role]
        out.append(
            {
                "group": GROUPS.get(role, role),
                "instances_with_rows": len(inst),
                "with_dense": sum(1 for c in inst if c["has_dense"]),
                "without_dense": sum(1 for c in inst if not c["has_dense"]),
            }
        )
    return out
