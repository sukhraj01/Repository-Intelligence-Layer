"""Incremental graph update against a full rebuild on real commit histories (session A2a).

Usage: a_incremental_graph.py --repo owner/name=PATH [--repo ...] --commits N --out LOG.json
       [--table TABLE.csv]
A thin wrapper: the logic is in ``ril.bench.incremental_measure``.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.bench.incremental_measure import measure_repository  # noqa: E402
from ril.util.log import get_logger  # noqa: E402
from ril.util.machine import hardware  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", action="append", required=True, help="owner/name=PATH")
    ap.add_argument("--commits", type=int, default=21, help="base commit plus N-1 updates")
    ap.add_argument("--out", required=True)
    ap.add_argument("--table", default="")
    ap.add_argument("--host", default="local", help="host label recorded in the log")
    args = ap.parse_args()
    log = get_logger("a2")
    results = []
    for spec in args.repo:
        repo_id, _, path = spec.partition("=")
        res = measure_repository(path, repo_id, args.commits)
        log.info(
            "%s: %d/%d equal; incremental %s s; full %s s; speedup p50 %s",
            repo_id,
            res["equal_updates"],
            res["n_updates"],
            res["incremental_seconds"],
            res["full_seconds"],
            res["speedup_p50"],
        )
        results.append(res)
    record = {
        "experiment": "a2-incremental-graph",
        "date": date.today().isoformat(),
        "hardware": {**hardware(), "host": args.host},
        "commits_per_repo": args.commits,
        "repositories": results,
    }
    Path(args.out).write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if args.table:
        with open(args.table, "w", newline="", encoding="utf-8") as handle:
            w = csv.writer(handle)
            w.writerow(
                [
                    "repo_id",
                    "files",
                    "units",
                    "updates",
                    "equal",
                    "full_p50_s",
                    "full_p95_s",
                    "full_p99_s",
                    "incr_p50_s",
                    "incr_p95_s",
                    "incr_p99_s",
                    "speedup_p50",
                    "speedup_min",
                    "reresolved_share_p50",
                    "reresolved_share_p95",
                ]
            )
            for r in results:
                w.writerow(
                    [
                        r["repo_id"],
                        r["files_total_last"],
                        r["n_units_last"],
                        r["n_updates"],
                        r["equal_updates"],
                        *[r["full_seconds"][p] for p in ("p50", "p95", "p99")],
                        *[r["incremental_seconds"][p] for p in ("p50", "p95", "p99")],
                        r["speedup_p50"],
                        r["speedup_min"],
                        r["reresolved_share"]["p50"],
                        r["reresolved_share"]["p95"],
                    ]
                )
    return 0 if all(r["equal_updates"] == r["n_updates"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
