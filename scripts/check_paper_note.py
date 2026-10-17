"""Check a paper note against the text extracted from its PDF.

Thin driver around ``ril.util.paper_note``. Exit status 0 when the note passes.

Usage: python -I scripts/check_paper_note.py NOTE.md EXTRACTED.txt [--pdf PAPER.pdf]
  EXTRACTED.txt is ``pdftotext -layout PAPER.pdf EXTRACTED.txt`` (pages separated by form feeds).
  With --pdf the declared page count is also compared with ``pdfinfo``.
"""

# ruff: noqa: T201

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ril.util.paper_note import check_note, pdf_page_count  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("note", type=Path)
    ap.add_argument("text", type=Path)
    ap.add_argument("--pdf", type=Path, default=None)
    args = ap.parse_args()
    note = args.note.read_text(encoding="utf-8")
    text = args.text.read_text(encoding="utf-8")
    rep = check_note(note, text)
    if args.pdf is not None and rep.declared_pages is not None:
        n = pdf_page_count(args.pdf)
        if n != rep.declared_pages:
            rep.errors.append(f"note declares {rep.declared_pages} pages, pdfinfo says {n}")
    for w in rep.warnings:
        print(f"warning: {w}")
    for e in rep.errors:
        print(f"error: {e}")
    status = "PASS" if rep.ok else "FAIL"
    print(
        f"{status} {args.note} pages declared={rep.declared_pages} extracted={rep.extracted_pages} "
        f"numbers checked={rep.checked_numbers}"
    )
    return 0 if rep.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
