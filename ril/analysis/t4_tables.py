"""Tables of the arms pilot, stage 1 (E-PILOT-ARMS; exploratory, outside the RQ tables).

Reuses the conventions of ``ril.analysis.t2_tables`` (percentage points, paired queries, 2,000
bootstrap draws shared by the columns of a table, seeds averaged for the cell effect and shown
beside it). The runs evaluated no baseline column, so the untrained encoder's per-query values are
read from the learning curve's step-0 rows (same dev subset, same encoder, same code) and attached
as the base column. Two additions:

* ``noise_share``: the NOISE control's gain over the base as a share of RAW's gain over the base,
  with a query-level bootstrap interval on the ratio of the means (a ratio of two noisy gains is
  unstable when RAW's gain is small; the interval is reported, not trusted below that).
* ``stage2_trigger``: the rule of the brief, fixed before any result: (i) a non-RAW, non-NOISE cell
  whose paired difference to RAW has an interval excluding 0 at either level; (ii) the RAW seed gap
  above 1.0 point at either level. The interval used is the repository-clustered one where the level
  has at least three repositories (L2: three) and the query-level one otherwise (L3: two).

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import csv
import json
import os
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from ril.analysis import t2_tables as tt
from ril.analysis.x2_tables import write_csv

Record = dict[str, Any]
T4_TABLES_VERSION = "t4-tables/v1"
NON_ARMS = ("t4a_raw", "t4a_noise")


def attach_base(runs: Sequence[tt.Run], step0_rows: str) -> None:
    """Add the untrained encoder's columns (``dense:``/``rrf:`` + ``tt.BASE``) to every run."""
    base: dict[tuple[str, str, str, str], float] = {}
    repo_of: dict[tuple[str, str], str] = {}
    with open(step0_rows, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            kind = row["name"].split(":", 1)[0]
            if kind not in ("dense", "rrf"):
                continue
            q = (row["instance"], row["level"])
            repo_of[q] = row["repo"]
            for k, v in row.items():
                if ":" in k and v not in ("", None):
                    base[(q[0], q[1], f"{kind}:{tt.BASE}", k)] = float(v)
    for r in runs:
        for key, val in base.items():
            r.values.setdefault(key, val)
        for q, repo in repo_of.items():
            r.repo_of.setdefault(q, repo)


def noise_share(
    raw: Sequence[tt.Run], noise: Sequence[tt.Run], *, level: str, reading: str, seed: int
) -> Record:
    """NOISE gain over base / RAW gain over base on the common queries (dense column)."""
    key = f"{reading}:{tt.LEVEL_METRIC[level]}"
    qs = tt.common_queries([*raw, *noise], ["dense"], level, key)
    base_name = tt.column(raw[0], "base_dense")
    qs = [q for q in qs if (q[0], q[1], base_name, key) in raw[0].values]
    b = tt._vector(raw[0], qs, "base_dense", key)
    r = np.mean([tt._vector(x, qs, "dense", key) for x in raw], axis=0) - b
    n = np.mean([tt._vector(x, qs, "dense", key) for x in noise], axis=0) - b
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(2000):
        i = rng.integers(0, len(qs), len(qs))
        den = r[i].mean()
        draws.append(n[i].mean() / den if abs(den) > 1e-12 else np.nan)
    lo, hi = np.nanpercentile(draws, [2.5, 97.5])
    return {
        "level": level,
        "reading": reading,
        "queries": len(qs),
        "raw_gain": round(100 * float(r.mean()), 2),
        "noise_gain": round(100 * float(n.mean()), 2),
        "noise_share": round(float(n.mean() / r.mean()), 3),
        "q_lo": round(float(lo), 3),
        "q_hi": round(float(hi), 3),
    }


def stage2_trigger(effects: Sequence[Record], spread: Sequence[Record]) -> Record:
    """Evaluate the stage-2 trigger on the primary reading, dense column."""
    reading = tt.READINGS[0]
    hits: list[Record] = []
    for row in effects:
        if (
            row.get("kind") != "dense"
            or row.get("reading") != reading
            or row.get("part") != "mean"
            or row.get("condition") in NON_ARMS
            or not row.get("ref")
        ):
            continue
        clustered = int(row["repos"]) >= 3
        lo = row["d_c_lo"] if clustered else row["d_q_lo"]
        hi = row["d_c_hi"] if clustered else row["d_q_hi"]
        hits.append(
            {
                "condition": row["condition"],
                "level": row["level"],
                "d": row["d"],
                "lo": lo,
                "hi": hi,
                "interval": "repository-clustered" if clustered else "query-level",
                "excludes_zero": bool(lo > 0 or hi < 0),
            }
        )
    gaps = [
        {"level": s["level"], "range": s["range"], "per_seed": s["per_seed"]}
        for s in spread
        if s["condition"] == "t4a_raw" and s["kind"] == "dense" and s["reading"] == reading
    ]
    return {
        "reading": reading,
        "cells": hits,
        "raw_seed_gap": gaps,
        "i_any_excludes_zero": any(h["excludes_zero"] for h in hits),
        "ii_raw_gap_above_1": any(g["range"] is not None and g["range"] > 1.0 for g in gaps),
    }


def arms_tables(
    results_root: str,
    conditions: Sequence[str],
    step0_rows: str,
    out_dir: str,
    seed: int = 0,
) -> Record:
    """All stage-1 tables; returns the log record (including the trigger and the NOISE share)."""
    conds = {c: tt.load_condition(results_root, c) for c in conditions}
    for runs in conds.values():
        attach_base(runs, step0_rows)
    labels = {"pilot": "t4a", "evaluation": "evaluation", "label": "E-PILOT-ARMS stage 1"}
    effects: list[Record] = []
    spread: list[Record] = []
    for kind in ("dense", "rrf"):
        for level in ("L2", "L3"):
            for reading in tt.READINGS:
                effects += tt.contrast_rows(
                    conds,
                    "t4a_raw",
                    kind=kind,
                    level=level,
                    reading=reading,
                    seed=seed,
                    labels=labels,
                )
                spread += tt.seed_spread(conds, kind=kind, level=level, reading=reading)
    costs = tt.cost_rows(conds)
    shares = [
        noise_share(conds["t4a_raw"], conds["t4a_noise"], level=lv, reading=rd, seed=seed)
        for lv in ("L2", "L3")
        for rd in tt.READINGS
    ]
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.join(out_dir, "t4a")
    write_csv(f"{stem}_effects.csv", effects)
    write_csv(f"{stem}_seeds.csv", spread)
    write_csv(f"{stem}_runs.csv", costs)
    write_csv(f"{stem}_noise_share.csv", shares)
    return {
        "version": T4_TABLES_VERSION,
        "runs": {c: [r.seed for r in rs] for c, rs in conds.items()},
        "noise_share": shares,
        "trigger": stage2_trigger(effects, spread),
        "tables": [f"{stem}_{n}.csv" for n in ("effects", "seeds", "runs", "noise_share")],
    }


def dump(record: Mapping[str, Any], path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=1, sort_keys=True, default=str)
        handle.write("\n")
