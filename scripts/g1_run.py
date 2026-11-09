"""Stacked expansion and L3 edge-set measurement G1: evaluation and tables. Thin wrapper.

Usage:
  g1_run.py eval CONFIG E3_CACHE DENSE_ROOT OUT_DIR [--s1-dir DIR]
  g1_run.py tables OUT_DIR TABLE_PREFIX
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

from ril.util.log import get_logger  # noqa: E402
from ril.util.seed import set_seed  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("stage", choices=["eval", "tables"])
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--s1-dir", default=None)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    set_seed(args.seed)
    log = get_logger("g1")
    if args.stage == "eval":
        from ril.evaluation.g1_stacked import run_g1_eval

        cfg = yaml.safe_load(Path(args.paths[0]).read_text(encoding="utf-8"))
        _, cache, dense_root, out = args.paths
        log.info("%s", run_g1_eval(cfg, cache, dense_root, out, args.s1_dir))
        return 0
    from ril.analysis import g1_tables as gt
    from ril.analysis.e3_tables import load_eval_dir
    from ril.analysis.x2_tables import write_csv

    out, prefix = args.paths
    tab = load_eval_dir(out)
    rows, per_repo = gt.contrast_rows(tab, "dev", args.seed)
    write_csv(f"{prefix}_contrasts.csv", rows)  # type: ignore[arg-type]
    write_csv(f"{prefix}_per_repo.csv", per_repo)  # type: ignore[arg-type]
    write_csv(f"{prefix}_sizes.csv", gt.size_rows(tab, "dev"))  # type: ignore[arg-type]
    write_csv(f"{prefix}_query_rows.csv", gt.query_rows(tab))  # type: ignore[arg-type]
    log.info("contrasts %d, per repo %d -> %s_*.csv", len(rows), len(per_repo), prefix)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
