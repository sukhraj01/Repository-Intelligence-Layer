"""Dense scores for pilot E6. Thin wrapper over ``ril.evaluation.e6_dense``.

Usage: e6_dense.py E1_CONFIG DATA_ROOT META_JSON REPO_CACHE CACHE_DIR DENSE_DIR WORK_DIR STORE_DIR
                   --roles dev [--only FOLDER] [--limit N]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.evaluation.e6_dense import run_dense  # noqa: E402
from ril.util.log import get_logger  # noqa: E402
from ril.util.seed import set_seed  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("paths", nargs=8)
    ap.add_argument("--roles", nargs="+", default=["dev"])
    ap.add_argument("--only", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    set_seed(args.seed)
    log = get_logger("e6")
    e1_cfg, data_root, meta_json, repo_cache, cache_dir, dense_dir, work_dir, store_dir = args.paths
    with open(meta_json, encoding="utf-8") as handle:
        meta = json.load(handle)
    fails = run_dense(
        e1_cfg,
        set(args.roles),
        data_root,
        meta,
        repo_cache,
        cache_dir,
        dense_dir,
        work_dir,
        store_dir,
        only=args.only,
        limit=args.limit,
    )
    log.info("dense failures: %d", len(fails))
    return 0 if not fails else 2


if __name__ == "__main__":
    raise SystemExit(main())
