"""Tables of the graph-role measurement S1: paired comparisons and the reachability table.

Exploratory. Reads the per-instance files of ``ril.evaluation.s1_graph_role``. Every row gives the
mean over queries with a query-level and a repository-clustered bootstrap interval (decision D17;
``ril.analysis.e3_tables.Boot``), for the value and for the paired difference against a stated
reference. The reachability table gives shares as ratios of sums over L3 gold units (gold units
outside the first-stage top 100), repositories resampled whole; the denominators are printed.

Values are percentages; differences percentage points.
"""

from __future__ import annotations

import glob
import os
from typing import Any

import numpy as np

from ril.analysis.e3_tables import DRAWS, Boot, EvalTable
from ril.analysis.x2_tables import PRIMARY, unit_rows
from ril.evaluation.e3_eval import read_eval
from ril.evaluation.e3_prepare import READINGS
from ril.evaluation.s1_graph_role import REACH_FAMILIES, VARIANT_FAMILIES

Record = dict[str, Any]
Arr = np.ndarray[Any, Any]
VARIANT_LABEL = {"b": "graph as stored (core)", "e": "non-contain only", "f": "contain only"}


def comparison_rows(tab: EvalTable, group: str, weight: float, seed: int) -> list[Record]:
    """Rows of the six candidate sources, each against the sources it is to be told apart from."""
    w = f"w{weight}"
    rows: list[Record] = []

    def add(cols: list[tuple[str, str, str | None]], against: str) -> None:
        for r in unit_rows(tab, group, cols, seed):
            r["against"] = against
            r["weight"] = weight
            rows.append(r)

    base = [("a_none", "a_none", None), ("a_rrf", "a_rrf", "a_none")]
    for v in VARIANT_FAMILIES:
        base += [
            (f"graph|{v}", f"graph|{v}|{w}", "a_none"),
            (f"sfscore|{v}", f"sfscore|{v}|{w}", "a_none"),
            (f"sfrand|{v}", f"sfrand|{v}|{w}", "a_none"),
        ]
    add(base, "a_none")
    for v in VARIANT_FAMILIES:
        for other in ("sfscore", "sfrand"):
            add(
                [
                    (f"{other}|{v}", f"{other}|{v}|{w}", None),
                    (f"graph|{v}", f"graph|{v}|{w}", f"{other}|{v}"),
                ],
                other,
            )
        add(
            [
                (f"sfrand|{v}", f"sfrand|{v}|{w}", None),
                (f"sfscore|{v}", f"sfscore|{v}|{w}", f"sfrand|{v}"),
            ],
            "sfrand",
        )
    # graph variants against each other and against the stored graph
    add(
        [
            (f"graph|{v}", f"graph|{v}|{w}", None if v == "b" else "graph|b")
            for v in ("b", "e", "f")
        ],
        "graph|b",
    )
    return rows


def size_rows(tab: EvalTable, group: str) -> list[Record]:
    """Mean expansion size and mean gold hits per candidate source, per level (primary reading)."""
    out: list[Record] = []
    col = 1 + READINGS.index(PRIMARY)
    for level in ("L2", "L3"):
        sel = tab.mask(role=group) & np.asarray([r["level"] == level for r in tab.rows])
        for i, k in enumerate(tab.aux_keys):
            vals = tab.aux[sel][:, i, :]
            out.append(
                {
                    "group": group,
                    "level": level,
                    "name": k,
                    "queries": int(sel.sum()),
                    "mean_size": round(float(vals[:, 0].mean()), 2) if len(vals) else "",
                    "mean_gold_hits": round(float(vals[:, col].mean()), 3) if len(vals) else "",
                }
            )
    return out


def load_reach(path: str, group: str) -> tuple[list[str], list[str], Arr, dict[str, Arr]]:
    """Reach matrices of the L3 queries of ``group``: keys, repositories, per-reading views."""
    keys: list[str] = []
    repos: list[str] = []
    blocks: list[Arr] = []
    for name in sorted(glob.glob(os.path.join(path, "*.npz"))):
        info, arrays = read_eval(name)
        if info["role"] != group or "reach_L3" not in arrays:
            continue
        keys = [str(x) for x in arrays["reach_keys"]]
        repos.append(info["repo_id"])
        blocks.append(arrays["reach_L3"])
    if not blocks:
        return keys, repos, np.zeros((0, 0, 4)), {}
    per_reading = len(keys)
    stack = np.stack(blocks)  # (queries, readings * rows, 4)
    by = {r: stack[:, i * per_reading : (i + 1) * per_reading, :] for i, r in enumerate(READINGS)}
    return keys, repos, stack, by


def reach_rows(path: str, group: str, seed: int, draws: int = DRAWS) -> list[Record]:
    """Reachability shares with denominators, per source set, family and hop."""
    keys, repos, _, by = load_reach(path, group)
    if not repos:
        return []
    boot = Boot(repos, seed, draws)
    out: list[Record] = []
    for reading in (PRIMARY, "units_all"):
        m = by[reading]  # (queries, rows, 4)
        den = m[:, 0, 0]
        n_q = int((den > 0).sum())
        for j, key in enumerate(keys):
            top, fam, hop = key.split("|")
            cells = {
                "same_file": m[:, j, 1] if fam != "samefile" else m[:, j, 2],
                "reach": m[:, j, 2],
                "reach_not_same_file": m[:, j, 3],
            }
            row: Record = {
                "group": group,
                "reading": reading,
                "sources": top,
                "family": fam,
                "hops": int(hop),
                "queries": int(m.shape[0]),
                "queries_with_gold_outside_top100": n_q,
                "repos": len(set(repos)),
                "gold_outside_top100": int(den.sum()),
            }
            for name, num in cells.items():
                if fam == "samefile" and name != "same_file":
                    continue
                if fam != "samefile" and name == "same_file":
                    continue
                d = np.stack([num, den], axis=1)
                pt = float(num.sum() / den.sum()) if den.sum() else float("nan")
                bs = boot.cluster @ d
                with np.errstate(invalid="ignore", divide="ignore"):
                    ratio = bs[:, 0] / bs[:, 1]
                lo, hi = np.nanquantile(ratio, [0.025, 0.975]) if len(ratio) else (np.nan, np.nan)
                row[f"{name}_count"] = int(num.sum())
                row[f"{name}_pct"] = round(100 * pt, 2)
                row[f"{name}_c_lo"] = round(100 * float(lo), 2)
                row[f"{name}_c_hi"] = round(100 * float(hi), 2)
            out.append(row)
    return out


__all__ = ["REACH_FAMILIES", "comparison_rows", "load_reach", "reach_rows", "size_rows"]
