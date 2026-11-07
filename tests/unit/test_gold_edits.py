"""Edit blocks derived from a gold patch (D110): procedure, limits, and the round trip."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from ril.agent.providers.patch_convert import convert_reply, reader_of, unified_diff
from ril.evaluation.gold_edits import derive_edits, parse_hunks, render_reply, tree_after

BASE = "".join(f"line {i}\n" for i in range(1, 41))


def _gold(after: str, path: str = "m.py") -> str:
    return unified_diff(path, BASE, after)


def test_hunks_of_a_two_hunk_patch() -> None:
    after = BASE.replace("line 3\n", "line three\n").replace("line 30\n", "line 30\nextra\n")
    hunks, why = parse_hunks(_gold(after))
    assert not why and len(hunks) == 2
    assert hunks[0].before[0] == "line 1" and "line three" in hunks[0].after


def test_derived_edits_reproduce_the_gold_result() -> None:
    after = BASE.replace("line 3\n", "line three\n").replace("line 30\n", "line 30\nextra\n")
    files = {"m.py": BASE}
    derived = derive_edits(_gold(after), reader_of(files))
    assert not derived.limit and len(derived.edits) == 2
    converted = convert_reply(render_reply(derived.edits), reader_of(files), "exact")
    assert converted.applied and converted.diff == _gold(after)


def test_context_is_extended_until_the_search_text_is_unique() -> None:
    base = "a = 1\nb = 2\nc = 3\n" * 3 + "d = 4\n"
    after = base.replace("d = 4", "d = 5")
    patch = unified_diff("m.py", base, after)
    derived = derive_edits(patch, reader_of({"m.py": base}))
    assert not derived.limit
    assert derived.edits[0].old.count("\n") >= 1 and base.count(derived.edits[0].old) == 1


def test_new_file_and_rename_are_derivation_limits() -> None:
    new = (
        "diff --git a/n.py b/n.py\nnew file mode 100644\n--- /dev/null\n+++ b/n.py\n"
        "@@ -0,0 +1 @@\n+x\n"
    )
    assert derive_edits(new, reader_of({})).limit == "unsupported:new_file"
    ren = "diff --git a/a.py b/b.py\nrename from a.py\nrename to b.py\n"
    assert derive_edits(ren, reader_of({})).limit == "unsupported:rename"


def test_missing_base_file_is_a_limit() -> None:
    after = BASE.replace("line 3\n", "x\n")
    assert derive_edits(_gold(after), reader_of({})).limit == "unsupported:file_missing"


def test_deletion_of_the_last_line_without_newline() -> None:
    base = "a\nb\nc"
    after = "a\nb"
    patch = unified_diff("m.py", base, after)
    derived = derive_edits(patch, reader_of({"m.py": base}))
    assert not derived.limit
    out = convert_reply(render_reply(derived.edits), reader_of({"m.py": base}))
    assert out.applied


def test_tree_after_equal_for_gold_and_converted_patch(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "m.py").write_text(BASE)
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.org",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.org",
    }
    subprocess.run(["git", "-C", str(repo), "add", "m.py"], check=True, env=env)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "x"], check=True, env=env)
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    after = BASE.replace("line 3\n", "line three\n")
    gold = _gold(after)
    derived = derive_edits(gold, reader_of({"m.py": BASE}))
    converted = convert_reply(render_reply(derived.edits), reader_of({"m.py": BASE}), "exact")
    scratch = str(tmp_path)
    a = tree_after(str(repo / ".git"), head, gold, scratch)
    b = tree_after(str(repo / ".git"), head, converted.diff or "", scratch)
    assert a and a == b
    assert tree_after(str(repo / ".git"), head, "not a patch", scratch) is None
