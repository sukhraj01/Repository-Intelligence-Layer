"""Summary CSV of the edited-function follow-up of the contamination scan (E-CONTAM-EDITED).

Usage: x5_tables.py RESULT.json OUT.csv
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.analysis.x5_tables import summary_rows  # noqa: E402


def main() -> int:
    with open(sys.argv[1], encoding="utf-8") as handle:
        rows = summary_rows(json.load(handle))
    with open(sys.argv[2], "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
