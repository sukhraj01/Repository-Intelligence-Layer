"""Docstring-to-function retrieval with BM25 variants on local checkouts (session A1, exploratory).

Usage: a_bm25_docstring_pilot.py --repo owner/name=PATH [--repo ...] --out LOG.json
       [--table TABLE.csv] [--seed 0]
A thin wrapper: the logic is in ``ril.analysis.rq1_docstring_pilot``.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.analysis.rq1_docstring_pilot import (  # noqa: E402
    VARIANTS,
    config_hash,
    run_repository,
    summarise,
)
from ril.util.log import get_logger  # noqa: E402
from ril.util.machine import hardware  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", action="append", required=True, help="owner/name=PATH")
    ap.add_argument("--out", required=True)
    ap.add_argument("--table", default="")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--host", default="local", help="host label recorded in the log")
    args = ap.parse_args()
    log = get_logger("a1")
    repos = []
    for spec in args.repo:
        repo_id, _, path = spec.partition("=")
        res = run_repository(path, repo_id, args.seed)
        res["commit"] = subprocess.run(
            ["git", "-C", path, "rev-parse", "HEAD"], capture_output=True, text=True, check=False
        ).stdout.strip()
        rr = {
            v: round(
                100 * sum(r[0] for r in res["variants"][v]["rows"]) / max(1, res["n_queries"]), 2
            )
            for v in VARIANTS
        }
        log.info(
            "%s: %d queries over %d units; MRR %s", repo_id, res["n_queries"], res["n_units"], rr
        )
        repos.append(res)
    summary = summarise(repos)
    record = {
        "experiment": "a1-bm25-docstring-pilot",
        "date": date.today().isoformat(),
        "seed": args.seed,
        "config_hash": config_hash(),
        "hardware": {**hardware(), "host": args.host},
        "summary": summary,
        "repositories": repos,
    }
    Path(args.out).write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if args.table:
        with open(args.table, "w", newline="", encoding="utf-8") as handle:
            w = csv.writer(handle)
            w.writerow(
                [
                    "repo_id",
                    "variant",
                    "n_queries",
                    "mrr",
                    "recall10",
                    "ndcg10",
                    "build_s",
                    "units_per_s",
                    "q_p50_ms",
                    "q_p95_ms",
                    "q_p99_ms",
                ]
            )
            for r in repos:
                for v in VARIANTS:
                    vr = r["variants"][v]
                    n = max(1, r["n_queries"])
                    w.writerow(
                        [
                            r["repo_id"],
                            v,
                            r["n_queries"],
                            *[
                                round(100 * sum(row[i] for row in vr["rows"]) / n, 2)
                                for i in range(3)
                            ],
                            vr["build_seconds"],
                            vr["units_per_second"],
                            *[vr["query_ms"].get(p) for p in ("p50", "p95", "p99")],
                        ]
                    )
            for v in VARIANTS:
                s = summary[v]
                w.writerow(
                    [
                        "pooled",
                        v,
                        sum(r["n_queries"] for r in repos),
                        s["rr"][0],
                        s["recall10"][0],
                        s["ndcg10"][0],
                        "",
                        "",
                        "",
                        "",
                        "",
                    ]
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
