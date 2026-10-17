"""Sweep BM25 k1 and b on the development folders only (pilot E1, exploratory).

Usage: e1_dev_sweep.py CONFIG DATA_ROOT OUT_DIR
Grid: k1 in {0.9, 1.2, 1.5, 2.0}, b in {0.4, 0.6, 0.75, 0.9}. Test folders are never read.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ril.evaluation.e1_run import load_config, run_dev_sweep  # noqa: E402
from ril.util.log import get_logger  # noqa: E402

GRID = [(k1, b) for k1 in (0.9, 1.2, 1.5, 2.0) for b in (0.4, 0.6, 0.75, 0.9)]


def main() -> int:
    cfg_path, data_root, out_dir = sys.argv[1:4]
    done = run_dev_sweep(load_config(cfg_path), data_root, out_dir, GRID)
    get_logger("e1_sweep").info("cells done: %d", len(done))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
