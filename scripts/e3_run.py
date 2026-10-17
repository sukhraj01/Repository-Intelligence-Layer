"""Run the graph-signal pilots (E3 to E5): per-instance cache, then evaluation. Thin wrapper.

Usage:
  e3_run.py prepare E1_CONFIG DATA_ROOT META_JSON REPO_CACHE CACHE_DIR WORK_DIR OUT_DIR E1_UNITS_DIR
            --roles dev [test] [--only FOLDER] [--limit N] [--shard I K]
  e3_run.py eval EVAL_CONFIG CACHE_DIR OUT_DIR
Writes arrays and counts only (no text).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

from ril.evaluation.e3_eval import eval_hash, run_eval, spec_from_config  # noqa: E402
from ril.evaluation.e3_prepare import run_prepare  # noqa: E402
from ril.util.log import get_logger  # noqa: E402
from ril.util.seed import set_seed  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("stage", choices=["prepare", "eval"])
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--roles", nargs="+", default=["dev"])
    ap.add_argument("--only", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--shard", nargs=2, type=int, default=[0, 1])
    ap.add_argument("--dense-dir", default=None)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    set_seed(args.seed)
    log = get_logger("e3")
    if args.stage == "prepare":
        e1_cfg, data_root, meta_json, repo_cache, cache_dir, work_dir, out_dir, units_dir = (
            args.paths
        )
        with open(meta_json, encoding="utf-8") as handle:
            meta = json.load(handle)
        fails = run_prepare(
            e1_cfg,
            set(args.roles),
            data_root,
            meta,
            repo_cache,
            cache_dir,
            work_dir,
            out_dir,
            units_dir,
            only=args.only,
            limit=args.limit,
            shard=(args.shard[0], args.shard[1]),
        )
        log.info("prepare failures: %d", len(fails))
        return 0 if not fails else 2
    cfg_path, cache_dir, out_dir = args.paths
    with open(cfg_path, encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle)
    spec_from_config(cfg)  # validates the tuning discipline before touching data
    log.info("eval config %s", cfg_path)
    counts = run_eval(cfg, cache_dir, out_dir, args.dense_dir)
    log.info("evaluation: %s", counts)
    sys.stdout.write(json.dumps({"eval_hash_of_config": eval_hash(cfg, ""), **counts}) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
