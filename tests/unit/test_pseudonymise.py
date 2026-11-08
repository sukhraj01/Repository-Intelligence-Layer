"""Pseudonymise-and-restore for the RQ3 prompts (docs/RQ3_PILOT.md, D120)."""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from ril.agent.providers.calllog import sha256_text
from ril.agent.providers.patch_convert import convert_reply, reader_of
from ril.agent.providers.patch_format import build_prompt
from ril.agent.providers.pilot_run import load_items
from ril.agent.providers.pseudonymise import (
    PseudonymMap,
    pseudonymise,
    quote_text,
    restore_text,
)
from ril.agent.providers.rq3_prompts import (
    check_prefix_identity,
    prepare_screened,
)
from ril.agent.providers.screen import screen_text

SRC = (
    "# Author: Jane Doe <jane@corp.example>\n"
    "DEFAULT = '\x2fhome/jane/data'\n"
    "def f(user):\n"
    "    return jane_lookup(user)  # jane is also a word here\n"
    "CONTACT = 'jane@corp.example'\n"
)


def test_emails_numbered_by_first_occurrence_and_repeated_address_shares_a_placeholder() -> None:
    out, mp = pseudonymise("a@x.org b@y.org a@x.org")
    assert out == "person1@example.invalid person2@example.invalid person1@example.invalid"
    assert mp.emails == {"person1@example.invalid": "a@x.org", "person2@example.invalid": "b@y.org"}
    assert mp.touched == "email"


def test_path_user_replaced_only_in_path_position() -> None:
    out, mp = pseudonymise(SRC)
    assert "'\x2fhome/user1/data'" in out
    assert "jane_lookup(user)  # jane is also a word here" in out  # outside path position
    assert "person1@example.invalid" in out and "jane@corp" not in out
    assert mp.touched == "both" and mp.users == {"user1": "jane"}


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("see \x2fUsers/bob/work/x.py", "\x2fUsers/user1/work/x.py"),
        ("open \x2fhome2/bob/repo", "\x2fhome2/user1/repo"),
        ("C:\\Users\\bob\\x", "C:\\Users\\user1\\x"),
        ('File "\x2fhome/bob/a.py", line 3', '"\x2fhome/user1/a.py"'),
        ("in \x2fhome/bob.", "\x2fhome/user1."),
        ('C:\\Users\\bob"', 'C:\\Users\\user1"'),
        ("C:\\Users\\Jos\u00e9\\x", "C:\\Users\\user1\u00e9\\x"),
    ],
)
def test_path_forms(text: str, kind: str) -> None:
    out, mp = pseudonymise(text)
    assert kind in out
    assert restore_text(out, mp) == text
    assert screen_text(out) == []


def test_address_inside_a_path_is_refused_not_sent() -> None:
    out, mp = pseudonymise("\x2fhome/foo@bar.com/x")  # not a real shape; fails closed
    assert screen_text(out)


def test_same_name_in_two_roots_shares_a_placeholder() -> None:
    out, mp = pseudonymise("\x2fhome/bob/a \x2fUsers/bob/b \x2fhome/eve/c")
    assert out == "\x2fhome/user1/a \x2fUsers/user1/b \x2fhome/user2/c"
    assert mp.users == {"user1": "bob", "user2": "eve"}


def test_screen_accepts_exactly_the_placeholder_forms() -> None:
    assert (
        screen_text(
            "x person1@example.invalid \x2fhome/user1/a \x2fUsers/user12 C:\\Users\\user3\\x"
        )
        == []
    )
    for bad in (
        "person1@example.com",
        "person1@example.invalid.org",
        "xperson1@example.invalid",
        "\x2fhome/user1evil/a",
        "\x2fhome/user1-bob/a",
        "\x2fhome/user/a",
        "\x2fhome/bob/a",
        "\x2fUsers/User1",
    ):
        assert screen_text(bad), bad


def test_screen_after_transform_finds_nothing_but_a_token() -> None:
    text = SRC + "mail <x.y+z@a-b.co.uk>, C:\\Users\\Al\\y, \x2fUsers/a.b/z\n"
    out, _ = pseudonymise(text)
    assert screen_text(out) == []
    assert [f.kind for f in screen_text(out + "ghp_" + "a" * 36)] == ["token"]


def test_transform_is_deterministic_and_idempotent_on_the_original_form_only() -> None:
    a = pseudonymise(SRC)
    assert a == pseudonymise(SRC)
    # a second pass over transformed text finds an address and a path again; it renumbers them,
    # and restoring both passes in reverse order gives back the first pass's text
    once, m1 = pseudonymise(SRC)
    twice, m2 = pseudonymise(once)
    assert restore_text(restore_text(twice, m2), m1) == SRC


def test_original_that_looks_like_a_placeholder_still_round_trips() -> None:
    text = "b@x.org person1@example.invalid \x2fhome/user1/a \x2fhome/bob/b person2@example.invalid"
    out, mp = pseudonymise(text)
    assert restore_text(out, mp) == text
    assert (
        out.split()[0] == "person1@example.invalid" and out.split()[1] == "person2@example.invalid"
    )


def test_restore_leaves_unknown_placeholders_and_other_words_alone() -> None:
    _, mp = pseudonymise("a@x.org \x2fhome/bob/z")
    assert restore_text("person9@example.invalid \x2fhome/user9/q user1", mp) == (
        "person9@example.invalid \x2fhome/user9/q user1"
    )
    assert restore_text("anything", None) == "anything"
    assert restore_text("anything", PseudonymMap()) == "anything"


def test_random_texts_round_trip_or_are_refused_by_the_screen() -> None:
    """Fail closed: if the screen accepts the transformed text, restoring gives back the original.

    Texts that do not round trip are two addresses with nothing between them (the second one's
    local part starts with a dot) and a path root followed only by punctuation (``\x2fhome/-``); the
    screen then rejects the prompt, which is reported as a transform defect (never sent).
    """
    rng = random.Random(0)
    parts = [
        "a@b.co",
        "x.y@z.org.uk",
        "\x2fhome/bob/f.py",
        "\x2fUsers/Al.B/x",
        "C:\\Users\\Zed\\q",
        "user1",
        "person1@example.invalid",
        "\x2fhome/user2/x",
        "bob",
        "@decorator",
        "a@b.T",
        ".",
        ",",
        "\n",
        " ",
        "'",
        "(",
        "\x2fhome/",
        "x" * 3,
        "\x2fhome/-",
        "jane@corp.example",
        "\x2fhome3/q-r_s",
    ]
    refused = 0
    for _ in range(2000):
        text = "".join(rng.choice(parts) for _ in range(rng.randint(1, 25)))
        out, mp = pseudonymise(text)
        if screen_text(out):
            refused += 1
        else:
            assert restore_text(out, mp) == text, text
    assert (
        refused < 2000
    )  # the parts are adversarial joins; real prompts are counted at preparation


def _files() -> dict[str, str | None]:
    return {"pkg/mod.py": SRC, "pkg/other.py": "x = 1\n"}


def _edit_roundtrip(search: str, replace: str, mp: PseudonymMap) -> str | None:
    reply = f"FILE: pkg/mod.py\n<<<<<<< SEARCH\n{search}\n=======\n{replace}\n>>>>>>> REPLACE\n"
    conv = convert_reply(restore_text(reply, mp), reader_of(_files()))
    assert conv.failure is None, conv.failure
    return conv.diff


def test_placeholder_in_search_replace_and_both_write_the_original_text() -> None:
    prompt, mp = pseudonymise(build_prompt("issue", SRC))
    assert "jane@corp" not in prompt
    quoted = quote_text("CONTACT = 'jane@corp.example'", mp)
    assert quoted == "CONTACT = 'person1@example.invalid'"
    # in SEARCH: the placeholder line matches the original file
    d1 = _edit_roundtrip(quoted, "CONTACT = None", mp)
    assert d1 is not None and "-CONTACT = 'jane@corp.example'" in d1 and "+CONTACT = None" in d1
    # in REPLACE: the original text is written
    d2 = _edit_roundtrip("CONTACT = 'jane@corp.example'", "CONTACT = 'person1@example.invalid'", mp)
    assert d2 == ""  # replacing a line by itself is an empty diff
    # in both, with a path user name too
    s = quote_text("DEFAULT = '\x2fhome/jane/data'", mp)
    d3 = _edit_roundtrip(s, s + "  # kept", mp)
    assert d3 is not None and "+DEFAULT = '\x2fhome/jane/data'  # kept" in d3
    assert "user1" not in d3 and "person1" not in d3


def test_word_equal_to_a_path_user_name_matches_the_file_unchanged() -> None:
    _, mp = pseudonymise(build_prompt("issue", SRC))
    d = _edit_roundtrip(
        "    return jane_lookup(user)  # jane is also a word here", "    return 0", mp
    )
    assert d is not None and "-    return jane_lookup(user)" in d


def _row(iid: str, arm: str, issue: str, context: str) -> dict[str, object]:
    return {
        "instance_id": iid,
        "arm": arm,
        "first_stage": arm,
        "repo": "o/r",
        "issue": issue,
        "context": context,
        "context_sha256": sha256_text(context),
        "files": ["pkg/mod.py"],
        "budget": 8000,
        "tokenizer": "approx",
    }


def test_prepare_pseudonymises_stores_the_map_and_keeps_the_prefix_identical(
    tmp_path: Path,
) -> None:
    issue = "Traceback in \x2fhome/jane/app.py, mail jane@corp.example or lead@other.org"
    rows = [
        _row("i1", "bm25", issue, "### pkg/mod.py:1-5 module m (rank 1)\n" + SRC),
        _row("i1", "rrf", issue, "### other.py:1-1 module o (rank 1)\nmail lead@other.org\n"),
    ]
    n, rejected = prepare_screened(rows, tmp_path)
    assert (n, rejected) == (2, [])
    items = load_items(tmp_path)
    assert all(
        "\x2fhome/jane" not in it["prompt"]
        and "@" not in it["prompt"].replace("@example.invalid", "")
        for it in items
    )
    assert check_prefix_identity(items)["identical"]
    by_arm = {it["arm"]: it for it in items}
    assert by_arm["bm25"]["pseudonymised"] == "both" and by_arm["rrf"]["pseudonymised"] == "both"
    assert by_arm["bm25"]["restore"].users == {"user1": "jane"}
    assert restore_text(by_arm["bm25"]["prompt"], by_arm["bm25"]["restore"]) == build_prompt(
        issue, "### pkg/mod.py:1-5 module m (rank 1)\n" + SRC
    )
    # the issue part equals the transform of the issue alone
    head = by_arm["rrf"]["prompt"].split("## Repository excerpts")[0]
    assert pseudonymise(issue)[0] in head
    stored = (tmp_path / "items.jsonl").read_text()
    assert "jane" not in stored and "corp.example" not in stored  # only counts and hashes
    maps = sorted((tmp_path / "maps").iterdir())
    assert len(maps) == 2 and json.loads(maps[0].read_text())["version"]


def test_prepare_with_the_transform_off_keeps_the_old_screen_behaviour(tmp_path: Path) -> None:
    rows = [_row("i1", "bm25", "see \x2fhome/jane/x", "### a.py:1-1 module m (rank 1)\nx = 1\n")]
    n, rejected = prepare_screened(rows, tmp_path, pseudonymise_prompts=False)
    assert n == 0 and rejected[0]["kinds"] == ["home_path"]


def test_report_counts_kinds_arms_and_token_effect(tmp_path: Path) -> None:
    from ril.agent.providers.rq3_prompts import pseudonymise_report

    ctx = "### pkg/mod.py:1-5 module m (rank 1)\n" + SRC
    rows = [
        _row("i1", "bm25", "a clean issue", ctx),
        _row("i1", "rrf", "a clean issue", "### a.py:1-1 module m (rank 1)\nx = 1\n"),
    ]
    prepare_screened(rows, tmp_path)
    items = load_items(tmp_path)
    rep = pseudonymise_report(items, budget=8000, tolerance=0.01)
    assert rep["by_kind"] == {"both": 1, "none": 1}
    assert rep["by_arm"]["rrf"] == {"none": 1}
    assert rep["max_context_overshoot"] == 0 and rep["within_tolerance"]
    assert rep["tokens_delta_prompt_touched"]["max"] == rep["tokens_delta_prompt_all"]["max"]
    tight = pseudonymise_report(items, budget=10, tolerance=0.0)
    assert not tight["within_tolerance"] and tight["prompts_over_budget"] == 2


def test_driver_restores_the_reply_before_converting() -> None:
    from ril.agent.providers.driver import DriverConfig, Reply, process_unit
    from ril.evaluation.executor.runner import ExecResult

    _, mp = pseudonymise(build_prompt("issue", SRC))
    reply = (
        "FILE: pkg/mod.py\n<<<<<<< SEARCH\nCONTACT = 'person1@example.invalid'\n=======\n"
        "CONTACT = None\n>>>>>>> REPLACE\n"
    )
    seen: list[str] = []

    def executor(iid: str, diff: str) -> ExecResult:
        seen.append(diff)
        return ExecResult(
            instance_id=iid,
            built=True,
            patch_applied=True,
            tests_ran=True,
            f2p_total=1,
            f2p_passed=1,
            p2p_total=1,
            p2p_passed=1,
        )

    def read(path: str) -> str | None:
        return _files().get(path)

    cfg = DriverConfig(model="m", mode="replay")
    item = {"instance_id": "i", "arm": "a", "paths": ["pkg/mod.py"], "restore": mp}
    row = process_unit(("i", "a", 0), item, Reply(reply, True), read, executor, cfg, None)
    assert row["outcome"] == "resolved"
    assert seen and "-CONTACT = 'jane@corp.example'" in seen[0] and "person1" not in seen[0]
    # without the mapping the same reply does not match the original file
    bare = {**item, "restore": None}
    row2 = process_unit(("i", "a", 0), bare, Reply(reply, True), read, executor, cfg, None)
    assert row2["outcome"] == "apply_failed:no_match"
