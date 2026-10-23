"""Dense and fusion measurements X2, local half: evaluation on the cache and tables. Thin wrapper.

Usage:
  x2_tables.py eval CONFIG E3_CACHE DENSE_ROOT OUT_DIR
  x2_tables.py first CONFIG OUT_DIR TABLE_PREFIX [--selection JSON]
  x2_tables.py graph CONFIG OUT_DIR TABLE_PREFIX
  x2_tables.py chunks CONFIG CHUNK_DIR TABLE_PREFIX --variants V.. [--selection JSON]
Configurations name their roles; a test configuration takes the dev selection file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

from ril.util.log import get_logger  # noqa: E402
from ril.util.seed import set_seed  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("stage", choices=["eval", "first", "graph", "chunks"])
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--selection", default=None)
    ap.add_argument("--variants", nargs="*", default=[])
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    set_seed(args.seed)
    log = get_logger("x2")
    from ril.analysis import x2_tables as xt
    from ril.analysis.e3_tables import load_eval_dir
    from ril.evaluation.x2_eval import run_x2_eval

    cfg = yaml.safe_load(Path(args.paths[0]).read_text(encoding="utf-8"))
    group = "test" if "test" in cfg["roles"] else "dev"
    given = json.loads(Path(args.selection).read_text()) if args.selection else None
    if args.stage == "eval":
        _, cache, dense_root, out = args.paths
        log.info("%s", run_x2_eval(cfg, cache, dense_root, out))
        return 0
    if args.stage == "first":
        _, out, prefix = args.paths
        fc = cfg["first"]
        rows, sel = xt.first_report(
            load_eval_dir(out),
            fc["variants"],
            fc.get("rrf_ks", []),
            fc.get("alphas", []),
            group,
            args.seed,
            given,
        )
    elif args.stage == "graph":
        _, out, prefix = args.paths
        rows = xt.graph_report(load_eval_dir(out), group, args.seed)
        sel = {"graph": xt.select_graph(rows)} if group == "dev" else {}
    else:
        _, chunk_dir, prefix = args.paths
        rows_q, cols = xt.load_chunk_dir(chunk_dir)
        rows, sel = xt.chunk_report(
            rows_q, cols, args.variants, cfg["first"]["rrf_ks"], group, args.seed, given
        )
    xt.write_csv(f"{prefix}.csv", rows)
    if sel and given is None:
        Path(f"{prefix}_selection.json").write_text(json.dumps(sel, indent=1, sort_keys=True))
    log.info("rows %d -> %s.csv", len(rows), prefix)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
