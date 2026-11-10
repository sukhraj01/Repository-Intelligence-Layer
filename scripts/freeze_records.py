"""Write or verify the configuration freeze records of ``configs/frozen/``. Thin wrapper.

Usage:
  freeze_records.py write ROOT DATE     (refuses to overwrite an existing record)
  freeze_records.py verify ROOT         (exit 1 and the list of problems if anything changed)
The logic is in ``ril.bench.freeze``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.bench.freeze import verify, write_records  # noqa: E402
from ril.util.log import get_logger  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=["write", "verify"])
    ap.add_argument("root")
    ap.add_argument("date", nargs="?", default="")
    args = ap.parse_args()
    log = get_logger("freeze")
    if args.action == "write":
        if not args.date:
            ap.error("write needs a DATE")
        for path in write_records(args.root, args.date):
            log.info("wrote %s", path)
        return 0
    problems = verify(args.root)
    for p in problems:
        log.error("%s", p)
    log.info("%d problem(s)", len(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
