"""Prompt screening before submission (docs/RQ3_PILOT.md, "Terms of use")."""

from __future__ import annotations

import pytest

from ril.agent.providers.calllog import sha256_text
from ril.agent.providers.pilot_run import prepare_items
from ril.agent.providers.screen import email_digest, screen_items, screen_text

ALLOWED = {email_digest("info@project.example")}


def test_clean_text_passes() -> None:
    assert screen_text("def f(x):\n    return x + 1\n", ALLOWED) == []


@pytest.mark.parametrize(
    "text",
    [
        "see /Users/someone/work/file.py",
        "open /home2/someone/repo",
        "C:\\Users\\someone\\x",
    ],
)
def test_home_path_rejected(text: str) -> None:
    assert [f.kind for f in screen_text(text, ALLOWED)] == ["home_path"]


@pytest.mark.parametrize(
    "text",
    [
        "key = 'AIza" + "A" * 35 + "'",
        "ghp_" + "a" * 36,
        "github_pat_" + "a" * 30,
        "-----BEGIN RSA PRIVATE KEY-----",
    ],
)
def test_token_shapes_rejected(text: str) -> None:
    assert "token" in {f.kind for f in screen_text(text, ALLOWED)}


def test_email_needs_review_and_forbidden_wins() -> None:
    assert screen_text("write to info@project.example", ALLOWED) == []
    assert [f.kind for f in screen_text("mail other@person.example", ALLOWED)] == ["email"]
    own = "me@mine.example"
    both = {email_digest(own)}
    assert [f.kind for f in screen_text(f"cc {own}", both, [own])] == ["email"]


def test_findings_do_not_carry_the_matched_text() -> None:
    (f,) = screen_text("/Users/someone/x", ALLOWED)
    assert "someone" not in repr(f)


def test_screen_items_names_the_item() -> None:
    items = [
        {"instance_id": "a-1", "arm": "bm25", "prompt": "fine"},
        {"instance_id": "a-2", "arm": "rrf", "prompt": "/" + "home/u1/x"},
    ]
    assert list(screen_items(items, ALLOWED)) == ["a-2/rrf"]


def test_prepare_refuses_an_unsendable_prompt(tmp_path) -> None:  # type: ignore[no-untyped-def]
    ctx = "code at /Users/someone/repo"
    row = {
        "instance_id": "a-1",
        "arm": "bm25",
        "issue": "bug",
        "context": ctx,
        "context_sha256": sha256_text(ctx),
        "files": ["a.py"],
    }
    with pytest.raises(ValueError, match="not sendable"):
        prepare_items([row], tmp_path)
    assert prepare_items([dict(row, context="x", context_sha256=sha256_text("x"))], tmp_path) == 1
