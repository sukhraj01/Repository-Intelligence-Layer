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
from ril.assembly.config import DEFAULT_MAX_UNIT_TOKENS

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


def _cap_of(r: Record) -> int:
    """Unit cap of a row; rows of the first E-ASSEMBLY run carry none and used the default."""
    return int(r.get("max_unit_tokens", DEFAULT_MAX_UNIT_TOKENS))


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
        by_stage: dict[str, dict[str, dict[tuple[int, int], Record]]] = {}
        for r in sel:
            by_stage.setdefault(r["first_stage"], {}).setdefault(r["instance"], {})[
                (_cap_of(r), int(r["budget"]))
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
            for cap, budget in sorted({k for q in queries for k in by_stage[stage][q]}):
                d = np.asarray([_values(by_stage[stage][q][(cap, budget)]) for q in queries])
                mean, qlo, qhi = boot.summarize(d, "micro")
                _, clo, chi = boot.summarize(d, "cluster")
                row: Record = {
                    "group": GROUPS.get(role, role),
                    "level": level,
                    "reading": reading,
                    "first_stage": stage,
                    "scope": scope,
                    "budget": budget,
                    "max_unit_tokens": cap,
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


def _repo_of(by_budget: dict[tuple[int, int], Record]) -> str:
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


# --------------------------------------------------------------------------- E-ASSEMBLY-CAP

PRIMARY_READING = "units_all_nomod"
SELECTION_BUDGETS = (8000, 16000)
SELECTION_LEVELS = ("L2", "L3")
SELECTION_STAGES = ("bm25", "rrf")
SELECTION_TOLERANCE = 1.0
"""Points; caps within this of the best value tie and the smaller cap wins (decision D103)."""


def _matched_queries(
    rows: list[Record], role: str, level: str, reading: str
) -> tuple[list[str], dict[str, dict[str, dict[tuple[int, int], Record]]]]:
    """Instances (sorted) with gold under the reading and rows for both first stages, and rows."""
    sel = [
        r
        for r in rows
        if (r["role"], r["level"], r["reading"]) == (role, level, reading)
        and r["n_gold_units"] > 0
        and r["n_gold_files"] > 0
    ]
    by_stage: dict[str, dict[str, dict[tuple[int, int], Record]]] = {}
    for r in sel:
        by_stage.setdefault(r["first_stage"], {}).setdefault(r["instance"], {})[
            (_cap_of(r), int(r["budget"]))
        ] = r
    if not all(s in by_stage for s in SELECTION_STAGES):
        return [], by_stage
    return sorted(set.intersection(*(set(by_stage[s]) for s in SELECTION_STAGES))), by_stage


def select_cap(values: dict[int, float], tolerance: float = SELECTION_TOLERANCE) -> int:
    """The rule of decision D103: the highest value; among caps within ``tolerance`` points of it,
    the smallest cap."""
    best = max(values.values())
    return min(c for c, v in values.items() if best - v <= tolerance)


def cap_selection_rows(rows: list[Record], role: str = "dev") -> list[Record]:
    """Per cap, the selection metric of decision D103 (intact share, mean over the eight cells
    {L2, L3} x B {8,000, 16,000} x {BM25, RRF}, each the mean over the dev queries that have both
    first stages), the gold-file share beside it, and the cells. The ``selected`` flag marks the
    cap the rule picks. Points, unrounded in the means and rounded to 2 places on output."""
    cells: dict[int, list[tuple[str, int, str, float, float, int]]] = {}
    for level in SELECTION_LEVELS:
        queries, by_stage = _matched_queries(rows, role, level, PRIMARY_READING)
        for stage in SELECTION_STAGES:
            for cap, budget in sorted({k for q in queries for k in by_stage[stage][q]}):
                if budget not in SELECTION_BUDGETS:
                    continue
                v = np.asarray([_values(by_stage[stage][q][(cap, budget)]) for q in queries])
                cells.setdefault(cap, []).append(
                    (
                        level,
                        budget,
                        stage,
                        float(v[:, 2].mean()),
                        float(v[:, 0].mean()),
                        len(queries),
                    )
                )
    needed = len(SELECTION_LEVELS) * len(SELECTION_BUDGETS) * len(SELECTION_STAGES)
    for cap, c in cells.items():
        if len(c) != needed:
            raise ValueError(f"cap {cap}: {len(c)} cells, expected {needed}")
    metric = {cap: float(np.mean([c[3] for c in cl])) for cap, cl in cells.items()}
    files = {cap: float(np.mean([c[4] for c in cl])) for cap, cl in cells.items()}
    chosen = select_cap(metric) if metric else None
    out: list[Record] = []
    for cap in sorted(cells):
        out.append(
            {
                "max_unit_tokens": cap,
                "intact_share_selection_metric": round(metric[cap], 2),
                "file_share_beside": round(files[cap], 2),
                "cells": len(cells[cap]),
                "selected": cap == chosen,
            }
        )
        for level, budget, stage, intact, fshare, nq in cells[cap]:
            out.append(
                {
                    "max_unit_tokens": cap,
                    "cell": f"{level} B{budget} {stage}",
                    "intact_share_selection_metric": round(intact, 2),
                    "file_share_beside": round(fshare, 2),
                    "cells": nq,
                    "selected": "",
                }
            )
    return out


def paired_rows(rows: list[Record], role: str = "dev", seed: int = 0) -> list[Record]:
    """RRF minus BM25 on the queries that have both, per cap, level and budget, for the share of
    gold files in the context and the share of gold units intact (primary reading): mean
    difference in points with the query-level and the repository-clustered 95% interval, and
    whether each excludes 0. Intervals only; no multiplicity claim is made."""
    out: list[Record] = []
    for level in SELECTION_LEVELS:
        queries, by_stage = _matched_queries(rows, role, level, PRIMARY_READING)
        if not queries:
            continue
        repos = [_repo_of(by_stage["bm25"][q]) for q in queries]
        boot = Boot(repos, seed)
        keys = sorted({k for q in queries for k in by_stage["bm25"][q]})
        for cap, budget in keys:
            a = np.asarray([_values(by_stage["rrf"][q][(cap, budget)]) for q in queries])
            b = np.asarray([_values(by_stage["bm25"][q][(cap, budget)]) for q in queries])
            diff = a[:, [0, 2]] - b[:, [0, 2]]
            mean, qlo, qhi = boot.summarize(diff, "micro")
            _, clo, chi = boot.summarize(diff, "cluster")
            for j, name in enumerate(("file_share", "unit_intact_share")):
                out.append(
                    {
                        "group": GROUPS.get(role, role),
                        "level": level,
                        "max_unit_tokens": cap,
                        "budget": budget,
                        "metric": name,
                        "queries": len(queries),
                        "repositories": len(set(repos)),
                        "rrf_minus_bm25": round(float(mean[j]), 2),
                        "ci_q": f"[{qlo[j]:.1f}, {qhi[j]:.1f}]",
                        "ci_cl": f"[{clo[j]:.1f}, {chi[j]:.1f}]",
                        "excludes_0_q": bool(qlo[j] > 0 or qhi[j] < 0),
                        "excludes_0_cl": bool(clo[j] > 0 or chi[j] < 0),
                    }
                )
    return out
