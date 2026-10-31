"""Unit tests for the documentation link and reference checker (``ril.util.doc_check``)."""

from __future__ import annotations

from pathlib import Path

from ril.util.doc_check import (
    check_document,
    check_tree,
    deviation_numbers,
    highest_question,
    looks_like_repo_path,
    with_directories,
)

FILES = {
    "README.md",
    "docs/ROADMAP.md",
    "docs/DEVIATIONS.md",
    "ril/parsing/code_unit.py",
    "decisions/ADR-001-training-pool.md",
    "data/held_out/report.md",
}
KNOWN = with_directories(FILES)
ADRS = {1}
DEVS = {1, 2}


def _check(text: str, name: str = "docs/ROADMAP.md") -> list[str]:
    return [f.target for f in check_document(name, text, KNOWN, ADRS, DEVS, 10)]


def test_existing_path_and_directory_resolve() -> None:
    assert _check("see `ril/parsing/code_unit.py` and `ril/parsing/`") == []


def test_missing_path_is_reported() -> None:
    assert _check("see `ril/parsing/nothing.py`") == ["ril/parsing/nothing.py"]


def test_relative_link_resolves_from_the_document_folder() -> None:
    assert _check("[d](DEVIATIONS.md#dev-001)") == []
    assert _check("[x](missing.md)") == ["missing.md"]
    assert _check("[web](https://example.org/a.md) [top](#here)") == []


def test_bare_name_resolves_by_basename_and_symbol_suffix_is_dropped() -> None:
    assert _check("`code_unit.py` and `ril/parsing/code_unit.py::CodeUnit`") == []
    assert _check("`absent.py`") == ["absent.py"]


def test_rebuilt_directories_are_exempt() -> None:
    assert _check("`data/processed/pool.jsonl` and `data/raw/x/provenance.json`") == []


def test_placeholders_and_code_are_ignored() -> None:
    assert not looks_like_repo_path("results/<rq>/<exp>/")
    assert not looks_like_repo_path("results/rq*/run.csv")
    assert not looks_like_repo_path("git push origin")
    assert looks_like_repo_path("scripts/check_docs.py")
    assert _check("`results/<rq>/<exp>/config.yaml`") == []


def test_fenced_blocks_are_skipped() -> None:
    assert _check("```\nril/parsing/nothing.py ADR-099\n```") == []


def test_numbered_references_must_exist() -> None:
    assert _check("ADR-001 DEV-002 Q3") == []
    assert _check("ADR-007") == ["ADR-007"]
    assert _check("DEV-009") == ["DEV-009"]
    assert _check("Q11") == ["Q11"]
    assert _check("ADR-001..001 and ADR-0NN and Q-G3") == []


def test_adr_range_checks_both_ends() -> None:
    assert _check("ADR-001..010") == ["ADR-010"]


def test_state_file_helpers() -> None:
    assert highest_question("Q1 and Q57, also Q-G9") == 57
    assert deviation_numbers("## DEV-001 — a\n## DEV-003 — b\nDEV-002 inline") == {1, 3}


def test_check_tree_on_a_small_tree(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "decisions").mkdir()
    (tmp_path / "README.md").write_text("start at `docs/GOOD.md` then `docs/BAD.md`; ADR-001\n")
    (tmp_path / "docs/GOOD.md").write_text("fine\n")
    (tmp_path / "docs/DEVIATIONS.md").write_text("## DEV-001 — x\n")
    (tmp_path / "decisions/ADR-001-a.md").write_text("# a\n")
    (tmp_path / "PROJECT_STATE.md").write_text("Q1\n")
    findings = check_tree(tmp_path)
    assert [f.target for f in findings] == ["docs/BAD.md"]
    assert findings[0].line == 1


def test_repository_documents_have_no_dangling_references() -> None:
    root = Path(__file__).resolve().parents[2]
    findings = check_tree(root)
    assert [f.render() for f in findings] == []
