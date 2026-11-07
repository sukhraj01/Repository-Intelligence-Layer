"""Tables of the RQ3 contexts: coverage, size and the manifest of files (E-RQ3-CONTEXTS, D108).

Implements ``docs/experiments/B.md`` E-RQ3-CONTEXTS. Everything here is descriptive: counts and
shares with their denominators, no interval and no test, and nothing is selected from it. Reads the
per-instance files written by ``ril.assembly.rq3_contexts``.

Two views of coverage, each with its own denominator:

- ``file``: reading ``units_all`` (the files of every found positive); denominator = instances
  with at least one gold file at the level;
- ``unit``: reading ``units_all_nomod`` (D18's primary reading); denominator = instances with at
  least one gold unit at the level. This is the view that matches the dev cells of E-ASSEMBLY
  (mean share of gold files, mean share of gold units, share with no gold file).
"""

from __future__ import annotations

import glob
import os
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import numpy as np

from ril.assembly.rq3_contexts import (
    FILE_READING,
    UNIT_READING,
    decode_record,
    sha256_file,
)

Record = dict[str, Any]


def load_records(out_dir: str) -> list[Record]:
    """Decoded per-instance records, in sorted instance order."""
    out: list[Record] = []
    for path in sorted(glob.glob(os.path.join(out_dir, "instances", "*.json.gz"))):
        with open(path, "rb") as handle:
            out.append(decode_record(handle.read()))
    return out


def coverage_summary(records: Iterable[Mapping[str, Any]]) -> list[Record]:
    """Per level, arm, budget and view: denominators and the shares of the module docstring."""
    cells: dict[tuple[str, str, int, str], list[Mapping[str, Any]]] = {}
    for rec in records:
        for row in rec["coverage"]:
            view = {FILE_READING: "file", UNIT_READING: "unit"}.get(row["reading"])
            if view is None:
                continue
            gold = row["n_gold_files"] if view == "file" else row["n_gold_units"]
            if gold <= 0:
                continue
            cells.setdefault((row["level"], row["arm"], int(row["budget"]), view), []).append(row)
    out: list[Record] = []
    for (level, arm, budget, view), rows in sorted(cells.items()):
        n = len(rows)
        file_share = [r["files_in"] / r["n_gold_files"] for r in rows if r["n_gold_files"]]
        unit_share = [r["units_in"] / r["n_gold_units"] for r in rows if r["n_gold_units"]]
        out.append(
            {
                "level": level,
                "arm": arm,
                "budget": budget,
                "view": view,
                "instances": n,
                "gold_file_in_context": sum(1 for r in rows if r["files_in"] > 0),
                "gold_unit_in_context": sum(1 for r in rows if r["units_in"] > 0),
                "gold_unit_intact_in_context": sum(1 for r in rows if r["units_intact"] > 0),
                "pct_gold_file_in_context": round(
                    100.0 * sum(1 for r in rows if r["files_in"] > 0) / n, 1
                ),
                "pct_gold_unit_in_context": round(
                    100.0 * sum(1 for r in rows if r["units_in"] > 0) / n, 1
                ),
                "mean_pct_gold_files": round(100.0 * float(np.mean(file_share)), 1),
                "mean_pct_gold_units": round(100.0 * float(np.mean(unit_share)), 1),
                "pct_no_gold_file": round(
                    100.0 * sum(1 for r in rows if r["n_gold_files"] and r["files_in"] == 0) / n,
                    1,
                ),
            }
        )
    return out


def _quantiles(values: Sequence[float]) -> Record:
    a = np.asarray(values, dtype=np.float64)
    return {
        "min": float(a.min()),
        "p5": float(np.percentile(a, 5)),
        "p50": float(np.percentile(a, 50)),
        "p95": float(np.percentile(a, 95)),
        "max": float(a.max()),
    }


def size_summary(records: Iterable[Mapping[str, Any]]) -> list[Record]:
    """Per arm and budget over all instances: tokens, units and files (quantiles), the share whose
    walk left a candidate out for lack of room (budget binding) and the share of truncated units."""
    cells: dict[tuple[str, int], list[Mapping[str, Any]]] = {}
    for rec in records:
        for key, ctx in rec["contexts"].items():
            arm, budget = key.split("|")
            cells.setdefault((arm, int(budget)), []).append(ctx["manifest"])
    out: list[Record] = []
    for (arm, budget), manifests in sorted(cells.items()):
        tokens = [m["total_tokens"] for m in manifests]
        units = [len(m["entries"]) for m in manifests]
        files = [len({e["file"] for e in m["entries"]}) for m in manifests]
        binding = sum(
            1 for m in manifests if any(s["reason"] == "does_not_fit" for s in m["skipped"])
        )
        entries = sum(len(m["entries"]) for m in manifests)
        cut = sum(1 for m in manifests for e in m["entries"] if e["truncated"])
        tq, uq, fq = _quantiles(tokens), _quantiles(units), _quantiles(files)
        row: Record = {
            "arm": arm,
            "budget": budget,
            "instances": len(manifests),
            "budget_binding": binding,
            "pct_budget_binding": round(100.0 * binding / len(manifests), 1),
            "pct_units_truncated": round(100.0 * cut / entries, 1) if entries else 0.0,
        }
        for name, q in (("tokens", tq), ("units", uq), ("files", fq)):
            for k, v in q.items():
                row[f"{name}_{k}"] = round(v, 1)
        out.append(row)
    return out


def file_manifest(out_dir: str) -> list[Record]:
    """Path (relative to ``out_dir``), size and SHA-256 of every instance file, sorted by path."""
    rows: list[Record] = []
    for path in sorted(glob.glob(os.path.join(out_dir, "instances", "*.json.gz"))):
        rows.append(
            {
                "path": os.path.relpath(path, out_dir),
                "bytes": os.path.getsize(path),
                "sha256": sha256_file(path),
            }
        )
    return rows


def context_rows(records: Iterable[Mapping[str, Any]]) -> list[Record]:
    """One row per (instance, arm, budget): the context's hash, tokens, units and files."""
    out: list[Record] = []
    for rec in records:
        for key, ctx in sorted(rec["contexts"].items()):
            arm, budget = key.split("|")
            m = ctx["manifest"]
            out.append(
                {
                    "instance": rec["instance"],
                    "arm": arm,
                    "budget": int(budget),
                    "context_sha256": m["context_sha256"],
                    "tokens": m["total_tokens"],
                    "units": len(m["entries"]),
                    "files": len({e["file"] for e in m["entries"]}),
                    "budget_binding": any(s["reason"] == "does_not_fit" for s in m["skipped"]),
                }
            )
    return out
