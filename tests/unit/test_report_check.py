"""Prose checks of the final report (``ril.util.report_check``).

Every number of the prose carries a source comment; the open slots are listed.
"""

from __future__ import annotations

from pathlib import Path

from ril.util import report_check as rc

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports" / "final" / "final_report.tex"


def _doc(body: str) -> str:
    return (
        "\\documentclass{article}\n\\begin{document}\n"
        + body
        + "\n\\begin{thebibliography}{9}\n\\bibitem{a} x\n\\end{thebibliography}\n"
    )


def test_a_number_without_a_source_is_found() -> None:
    found = rc.untraced_numbers(_doc("Recall rose by 4.2 points.\n"))
    assert [f.line for f in found] == [3]


def test_a_source_comment_closes_the_lines_above_it() -> None:
    text = _doc("It rose by 4.2 points\nand then by 3 more.% E-ASSEMBLY results/x.csv\n")
    assert rc.untraced_numbers(text) == []


def test_a_comment_does_not_cover_the_next_paragraph() -> None:
    text = _doc("First 4.2.% E-ASSEMBLY\n\nSecond 5.1.\n")
    assert [f.line for f in rc.untraced_numbers(text)] == [5]


def test_names_labels_and_slots_are_not_numbers() -> None:
    body = (
        "In RQ2 at Level~3 with BM25 and nDCG@10, see Table~\\ref{tab:x2} "
        "\\todo{fill 12: \\entry{E-A1}}.\n"
    )
    assert rc.untraced_numbers(_doc(body)) == []


def test_slots_are_listed_with_their_entries() -> None:
    text = _doc("\\todo{one \\entry{E-RQ3-AGENT} and \\entry{E-POWER}}\n")
    assert rc.slots(text)[0][2] == ["E-RQ3-AGENT", "E-POWER"]


def test_unresolved_citation_and_reference() -> None:
    text = _doc("See \\cite{a,b} and Section~\\ref{sec:nowhere}.\n")
    kinds = sorted(f.kind for f in rc.unresolved(text))
    assert kinds == ["undefined citation", "undefined reference"]


def test_the_report_has_no_untraced_number_and_resolves_every_reference() -> None:
    text = REPORT.read_text(encoding="utf-8")
    assert [f.render() for f in rc.untraced_numbers(text)] == []
    assert [f.render() for f in rc.unresolved(text)] == []


def test_a_source_comment_naming_a_missing_file_is_found(tmp_path: Path) -> None:
    (tmp_path / "results").mkdir()
    (tmp_path / "results" / "there.csv").write_text("a\n")
    text = _doc("Seven. % results/there.csv and results/gone.csv and E-FOO\n")
    found = rc.missing_sources(text, tmp_path)
    assert [f.text for f in found] == ["results/gone.csv"]


def test_every_file_named_in_a_report_comment_exists() -> None:
    text = REPORT.read_text(encoding="utf-8")
    assert [f.render() for f in rc.missing_sources(text, ROOT)] == []
