"""Census of positives by kind and file novelty."""

from __future__ import annotations

from typing import Any

import pytest

from ril.analysis.l3_census import census, census_meta, instance_rows


def _rec(instance: str, repo: str, positives: list[tuple[str, str, str]]) -> dict[str, Any]:
    return {
        "instance": instance,
        "repo_id": repo,
        "role": "dev",
        "positives": [
            {"status": "found", "level": lv, "kind": kind, "path": path}
            for lv, kind, path in positives
        ],
    }


RECS = [
    _rec(
        "i1",
        "a/x",
        [
            ("L2", "method", "a.py"),
            ("L3", "method", "a.py"),
            ("L3", "test_unit", "tests/test_a.py"),
            ("L3", "non_python_docs", "README.rst"),
        ],
    ),
    _rec("i2", "b/y", [("L3", "function", "b.py")]),  # L3 only: no novelty reading
]


def test_kinds_and_novelty() -> None:
    kinds, novelty = census(RECS, seed=0)
    all_l3 = next(r for r in kinds if r["group"] == "all" and r["level"] == "L3")
    assert all_l3["positives"] == 4 and all_l3["non_python"] == 1 and all_l3["test_unit"] == 1
    assert all_l3["non_python_docs"] == 1 and all_l3["instances"] == 2
    nov = next(r for r in novelty if r["group"] == "all")
    assert nov["instances_with_l2"] == 1 and nov["l3_positives_with_l2"] == 3
    assert nov["in_new_file"] == 2 and nov["new_file_pct"] == pytest.approx(66.67)
    assert nov["new_test_unit"] == 1 and nov["new_non_python"] == 1


def test_rows_ignore_unlocated_positives() -> None:
    rec = _rec("i3", "a/x", [("L3", "method", "a.py")])
    rec["positives"].append({"status": "not_found", "level": "L3", "kind": "", "path": ""})
    assert len(instance_rows(rec)) == 1


def test_census_meta_keeps_only_wanted_ids() -> None:
    rows = [[{"instance_id": "x-1", "repo": "o/x", "base_commit": "abc", "patch": "p"}]]
    meta = census_meta({"D/F": ["x-1", "x-2"]}, rows)
    assert list(meta) == ["x-1"] and meta["x-1"]["folder"] == "F" and meta["x-1"]["dataset"] == "D"
