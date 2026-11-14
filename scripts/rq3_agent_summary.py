#!/usr/bin/env python3
"""Summarise the graded RQ3 arms from stored files (thin wrapper, D167).

rq3_agent_summary.py OUT.json --arm NAME RESULTS.jsonl CALLS.jsonl [--arm ...] --runs 0 1 2
                     [--input LABEL PATH ...]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.analysis.rq3_agent_summary import build  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("out")
    p.add_argument("--arm", nargs=3, action="append", metavar=("NAME", "RESULTS", "CALLS"))
    p.add_argument("--runs", type=int, nargs="+", required=True)
    p.add_argument("--input", nargs=2, action="append", default=[], metavar=("LABEL", "PATH"))
    a = p.parse_args()
    arms = {n: (r, c) for n, r, c in a.arm}
    out = build(arms, a.runs, {k: v for k, v in a.input})
    Path(a.out).write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
