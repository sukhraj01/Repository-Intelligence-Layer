"""Edit blocks to a unified diff (D110): exact and tolerant readings, atomicity, round trip."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ril.agent.contracts import FileEdit
from ril.agent.providers.patch_convert import (
    blocks_overlap_in_base,
    convert_edits,
    convert_reply,
    git_reader,
    reader_of,
    unified_diff,
)

SRC = "def f(x):\n    y = x + 1\n    return y\n\n\ndef g():\n    return 0\n"


def _apply(tmp: Path, files: dict[str, str], diff: str) -> dict[str, str]:
    """Commit ``files``, run ``git apply --check`` then ``git apply``, return the new texts."""
    subprocess.run(["git", "init", "-q", str(tmp)], check=True)
    for name, text in files.items():
        (tmp / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp / name).write_bytes(text.encode())
    patch = tmp.parent / (tmp.name + ".patch")
    patch.write_text(diff)
    for flags in (["--check"], []):
        subprocess.run(
            ["git", "-C", str(tmp), "apply", "--whitespace=nowarn", *flags, str(patch)], check=True
        )
    return {name: (tmp / name).read_bytes().decode() for name in files}


def _expect(
    files: dict[str, str], edits: list[FileEdit], tmp: Path, reading="exact"
) -> dict[str, str]:
    result = convert_edits(edits, reader_of(files), reading)
    assert result.applied and result.diff
    return _apply(tmp, files, result.diff)


def test_exact_hit_round_trip(tmp_path: Path) -> None:
    out = _expect({"a.py": SRC}, [FileEdit("a.py", "y = x + 1", "y = x + 2")], tmp_path / "r")
    assert out["a.py"] == SRC.replace("x + 1", "x + 2")


def test_exact_no_match_and_missing_file() -> None:
    files = {"a.py": SRC}
    r = convert_edits([FileEdit("a.py", "y = x + 3", "z")], reader_of(files))
    assert r.failure and r.failure.kind == "no_match" and r.diff is None
    r = convert_edits([FileEdit("b.py", "y", "z")], reader_of(files))
    assert r.failure and r.failure.kind == "file_missing" and r.failure.path == "b.py"


def test_exact_two_matches_fail_and_overlapping_occurrences_count() -> None:
    files = {"a.py": "return 0\nreturn 0\n", "b.py": "aaa"}
    r = convert_edits([FileEdit("a.py", "return 0", "return 1")], reader_of(files))
    assert r.failure and r.failure.kind == "multiple_matches" and r.failure.detail == "2"
    # "aa" occurs at offsets 0 and 1 of "aaa": two occurrences, not one
    r = convert_edits([FileEdit("b.py", "aa", "b")], reader_of(files))
    assert r.failure and r.failure.kind == "multiple_matches"


def test_crlf_file_with_lf_block_only_tolerant(tmp_path: Path) -> None:
    crlf = SRC.replace("\n", "\r\n")
    files = {"a.py": crlf}
    edit = FileEdit("a.py", "def g():\n    return 0", "def g():\n    return 1")
    assert convert_edits([edit], reader_of(files), "exact").failure.kind == "no_match"  # type: ignore[union-attr]
    out = _expect(files, [edit], tmp_path / "r", "tolerant")
    # the replacement is inserted as given: the edited lines carry no carriage return
    assert out["a.py"] == crlf.replace("def g():\r\n    return 0", "def g():\n    return 1")


def test_trailing_whitespace_difference_only_tolerant(tmp_path: Path) -> None:
    files = {"a.py": "x = 1   \ny = 2\t\nz = 3\n"}
    edit = FileEdit("a.py", "x = 1\ny = 2", "x = 5\ny = 6")
    assert convert_edits([edit], reader_of(files), "exact").failure.kind == "no_match"  # type: ignore[union-attr]
    out = _expect(files, [edit], tmp_path / "r", "tolerant")
    assert out["a.py"] == "x = 5\ny = 6\t\nz = 3\n"


def test_tolerant_ignores_blank_lines_around_block_but_not_indentation(tmp_path: Path) -> None:
    files = {"a.py": SRC}
    edit = FileEdit("a.py", "\n\n    y = x + 1\n    return y\n\n", "    y = 0\n    return y")
    out = _expect(files, [edit], tmp_path / "r", "tolerant")
    assert "    y = 0\n    return y\n" in out["a.py"]
    # indentation is never repaired
    bad = FileEdit("a.py", "y = x + 1\nreturn y", "y = 0")
    assert convert_edits([bad], reader_of(files), "tolerant").failure.kind == "no_match"  # type: ignore[union-attr]


def test_tolerant_still_requires_exactly_one_match() -> None:
    files = {"a.py": "a = 1  \na = 1\n"}
    r = convert_edits([FileEdit("a.py", "a = 1", "a = 2")], reader_of(files), "tolerant")
    assert r.failure and r.failure.kind == "multiple_matches"


def test_multi_block_multi_file_round_trip(tmp_path: Path) -> None:
    files = {"pkg/a.py": SRC, "pkg/b.py": "A = 1\nB = 2\n"}
    edits = [
        FileEdit("pkg/b.py", "B = 2", "B = 3"),
        FileEdit("pkg/a.py", "return 0", "return 1"),
        FileEdit("pkg/a.py", "y = x + 1", "y = x * 2"),
    ]
    out = _expect(files, edits, tmp_path / "r")
    assert out["pkg/b.py"] == "A = 1\nB = 3\n"
    assert out["pkg/a.py"] == SRC.replace("return 0", "return 1").replace("x + 1", "x * 2")


def test_atomic_failure_has_no_diff() -> None:
    files = {"a.py": SRC, "b.py": "A = 1\n"}
    edits = [FileEdit("a.py", "return 0", "return 1"), FileEdit("b.py", "A = 9", "A = 2")]
    r = convert_edits(edits, reader_of(files))
    assert r.diff is None and r.failure and (r.failure.kind, r.failure.block) == ("no_match", 1)


def test_blocks_apply_in_order_to_the_text_the_earlier_blocks_left(tmp_path: Path) -> None:
    files = {"a.py": SRC}
    # a repeated block fails: its SEARCH text is gone after the first one
    twice = [FileEdit("a.py", "return 0", "return 5"), FileEdit("a.py", "return 0", "return 5")]
    r = convert_edits(twice, reader_of(files))
    assert r.failure and (r.failure.kind, r.failure.block) == ("no_match", 1)
    # a block may match text an earlier block produced
    chained = [FileEdit("a.py", "return 0", "return 5"), FileEdit("a.py", "return 5", "return 6")]
    out = _expect(files, chained, tmp_path / "r")
    assert out["a.py"] == SRC.replace("return 0", "return 6")


def test_overlap_in_base_text_is_reported_as_a_sensitivity_only() -> None:
    files = {"a.py": SRC}
    nested = [
        FileEdit("a.py", "y = x + 1\n    return y", "return x"),
        FileEdit("a.py", "return y", "return 0"),
    ]
    assert blocks_overlap_in_base(nested, reader_of(files))
    apart = [FileEdit("a.py", "y = x + 1", "y = 0"), FileEdit("a.py", "return 0", "return 1")]
    assert not blocks_overlap_in_base(apart, reader_of(files))
    assert convert_edits(apart, reader_of(files)).applied


def test_no_trailing_newline_and_form_feed_round_trip(tmp_path: Path) -> None:
    files = {"a.py": "x = 1\n\x0c\ny = 2"}
    out = _expect(files, [FileEdit("a.py", "y = 2", "y = 3")], tmp_path / "r")
    assert out["a.py"] == "x = 1\n\x0c\ny = 3"


def test_noop_edit_set_is_applied_empty() -> None:
    r = convert_edits([FileEdit("a.py", "return 0", "return 0")], reader_of({"a.py": SRC}))
    assert r.applied and r.diff == "" and r.outcome == "applied_empty"


def test_unified_diff_of_equal_texts_is_empty() -> None:
    assert unified_diff("a.py", SRC, SRC) == ""


def test_reply_parse_failure_is_typed_and_distinct() -> None:
    r = convert_reply("I cannot give an edit.", reader_of({}))
    assert r.failure and r.failure.kind == "parse" and r.failure.detail == "no_edit_block"
    reply = "FILE: a.py\n<<<<<<< SEARCH\nreturn 0\n=======\nreturn 1\n>>>>>>> REPLACE\n"
    r = convert_reply(reply, reader_of({"a.py": SRC}))
    assert r.outcome == "applied" and "-    return 0" in (r.diff or "")


def test_deterministic() -> None:
    files = {"a.py": SRC}
    edits = [FileEdit("a.py", "return 0", "return 1")]
    assert (
        convert_edits(edits, reader_of(files)).diff == convert_edits(edits, reader_of(files)).diff
    )


def test_unknown_reading_rejected() -> None:
    with pytest.raises(ValueError):
        convert_edits([FileEdit("a.py", "x", "y")], reader_of({"a.py": "x"}), "fuzzy")  # type: ignore[arg-type]


def test_git_reader_reads_blob_at_commit(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "a.py").write_text(SRC)
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.org",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.org",
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
    }
    subprocess.run(["git", "-C", str(repo), "add", "a.py"], check=True, env=env)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "x"], check=True, env=env)
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    read = git_reader(str(repo / ".git"), head)
    assert read("a.py") == SRC and read("nope.py") is None


def test_git_reader_refuses_an_unreadable_repository_or_commit(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        git_reader(str(tmp_path / "nope.git"), "0" * 40)
