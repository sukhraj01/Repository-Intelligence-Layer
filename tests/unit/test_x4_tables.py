"""Tests for the contamination-scan tables (E-CONTAM-SCAN)."""

from __future__ import annotations

import math
import os
import subprocess
from pathlib import Path

from ril.analysis import x4_tables as t


def test_wilson_bounds_and_empty() -> None:
    lo, hi = t.wilson(0, 10)
    assert abs(lo) < 1e-9 and 0 < hi < 0.4
    lo, hi = t.wilson(10, 10)
    assert abs(hi - 1.0) < 1e-9 and lo > 0.6
    assert all(math.isnan(x) for x in t.wilson(0, 0))


def test_collect_hits_flags_truncation_and_text_only() -> None:
    a = {
        "shard": 3,
        "counts": {"rows": 10, "documents": 10, "any_hits": 3},
        "hits": [{"ast_hash": "x"}, {"ast_hash": "x"}, {"ast_hash": None}],
    }
    b = {
        "shard": 4,
        "counts": {"rows": 5, "documents": 5, "any_hits": 2},
        "hits": [{"ast_hash": "y"}],
    }
    docs, chk = t.collect_hits([a, b])
    assert docs == {"x": 2, "y": 1}
    assert chk["text_only_hits"] == 1 and chk["truncated_shards"] == [4]
    assert chk["rows"] == 15 and chk["shards"] == 2


def test_repo_table_floor_and_own_base_commit() -> None:
    inst = {
        "i1": ("r/a", {"h1": 25, "h2": 5, "h3": 60}),
        "i2": ("r/a", {"h1": 25}),
        "i3": ("r/b", {"h4": 30}),
    }
    docs = {"h1": 3, "h2": 100, "h4": 2, "h9": 7}  # h9 is not at any base commit
    rows = {r["repo"]: r for r in t.repo_table(inst, docs, floor=20)}
    a = rows["r/a"]
    assert a["functions_above_floor"] == 2  # h2 is under the floor
    assert a["functions_matched"] == 1 and a["hit_documents"] == 3
    assert a["instances_with_hit"] == 2 and a["instances"] == 2
    assert rows["r/b"]["hit_documents"] == 2
    assert rows["ALL (hash counted once)"]["hit_documents"] == 5


def test_share_per_instance() -> None:
    inst = {"i1": ("r/a", {"h1": 25, "h3": 60}), "i2": ("r/a", {"h3": 60, "h4": 70})}
    rows = {r["repo"]: r for r in t.repo_table(inst, {"h1": 1}, floor=20)}
    a = rows["r/a"]
    assert a["matched_share_per_instance_min"] == 0.0
    assert a["matched_share_per_instance_max"] == 0.5
    assert a["instances_with_hit"] == 1


def test_size_profile_buckets() -> None:
    p = t.size_profile({"a": 2, "b": 1, "c": 1}, {"a": 5, "b": 30, "c": 150})
    assert p == {"under 20": 2, "20 to 49": 1, "50 to 99": 0, "100 or more": 1}


def test_config_hash_stable() -> None:
    assert t.config_hash({"a": 1}) == t.config_hash({"a": 1})
    assert t.config_hash({"a": 1}) != t.config_hash({"a": 2})


def test_instance_hashes_follow_the_commit(tmp_path: Path) -> None:
    from ril.training.contamination_index import instance_hashes

    def git(*a: str) -> str:
        env = {
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t",
            "PATH": os.environ["PATH"],
            "HOME": str(tmp_path),
        }
        return subprocess.run(
            ["git", "-C", str(tmp_path), *a], check=True, capture_output=True, text=True, env=env
        ).stdout.strip()

    git("init", "-q")
    big = "def f(x):\n    y = x + 1\n    z = [i for i in range(y)]\n    return sum(z) * 2\n"
    (tmp_path / "a.py").write_text(big)
    git("add", "a.py")
    git("commit", "-q", "-m", "one")
    c1 = git("rev-parse", "HEAD")
    (tmp_path / "a.py").write_text("def g():\n    return 1\n")
    git("commit", "-q", "-am", "two")
    c2 = git("rev-parse", "HEAD")
    out = instance_hashes(
        {"r/a": str(tmp_path / ".git")}, {"i1": ("r/a", c1), "i2": ("r/a", c2)}, 10
    )
    assert len(out["i1"]) == 1 and out["i2"] == {}
