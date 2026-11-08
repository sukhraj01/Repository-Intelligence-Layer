"""Final-report tables: command line over ``ril.analysis.report_tables``.

[--results-root DIR] [--out-dir DIR]. Reads ``results/`` and writes the LaTeX fragments that
``reports/final/final_report.tex`` inputs; every number comes from a stored file.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--results-root", type=Path, default=ROOT, help="repository root holding results/"
    )
    p.add_argument("--out-dir", type=Path, default=ROOT / "reports" / "final" / "generated")
    a = p.parse_args(argv)
    from ril.analysis import report_tables

    tables = report_tables.write_all(a.results_root, a.out_dir)
    sys.stdout.write(f"{len(tables)} fragments in {a.out_dir}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
