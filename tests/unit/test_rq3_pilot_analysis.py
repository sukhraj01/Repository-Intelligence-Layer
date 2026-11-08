"""Tests for the RQ3 pilot analysis (docs/RQ3_PILOT.md, decision D109)."""

from __future__ import annotations

import math

from ril.analysis import rq3_pilot_analysis as ana

PROMPT = (
    "head\n\n## Issue\n\nbug\n\n## Repository excerpts\n\n"
    "### pkg/a.py:1-3 function f (rank 1)\n"
    "def f():\n    return 1\n\n"
    "### pkg/b.py:5-6 function g (rank 2)\n"
    "def g():\n    return 2\n"
)
BLOCK = "FILE: {p}\n<<<<<<< SEARCH\n{old}\n=======\nnew\n>>>>>>> REPLACE\n"


def _row(**kw: object) -> dict[str, object]:
    base: dict[str, object] = {"format_error": "", "finish_reason": "STOP", "patch_ok": False}
    base.update(kw)
    return base


def test_wilson_and_empty() -> None:
    p, lo, hi = ana.wilson(10, 100)
    assert p == 0.1 and lo < 0.1 < hi
    assert all(math.isnan(x) for x in ana.wilson(0, 0))


def test_excerpts_split_by_header() -> None:
    files = ana.excerpts_of(PROMPT)
    assert set(files) == {"pkg/a.py", "pkg/b.py"}
    assert "return 1" in files["pkg/a.py"] and "return 2" not in files["pkg/a.py"]


def test_search_check_counts_exact_and_squashed() -> None:
    ok = BLOCK.format(p="pkg/a.py", old="def f():\n    return 1")
    wrong_file = BLOCK.format(p="pkg/b.py", old="def f():\n    return 1")
    squashed = BLOCK.format(p="pkg/a.py", old="def f():\n  return 1")
    missing = BLOCK.format(p="pkg/a.py", old="def h():\n    return 9")
    assert ana.search_check(ok, PROMPT) == {
        "blocks": 1,
        "anywhere": 1,
        "in_named_file": 1,
        "squashed": 1,
    }
    c = ana.search_check(wrong_file, PROMPT)
    assert c["anywhere"] == 1 and c["in_named_file"] == 0
    c = ana.search_check(squashed, PROMPT)
    assert c["anywhere"] == 0 and c["squashed"] == 1
    assert ana.search_check(missing, PROMPT)["squashed"] == 0


def test_classify_reply_rules() -> None:
    shown = ["pkg/a.py", "pkg/b.py"]
    assert ana.classify_reply(_row(patch_ok=True), "x", shown) == "ok"
    assert ana.classify_reply(
        _row(finish_reason="MAX_TOKENS", format_error="no_edit_block"), "t", shown
    ) == ("truncated_at_output_limit")
    assert ana.classify_reply(_row(format_error="no_edit_block"), "  ", shown) == "empty_text"
    assert (
        ana.classify_reply(_row(format_error="no_edit_block"), "I cannot provide a block", shown)
        == "decline_prose"
    )
    assert (
        ana.classify_reply(_row(format_error="no_edit_block"), "Here is the answer", shown)
        == "other_prose"
    )
    assert (
        ana.classify_reply(
            _row(format_error="path_not_in_context"), BLOCK.format(p="a/pkg/a.py", old="x"), shown
        )
        == "path_prefix_variant_of_shown_path"
    )
    assert (
        ana.classify_reply(
            _row(format_error="path_not_in_context"), BLOCK.format(p="other/a.py", old="x"), shown
        )
        == "path_wrong_directory_same_file_name"
    )
    assert (
        ana.classify_reply(
            _row(format_error="path_not_in_context"), BLOCK.format(p="zzz/q.py", old="x"), shown
        )
        == "path_not_shown"
    )
    assert ana.classify_reply(_row(format_error="empty_search"), "x", shown) == "empty_search"


def test_repo_of_handles_both_id_forms() -> None:
    assert ana.repo_of("conan-io__conan-15377") == "conan-io__conan"
    assert ana.repo_of("instance_qutebrowser__qutebrowser-01d1d14") == "qutebrowser__qutebrowser"


def test_standardised_gap_removes_stratum_mix() -> None:
    # arm A fails only where gold is absent; B has gold present everywhere and never fails.
    units = []
    for i in range(20):
        absent = i < 10
        for run in (0, 1):
            units.append(
                {"instance_id": f"i{i}", "arm": "a", "run": run, "g": not absent, "ok": not absent}
            )
            units.append({"instance_id": f"i{i}", "arm": "b", "run": run, "g": True, "ok": True})
    r = ana.standardised_gap(units, "g", "ok", draws=200)
    assert abs(r["raw_gap"][0] - 0.5) < 1e-9
    assert abs(r["gap_after_standardising"][0]) < 1e-9
    assert abs(r["share_of_gap_explained"] - 1.0) < 1e-9


def test_boot_is_deterministic() -> None:
    assert ana.boot_mean([1, 0, 1, 1], draws=100) == ana.boot_mean([1, 0, 1, 1], draws=100)
