"""Add gold readings missing from older cache files (pilot E3 caches).

Usage: e3_add_readings.py CACHE_DIR E1_UNITS_DIR
"""

from __future__ import annotations

import glob
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.evaluation.e3_prepare import add_missing_readings  # noqa: E402


def main() -> int:
    cache_dir, units_dir = sys.argv[1:3]
    n = 0
    for path in sorted(glob.glob(os.path.join(cache_dir, "*.npz"))):
        instance = os.path.basename(path)[: -len(".npz")]
        with open(os.path.join(units_dir, f"{instance}.json"), encoding="utf-8") as handle:
            rec = json.load(handle)
        n += int(add_missing_readings(path, rec))
    sys.stdout.write(f"updated {n} cache files\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
