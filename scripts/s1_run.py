"""Graph-role measurement S1 (Q49): evaluation on the cache and tables. Thin wrapper.

Usage:
  s1_run.py eval CONFIG E3_CACHE DENSE_ROOT OUT_DIR
  s1_run.py tables CONFIG OUT_DIR TABLE_PREFIX
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
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    set_seed(args.seed)
    log = get_logger("s1")
    from ril.analysis import s1_tables as st
    from ril.analysis.e3_tables import load_eval_dir
    from ril.analysis.x2_tables import write_csv
    from ril.evaluation.s1_graph_role import run_s1_eval, spec_from_config

    cfg = yaml.safe_load(Path(args.paths[0]).read_text(encoding="utf-8"))
    if args.stage == "eval":
        _, cache, dense_root, out = args.paths
        log.info("%s", run_s1_eval(cfg, cache, dense_root, out))
        return 0
    _, out, prefix = args.paths
    sp, roles = spec_from_config(cfg)
    tab = load_eval_dir(out)
    comp: list[dict[str, object]] = []
    sizes: list[dict[str, object]] = []
    reach: list[dict[str, object]] = []
    for group in roles:
        for w in sp.weights:
            comp += st.comparison_rows(tab, group, w, args.seed)
        sizes += st.size_rows(tab, group)
        reach += st.reach_rows(out, group, args.seed)
    write_csv(f"{prefix}_compare.csv", comp)  # type: ignore[arg-type]
    write_csv(f"{prefix}_sizes.csv", sizes)  # type: ignore[arg-type]
    write_csv(f"{prefix}_reach.csv", reach)  # type: ignore[arg-type]
    log.info("rows %d / %d / %d -> %s_*.csv", len(comp), len(sizes), len(reach), prefix)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
