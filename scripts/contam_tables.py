"""Summarise the per-shard scan outputs of the contamination probe (thin wrapper).

Usage: contam_tables.py SCAN_DIR PROBE_WITH_NODES.json OUT_JSON OUT_CSV_DIR
Logic: ``ril.training.contamination.summarize_scan``. Counts and hashes only.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.training import contamination as cm  # noqa: E402


def main() -> int:
    scan_dir, probe_path, out_json, out_dir = sys.argv[1:5]
    shards = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(Path(scan_dir).glob("shard-*.json"))
    ]
    sizes = cm.ProbeSet.from_json(Path(probe_path).read_text(encoding="utf-8")).nodes
    summary = cm.summarize_scan(shards, sizes)
    summary["shard_ids"] = sorted(int(s["shard"]) for s in shards)
    Path(out_json).write_text(json.dumps(summary, indent=1, sort_keys=True), encoding="utf-8")
    rows = [{"quantity": k, "value": v} for k, v in sorted(summary["totals"].items())]
    rows += [
        {"quantity": f"hits_{k}", "value": v} for k, v in summary["hits_by_node_bucket"].items()
    ]
    rows += [{"quantity": f"hits_repo_{k}", "value": v} for k, v in summary["hits_by_repo"].items()]
    with (Path(out_dir) / "x_contam_probe_slice.csv").open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=["quantity", "value"])
        w.writeheader()
        w.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
