"""Two-page report: tables rebuilt from stored files, source comments, consistency, build rules.

Implements ``docs/experiments/B.md`` E-REPORT-SHORT: the fragments equal a fresh build, no number
is typed in them, a sentence with a number and no comment on its line is refused, a number that is
not in the full report is refused, and the build refuses an overfull box, a third page or a
smaller type size or margin.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ril.analysis import short_report_tables as st
from ril.util import report_check as rc
from ril.util import short_report_build as sb

ROOT = Path(__file__).resolve().parents[2]
SHORT_DIR = ROOT / "reports" / "short"
SHORT = SHORT_DIR / "short_report.tex"
FULL = ROOT / "reports" / "final" / "final_report.tex"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _with_fragments(report: Path) -> str:
    gen = report.parent / "generated"
    return "\n".join([_read(report), *(_read(p) for p in sorted(gen.glob("*.tex")))])


def test_committed_fragments_equal_a_fresh_build(tmp_path: Path) -> None:
    tables = st.write_all(ROOT, tmp_path)
    names = sorted([f"{t.name}.tex" for t in tables] + ["SOURCES.csv"])
    assert names == sorted(p.name for p in (SHORT_DIR / "generated").iterdir())
    for name in names:
        assert _read(tmp_path / name) == _read(SHORT_DIR / "generated" / name), name


def test_the_short_tables_are_not_in_the_full_reports_folder() -> None:
    assert not list((ROOT / "reports" / "final" / "generated").glob("short_*"))


def test_a_typed_digit_in_a_short_table_is_refused() -> None:
    t = st.short_rq3(ROOT)
    t.facts += ", about 7 points"
    with pytest.raises(ValueError):
        t.check()


def test_the_short_report_passes_its_checks() -> None:
    text = _read(SHORT)
    assert rc.untraced_numbers_same_line(text) == []
    assert rc.missing_sources(text, ROOT) == []
    assert rc.numbers_missing_from_full(_with_fragments(SHORT), _with_fragments(FULL)) == []
    assert sb.check_source_format(text) == []
    labels = set(re.findall(r"\\label\{([^}]+)\}", _with_fragments(SHORT)))
    for ref in re.findall(r"\\ref\{([^}]+)\}", text):
        assert ref in labels


def test_header_names_the_authors_and_has_no_placeholder() -> None:
    text = _read(SHORT)
    assert "Sukhraj Singh" in text and "2025202009" in text
    assert "Neill Rawani" in text and "2025202027" in text
    assert "Chaitanya Shah" in text and "2025202033" in text
    assert "M.Tech CSIS" in text and "IIIT Hyderabad" in text
    assert "http" not in text and "github" not in text.lower()
    assert "todo" not in text.lower() and "TBD" not in text


def test_a_line_with_a_number_and_no_comment_is_refused() -> None:
    doc = (
        "\\begin{document}\nIt gained 3.5 points.\n"
        "It gained 4.5 points. % E-X results/a.csv\n\\end{document}\n"
    )
    found = rc.untraced_numbers_same_line(doc)
    assert [f.line for f in found] == [2]


def test_a_comment_on_a_later_line_does_not_cover_an_earlier_one() -> None:
    doc = (
        "\\begin{document}\nIt gained 3.5 points.\nand more. % E-X results/a.csv\n\\end{document}\n"
    )
    assert len(rc.untraced_numbers_same_line(doc)) == 1


def test_a_number_missing_from_the_full_report_is_refused() -> None:
    full = "The gain was 12.25 points and 4,096 tokens, 21.32 upper.\n"
    assert rc.numbers_missing_from_full("12.25 and 4096 and 21.3\n", full) == []
    bad = rc.numbers_missing_from_full("a gain of 12.35 points\n", full)
    assert [f.text for f in bad] == ["12.35"]
    assert rc.numbers_missing_from_full("a gain of 12.2 points\n", full)[0].text == "12.2"


def test_the_build_refuses_overfull_boxes_and_undefined_references() -> None:
    log = "warning: x.tex:3: Overfull \\hbox (2pt too wide)\nok\nwarning: Reference `a' undefined\n"
    assert len(sb.log_problems(log)) == 2
    assert sb.log_problems("warning: Underfull \\hbox (badness 1762)\n") == []


def test_the_format_check_refuses_smaller_type_or_margins() -> None:
    ok = "\\documentclass[10pt,twocolumn]{article}\n\\usepackage[margin=0.7in]{geometry}\n"
    assert sb.check_source_format(ok) == []
    assert sb.check_source_format(ok.replace("10pt", "9pt"))
    assert sb.check_source_format(ok.replace("0.7in", "0.6in"))
    assert sb.check_source_format(ok + "\\linespread{0.9}\n")


def test_the_built_pdf_has_two_pages() -> None:
    pdf = SHORT_DIR / "short_report.pdf"
    if not pdf.exists():
        pytest.skip("the PDF is a build product; run `make report-short`")
    assert sb.page_count(pdf) == sb.PAGE_LIMIT
