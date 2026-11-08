"""Unit tests for the paper-note checker (``ril.util.paper_note``)."""

from __future__ import annotations

from pathlib import Path

from ril.util.paper_note import (
    check_note,
    number_present,
    parse_page_refs,
    split_pages,
)

PAGE1 = "Title of the paper. We train on 9,377,120 chunks and obtain 13.0 at the top. " * 2
PAGE2 = "Second page with Table 3 showing 62.0 percent and a value of 113.5 elsewhere in text. " * 2
TEXT = PAGE1 + "\f" + PAGE2 + "\f"

HEAD = "read: full — 2 pages incl. appendices, PDF v1, pdftotext -layout, 2026-10-17\n\n"
SECTIONS = (
    "## What it established\n- x\n## What it did not establish\n- y\n## Method details\n- z\n"
    "## Relation to RQ1/RQ2/RQ3\n- r\n## Discrepancies\n- d\n## Claims checked\n- c\n"
)


def _note(rows: str, head: str = HEAD) -> str:
    table = "## Numbers we may quote\n\n| Claim | Value | Where |\n|---|---|---|\n" + rows + "\n"
    return head + SECTIONS + table


def test_split_pages_drops_trailing_empty_piece() -> None:
    assert len(split_pages(TEXT)) == 2
    assert len(split_pages("a\fb")) == 2


def test_number_present_whole_token_and_commas() -> None:
    assert number_present("13.0", PAGE1)
    assert number_present("9377120", PAGE1)  # comma-free form of a comma-grouped number
    assert not number_present("3.0", PAGE1)  # inside 13.0
    assert not number_present("113", PAGE1)
    assert number_present("113.5", PAGE2)
    assert not number_present("13.5", PAGE2)  # inside 113.5


def test_parse_page_refs() -> None:
    assert parse_page_refs("p.5") == [5]
    assert parse_page_refs("pp. 3-5, Table 2") == [3, 4, 5]
    assert parse_page_refs("p.3, 14") == [3, 14]
    assert parse_page_refs("Table 2") == []


def test_passing_note() -> None:
    rows = "| chunks | 9,377,120 | p.1 |\n| score | 13.0 / 62.0 | p.1; p.2 |"
    rep = check_note(_note(rows), TEXT)
    assert rep.errors == [], rep.errors
    assert rep.ok
    assert rep.checked_numbers == 3


def test_number_not_on_declared_page_fails() -> None:
    rep = check_note(_note("| score | 62.0 | p.1 |"), TEXT)
    assert not rep.ok
    assert any("62.0" in e and "page" in e for e in rep.errors)


def test_number_absent_from_text_fails() -> None:
    rep = check_note(_note("| invented | 55.5 | |"), TEXT)
    assert not rep.ok
    assert any("55.5" in e for e in rep.errors)


def test_page_count_mismatch_fails() -> None:
    rep = check_note(_note("| chunks | 13.0 | p.1 |", HEAD.replace("2 pages", "3 pages")), TEXT)
    assert not rep.ok
    assert any("declares 3 pages" in e for e in rep.errors)


def test_blank_page_fails() -> None:
    rep = check_note(_note("| chunks | 13.0 | p.1 |"), PAGE1 + "\f  \n\f" + PAGE2 + "\f")
    assert any("blank" in e for e in rep.errors)


def test_page_ref_out_of_range_fails() -> None:
    rep = check_note(_note("| chunks | 13.0 | p.9 |"), TEXT)
    assert any("out of range" in e for e in rep.errors)


def test_bad_first_line_fails() -> None:
    rep = check_note("# Note\n" + _note("| a | 13.0 | |"), TEXT)
    assert not rep.ok
    assert any("first line" in e for e in rep.errors)


def test_not_read_note_must_not_quote_numbers() -> None:
    clean = (
        "read: NOT READ (no PDF available)\n\n## Numbers we may quote\n\n"
        "| Claim | Value | Where |\n|---|---|---|\n"
    )
    assert check_note(clean, TEXT).ok
    dirty = clean + "| x | 13.0 | p.1 |\n"
    assert not check_note(dirty, TEXT).ok


def test_missing_numbers_section_fails() -> None:
    rep = check_note(HEAD + SECTIONS, TEXT)
    assert any("Numbers we may quote" in e for e in rep.errors)


def test_missing_other_sections_only_warn() -> None:
    table = "| Claim | Value | Where |\n|---|---|---|\n| a | 13.0 | p.1 |\n"
    note = HEAD + "## Numbers we may quote\n\n" + table
    rep = check_note(note, TEXT)
    assert rep.ok
    assert rep.warnings


PARTIAL = (
    "read: in full except the numbered source-code listings inside the appendix trajectories "
    "(pp. 2 to 2); every agent turn, error message, patch and summary was read — 2 pages incl. "
    "appendices, PDF v1, pdftotext -layout, 2026-11-08\n\n"
)


def test_qualified_header_passes() -> None:
    rep = check_note(_note("| chunks | 9,377,120 | p.1 |", PARTIAL), TEXT)
    assert rep.errors == [], rep.errors


def test_plain_full_header_with_skipped_part_fails() -> None:
    note = (
        _note("| chunks | 13.0 | p.1 |")
        + "\nDepth caveat: pages 2 were filtered out and not read line by line.\n"
    )
    rep = check_note(note, TEXT)
    assert not rep.ok
    assert any("skipped part" in e for e in rep.errors)


def test_plain_full_header_may_mention_other_versions_not_read() -> None:
    note = (
        _note("| chunks | 13.0 | p.1 |")
        + "\nv1 (found by search, v1 not read in full) says otherwise.\n"
    )
    assert check_note(note, TEXT).ok


def test_qualified_header_number_on_skipped_page_fails() -> None:
    rep = check_note(_note("| score | 62.0 | p.2 |", PARTIAL), TEXT)
    assert any("skipped page" in e for e in rep.errors)


def test_qualified_header_range_outside_document_fails() -> None:
    bad = PARTIAL.replace("(pp. 2 to 2)", "(pp. 2 to 9)")
    rep = check_note(_note("| chunks | 13.0 | p.1 |", bad), TEXT)
    assert any("not inside" in e for e in rep.errors)


def test_qualified_header_page_count_mismatch_fails() -> None:
    rep = check_note(
        _note("| chunks | 13.0 | p.1 |", PARTIAL.replace("— 2 pages", "— 3 pages")), TEXT
    )
    assert any("declares 3 pages" in e for e in rep.errors)


def test_repository_notes_never_hide_a_skipped_part() -> None:
    """Every tracked note either says 'read: in full except' or describes no skipped part."""
    from ril.util.paper_note import READ_FULL, SKIP_MARKERS

    root = Path(__file__).resolve().parents[2] / "knowledge" / "papers"
    for path in sorted(root.glob("*.md")):
        note = path.read_text(encoding="utf-8")
        first = next((ln for ln in note.splitlines() if ln.strip()), "")
        if READ_FULL.match(first):
            assert not SKIP_MARKERS.search(note), path.name
