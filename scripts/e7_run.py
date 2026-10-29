"""Encoder numbers E7, CPU half: paired encoder comparison and class-form table. Thin wrapper.

Usage:
  e7_run.py pair EVAL_FIRST_DIR GROUP OUT_PREFIX
  e7_run.py form E3_CACHE X1_CACHE DENSE_ROOT OUT_PREFIX [--role dev]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.util.log import get_logger  # noqa: E402
from ril.util.seed import set_seed  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("stage", choices=["pair", "form"])
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--role", default="dev")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    set_seed(args.seed)
    log = get_logger("e7")
    from ril.analysis import e7_tables as et

    if args.stage == "pair":
        ev, group, prefix = args.paths
        n = et.write_pair(ev, group, prefix, args.seed)
    else:
        e3, x1, dense, prefix = args.paths
        n = et.write_form(e3, x1, dense, args.role, prefix, args.seed)
    log.info("wrote %d rows", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
