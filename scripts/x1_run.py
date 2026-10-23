"""Structure measurements X1: per-instance extras, evaluation of the variants, tables. Thin wrapper.

Usage:
  x1_run.py prepare E1_CONFIG DATA_ROOT META_JSON REPO_CACHE X1_CACHE WORK_DIR OUT_DIR E1_UNITS_DIR
            --roles dev [test] [--only FOLDER] [--limit N] [--shard I K]
  x1_run.py eval EVAL_CONFIG E3_CACHE X1_CACHE OUT_DIR
  x1_run.py tables EVAL_CONFIG OUT_DIR TABLE_PREFIX
  x1_run.py sizes X1_CACHE TABLE_PREFIX --roles dev [test]
Writes arrays and counts only (no text).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

from ril.evaluation.x1_prepare import run_x1_prepare  # noqa: E402
from ril.util.log import get_logger  # noqa: E402
from ril.util.seed import set_seed  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("stage", choices=["prepare", "eval", "tables", "sizes"])
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--roles", nargs="+", default=["dev"])
    ap.add_argument("--only", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--shard", nargs=2, type=int, default=[0, 1])
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    set_seed(args.seed)
    log = get_logger("x1")
    if args.stage == "prepare":
        e1_cfg, data_root, meta_json, repo_cache, x1_cache, work_dir, out_dir, units_dir = (
            args.paths
        )
        with open(meta_json, encoding="utf-8") as handle:
            meta = json.load(handle)
        fails = run_x1_prepare(
            e1_cfg,
            set(args.roles),
            data_root,
            meta,
            repo_cache,
            x1_cache,
            work_dir,
            out_dir,
            units_dir,
            only=args.only,
            limit=args.limit,
            shard=(args.shard[0], args.shard[1]),
        )
        log.info("prepare failures: %d", len(fails))
        return 0 if not fails else 2
    if args.stage == "sizes":
        from ril.analysis.e1_tables import write_csv  # noqa: PLC0415
        from ril.analysis.x1_tables import ambiguity_rows, size_rows  # noqa: PLC0415

        x1_cache, prefix = args.paths
        roles = tuple(args.roles)
        write_csv(f"{prefix}_sizes.csv", size_rows(x1_cache, roles))
        write_csv(f"{prefix}_ambiguous.csv", ambiguity_rows(x1_cache, roles))
        return 0
    from ril.evaluation.x1_eval import run_x1_eval, x1_spec  # noqa: PLC0415

    cfg_path = args.paths[0]
    with open(cfg_path, encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle)
    x1_spec(cfg)  # validates the tuning discipline before touching data
    if args.stage == "eval":
        _, e3_cache, x1_cache, out_dir = args.paths
        counts = run_x1_eval(cfg, e3_cache, x1_cache, out_dir)
        log.info("evaluation: %s", counts)
        sys.stdout.write(json.dumps(counts) + "\n")
        return 0
    from ril.analysis.x1_tables import write_x1_tables  # noqa: PLC0415

    _, out_dir, prefix = args.paths
    summary = write_x1_tables(cfg, out_dir, prefix, seed=args.seed)
    sys.stdout.write(json.dumps(summary, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
