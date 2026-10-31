"""Arms-pilot stage 1 tables (E-PILOT-ARMS): thin command line over ``ril.analysis.t4_tables``.

RESULTS_ROOT STEP0_ROWS OUT_DIR LOG [--seed S]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

CELLS = (
    "t4a_raw",
    "t4a_noise",
    "t4a_filter_bm25",
    "t4a_filter_srs",
    "t4a_filter_cre",
    "t4a_weight_cre",
    "t4a_curr_cre",
    "t4a_currrev_cre",
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    for x in ("results_root", "step0_rows", "out_dir", "log"):
        p.add_argument(x)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--stage", type=int, choices=[1, 2], default=1)
    a = p.parse_args(argv)
    from ril.analysis import t4_tables as t4

    if a.stage == 2:
        out = t4.persistence_tables(
            a.results_root,
            ("t4b_raw", "t4b_filter_cre", "t4b_curr_cre"),
            "t4b_raw",
            a.step0_rows,
            a.out_dir,
            a.seed,
        )
        t4.dump(out, a.log)
        return 0
    out = t4.arms_tables(a.results_root, CELLS, a.step0_rows, a.out_dir, a.seed)
    t4.dump(out, a.log)
    json.dump(out["trigger"], sys.stdout, indent=1, sort_keys=True, default=str)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
