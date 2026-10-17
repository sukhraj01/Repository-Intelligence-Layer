"""Unit tests for ril.parsing.repo_id (specs/code_unit.md decision D5)."""

import pytest

from ril.parsing.repo_id import is_normalized_repo_id, normalize_repo_id


@pytest.mark.parametrize(
    "spelling",
    [
        "Owner/Repo",
        "owner/repo",
        "OWNER__REPO",
        "owner__repo",
        "https://github.com/Owner/Repo",
        "http://www.github.com/owner/repo.git",
        "github.com/owner/repo/",
        "  owner/repo  ",
    ],
)
def test_spellings_collapse(spelling: str) -> None:
    assert normalize_repo_id(spelling) == "owner/repo"


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "scikit",
        "owner/",
        "/repo",
        "a/b/c",
        "owner/repo@abc123",
        "owner/repo#2",
        "o w/r",
        ".git",
    ],
)
def test_unreadable_names_are_refused_not_guessed(bad: str) -> None:
    with pytest.raises(ValueError):
        normalize_repo_id(bad)


def test_name_with_dots_and_dashes_is_kept() -> None:
    assert normalize_repo_id("Pylint-Dev/Pylint.Core") == "pylint-dev/pylint.core"


def test_idempotent() -> None:
    once = normalize_repo_id("Pallets__Flask")
    assert normalize_repo_id(once) == once


def test_is_normalized() -> None:
    assert is_normalized_repo_id("pallets/flask")
    assert not is_normalized_repo_id("Pallets/Flask")
    assert not is_normalized_repo_id("pallets__flask")
    assert not is_normalized_repo_id("pallets/flask@abc")
    assert not is_normalized_repo_id("")
