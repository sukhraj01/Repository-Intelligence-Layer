"""Write the RQ3 power table (exact and normal minimum detectable effects).

Thin wrapper around ``ril.analysis.rq3_power``. Usage: rq3_power.py OUT.csv --seed 0
(no randomness is used; the seed is recorded for the run log).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.analysis import rq3_power  # noqa: E402
from ril.util.log import get_logger  # noqa: E402
from ril.util.seed import set_seed  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out")
    ap.add_argument("--seed", type=int, required=True)
    args = ap.parse_args()
    set_seed(args.seed)
    rows = rq3_power.build_rows()
    Path(args.out).write_text(rq3_power.to_csv(rows))
    get_logger("rq3_power").info("wrote %d rows to %s", len(rows), args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
