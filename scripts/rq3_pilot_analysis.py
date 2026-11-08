"""Write the RQ3 pilot analysis tables from the stored call log (no network, no model).

Thin wrapper around ``ril.analysis.rq3_pilot_analysis``. Usage:
rq3_pilot_analysis.py LOG PREPARED OUT --seed 0
(the bootstrap seed is fixed in the module; the argument is recorded for the run log).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.analysis import rq3_pilot_analysis as ana  # noqa: E402
from ril.util.log import get_logger  # noqa: E402
from ril.util.seed import set_seed  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("log")
    ap.add_argument("prepared")
    ap.add_argument("out")
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument(
        "--gold-rows",
        default=str(ROOT / "results/rq3/assembly_gold_2026-11-06/assembly_gold_query_rows.csv"),
    )
    ap.add_argument(
        "--dev-summary", default=str(ROOT / "results/tables/assembly/assembly_gold_summary.csv")
    )
    ap.add_argument(
        "--coverage", default=str(ROOT / "results/rq3_contexts/rq3_contexts_coverage.csv")
    )
    args = ap.parse_args()
    set_seed(args.seed)
    head = ana.run_all(
        Path(args.log).expanduser(),
        Path(args.prepared).expanduser(),
        Path(args.gold_rows),
        Path(args.dev_summary),
        Path(args.coverage),
        Path(args.out),
    )
    get_logger("rq3_pilot_analysis").info("wrote tables to %s: %s", args.out, head)
    return 0


if __name__ == "__main__":
    sys.exit(main())
