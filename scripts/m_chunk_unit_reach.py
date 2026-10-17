"""Run pilot M (chunk-to-unit mapping and graph reach) on a data root. Thin wrapper.

Usage: m_chunk_unit_reach.py DATA_ROOT PARQUET CACHE_DIR WORK_DIR OUT_DIR --seed N [--draws N]
       [--force] REPO [REPO ...]      (REPO is owner__name)
Writes OUT_DIR/records.json (ids, paths, lines, unit ids; no chunk text) and one file per instance.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.evaluation.chunk_unit_pilot import (  # noqa: E402
    DEFAULT_DRAWS,
    read_base_commits,
    run_pilot,
)
from ril.util.log import get_logger  # noqa: E402
from ril.util.seed import set_seed  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("data_root")
    ap.add_argument("parquet")
    ap.add_argument("cache_dir")
    ap.add_argument("work_dir")
    ap.add_argument("out_dir")
    ap.add_argument("repos", nargs="+")
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--draws", type=int, default=DEFAULT_DRAWS)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    set_seed(args.seed)
    log = get_logger("pilot_m")
    doc = run_pilot(
        data_root=args.data_root,
        repos=args.repos,
        base_commits=read_base_commits(args.parquet),
        cache_dir=args.cache_dir,
        work_dir=args.work_dir,
        out_dir=args.out_dir,
        seed=args.seed,
        draws=args.draws,
        force=args.force,
    )
    log.info(
        "instances=%d failures=%d hash=%s",
        len(doc["instances"]),
        len(doc["failures"]),
        doc["config_hash"][:12],
    )
    return 0 if not doc["failures"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
