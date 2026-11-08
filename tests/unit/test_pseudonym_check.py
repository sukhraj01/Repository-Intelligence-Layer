"""Round-trip checks on prepared prompts (docs/RQ3_PILOT.md, D120)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from ril.agent.contracts import FileEdit
from ril.agent.providers.patch_convert import git_reader, reader_of
from ril.agent.providers.patch_format import build_prompt
from ril.agent.providers.pseudonym_check import (
    excerpt_round_trip,
    gold_round_trip,
    overlaps,
    placeholder_lines,
)
from ril.agent.providers.pseudonymise import pseudonymise

SRC = (
    "import os\n"
    "AUTHOR = 'jane@corp.example'\n"
    "ROOT = '\x2fhome/jane/data'\n"
    "def f():\n"
    "    return 1\n"
    "def g():\n"
    "    return 2\n"
)
CONTEXT = "### pkg/mod.py:1-5 module m (rank 1)\n" + SRC.rsplit("def g", 1)[0]


def test_placeholder_lines_and_excerpt_round_trip() -> None:
    prompt, mp = pseudonymise(build_prompt("an issue", CONTEXT))
    lines = placeholder_lines(prompt)
    assert [f for f, _ in lines] == ["pkg/mod.py", "pkg/mod.py"]
    rows = excerpt_round_trip(prompt, mp, reader_of({"pkg/mod.py": SRC}))
    assert [r["outcome"] for r in rows] == ["applied", "applied"]
    assert all(r["writes_original"] for r in rows)
    # a line that is not unique in the file is reported as such, not as a defect
    twice = reader_of({"pkg/mod.py": SRC + "AUTHOR = 'jane@corp.example'\n"})
    assert [r["outcome"] for r in excerpt_round_trip(prompt, mp, twice)][0] == "multiple_matches"


def test_overlap_is_false_for_edits_away_from_substitutions() -> None:
    _, mp = pseudonymise(build_prompt("an issue", CONTEXT))
    assert not overlaps([FileEdit("pkg/mod.py", "def g():\n    return 2", "x")], mp)
    assert overlaps([FileEdit("pkg/mod.py", "AUTHOR = 'jane@corp.example'", "x")], mp)


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t.invalid", *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.strip()


def test_gold_round_trip_gives_the_gold_tree(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    (repo / "pkg").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "pkg" / "mod.py").write_text(SRC, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    commit = _git(repo, "rev-parse", "HEAD")
    new = SRC.replace("ROOT = '\x2fhome/jane/data'", "ROOT = None").replace("return 1", "return 3")
    (repo / "pkg" / "mod.py").write_text(new, encoding="utf-8")
    gold = _git(repo, "diff") + "\n"
    _git(repo, "checkout", "-q", "--", ".")
    _, mp = pseudonymise(build_prompt("an issue", CONTEXT))
    read = git_reader(str(repo), commit)
    scratch = tmp_path / "s"
    scratch.mkdir()
    out = gold_round_trip(gold, mp, read, str(repo), commit, str(scratch))
    assert out == {"outcome": "tree_equal", "detail": "", "overlap": True}
