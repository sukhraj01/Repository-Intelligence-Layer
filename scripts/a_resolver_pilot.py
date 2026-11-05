"""Resolver typing pilots on real checkouts (session A2b): static counts and trace recall.

Usage: a_resolver_pilot.py --repo owner/name=PATH [--repo ...] [--trace owner/name=PATH=TRACE.json]
       --out LOG.json [--table TABLE.csv] [--host local]
A thin wrapper: the logic is in ``ril.bench.resolver_pilot``.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.bench.resolver_pilot import PILOTS, dynamic_rows, receiver_census, static_rows  # noqa: E402 (path set above)
from ril.util.log import get_logger  # noqa: E402 (path set above)
from ril.util.machine import hardware  # noqa: E402 (path set above)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", action="append", default=[], help="owner/name=PATH")
    ap.add_argument("--trace", action="append", default=[], help="owner/name=PATH=TRACE.json")
    ap.add_argument("--out", required=True)
    ap.add_argument("--table", default="")
    ap.add_argument("--host", default="local", help="host label recorded in the log")
    args = ap.parse_args()
    log = get_logger("a2b")
    static: list[dict[str, object]] = []
    receivers: dict[str, dict[str, int]] = {}
    for spec in args.repo:
        repo_id, _, path = spec.partition("=")
        static.extend(static_rows(path, repo_id))
        receivers[repo_id] = receiver_census(path, repo_id, PILOTS[-1])
        log.info("%s: static rows done", repo_id)
    dynamic: list[dict[str, object]] = []
    traces = []
    for spec in args.trace:
        repo_id, path, trace_path = spec.split("=", 2)
        trace = json.loads(Path(trace_path).read_text(encoding="utf-8"))
        dynamic.extend(dynamic_rows(path, repo_id, trace))
        traces.append(
            {
                "repo_id": repo_id,
                "trace": trace_path,
                "python": trace.get("python"),
                "pytest_exit_code": trace.get("pytest_exit_code"),
                "outcomes": trace.get("outcomes"),
            }
        )
        log.info("%s: dynamic rows done", repo_id)
    record = {
        "experiment": "a2b-resolver-pilot",
        "date": date.today().isoformat(),
        "hardware": {**hardware(), "host": args.host},
        "static": static,
        "untyped_receivers_combined_options": receivers,
        "dynamic": dynamic,
        "traces": traces,
    }
    Path(args.out).write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if args.table and static:
        with open(args.table, "w", newline="", encoding="utf-8") as handle:
            w = csv.DictWriter(handle, fieldnames=list(static[0]))
            w.writeheader()
            w.writerows(static)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
