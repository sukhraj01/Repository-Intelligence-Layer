"""Stored-output analysis (E-STORED-ANALYSIS): command line over ``ril.analysis.stored_analysis``.

RESULTS_ROOT UNITS_DIR OUT_DIR LOG [--draws N] [--seed S]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    for x in ("results_root", "units_dir", "out_dir", "log"):
        p.add_argument(x)
    p.add_argument("--draws", type=int, default=2000)
    p.add_argument("--seed", type=int, default=0)
    a = p.parse_args(argv)
    from ril.analysis import stored_analysis as sa

    log = sa.run_all(a.results_root, a.units_dir, a.out_dir, a.draws, a.seed)
    sa.dump(log, a.log)
    sys.stdout.write(
        f"{log['decomposition']} {log['gain']} {log['complementarity']} {log['noise']}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
