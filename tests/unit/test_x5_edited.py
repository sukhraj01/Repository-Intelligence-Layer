"""Tests for the edited-function follow-up of the contamination scan (E-CONTAM-EDITED)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from ril.analysis import x5_tables as t
from ril.training import contamination_edited as ce

BASE = '''def keep(x):
    return x + 1


def fix(a, b):
    """Doc."""
    total = a + b
    return total


class K:
    def method(self, n):
        return n * 2
'''

PATCH = '''diff --git a/pkg/mod.py b/pkg/mod.py
--- a/pkg/mod.py
+++ b/pkg/mod.py
@@ -4,4 +4,4 @@
 def fix(a, b):
     """Doc."""
-    total = a + b
+    total = a - b
     return total
diff --git a/docs/readme.rst b/docs/readme.rst
--- a/docs/readme.rst
+++ b/docs/readme.rst
@@ -1,1 +1,2 @@
 hello
+world
'''


def _repo(tmp: Path) -> tuple[str, str]:
    work = tmp / "w"
    (work / "pkg").mkdir(parents=True)
    (work / "pkg" / "mod.py").write_text(BASE)
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "a",
        "GIT_AUTHOR_EMAIL": "a@b",
        "GIT_COMMITTER_NAME": "a",
        "GIT_COMMITTER_EMAIL": "a@b",
    }
    for cmd in (["init", "-q"], ["add", "."], ["commit", "-q", "-m", "m"]):
        subprocess.run(["git", "-C", str(work), *cmd], check=True, env=env, capture_output=True)
    sha = subprocess.run(
        ["git", "-C", str(work), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    return str(work / ".git"), sha


def test_python_part_drops_non_python_sections() -> None:
    kept = ce.python_part(PATCH)
    assert "mod.py" in kept and "readme.rst" not in kept


def test_edited_function_before_and_after(tmp_path: Path) -> None:
    git_dir, sha = _repo(tmp_path)
    rec = ce.edited_functions(git_dir, "o/r", sha, PATCH)
    assert rec["patch_applied"] and rec["patched_py_files"] == 1
    assert [e["qname"] for e in rec["edited"]] == ["fix"]
    e = rec["edited"][0]
    assert e["pre_hash"] and e["post_hash"] and e["pre_hash"] != e["post_hash"]
    assert rec["added"] == []


def test_patch_that_does_not_apply_is_flagged(tmp_path: Path) -> None:
    git_dir, sha = _repo(tmp_path)
    bad = PATCH.replace("total = a + b", "total = zzz")
    rec = ce.edited_functions(git_dir, "o/r", sha, bad)
    assert not rec["patch_applied"]
    assert rec["edited"][0]["post_known"] is False


def test_added_function_from_created_file(tmp_path: Path) -> None:
    git_dir, sha = _repo(tmp_path)
    new = (
        "diff --git a/pkg/new.py b/pkg/new.py\nnew file mode 100644\n"
        "--- /dev/null\n+++ b/pkg/new.py\n"
        "@@ -0,0 +1,2 @@\n+def fresh(q):\n+    return q * q + 1\n"
    )
    rec = ce.edited_functions(git_dir, "o/r", sha, new)
    assert rec["edited"] == [] and [a["qname"] for a in rec["added"]] == ["fresh"]


def _rec(
    pre: str, post: str | None, nodes: int = 30, same: list[list[object]] | None = None
) -> dict[str, object]:
    return {
        "patch_applied": True,
        "unparseable_pre": 0,
        "unparseable_post": 0,
        "patched_py_files": 1,
        "created_py_files": 0,
        "added": [],
        "same_file_unedited": same or [],
        "edited": [
            {
                "file": "f.py",
                "qname": "g",
                "occurrence": 1,
                "pre_hash": pre,
                "pre_nodes": nodes,
                "post_hash": post,
                "post_nodes": nodes,
                "post_known": True,
            }
        ],
    }


def test_floor_table_counts_and_denominators() -> None:
    edited = {"i1": _rec("a", "a2", same=[["x", 30]]), "i2": _rec("b", "b2", same=[["z", 30]])}
    inst = {
        "i1": ("r1", {"a": 30, "x": 30, "y": 30}),
        "i2": ("r2", {"b": 30, "x": 30, "z": 30}),
    }
    docs = {"a", "x", "a2"}
    tab = t.floor_table(edited, inst, docs, 20)
    pre = tab["pre_vs_other"]
    assert (pre["a_matched"], pre["a_n"]) == (1, 2)  # edited a (hit), b (no hit)
    assert (pre["b_matched"], pre["b_n"]) == (2, 4)  # x is a hit in both repositories
    assert tab["pre_vs_same_file"]["b_n"] == 2
    assert tab["post_vs_other"]["a_matched"] == 1 and tab["post_vs_other"]["a_n"] == 2
    assert tab["all_base_commit_functions_n"] == 5 and tab["all_base_commit_functions_matched"] == 2
    assert tab["changed_pre_and_post_looked_up"] == 2
    assert tab["changed_pre_only_match"] == 0 and tab["changed_post_only_match"] == 0
    assert tab["changed_pre_and_post_match"] == 1 and tab["changed_neither_match"] == 1
    assert tab["instances_with_a_matched_edited_function"] == 1


def test_clustered_diff_is_deterministic() -> None:
    rows = [[1, 2, 3, 10], [0, 3, 2, 10], [2, 2, 1, 10]]
    assert t.clustered_diff(rows, 200, 0) == t.clustered_diff(rows, 200, 0)
