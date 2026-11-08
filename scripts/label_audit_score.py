"""Score filled label sheets of the noise audit against the key file.

Usage: python -I scripts/label_audit_score.py --key KEY.csv --sheet reader_1.csv
           [--sheet reader_2.csv] [--seed N] [--draws N] [--json OUT.json]
Prints the headline numbers and writes the full report as JSON. With two sheets the agreement on
the shared pairs is scored. A thin wrapper around ``ril.evaluation.label_audit_score``.
"""

# ruff: noqa: T201

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ril.evaluation import label_audit_score as sc  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--key", required=True)
    ap.add_argument(
        "--sheet", action="append", required=True, help="a filled sheet (repeat for two readers)"
    )
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--draws", type=int, default=2000)
    ap.add_argument("--json", type=Path, default=None)
    a = ap.parse_args()
    if len(a.sheet) > 2:
        print("error: at most two sheets")
        return 2
    key = sc.read_key(a.key)
    try:
        sheets = [sc.read_sheet(p, key) for p in a.sheet]
    except sc.SheetError as exc:
        print(f"error: {exc}")
        return 1
    report = sc.score(key, sheets, seed=a.seed, draws=a.draws)
    print(sc.format_text(report))
    if a.json:
        a.json.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
