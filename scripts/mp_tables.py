"""Mined-set integration pilot tables (E-MINED-PILOT): command line over ``ril.analysis.mp_tables``.

RESULTS_ROOT STEP0_ROWS OUT_DIR LOG [--seed S] [--draws N]
RESULTS_ROOT is the folder that holds ``rq2/`` (and so ``rq2/mp_raw``, ``rq2/t5a_raw``, ...).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    for x in ("results_root", "step0_rows", "out_dir", "log"):
        p.add_argument(x)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--draws", type=int, default=300)
    a = p.parse_args(argv)
    from ril.analysis import mp_tables as mp
    from ril.analysis import t4_tables as t4

    effects, spread, uniq = mp.effect_tables(a.results_root, a.step0_rows, a.out_dir, a.seed)
    mdd = mp.minimum_detectable_rows(
        os.path.join(a.results_root, "rq2"), a.out_dir, draws=a.draws, seed=a.seed
    )
    log = {
        "version": mp.MP_TABLES_VERSION,
        "effects": len(effects),
        "seeds": len(spread),
        "unique": len(uniq),
        "mdd": mdd,
    }
    t4.dump(log, a.log)
    json.dump({"unique": uniq, "mdd": mdd}, sys.stdout, indent=1, sort_keys=True, default=str)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
