"""Edge store cost on real checkouts (session A2c): size, write, load and adjacency times.

Usage: a_edge_store.py --repo owner/name=PATH [--repo ...] --work DIR --out LOG.json
       [--table TABLE.csv] [--repeats 7] [--host local]
A thin wrapper: the logic is in ``ril.bench.edge_store_measure``.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.bench.edge_store_measure import measure_repository  # noqa: E402
from ril.util.log import get_logger  # noqa: E402
from ril.util.machine import hardware  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", action="append", required=True, help="owner/name=PATH")
    ap.add_argument("--work", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--table", default="")
    ap.add_argument("--repeats", type=int, default=7)
    ap.add_argument("--host", default="local", help="host label recorded in the log")
    args = ap.parse_args()
    log = get_logger("a2c")
    results = []
    for spec in args.repo:
        repo_id, _, path = spec.partition("=")
        res = measure_repository(path, repo_id, args.work, args.repeats)
        log.info(
            "%s: %d edges, %d bytes, load %s s (verified), equal %s",
            repo_id,
            res["n_edges"],
            res["store_bytes"],
            res["load_verify_seconds"]["p50"],
            res["round_trip_equal"],
        )
        results.append(res)
    record = {
        "experiment": "a2c-edge-store",
        "date": date.today().isoformat(),
        "hardware": {**hardware(), "host": args.host},
        "repositories": results,
    }
    Path(args.out).write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if args.table:
        cols = ["load_fast", "load_verify", "load_deep", "adjacency"]
        with open(args.table, "w", newline="", encoding="utf-8") as handle:
            w = csv.writer(handle)
            w.writerow(
                [
                    "repo_id",
                    "nodes",
                    "edges",
                    "raw_jsonl_bytes",
                    "store_bytes",
                    "write_s",
                    *[f"{c}_p50_s" for c in cols],
                    *[f"{c}_p95_s" for c in cols],
                    "round_trip_equal",
                ]
            )
            for r in results:
                w.writerow(
                    [
                        r["repo_id"],
                        r["n_nodes"],
                        r["n_edges"],
                        r["raw_jsonl_bytes"],
                        r["store_bytes"],
                        r["write_seconds"],
                        *[r[f"{c}_seconds"]["p50"] for c in cols],
                        *[r[f"{c}_seconds"]["p95"] for c in cols],
                        r["round_trip_equal"],
                    ]
                )
    return 0 if all(r["round_trip_equal"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
