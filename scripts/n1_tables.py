"""Noise dose-response tables (E-PILOT-NOISE): command line over ``ril.analysis.n1_tables``.

RESULTS_ROOT STEP0_ROWS OUT_DIR LOG [--rates 20 40] [--prefix n1] [--seed S]
[--cells raw filter_bm25 ...] [--stem n1] [--label ...]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    for x in ("results_root", "step0_rows", "out_dir", "log"):
        p.add_argument(x)
    p.add_argument("--rates", nargs="+", type=int, default=[20, 40])
    p.add_argument("--prefix", default="n1")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument(
        "--cells", nargs="+", default=None, help="cells of the run set (default: all six)"
    )
    p.add_argument("--stem", default="n1", help="output table name prefix")
    p.add_argument("--label", default="E-PILOT-NOISE")
    p.add_argument(
        "--mdd-seeds",
        nargs="+",
        default=[],
        metavar="RATE=K",
        help="seeds per arm at a rate for the minimum detectable difference (default 2)",
    )
    a = p.parse_args(argv)
    from ril.analysis import n1_tables as n1
    from ril.analysis import t4_tables as t4

    cells = tuple(a.cells) if a.cells else n1.CELLS
    methods = tuple(m for m in n1.METHODS if m in cells)
    out = n1.noise_tables(
        a.results_root,
        a.prefix,
        a.rates,
        a.step0_rows,
        a.out_dir,
        a.seed,
        cells=cells,
        methods=methods,
        stem_name=a.stem,
        label=a.label,
        mdd_seeds={int(x.split("=")[0]): int(x.split("=")[1]) for x in a.mdd_seeds},
    )
    t4.dump(out, a.log)
    json.dump(
        {k: out[k] for k in ("runs", "reading", "minimum_detectable")},
        sys.stdout,
        indent=1,
        sort_keys=True,
        default=str,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
