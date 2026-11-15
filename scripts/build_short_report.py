"""Build the two-page report: tables, check, typeset, and verify exactly two pages.

Thin driver around ``ril.util.short_report_build``. Exit status 1 when any problem is found
(overfull box, unresolved reference, a page count other than two, type below 10 pt, margins
below 0.7 in, or a failed source check).

Usage: python -I scripts/build_short_report.py
"""

# ruff: noqa: T201

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from ril.util.short_report_build import build

    problems = build(ROOT)
    for p in problems:
        print(f"short report: {p}")
    if not problems:
        print(f"short report: ok, {ROOT / 'reports' / 'short' / 'short_report.pdf'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
