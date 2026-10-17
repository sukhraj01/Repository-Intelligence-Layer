"""Confirm one stated BM25 setting on the test folders (pilot E1, exploratory).

Usage: e1_confirm.py CONFIG DATA_ROOT OUT_DIR K1 B
The setting must be stated (and recorded) before this runs; it is never chosen on these folders.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ril.evaluation.e1_run import load_config, run_confirm  # noqa: E402
from ril.util.log import get_logger  # noqa: E402


def main() -> int:
    cfg_path, data_root, out_dir, k1, b = sys.argv[1:6]
    n = run_confirm(load_config(cfg_path), data_root, out_dir, float(k1), float(b))
    get_logger("e1_confirm").info("items: %d", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
