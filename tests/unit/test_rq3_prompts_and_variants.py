"""Screened preparation, prefix identity, stored-context rows, replay variants."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ril.agent.contracts import FileEdit
from ril.agent.providers.calllog import sha256_text
from ril.agent.providers.patch_convert import convert_reply, reader_of
from ril.agent.providers.patch_format import parse_edits
from ril.agent.providers.pilot_run import load_items
from ril.agent.providers.replay_variants import (
    GOLD_ARM,
    ambiguous_fragment,
    build_replay_set,
    import_line,
    make_variant,
)
from ril.agent.providers.rq3_prompts import (
    check_prefix_identity,
    prepare_screened,
    rejection_table,
    rows_from_records,
)
from ril.agent.providers.screen import email_digest
from ril.assembly.rq3_contexts import encode_record


def row(iid: str, arm: str, context: str, issue: str = "x is wrong") -> dict[str, Any]:
    return {
        "instance_id": iid,
        "arm": arm,
        "issue": issue,
        "context": context,
        "context_sha256": sha256_text(context),
        "files": ["a/b.py"],
        "budget": 8000,
        "tokenizer": "approx-words-v1",
    }


def test_screened_preparation_reports_instead_of_raising(tmp_path: Path) -> None:
    ok = "### a/b.py:1-2 function f (rank 1)\nx = 1\n"
    bad = "### a/b.py:1-2 function f (rank 1)\n# contact: someone@example.org\nx = 1\n"
    path = "see /Users/someone/project/file"
    rows = [row("i1", "bm25", ok), row("i1", "rrf", bad), row("i2", "bm25", ok, issue=path)]
    n, rejected = prepare_screened(rows, tmp_path / "p", pseudonymise_prompts=False)
    assert n == 1 and [(r["instance_id"], r["arm"]) for r in rejected] == [
        ("i1", "rrf"),
        ("i2", "bm25"),
    ]
    assert rejected[0]["kinds"] == ["email"] and rejected[1]["kinds"] == ["home_path"]
    assert "someone@example.org" not in str(rejected)
    # the same address on the reviewed list passes
    n2, rej2 = prepare_screened(
        rows[:2],
        tmp_path / "p2",
        allowed_email_digests={email_digest("someone@example.org")},
        pseudonymise_prompts=False,
    )
    assert n2 == 2 and rej2 == []
    table = rejection_table(rejected)
    assert table[-1]["prompts_rejected"] == 2 and table[-1]["instances_affected"] == 2
    with pytest.raises(ValueError):
        prepare_screened([{**rows[0], "context_sha256": "0" * 64}], tmp_path / "p3")
    # with the transform (the default since D120) nothing here is rejected
    n3, rej3 = prepare_screened(rows, tmp_path / "p4")
    assert n3 == 3 and rej3 == []


def test_prefix_identity_across_arms(tmp_path: Path) -> None:
    rows = [
        row("i1", a, f"### a/b.py:1-2 function f (rank 1)\nx = {k}\n") for k, a in enumerate("abc")
    ]
    prepare_screened(rows, tmp_path / "p")
    report = check_prefix_identity(load_items(tmp_path / "p"))
    assert report["identical"] and report["prompts_by_arm"] == {"a": 1, "b": 1, "c": 1}
    items = load_items(tmp_path / "p")
    items[1]["prompt"] = items[1]["prompt"].replace("x is wrong", "x is very wrong")
    assert check_prefix_identity(items)["differing_instances"] == ["i1"]


def test_rows_from_stored_records(tmp_path: Path) -> None:
    (tmp_path / "instances").mkdir()
    ctx = "### a/b.py:1-2 function f (rank 1)\nx = 1\n"
    rec = {
        "instance": "i1",
        "repo_id": "o/r",
        "tokenizer": "approx-words-v1",
        "contexts": {
            f"{arm}|8000": {
                "context": ctx,
                "manifest": {"context_sha256": sha256_text(ctx), "entries": [{"file": "a/b.py"}]},
            }
            for arm in ("bm25", "rrf")
        },
    }
    (tmp_path / "instances" / "i1.json.gz").write_bytes(encode_record(rec))
    rows, skipped = rows_from_records(
        str(tmp_path), {"i1": "issue"}, 8000, ("bm25", "dense", "rrf")
    )
    assert [r["arm"] for r in rows] == ["bm25", "rrf"] and rows[0]["repo"] == "o/r"
    assert skipped == [{"instance_id": "i1", "arm": "dense", "reason": "no_context"}]
    _, none = rows_from_records(str(tmp_path), {}, 8000, ("bm25",))
    assert none[0]["reason"] == "no_issue_text"


FILES = {
    "m.py": "import os\nimport sys\n\ndef f(a):\n    return a + 1\n\ndef g(a):\n    return a + 1\n",
    "n.py": "def h():\n    pass\n",
}
GOLD = (FileEdit("m.py", "def f(a):\n    return a + 1", "def f(a):\n    return a + 2"),)


def test_variants_have_the_expected_conversion_outcome() -> None:
    read = reader_of(FILES)
    expect = {"no_match": "no_match", "multiple_matches": "multiple_matches", "breaks_code": None}
    for kind, failure in expect.items():
        reply = make_variant(kind, GOLD, read)
        assert reply is not None
        conv = convert_reply(reply, read)
        assert (conv.failure.kind if conv.failure else None) == failure
    broken = convert_reply(make_variant("breaks_code", GOLD, read) or "", read)
    assert broken.diff and "+raise RuntimeError" in broken.diff


def test_fragment_and_import_line_rules() -> None:
    assert ambiguous_fragment(FILES["m.py"]) == "return a + 1"
    assert ambiguous_fragment(FILES["n.py"]) is None
    assert import_line(FILES["m.py"]) == "import os"
    assert import_line("from x import (\n    a,\n)\n") is None
    assert (
        make_variant("multiple_matches", (FileEdit("n.py", "pass", "pass"),), reader_of(FILES))
        is None
    )
    with pytest.raises(ValueError):
        make_variant("nope", GOLD, reader_of(FILES))


def test_replay_set_has_gold_and_ten_distinct_variants() -> None:
    ids = [f"i{k}" for k in range(12)]
    gold = {i: GOLD for i in ids}
    readers = {i: reader_of(FILES) for i in ids}
    items, replies = build_replay_set(ids, gold, readers)
    arms = [it["arm"] for it in items]
    assert arms.count(GOLD_ARM) == 12
    assert sum(a.startswith("broken_") for a in arms) == 10
    for it in items:
        text = replies[(it["instance_id"], it["arm"], 0)]
        assert parse_edits(text)[1] is None
        assert "expected" in it
    used = [it["instance_id"] for it in items if it["arm"].startswith("broken_")]
    assert len(set(used)) == 10


def test_model_choice_rule() -> None:
    from ril.agent.providers.model_choice import choose

    cheap = {"model": "a", "resolved": 5, "n": 50, "cost_usd": 1.0, "output_price": 2.5}
    mid = {"model": "b", "resolved": 9, "n": 50, "cost_usd": 4.0, "output_price": 9.0}
    top = {"model": "c", "resolved": 12, "n": 50, "cost_usd": 9.0, "output_price": 15.0}
    got = choose([cheap, mid, top])
    assert got["chosen"] == "b" and got["floor_met"]
    assert choose([{**cheap, "resolved": 8}, mid])["chosen"] == "a"  # exactly 16%
    none = choose([cheap, {**mid, "resolved": 7}, {**top, "resolved": 7}])  # 14% < 15%
    assert none["chosen"] == "c" and not none["floor_met"] and "low-power" in none["note"]


def test_thinking_config_is_sent_only_when_set() -> None:
    from ril.agent.providers.gemini import GeminiConfig, request_body

    base = request_body(GeminiConfig(model="m"), [])
    assert "thinkingConfig" not in base["generationConfig"]
    with_cfg = request_body(GeminiConfig(model="m", thinking_config={"thinkingBudget": 0}), [])
    assert with_cfg["generationConfig"]["thinkingConfig"] == {"thinkingBudget": 0}


def test_issue_agreement_counts_equal_and_different_texts() -> None:
    from ril.agent.providers.rq3_prompts import issue_agreement

    table = {"a": "x", "b": "y", "c": "z"}
    folder = {"a": "x", "b": "different"}
    rep = issue_agreement(table, folder, ["a", "b", "c", "d"])
    assert (rep["with_table_text"], rep["compared_with_folder"], rep["equal"]) == (3, 2, 1)
    assert rep["different"] == ["b"]
