"""Convert scoring results to the row files of the RQ2 final analysis (no torch).

  python3 -I scripts/rq2_rows.py final --index DIR/final_sets_index.jsonl
      --follows-dev-analysis ID --out-rows ROWS.csv [--docs-root .]
  python3 -I scripts/rq2_rows.py dev --results DIR [DIR ...] --out-rows ROWS.csv --out-runs RUNS.csv

``final`` refuses without the id of the finished dev analysis (the same guard the final-sets
scoring and the analysis use). ``dev`` reads the training runs' own dev results. Logic in
``ril/evaluation/final_rows.py``. Implements ``docs/RQ2_LAUNCH_PLAN.md`` section 10.6.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main(argv: list[str] | None = None) -> int:
    from ril.evaluation import final_rows as fr
    from ril.evaluation import final_sets, sealed

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("final")
    f.add_argument("--index", required=True)
    f.add_argument("--follows-dev-analysis")
    f.add_argument("--docs-root")
    f.add_argument("--out-rows", required=True)
    d = sub.add_parser("dev")
    d.add_argument("--results", nargs="+", required=True)
    d.add_argument("--out-rows", required=True)
    d.add_argument("--out-runs", required=True)
    a = p.parse_args(argv)
    if a.cmd == "final":
        try:
            rows = fr.final_rows(
                a.index,
                a.follows_dev_analysis,
                docs_root=Path(a.docs_root) if a.docs_root else None,
            )
        except (sealed.SealedOrderError, final_sets.FinalSetsRefused) as err:
            sys.stderr.write(f"refused: {err}\n")
            return 2
        n = fr.write_csv(a.out_rows, fr.ROW_FIELDS, rows)
        sys.stdout.write(json.dumps({"rows": n, "out": a.out_rows}) + "\n")
        return 0
    rows, runs = fr.dev_rows(a.results)
    n = fr.write_csv(a.out_rows, fr.ROW_FIELDS, rows)
    m = fr.write_csv(a.out_runs, fr.RUN_FIELDS, runs)
    sys.stdout.write(json.dumps({"rows": n, "runs": m}) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
