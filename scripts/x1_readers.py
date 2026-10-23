"""Readers of the call-site buckets per ambiguous-site policy (wrapper over
``ril.evaluation.policy_readers``). Counts and ids only.

Usage:
  x1_readers.py oracle ROOT OWNER/NAME TRACE.json COVERAGE.json OUT.json
  x1_readers.py jedi OUT.csv OUT.json --seed N --per-repo 150 LABEL=DIR=owner/name [...]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.evaluation.policy_readers import jedi_policy_sample, oracle_policy_report  # noqa: E402
from ril.parsing.call_graph import GraphBuilder  # noqa: E402
from ril.parsing.repository_parser import parse_repository  # noqa: E402
from ril.util.seed import set_seed  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("stage", choices=["oracle", "jedi"])
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--per-repo", type=int, default=150)
    args = ap.parse_args()
    set_seed(args.seed)
    if args.stage == "oracle":
        root, rid, trace_p, cov_p, out = args.paths
        parsed = parse_repository(root, rid)
        builder = GraphBuilder(parsed)
        graph = builder.build()
        report = oracle_policy_report(
            parsed,
            graph,
            builder,
            json.loads(Path(trace_p).read_text(encoding="utf-8")),
            json.loads(Path(cov_p).read_text(encoding="utf-8")),
        )
        report["graph_sha256"] = graph.digest()
        Path(out).write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        return 0
    out_csv, out_json, *specs = args.paths
    repos = {}
    for spec in specs:
        label, root, rid = spec.split("=", 2)
        repos[label] = (root, rid)
    rows, summary = jedi_policy_sample(repos, args.per_repo, args.seed)
    with open(out_csv, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    Path(out_json).write_text(
        json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
