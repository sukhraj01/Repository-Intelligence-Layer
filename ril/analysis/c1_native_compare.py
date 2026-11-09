"""Native re-run of the paired original/Rewrite BM25 dev comparison against the operator-reported
summary. Implements ``docs/experiments/B.md`` E-C-CATCHUP (question Q64) and reads the stored
summary of ``docs/experiments/C.md`` E-C1-COLAB-DEV.

Inputs are the ``results.json`` of one ``python -m ril.evaluation.run`` execution (query-level
rows and metrics) and the stored operator summary. Nothing is recomputed from the operator's
side: its twelve cells are compared as stored. Agreement is decided by a rule fixed before the
run: a point estimate agrees when the absolute difference is at most ``POINT_TOL`` (fractions),
an interval when both ends differ by at most ``INTERVAL_TOL``; the sample (n and repositories)
must be equal. Anything else is reported as a difference, never rounded into agreement.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

Row = dict[str, Any]
POINT_TOL = 1e-9
INTERVAL_TOL = 1e-9
ROW_FIELDS = (
    "level",
    "dataset",
    "folder",
    "repo",
    "query_id",
    "condition",
    "ndcg10",
    "recall100",
)
_KEY = ("level", "condition", "metric")


def _index(metrics: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str, str], Mapping[str, Any]]:
    out: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    for m in metrics:
        key = (str(m["level"]), str(m["condition"]), str(m["metric"]))
        if key in out:
            raise ValueError(f"duplicate metric cell {key}")
        out[key] = m
    return out


def compare_cells(
    native: Sequence[Mapping[str, Any]],
    reported: Sequence[Mapping[str, Any]],
    *,
    point_tol: float = POINT_TOL,
    interval_tol: float = INTERVAL_TOL,
) -> list[Row]:
    """One row per cell of the operator summary: both values, differences and the verdict.

    A cell missing on either side is an error (the comparison would be partial); the verdict is
    ``agree``, ``point_only`` (point equal, interval differs), or ``differ``.
    """
    a, b = _index(native), _index(reported)
    if a.keys() != b.keys():
        raise ValueError("native and reported cells differ: " + str(sorted(a.keys() ^ b.keys())))
    rows: list[Row] = []
    for key in sorted(b):
        n, r = a[key], b[key]
        same_sample = n["n"] == r["n"] and n["repositories"] == r["repositories"]
        d_mean = float(n["mean"]) - float(r["mean"])
        d_low = float(n["low"]) - float(r["low"])
        d_high = float(n["high"]) - float(r["high"])
        point_ok = same_sample and abs(d_mean) <= point_tol
        interval_ok = abs(d_low) <= interval_tol and abs(d_high) <= interval_tol
        verdict = "agree" if point_ok and interval_ok else "point_only" if point_ok else "differ"
        rows.append(
            {
                **dict(zip(_KEY, key, strict=True)),
                "n_native": n["n"],
                "n_reported": r["n"],
                "repos_native": n["repositories"],
                "repos_reported": r["repositories"],
                "mean_native": float(n["mean"]),
                "mean_reported": float(r["mean"]),
                "diff_mean": d_mean,
                "low_native": float(n["low"]),
                "low_reported": float(r["low"]),
                "diff_low": d_low,
                "high_native": float(n["high"]),
                "high_reported": float(r["high"]),
                "diff_high": d_high,
                "verdict": verdict,
            }
        )
    return rows


def query_rows(result: Mapping[str, Any]) -> list[Row]:
    """Query-level rows of a run, limited to the stored fields (anchor counts stay in the run)."""
    rows = [{f: r[f] for f in ROW_FIELDS} for r in result["query_rows"]]
    if not rows:
        raise ValueError("run has no query rows")
    return rows


def paired_deltas(rows: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    """Mean rewrite-minus-original per (level, metric) over paired queries, for a cheap re-check."""
    sums: dict[tuple[str, str], list[float]] = {}
    keyed: dict[tuple[str, str, str, str], Mapping[str, Any]] = {}
    for r in rows:
        keyed[(r["level"], r["folder"], r["query_id"], r["condition"])] = r
    for (level, folder, qid, cond), r in keyed.items():
        if cond != "rewrite":
            continue
        o = keyed[(level, folder, qid, "original")]
        for metric in ("ndcg10", "recall100"):
            sums.setdefault((level, metric), []).append(float(r[metric]) - float(o[metric]))
    return {f"{lv}:{m}": sum(v) / len(v) for (lv, m), v in sorted(sums.items())}


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError("nothing to write")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def run_file_listing(root: Path) -> list[Row]:
    """Size and SHA-256 of every file under ``root`` (sorted), for the run-file record."""
    return [
        {"path": str(p.relative_to(root)), "bytes": p.stat().st_size, "sha256": sha256_file(p)}
        for p in sorted(root.rglob("*"))
        if p.is_file()
    ]


def load_reported(path: Path) -> list[Mapping[str, Any]]:
    """The twelve stored cells of the operator summary (read as stored)."""
    summary = json.loads(path.read_text())
    metrics = summary["reported_cli_summary"]["metrics"]
    if len(metrics) != 12:
        raise ValueError("expected twelve reported cells")
    return list(metrics)
