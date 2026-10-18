"""Write the pool-check tables from the cluster summary (logic: ril.training.pool_check).

Usage: pool_check_tables.py SUMMARY.json OUT_DIR
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.training import pool_check as pc  # noqa: E402


def main() -> int:
    summary = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = Path(sys.argv[2])
    for name, rows in (("overlap", pc.overlap_table(summary)), ("facts", pc.facts_table(summary))):
        with (out / f"x_pool_check_{name}.csv").open("w", newline="", encoding="utf-8") as h:
            w = csv.DictWriter(h, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
