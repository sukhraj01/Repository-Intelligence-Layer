"""Contrast table of the RQ2 final analysis, written from the stored summary.

Implements docs/RQ2_PROTOCOL.md section 4 and DEV-040: one row per contrast with the estimate in
points, the decision interval (cluster-robust t), the repository bootstrap beside it, the
Holm-adjusted decision where the contrast is in the decision family, and the hash of the summary.
Nothing is recomputed here; every figure is read from the summary the analysis module wrote.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

COLUMNS = [
    "eval_set",
    "family",
    "level",
    "metric",
    "contrast",
    "repos",
    "queries",
    "estimate",
    "t_interval_df",
    "t_interval",
    "bootstrap_interval",
    "holm_t_interval",
    "holm_p_adjusted",
    "holm_rejected",
    "holm_boot_rejected",
    "klass",
    "primary",
    "status",
    "summary_sha256",
]


def _interval(value: Any) -> str:
    if not value:
        return ""
    return f"[{value[0]:+.2f}, {value[1]:+.2f}]"


def table_rows(summary: dict[str, Any], summary_sha256: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for c in summary["contrasts"]:
        holm = c.get("holm") or {}
        boot = holm.get("boot") or {}
        rows.append(
            {
                "eval_set": c["eval_set"],
                "family": c["family"],
                "level": c["level"],
                "metric": c["metric"],
                "contrast": c["contrast"],
                "repos": c["repos"],
                "queries": c["queries"],
                "estimate": f"{c['d']:+.2f}",
                "t_interval_df": c["df"],
                "t_interval": _interval(c["ci_cluster"]),
                "bootstrap_interval": _interval(c["ci_boot_uncorrected"]),
                "holm_t_interval": _interval(holm.get("ci")),
                "holm_p_adjusted": holm.get("p_adjusted", ""),
                "holm_rejected": holm.get("rejected", ""),
                "holm_boot_rejected": boot.get("rejected", ""),
                "klass": c.get("class") or "",
                "primary": c.get("primary", ""),
                "status": c.get("status", ""),
                "summary_sha256": summary_sha256,
            }
        )
    return rows


def write_table(summary_path: Path, out_path: Path) -> int:
    raw = summary_path.read_bytes()
    summary = json.loads(raw)
    rows = table_rows(summary, hashlib.sha256(raw).hexdigest())
    with open(out_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)
