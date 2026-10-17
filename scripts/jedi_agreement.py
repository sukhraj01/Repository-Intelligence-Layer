"""Agreement of Jedi with the own resolver on a stratified sample of call sites (ADR-012, (c)).

Usage: jedi_agreement.py OUT.csv OUT.json --seed N --total 300 LABEL=DIR=owner/name [...]
A thin wrapper around ``ril.evaluation.jedi_agreement``.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.evaluation.jedi_agreement import run_agreement  # noqa: E402
from ril.util.seed import set_seed  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out_csv")
    ap.add_argument("out_json")
    ap.add_argument("repo", nargs="+")
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--total", type=int, default=300)
    args = ap.parse_args()
    set_seed(args.seed)
    repos = {}
    for spec in args.repo:
        label, root, rid = spec.split("=", 2)
        repos[label] = (root, rid)
    rows, summary = run_agreement(repos, args.total, args.seed)
    with open(args.out_csv, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    Path(args.out_json).write_text(
        json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
