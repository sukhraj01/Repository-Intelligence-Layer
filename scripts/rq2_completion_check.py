"""Completion check of the RQ2 final runs from pulled result directories.

  rq2_completion_check.py RESOLVE_SUMMARY OUT.json --results A=DIR --results C=DIR
      [--retained C=DIR] --leakage A=FILE --leakage C=FILE [--exclude-conditional]

Reads only; writes the table of runs as JSON. Logic in ``ril/bench/rq2_completion.py``.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _pairs(items: list[str]) -> dict[str, Path]:
    return {k: Path(v) for k, v in (i.split("=", 1) for i in items)}


def main(argv: list[str] | None = None) -> int:
    from ril.bench import rq2_completion as rc

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("resolve_summary", type=Path)
    p.add_argument("out", type=Path)
    p.add_argument("--results", action="append", required=True)
    p.add_argument("--retained", action="append", default=[])
    p.add_argument("--leakage", action="append", required=True)
    p.add_argument("--exclude-conditional", action="store_true")
    a = p.parse_args(argv)
    runs = json.loads(a.resolve_summary.read_text(encoding="utf-8"))["runs"]
    excluded = frozenset(
        r["run_id"] for r in runs if a.exclude_conditional and r.get("conditional")
    )
    leakage = {k: json.loads(v.read_text(encoding="utf-8")) for k, v in _pairs(a.leakage).items()}
    checks = rc.check_all(
        runs,
        results_roots=_pairs(a.results),
        retained_roots=dict(_pairs(a.retained)),
        leakage=leakage,
        excluded_run_ids=excluded,
    )
    a.out.write_text(
        json.dumps([asdict(c) | {"complete": c.complete} for c in checks], indent=1) + "\n",
        encoding="utf-8",
    )
    bad = [c for c in checks if not c.complete]
    sys.stdout.write(f"{len(checks)} runs, {len(bad)} incomplete\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
