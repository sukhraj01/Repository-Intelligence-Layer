"""Check a paper note against the text extracted from the paper's PDF.

Why: a paper counts as a source only after it has been read in full, and every figure quoted from it
must be traceable to the paper. A note starts with a ``read:`` line (page count, PDF version,
method, date) and holds a table of numbers that may be quoted. This module verifies that the
extracted text has as many pages as the note says, that no page is blank, and that every number in
that table occurs in the extracted text (on the stated page when one is given).
A note that skipped part of its document (for example numbered source listings inside appendix
trajectories) may not say ``read: full``: it uses the qualified header
``read: in full except <part> (pp. A to B); <what was read of it> was read — N pages ...``, and no
number in its table may sit on a skipped page. Implements ``knowledge/papers/README.md`` (note
format); used by ``scripts/check_paper_note.py``.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

READ_FULL = re.compile(
    r"^read: full — (?P<pages>\d+) pages incl\. appendices, PDF v(?P<ver>\S+), "
    r"(?P<method>.+), (?P<date>\d{4}-\d{2}-\d{2})\s*$"
)
READ_PARTIAL = re.compile(
    r"^read: in full except (?P<part>[^;]+?) \(pp\. (?P<lo>\d+) to (?P<hi>\d+)\); "
    r"(?P<what>.+?) (?:was|were) read — (?P<pages>\d+) pages incl\. appendices, PDF v(?P<ver>\S+), "
    r"(?P<method>.+), (?P<date>\d{4}-\d{2}-\d{2})\s*$"
)
# Wording that says part of the paper's own document was not read; a plain "read: full" header may
# not sit above any of it. ("v1 was not read in full" about another version is not matched.)
SKIP_MARKERS = re.compile(
    r"depth caveat|not read line by line|\b(?:was|were) (?:filtered out|skipped)\b|\bskipped\b"
    r"|\bpages? \d+(?:\s*[–-]\s*\d+)? (?:was|were) not read",
    re.IGNORECASE,
)
READ_NONE = re.compile(r"^read: NOT READ \((?P<reason>.+)\)\s*$")
NUMBER = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?")
PAGE_REF = re.compile(r"\bpp?\.\s*(?P<refs>\d+(?:\s*(?:[,–-]|and)\s*\d+)*)")
MIN_PAGE_CHARS = 40
NUMBERS_HEADING = "numbers we may quote"
EXPECTED_HEADINGS = (
    "what it established",
    "what it did not establish",
    "numbers we may quote",
    "method details",
    "relation to",
    "discrepancies",
    "claims checked",
)


@dataclass
class NoteReport:
    """Outcome of checking one note; ``errors`` empty means the note passes."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checked_numbers: int = 0
    declared_pages: int | None = None
    extracted_pages: int | None = None

    @property
    def ok(self) -> bool:
        return not self.errors


def split_pages(text: str) -> list[str]:
    """Split ``pdftotext`` output on form feeds; a trailing empty piece is not a page."""
    pages = text.split("\f")
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    return pages


def pdf_page_count(pdf: Path) -> int:
    """Page count reported by ``pdfinfo``."""
    out = subprocess.run(["pdfinfo", str(pdf)], check=True, capture_output=True, text=True).stdout
    for line in out.splitlines():
        if line.startswith("Pages:"):
            return int(line.split()[1])
    raise ValueError(f"pdfinfo printed no page count for {pdf}")


def number_present(number: str, haystack: str) -> bool:
    """True if the number occurs as a whole token (commas optional) in ``haystack``."""
    bare = number.replace(",", "")
    variants = {number, bare}
    if re.fullmatch(r"\d+", bare) and len(bare) > 3:
        variants.add(f"{int(bare):,}")
    for v in variants:
        if re.search(rf"(?<![\d.,]){re.escape(v)}(?!\d)(?!\.\d)", haystack):
            return True
    return False


def parse_page_refs(cell: str) -> list[int]:
    """Page numbers named in a 'where' cell such as ``p.5``, ``pp. 12-13`` or ``p.3, 14``."""
    pages: list[int] = []
    for m in PAGE_REF.finditer(cell):
        refs = m.group("refs")
        if re.search(r"\d\s*[–-]\s*\d", refs):
            lo, hi = (int(x) for x in re.split(r"\s*[–-]\s*", refs.strip())[:2])
            pages.extend(range(lo, hi + 1))
        else:
            pages.extend(int(x) for x in re.findall(r"\d+", refs))
    return pages


def numbers_section(note: str) -> list[str] | None:
    """Table rows (as raw lines) of the 'Numbers we may quote' section, or None if absent."""
    lines = note.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith("#") and NUMBERS_HEADING in line.lower():
            start = i + 1
            break
    if start is None:
        return None
    rows: list[str] = []
    for line in lines[start:]:
        if line.startswith("#"):
            break
        if line.strip().startswith("|"):
            rows.append(line.strip())
    return rows


def _cells(row: str) -> list[str]:
    return [c.strip() for c in row.strip().strip("|").split("|")]


def check_note(note: str, text: str) -> NoteReport:
    """Check ``note`` (markdown) against the extracted ``text`` of its paper."""
    rep = NoteReport()
    first = next((ln for ln in note.splitlines() if ln.strip()), "")
    rows = numbers_section(note)
    m_none = READ_NONE.match(first)
    m_full = READ_FULL.match(first)
    m_part = READ_PARTIAL.match(first)
    if m_none:
        data_rows = [r for r in (rows or []) if not _is_header_or_rule(r)]
        if data_rows:
            rep.errors.append("note says NOT READ but lists numbers that may be quoted")
        return rep
    if not (m_full or m_part):
        rep.errors.append(
            "first line is not 'read: full — N pages incl. appendices, PDF vK, method, date', "
            "'read: in full except <part> (pp. A to B); <what was read> was read — N pages ...' "
            "or 'read: NOT READ (reason)'"
        )
        return rep
    skipped: range | None = None
    if m_full:
        marker = SKIP_MARKERS.search(note)
        if marker:
            rep.errors.append(
                f"header says 'read: full' but the note describes a skipped part "
                f"({marker.group(0)!r}); "
                "use 'read: in full except <part> (pp. A to B); <what was read> was read — ...'"
            )
        declared = int(m_full.group("pages"))
    else:
        assert m_part is not None
        declared = int(m_part.group("pages"))
        lo, hi = int(m_part.group("lo")), int(m_part.group("hi"))
        if not 1 <= lo <= hi <= declared:
            rep.errors.append(f"skipped range pp. {lo} to {hi} is not inside 1..{declared}")
        skipped = range(lo, hi + 1)
    pages = split_pages(text)
    rep.declared_pages, rep.extracted_pages = declared, len(pages)
    if len(pages) != declared:
        rep.errors.append(f"note declares {declared} pages, extracted text has {len(pages)}")
    for i, p in enumerate(pages, start=1):
        if len("".join(p.split())) < MIN_PAGE_CHARS:
            rep.errors.append(f"extracted page {i} is blank or nearly blank")
    lowered = note.lower()
    for h in EXPECTED_HEADINGS:
        if not any(ln.startswith("#") and h in ln.lower() for ln in lowered.splitlines()):
            rep.warnings.append(f"missing section: {h}")
    if rows is None:
        rep.errors.append("no 'Numbers we may quote' section")
        return rep
    header: list[str] | None = None
    vcol = wcol = -1
    for row in rows:
        cells = _cells(row)
        if _is_rule(row):
            continue
        if header is None:
            header = [c.lower() for c in cells]
            vcol = next((i for i, c in enumerate(header) if "value" in c), -1)
            wcol = next((i for i, c in enumerate(header) if "where" in c), -1)
            if vcol < 0 or wcol < 0:
                rep.errors.append("numbers table needs 'Value' and 'Where' columns")
                return rep
            continue
        if len(cells) <= max(vcol, wcol):
            rep.errors.append(f"short table row: {row[:60]}")
            continue
        value, where = cells[vcol], cells[wcol]
        nums = [n.rstrip(",") for n in NUMBER.findall(value)]
        refs = parse_page_refs(where)
        bad_refs = [p for p in refs if not 1 <= p <= len(pages)]
        in_skipped = [p for p in refs if skipped is not None and p in skipped]
        if in_skipped:
            rep.errors.append(f"number cites skipped page(s) {in_skipped}: {cells[0][:50]}")
            continue
        if bad_refs:
            rep.errors.append(f"page reference out of range {bad_refs}: {cells[0][:50]}")
            continue
        scope = "\n".join(pages[p - 1] for p in refs) if refs else text
        for n in nums:
            rep.checked_numbers += 1
            if not number_present(n, scope):
                loc = f"on page(s) {refs}" if refs else "anywhere"
                rep.errors.append(f"number {n} not found {loc}: {cells[0][:50]}")
    return rep


def _is_rule(row: str) -> bool:
    return bool(re.fullmatch(r"\|?[\s:|-]+\|?", row))


def _is_header_or_rule(row: str) -> bool:
    if _is_rule(row):
        return True
    return "value" in row.lower() and "where" in row.lower()
