"""RQ1 ladder (E-RQ1-LADDER): evaluation on the dev cache, inventory and tables. Thin wrapper.

Usage:
  rq1_ladder.py eval CONFIG E3_CACHE DENSE_ROOT OUT_DIR
  rq1_ladder.py inventory E3_CACHE DENSE_ROOT VARIANT [VARIANT ...]
  rq1_ladder.py tables ROOT DATE LABEL=EVAL_DIR [LABEL=EVAL_DIR ...] [--env KEY=VALUE ...]
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
    ap.add_argument("stage", choices=["eval", "inventory", "tables"])
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--env", nargs="*", default=[])
    args = ap.parse_args()
    set_seed(args.seed)
    log = get_logger("rq1_ladder")
    if args.stage == "eval":
        from ril.evaluation.rq1_ladder import run_ladder_eval

        cfg = yaml.safe_load(Path(args.paths[0]).read_text(encoding="utf-8"))
        _, cache, dense_root, out = args.paths
        log.info("%s", run_ladder_eval(cfg, cache, dense_root, out))
    elif args.stage == "inventory":
        from ril.evaluation.rq1_ladder import inventory

        cache, dense_root, *variants = args.paths
        inv = inventory(cache, {v: dense_root for v in variants})
        sys.stdout.write(json.dumps(inv, indent=2, sort_keys=True) + "\n")
    else:
        from ril.analysis.rq1_ladder import write_outputs

        root, date, *pairs = args.paths
        dirs = dict(p.split("=", 1) for p in pairs)
        env = dict(e.split("=", 1) for e in args.env)
        done = write_outputs(dirs, root, date, args.seed, env=env)
        log.info("%s", done)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
