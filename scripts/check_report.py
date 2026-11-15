"""Check the hand-written text of the final report and list its open slots.

Thin driver around ``ril.util.report_check``. Exit status 0 when every number of the prose has a
source comment and every citation and reference resolves; the open slots are listed either way.

Usage: python -I scripts/check_report.py [--slots]
"""

# ruff: noqa: T201

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ril.util.report_check import (  # noqa: E402
    Finding,
    missing_sources,
    numbers_missing_from_full,
    slots,
    unresolved,
    untraced_numbers,
    untraced_numbers_same_line,
)

REPORT = ROOT / "reports" / "final" / "final_report.tex"
SHORT = ROOT / "reports" / "short" / "short_report.tex"


def _with_fragments(report: Path) -> str:
    """The report source followed by the generated fragments it inputs."""
    parts = [report.read_text(encoding="utf-8")]
    gen = report.parent / "generated"
    parts += (
        [p.read_text(encoding="utf-8") for p in sorted(gen.glob("*.tex"))] if gen.is_dir() else []
    )
    return "\n".join(parts)


def check_short() -> list[Finding]:
    """Same-line source comments, references, stored files, and numbers against the full report."""
    text = SHORT.read_text(encoding="utf-8")
    fragments = _with_fragments(SHORT)
    findings = untraced_numbers_same_line(text) + missing_sources(text, ROOT)
    labels = set(re.findall(r"\\label\{([^}]+)\}", fragments))
    for n, line in enumerate(text.splitlines(), start=1):
        for ref in re.findall(r"\\(?:ref|cref)\{([^}]+)\}", re.split(r"(?<!\\)%", line)[0]):
            if ref not in labels:
                findings.append(Finding(n, "undefined reference", ref))
    findings += numbers_missing_from_full(fragments, _with_fragments(REPORT))
    return findings


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--slots", action="store_true", help="list the open slots with their entries")
    p.add_argument("--short", action="store_true", help="check the two-page report instead")
    a = p.parse_args(argv)
    if a.short:
        short = check_short()
        for f in short:
            print(f.render())
        print(f"{len(short)} finding(s) in the two-page report")
        return 1 if short else 0
    text = REPORT.read_text(encoding="utf-8")
    findings = untraced_numbers(text) + unresolved(text) + missing_sources(text, ROOT)
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
