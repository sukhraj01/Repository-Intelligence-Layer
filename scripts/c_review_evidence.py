"""Audit the stored operator summary without claiming query-level recomputation."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEM = "c1_colab_bm25_dev_v1_2026-10-31"


def emit(line: str) -> None:
    sys.stdout.write(line + "\n")


def main() -> None:
    summary = json.loads((ROOT / "results/logs" / (STEM + ".json")).read_text())
    stdout = (ROOT / summary["stdout_artifact"]).read_bytes()
    if hashlib.sha256(stdout).hexdigest() != summary["stdout_sha256"]:
        raise ValueError("operator stdout checksum changed")
    reported = summary["reported_cli_summary"]
    console = next(json.loads(line) for line in stdout.splitlines() if b'"metrics":' in line)
    if console != reported or summary["evidence_class"] != "operator_reported":
        raise ValueError("summary differs from stdout or overstates its evidence class")
    with (ROOT / "results/tables" / (STEM + ".csv")).open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    metrics = reported["metrics"]
    if len(rows) != 12 or len(metrics) != 12:
        raise ValueError("expected twelve stored aggregate rows")
    by_key = {(r["level"], r["condition"], r["metric"]): r for r in metrics}
    if len(by_key) != 12:
        raise ValueError("duplicate aggregate identity")
    for row in rows:
        condition = row["condition"].replace("-", "_")
        metric = by_key[(row["level"], condition, row["metric"])]
        if row["evidence_class"] != "operator_reported":
            raise ValueError("table evidence must remain operator_reported")
        if row["config_hash"] != reported["config_hash"]:
            raise ValueError("config identity differs")
        if row["source_commit"] != reported["git_hash"]:
            raise ValueError("source identity differs")
        for field in ("mean", "low", "high"):
            if not math.isfinite(float(row[field])) or float(row[field]) != metric[field]:
                raise ValueError(f"table differs at {field}")
        if not metric["low"] <= metric["mean"] <= metric["high"]:
            raise ValueError("unordered interval")
        if any(int(row[field]) != metric[field] for field in ("n", "repositories")):
            raise ValueError("denominator differs")
    ledger_rows = [
        line
        for line in (ROOT / "results/ledger_c.md").read_text().splitlines()
        if "| c1-colab-dev-v1-" in line
    ]
    if len(ledger_rows) != 13 or any("| operator_reported |" not in r for r in ledger_rows):
        raise ValueError("ledger evidence must remain operator_reported")
    if any(summary["audit_state"].values()):
        raise ValueError("review query-level evidence before changing the aggregate-only audit")
    emit("operator_reported: 12 aggregate rows and 13 ledger records agree with stored stdout")
    emit("Query-level pairing, bootstrap intervals and timing: NOT independently recomputed")
    emit("| Level | Metric | Difference (pp) | Reported 95% interval (pp) | n / repos |")
    emit("|---|---|---:|---|---|")
    for level in ("L2", "L3"):
        for name in ("ndcg10", "recall100"):
            delta = by_key[(level, "rewrite_minus_original", name)]
            original = by_key[(level, "original", name)]
            rewrite = by_key[(level, "rewrite", name)]
            if not math.isclose(delta["mean"], rewrite["mean"] - original["mean"], abs_tol=1e-14):
                raise ValueError("paired mean differs from aggregate subtraction")
            emit(
                f"| {level} | {name} | {100 * delta['mean']:+.4f} | "
                f"[{100 * delta['low']:+.4f}, {100 * delta['high']:+.4f}] | "
                f"{delta['n']} / {delta['repositories']} |"
            )


if __name__ == "__main__":
    main()
