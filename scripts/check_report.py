"""Check the hand-written text of the final report and list its open slots.

Thin driver around ``ril.util.report_check``. Exit status 0 when every number of the prose has a
source comment and every citation and reference resolves; the open slots are listed either way.

Usage: python -I scripts/check_report.py [--slots]
"""

# ruff: noqa: T201

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ril.util.report_check import slots, unresolved, untraced_numbers  # noqa: E402

REPORT = ROOT / "reports" / "final" / "final_report.tex"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--slots", action="store_true", help="list the open slots with their entries")
    a = p.parse_args(argv)
    text = REPORT.read_text(encoding="utf-8")
    findings = untraced_numbers(text) + unresolved(text)
    for f in findings:
        print(f.render())
    open_slots = slots(text)
    if a.slots:
        for line, body, entries in open_slots:
            print(f"line {line}: waits for {', '.join(entries) or 'none named'}: {body[:80]}")
    print(f"{len(findings)} finding(s), {len(open_slots)} open slot(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
