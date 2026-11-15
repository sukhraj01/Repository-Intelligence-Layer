"""Floor replay on synthetic text (E-RQ3-FLOOR addendum, D170)."""

from __future__ import annotations

from ril.agent.providers.patch_format import build_prompt
from ril.analysis import rq3_floor_replay as fr

BASE = "def f(x):\n    return x + 1\n\ndef g():\n    pass\n"
REPLY = (
    "FILE: pkg/a.py\n<<<<<<< SEARCH\n    return x + 1\n=======\n    return x + 2\n"
    ">>>>>>> REPLACE\n"
    "FILE: pkg/a.py\n<<<<<<< SEARCH\nnot in base\n=======\nnew text here\n>>>>>>> REPLACE\n"
)


def test_issue_of_prompt_roundtrip() -> None:
    assert fr.issue_of_prompt(build_prompt("  the issue\ntext ", "")) == "the issue\ntext"


def test_edited_lines_only_changed() -> None:
    assert fr.edited_lines("a\nb\nc", "a\nB\nc\nd") == ["B", "d"]


def test_replay_reply_counts() -> None:
    issue = "it fails with return x + 1 and new text here"
    row = fr.replay_reply(REPLY, issue, lambda p: BASE if p == "pkg/a.py" else None)
    assert row["n_blocks"] == 2
    assert (
        row["blocks_search_in_issue"] == 0
    )  # the indented search text is not verbatim in the issue
    assert row["blocks_search_in_issue_ws"] == 1  # but is once whitespace runs are collapsed
    assert row["blocks_search_in_base"] == 1
    assert row["blocks_search_unique_in_base"] == 1
    assert row["edited_lines"] == 2
    assert row["edited_lines_in_issue"] == 1
    assert row["edited_lines_long"] == 2 and row["edited_lines_long_in_issue"] == 1
    assert not row["all_search_in_base"] and row["any_search_in_base"]


def test_unreadable_and_no_blocks() -> None:
    row = fr.replay_reply(REPLY, "", lambda p: None)
    assert row["blocks_file_unreadable"] == 2 and row["blocks_search_in_base"] == 0
    none = fr.replay_reply("no edit here", "x", lambda p: None)
    assert none["n_blocks"] == 0 and none["parse_error"] == "no_edit_block"
    assert not none["all_search_in_base"]


def test_summaries() -> None:
    base = {
        k: 0
        for k in (
            "edited_lines",
            "edited_lines_in_issue",
            "edited_lines_long",
            "edited_lines_long_in_issue",
        )
    }
    rows = [
        {
            "stage": "s1",
            "repo": "a/a",
            "resolved": True,
            "n_blocks": 1,
            "all_search_in_issue": False,
            "all_search_in_issue_ws": False,
            "all_search_in_base": True,
            "any_search_in_base": True,
            **base,
        },
        {
            "stage": "s1",
            "repo": "a/a",
            "resolved": False,
            "n_blocks": 0,
            "all_search_in_issue": False,
            "all_search_in_issue_ws": False,
            "all_search_in_base": False,
            "any_search_in_base": False,
            **base,
        },
    ]
    s = {(r["stage"], r["repo"], r["class"]): r for r in fr.summarise(rows)}
    assert s[("all", "all", "resolved")]["all_search_in_base"] == 1
    assert s[("all", "all", "unresolved")]["with_blocks"] == 0
    f = {(r["stage"], r["repo"]): r for r in fr.resolved_by_repo(rows)}
    assert f[("all", "all")]["resolved"] == 1 and f[("all", "all")]["instances"] == 2
