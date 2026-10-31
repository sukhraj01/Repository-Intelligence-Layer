"""Unit tests for the entry-id checks of the split experiment logs."""

from __future__ import annotations

from pathlib import Path

from ril.util.doc_check import check_tree
from ril.util.experiment_registry import (
    check_registry,
    defined_ids,
    index_rows,
    owned_log,
)

HEADER = (
    "| ID | RQ | What varies | Held fixed | Seeds | Primary outputs | Status |\n"
    "|---|---|---|---|---|---|---|\n"
)


def _log(*entries: str, index: str = "") -> str:
    rows = "".join(f"| {e} | RQ1 | x | y | 0 | z | done |\n" for e in entries)
    heads = "".join(f"\n## {e}: text\n\nbody\n" for e in entries)
    return f"# Experiments\n\n{index}## Registry\n\n{HEADER}{rows}{heads}"


def _index(*rows: tuple[str, str]) -> str:
    body = "".join(f"| {i} | lead | `{f}` | done | |\n" for i, f in rows)
    head = (
        "## Index of entries\n\n| Entry id | Owner | File | Status | Date |\n"
        "|---|---|---|---|---|\n"
    )
    return f"{head}{body}\n"


def test_row_and_heading_of_one_entry_is_one_definition() -> None:
    ids = {i for _, i in defined_ids(_log("E-ONE", "A1-PILOT"))}
    assert ids == {"E-ONE", "A1-PILOT"}


def test_heading_lists_and_aliases_are_read() -> None:
    text = "## E-AA, E-BB (E2) and E-CC: text\n\n## Registry\n\n| E-DD (was E-OLD) | x |\n"
    assert {i for _, i in defined_ids(text)} == {"E-AA", "E-BB", "E-CC", "E-DD", "E-OLD"}


def test_subsection_headings_do_not_redefine() -> None:
    text = "## E-AA: text\n\n### E-AA: sub part\n\n#### E-AA update\n"
    assert [i for _, i in defined_ids(text)] == ["E-AA"]


def test_an_id_defined_in_two_files_fails() -> None:
    logs = {
        "docs/EXPERIMENTS.md": _log("E-ONE"),
        "docs/experiments/A.md": _log("E-ONE"),
        "docs/experiments/C.md": _log(),
    }
    found = check_registry(logs, {})
    assert [f.token for f in found] == ["E-ONE", "E-ONE"]
    assert all("also defined" in f.message for f in found)


def test_an_id_defined_twice_in_one_file_fails() -> None:
    text = _log("E-ONE") + "\n## E-ONE: again\n"
    found = check_registry({"docs/EXPERIMENTS.md": text}, {})
    assert [f.message for f in found] == ["entry id defined twice in this file"]


def test_a_citation_of_an_undefined_entry_fails() -> None:
    logs = {"docs/EXPERIMENTS.md": _log("E-ONE")}
    cites = {"RESULTS.md": "see `docs/EXPERIMENTS.md` E-MISSING and `docs/EXPERIMENTS.md` E-ONE\n"}
    found = check_registry(logs, cites)
    assert [(f.path, f.token) for f in found] == [("RESULTS.md", "E-MISSING")]
    assert found[0].message == "cited entry is defined in no log"


def test_a_citation_naming_the_wrong_file_fails() -> None:
    logs = {"docs/EXPERIMENTS.md": _log("E-ONE"), "docs/experiments/A.md": _log("A9")}
    cites = {"x.md": "docs/EXPERIMENTS.md, section A9 and docs/experiments/A.md section A9"}
    found = check_registry(logs, cites)
    assert [f.message for f in found] == [
        "cited in docs/EXPERIMENTS.md, entry is in docs/experiments/A.md"
    ]


def test_the_index_must_agree_with_the_definitions() -> None:
    index = _index(
        ("E-ONE", "docs/EXPERIMENTS.md"),
        ("E-GONE", "docs/EXPERIMENTS.md"),
        ("A9", "docs/EXPERIMENTS.md"),
    )
    logs = {"docs/EXPERIMENTS.md": _log("E-ONE", index=index), "docs/experiments/A.md": _log("A9")}
    assert [(r[1], r[2]) for r in index_rows(logs["docs/EXPERIMENTS.md"])][:1] == [
        ("E-ONE", "docs/EXPERIMENTS.md")
    ]
    msgs = sorted(f.message for f in check_registry(logs, {}))
    assert msgs == [
        "index names docs/EXPERIMENTS.md, entry is in docs/experiments/A.md",
        "index row for an undefined entry",
    ]


def test_clean_logs_pass() -> None:
    index = _index(("E-ONE", "docs/EXPERIMENTS.md"), ("A9", "docs/experiments/A.md"))
    logs = {"docs/EXPERIMENTS.md": _log("E-ONE", index=index), "docs/experiments/A.md": _log("A9")}
    cites = {"y.md": "`docs/experiments/A.md` A9, `docs/EXPERIMENTS.md` E-ONE"}
    assert check_registry(logs, cites) == []


def test_owned_log_by_branch() -> None:
    assert owned_log("a/rq1") == "docs/experiments/A.md"
    assert owned_log("c/loaders") == "docs/experiments/C.md"
    assert owned_log("b/review") is None
    assert owned_log("a") is None


def test_check_tree_reports_registry_findings(tmp_path: Path) -> None:
    (tmp_path / "docs/experiments").mkdir(parents=True)
    (tmp_path / "docs/EXPERIMENTS.md").write_text(_log("E-ONE"), encoding="utf-8")
    (tmp_path / "docs/experiments/A.md").write_text(_log("E-ONE"), encoding="utf-8")
    files = {"docs/EXPERIMENTS.md", "docs/experiments/A.md"}
    found = check_tree(tmp_path, files)
    assert {f.target for f in found} == {"E-ONE"}
