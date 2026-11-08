"""Stored-reply apply table (D110): mirror lookup and the counting tables."""

from __future__ import annotations

from pathlib import Path

import pytest

from ril.analysis.rq3_patch_apply import Unit, mirror_of, outcome_table, rescue_table, unit_rows

SRC = "def f():\n    return 1\n"
PROMPT = "## Repository excerpts\n\n### m.py:1-2 (function f) (rank 1)\n" + SRC + "\n"


def _reply(old: str, new: str, path: str = "m.py") -> str:
    return f"FILE: {path}\n<<<<<<< SEARCH\n{old}\n=======\n{new}\n>>>>>>> REPLACE\n"


def test_mirror_of_handles_both_id_forms(tmp_path: Path) -> None:
    for name in (
        "conan-io__conan.git",
        "internetarchive__openlibrary.git",
        "a__b.git",
        "a__b-c.git",
    ):
        (tmp_path / name).mkdir()
    assert mirror_of("conan-io__conan-15377", tmp_path).name == "conan-io__conan.git"
    assert (
        mirror_of("instance_internetarchive__openlibrary-00be-v136", tmp_path).name
        == "internetarchive__openlibrary.git"
    )
    assert mirror_of("a__b-c-12", tmp_path).name == "a__b-c.git"
    with pytest.raises(FileNotFoundError):
        mirror_of("x__y-1", tmp_path)


def test_tables_count_exact_tolerant_and_rescue() -> None:
    units = [
        Unit("i1", "bm25", 0, _reply("return 1", "return 2"), PROMPT, True),
        Unit("i2", "bm25", 0, _reply("return  1", "return 2"), PROMPT, True),
        Unit("i3", "rrf", 0, _reply("return 1", "return 2"), PROMPT, True),
        Unit("i4", "rrf", 0, "no blocks here", PROMPT, False),
    ]
    snaps = {
        ("i1", "m.py"): SRC,
        ("i2", "m.py"): "def f():\n    return  1   \n",
        ("i3", "m.py"): None,
    }
    urows, brows = unit_rows(units, snaps)
    by = {r["instance_id"]: r for r in urows}
    assert (by["i1"]["exact"], by["i1"]["tolerant"]) == ("applied", "applied")
    assert (by["i2"]["exact"], by["i2"]["tolerant"]) == ("applied", "applied")
    assert by["i3"]["exact"] == "file_missing"
    table = {(r["arm"], r["reading"]): r for r in outcome_table(urows, units)}
    assert table[("all", "exact")]["units"] == 4 and table[("all", "exact")]["usable"] == 3
    assert table[("rrf", "exact")]["file_missing"] == 1
    assert table[("all", "exact")]["usable_and_applying"] == 2
    rescue = {r["arm"]: r for r in rescue_table(urows)}
    assert rescue["all"]["exact_failing"] == 1 and rescue["all"]["rescued_by_tolerant"] == 0
    assert len(brows) == 3
