"""Curve tables of E-PILOT-CURVE (thin wrapper over ``ril.analysis.t3_tables``).

  python -I scripts/t3_tables.py OUT_DIR --run SEED=RUN_DIR [--run SEED=RUN_DIR ...]

Writes ``t3_curve_rows.csv`` and ``t3_decision.json`` to OUT_DIR and prints the decision.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.analysis.t3_tables import all_tables, load_runs  # noqa: E402
from ril.analysis.x2_tables import write_csv  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("out_dir")
    p.add_argument("--run", action="append", required=True, help="SEED=RUN_DIR")
    a = p.parse_args(argv)
    runs = load_runs({int(x.split("=", 1)[0]): x.split("=", 1)[1] for x in a.run})
    rows, decision = all_tables(runs)
    os.makedirs(a.out_dir, exist_ok=True)
    write_csv(os.path.join(a.out_dir, "t3_curve_rows.csv"), rows)
    with open(os.path.join(a.out_dir, "t3_decision.json"), "w", encoding="utf-8") as handle:
        json.dump(decision, handle, indent=1, sort_keys=True)
    sys.stdout.write(json.dumps(decision, indent=1, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
