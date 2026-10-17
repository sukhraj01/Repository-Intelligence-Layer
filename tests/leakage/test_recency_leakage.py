"""Leakage: the recency prior never sees a commit after the snapshot (decision D8)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import numpy as np
import pytest

from ril.evaluation.e3_prepare import snapshot_time, unit_graph_arrays
from ril.parsing.build import BuildConfig, build_repository
from ril.retrieval.recency import ages_in_days, parse_utc

ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.org",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.org",
}


def _git(cwd: Path, *args: str, when: str | None = None) -> str:
    env = dict(ENV)
    if when:
        env["GIT_AUTHOR_DATE"] = when
        env["GIT_COMMITTER_DATE"] = when
    return subprocess.run(
        ["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "r"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    (root / "a.py").write_text("def f():\n    return 1\n")
    (root / "b.py").write_text("def g():\n    return 2\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "one", when="2020-01-01T00:00:00Z")
    first = _git(root, "rev-parse", "HEAD")
    (root / "b.py").write_text("def g():\n    return 3\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "two", when="2021-06-01T00:00:00Z")
    return root, first


def test_ages_at_an_earlier_snapshot_ignore_later_commits(repo: tuple[Path, str]) -> None:
    root, first = repo
    _git(root, "checkout", "-q", first)
    snap = snapshot_time(str(root))
    assert snap == parse_utc("2020-01-01T00:00:00Z")
    result = build_repository(str(root), BuildConfig(repo_id="acme/mini", seed=0))
    stamps = {u.file: u.last_modified for u in result.parsed.units}
    assert stamps["b.py"] == "2020-01-01T00:00:00Z"  # not the 2021 commit
    ages = ages_in_days([u.last_modified for u in result.parsed.units], snap)
    assert np.all(ages >= 0) and np.all(ages == 0)
    units, _, _, _ = unit_graph_arrays(result)
    assert len(units) == len(result.parsed.units)


def test_latest_snapshot_sees_the_later_commit_and_a_future_stamp_is_rejected(
    repo: tuple[Path, str],
) -> None:
    root, first = repo
    snap = snapshot_time(str(root))
    result = build_repository(str(root), BuildConfig(repo_id="acme/mini", seed=0))
    stamps = {u.file: u.last_modified for u in result.parsed.units}
    assert stamps["b.py"] == "2021-06-01T00:00:00Z" and stamps["a.py"] == "2020-01-01T00:00:00Z"
    with pytest.raises(ValueError, match="leak"):
        ages_in_days(["2030-01-01T00:00:00Z"], snap)
