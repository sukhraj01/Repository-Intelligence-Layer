"""Checkpoint inventory (E-STORED-ANALYSIS): command line over ``checkpoint_inventory``.

RESULTS_ROOT LISTING OUT_CSV LOG
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    for x in ("results_root", "listing", "out_csv", "log"):
        p.add_argument(x)
    a = p.parse_args(argv)
    from ril.analysis import checkpoint_inventory as ci

    rows = ci.build(a.results_root, a.listing)
    ci.write(rows, a.out_csv)
    summary = ci.summarise(rows, a.listing)
    Path(a.log).write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    sys.stdout.write(json.dumps(summary, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
