"""Run pilot E1/E2 stages on a data root. Thin wrapper around ``ril.evaluation.e1_run``.

Usage:
  e1_run.py chunk CONFIG DATA_ROOT OUT_DIR [--only FOLDER]
  e1_run.py units CONFIG DATA_ROOT META_JSON CACHE_DIR WORK_DIR OUT_DIR [--only FOLDER]
Writes JSON records (ids, ranks, paths, lines; no text) under OUT_DIR.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.evaluation.e1_run import config_hash, load_config, run_chunk_level, run_unit_level  # noqa: E402
from ril.util.log import get_logger  # noqa: E402
from ril.util.seed import set_seed  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("stage", choices=["chunk", "units"])
    ap.add_argument("config")
    ap.add_argument("data_root")
    ap.add_argument("rest", nargs="*")
    ap.add_argument("--only", default=None)
    args = ap.parse_args()
    cfg = load_config(args.config)
    set_seed(int(cfg["seed"]))
    log = get_logger("e1")
    log.info("config hash %s", config_hash(cfg))
    if args.stage == "chunk":
        (out_dir,) = args.rest
        n = run_chunk_level(cfg, args.data_root, out_dir, only=args.only)
        log.info("chunk-level items done: %d", n)
        return 0
    meta_json, cache_dir, work_dir, out_dir = args.rest
    with open(meta_json, encoding="utf-8") as handle:
        meta = json.load(handle)
    fails = run_unit_level(cfg, args.data_root, meta, cache_dir, work_dir, out_dir, only=args.only)
    n_fail = sum(len(v) for v in fails.values())
    log.info("unit-level failures: %d", n_fail)
    return 0 if n_fail == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
