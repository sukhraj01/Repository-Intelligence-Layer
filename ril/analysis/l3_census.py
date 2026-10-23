"""Census of CORE-Bench positives by kind, repository and file novelty (exploratory, counts only).

Reads the pilot-E1 unit records (one per instance: every positive chunk located in the base-commit
checkout, its path and its kind from ``ril.evaluation.chunk_mapping.positive_kind``) and counts:

* positives by kind: function, method, class, module residual, test unit (decision D9 path rule,
  whatever the structure), non-Python artifact (documentation, configuration, data), and Python
  files the parser could not read;
* the same by repository and by role (dev, test);
* for L3: the share of positives in a file that holds none of the instance's L2 positives (what
  structure beyond the edited files the L3 labels ask for), with the kinds of those positives.

A positive is one qrels chunk (not a unit). Shares carry 95% intervals from a bootstrap over
instances (the positives of one instance are not independent). No text is read or written.
"""

from __future__ import annotations

import glob
import json
import os
from collections import Counter
from typing import Any

import numpy as np

Record = dict[str, Any]
KIND_GROUP = {
    "function": "function",
    "method": "method",
    "class": "class",
    "module_residual": "module_residual",
    "test_unit": "test_unit",
    "non_python_docs": "non_python",
    "non_python_config": "non_python",
    "non_python_data": "non_python",
    "python_not_parsed": "python_not_parsed",
}
GROUPS: tuple[str, ...] = (
    "function",
    "method",
    "class",
    "module_residual",
    "test_unit",
    "non_python",
    "python_not_parsed",
)


def load_records(units_dir: str) -> list[Record]:
    """Every pilot-E1 unit record under ``units_dir`` (sorted by instance)."""
    out: list[Record] = []
    for path in sorted(glob.glob(os.path.join(units_dir, "*.json"))):
        with open(path, encoding="utf-8") as handle:
            out.append(json.load(handle))
    return sorted(out, key=lambda r: r["instance"])


def instance_rows(rec: Record) -> list[Record]:
    """One row per located positive: level, kind group, sub-kind, and file novelty at L3."""
    found = [p for p in rec["positives"] if p["status"] == "found"]
    l2_files = {p["path"] for p in found if p["level"] == "L2"}
    rows: list[Record] = []
    for p in found:
        rows.append(
            {
                "instance": rec["instance"],
                "repo": rec["repo_id"],
                "role": rec["role"],
                "level": p["level"],
                "kind": KIND_GROUP.get(p["kind"], "other"),
                "sub_kind": p["kind"],
                "has_l2": bool(l2_files),
                "new_file": p["level"] == "L3" and bool(l2_files) and p["path"] not in l2_files,
            }
        )
    return rows


def _share_interval(
    num: np.ndarray[Any, Any], den: np.ndarray[Any, Any], seed: int, draws: int = 2000
) -> tuple[float, float, float]:
    """Ratio of sums with a bootstrap over instances (95% percentile interval), in percent."""
    if den.sum() == 0:
        return (float("nan"),) * 3
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(num), size=(draws, len(num)))
    n, d = num[idx].sum(axis=1), den[idx].sum(axis=1)
    ratios = np.where(d > 0, n / np.maximum(d, 1), np.nan)
    lo, hi = np.nanquantile(ratios, [0.025, 0.975])
    return 100 * num.sum() / den.sum(), 100 * float(lo), 100 * float(hi)


def census(records: list[Record], seed: int = 0) -> tuple[list[Record], list[Record]]:
    """(kind table, novelty table): rows per (role or repository, level)."""
    rows = [r for rec in records for r in instance_rows(rec)]
    groups: dict[str, list[Record]] = {}
    for r in rows:
        groups.setdefault(f"role:{r['role']}", []).append(r)
        groups.setdefault(f"repo:{r['repo']}", []).append(r)
        groups.setdefault("all", []).append(r)
    kinds: list[Record] = []
    novelty: list[Record] = []
    for gname in sorted(groups):
        for level in ("L2", "L3"):
            sel = [r for r in groups[gname] if r["level"] == level]
            if not sel:
                continue
            inst = sorted({r["instance"] for r in sel})
            c = Counter(r["kind"] for r in sel)
            sub = Counter(r["sub_kind"] for r in sel)
            row: Record = {
                "group": gname,
                "level": level,
                "instances": len(inst),
                "positives": len(sel),
            }
            for g in GROUPS:
                row[g] = c.get(g, 0)
            for s in ("non_python_docs", "non_python_config", "non_python_data"):
                row[s] = sub.get(s, 0)
            pos = {i: k for k, i in enumerate(inst)}
            npy = np.zeros(len(inst))
            tot = np.zeros(len(inst))
            for r in sel:
                tot[pos[r["instance"]]] += 1
                npy[pos[r["instance"]]] += r["kind"] == "non_python"
            row["non_python_pct"], row["non_python_lo"], row["non_python_hi"] = (
                round(x, 2) for x in _share_interval(npy, tot, seed)
            )
            kinds.append(row)
            if level != "L3":
                continue
            with_l2 = [r for r in sel if r["has_l2"]]
            inst2 = sorted({r["instance"] for r in with_l2})
            pos2 = {i: k for k, i in enumerate(inst2)}
            new = np.zeros(len(inst2))
            tot2 = np.zeros(len(inst2))
            for r in with_l2:
                tot2[pos2[r["instance"]]] += 1
                new[pos2[r["instance"]]] += r["new_file"]
            share, lo, hi = _share_interval(new, tot2, seed)
            nk = Counter(r["kind"] for r in with_l2 if r["new_file"])
            nrow: Record = {
                "group": gname,
                "instances_with_l2": len(inst2),
                "l3_positives_with_l2": len(with_l2),
                "in_new_file": int(new.sum()),
                "new_file_pct": round(share, 2),
                "new_file_lo": round(lo, 2),
                "new_file_hi": round(hi, 2),
                "instances_with_any_new_file": int(sum(1 for x in new if x > 0)),
            }
            for g in GROUPS:
                nrow[f"new_{g}"] = nk.get(g, 0)
            novelty.append(nrow)
    return kinds, novelty


def census_meta(
    instance_ids: dict[str, list[str]], tables: list[list[Record]]
) -> dict[str, Record]:
    """Base commit, repository and patch of each wanted instance, from dataset metadata rows.

    ``instance_ids`` maps ``dataset/folder`` to the L3 instance ids of that folder; ``tables`` are
    the rows (dicts with ``instance_id``, ``repo``, ``base_commit``, ``patch``) of the datasets'
    metadata files. Returns the ``meta.json`` mapping read by the pilot-E1 unit stage; an id with
    no row is left out (the stage reports it as ``no_metadata``). The output holds dataset text
    (patches) and is written under ``data/`` only, never tracked.
    """
    rows = {r["instance_id"]: r for t in tables for r in t}
    out: dict[str, Record] = {}
    for key, ids in sorted(instance_ids.items()):
        dataset, folder = key.split("/", 1)
        for i in ids:
            r = rows.get(i)
            if r is None:
                continue
            out[i] = {
                "repo": r["repo"],
                "base_commit": r["base_commit"],
                "patch": r["patch"],
                "dataset": dataset,
                "folder": folder,
            }
    return out
