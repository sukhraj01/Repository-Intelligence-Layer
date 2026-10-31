"""Matched-pool arms pilot tables (E-PILOT-ARMS2): command line over ``ril.analysis.t5_tables``.

RESULTS_ROOT STEP0_ROWS OUT_DIR LOG [--seed S] [--draws d0 d1 ...] [--mdd-seeds N]
[--stage 2 --stage2-cells RAW SUB CELL ...]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

CELLS = (
    "t5a_raw",
    "t5a_filter_bm25",
    "t5a_filter_srs",
    "t5a_filter_cre",
    "t5a_weight_cre",
    "t5a_curr_cre",
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    for x in ("results_root", "step0_rows", "out_dir", "log"):
        p.add_argument(x)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--draws", nargs="+", default=["t5a_sub_d0"])
    p.add_argument("--mdd-seeds", type=int, default=3)
    p.add_argument("--stage", type=int, choices=[1, 2], default=1)
    p.add_argument("--stage2-cells", nargs="+", default=["t5b_raw", "t5b_sub_d0", "t5b_weight_cre"])
    a = p.parse_args(argv)
    from ril.analysis import t4_tables as t4
    from ril.analysis import t5_tables as t5

    if a.stage == 2:
        out2 = t5.persistence_tables(
            a.results_root,
            a.stage2_cells,
            a.stage2_cells[0],
            a.stage2_cells[1],
            a.step0_rows,
            a.out_dir,
            a.seed,
        )
        t4.dump(out2, a.log)
        return 0
    out = t5.matched_tables(
        a.results_root, CELLS, a.draws, a.step0_rows, a.out_dir, a.seed, a.mdd_seeds
    )
    t4.dump(out, a.log)
    json.dump(
        {k: out[k] for k in ("trigger", "largest_cells", "minimum_detectable", "unique_flags")},
        sys.stdout,
        indent=1,
        sort_keys=True,
        default=str,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
