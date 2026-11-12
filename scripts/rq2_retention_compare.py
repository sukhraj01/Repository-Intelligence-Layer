"""Retention round trip, comparison step: dense rows of two ``query_rows.csv`` files.

  rq2_retention_compare.py IN_MEMORY_ROWS RETAINED_ROWS OUT

``IN_MEMORY_ROWS`` is the dev scoring of the run's own final model, ``RETAINED_ROWS`` the dev
scoring of the retained copy loaded back from disk. Reports the number of dense rows, the number
that differ in any metric, and the largest absolute difference. Exit 0 only if the two agree.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


def _dense(path: str) -> dict[tuple[str, str], dict[str, float]]:
    out: dict[tuple[str, str], dict[str, float]] = {}
    with open(path, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            name = str(row["name"])
            if not name.startswith("dense:"):
                continue
            metrics = {k: float(v) for k, v in row.items() if ":" in k and v != ""}
            out[(row["instance"], row["level"])] = metrics
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("in_memory")
    p.add_argument("retained")
    p.add_argument("out")
    a = p.parse_args()
    x, y = _dense(a.in_memory), _dense(a.retained)
    keys = sorted(set(x) | set(y))
    worst = 0.0
    differing = 0
    for k in keys:
        if k not in x or k not in y:
            differing += 1
            continue
        if set(x[k]) != set(y[k]):
            differing += 1
            continue
        d = max((abs(x[k][m] - y[k][m]) for m in x[k]), default=0.0)
        worst = max(worst, d)
        differing += d > 1e-9
    out = {
        "rows_in_memory": len(x),
        "rows_retained": len(y),
        "rows_differing": differing,
        "max_abs_difference": worst,
        "equal": bool(keys) and differing == 0 and len(x) == len(y),
    }
    Path(a.out).write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    sys.stdout.write(json.dumps(out, indent=1, sort_keys=True) + "\n")
    return 0 if out["equal"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
