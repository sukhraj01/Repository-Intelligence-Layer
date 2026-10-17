"""Commit history reachable from a snapshot commit.

Implements decision D8 (``last_modified`` = UTC time of the last commit touching the file, at or
before the snapshot) and the history side of ``co_change`` (``specs/repo_graph.md``, "co_change").
Only ancestors of the snapshot commit are read (``git log <commit>``), selected by ancestry and
never by date, so the fixing change and everything after it are unreachable.

One traversal serves both uses. File lists come from ``--name-only --no-renames``: a rename is a
delete plus an add, so history does not follow renames (a recorded limitation).

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import subprocess
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime

try:
    from datetime import UTC
except ImportError:  # Python 3.10 (cluster nodes)
    from datetime import timezone

    UTC = timezone.utc  # noqa: UP017
from itertools import combinations

_MARK = "\x01"


@dataclass(frozen=True)
class CommitFiles:
    """One commit: hash, committer time (UTC seconds) and the paths it touched."""

    sha: str
    timestamp: int
    paths: tuple[str, ...]


def iter_commits(repo_dir: str, commit: str) -> Iterator[CommitFiles]:
    """Yield the ancestors of ``commit`` (inclusive) with the files each changed.

    Merge commits list no files (git shows no diff for them by default); their changes appear in
    the commits they merge.
    """
    cmd = [
        "git",
        "-c",
        "core.quotepath=off",
        "-C",
        repo_dir,
        "log",
        commit,
        "--name-only",
        "--no-renames",
        f"--format={_MARK}%H%x09%ct",
    ]
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True, encoding="utf-8") as proc:
        assert proc.stdout is not None
        sha, ts = "", 0
        paths: list[str] = []
        for line in proc.stdout:
            line = line.rstrip("\n")
            if line.startswith(_MARK):
                if sha:
                    yield CommitFiles(sha, ts, tuple(paths))
                head, _, stamp = line[1:].partition("\t")
                sha, ts, paths = head, int(stamp), []
            elif line:
                paths.append(line)
        if sha:
            yield CommitFiles(sha, ts, tuple(paths))
        if proc.wait() != 0:
            raise RuntimeError(f"git log failed in {repo_dir} for {commit}")


def format_utc(timestamp: int) -> str:
    """``YYYY-MM-DDTHH:MM:SSZ`` for a UTC timestamp (the D8 spelling)."""
    return datetime.fromtimestamp(timestamp, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class History:
    """What one history traversal yields."""

    last_modified: dict[str, str]  # path -> D8 timestamp
    n_commits: int
    commit_py_sets: list[tuple[str, ...]]  # per commit, sorted .py paths (empty sets dropped)


def read_history(repo_dir: str, commit: str) -> History:
    """Single pass over the ancestors of ``commit``."""
    latest: dict[str, int] = {}
    sets: list[tuple[str, ...]] = []
    n = 0
    for c in iter_commits(repo_dir, commit):
        n += 1
        py: list[str] = []
        for p in c.paths:
            if latest.get(p, -1) < c.timestamp:
                latest[p] = c.timestamp
            if p.endswith(".py"):
                py.append(p)
        if py:
            sets.append(tuple(sorted(set(py))))
    return History({p: format_utc(t) for p, t in sorted(latest.items())}, n, sets)


def co_change_counts(
    commit_sets: list[tuple[str, ...]],
    snapshot_files: set[str],
    thresholds: tuple[int, ...] = (2, 3, 5),
    max_files_per_commit: int = 50,
) -> dict[str, object]:
    """Count file pairs changed together in at least N commits, for each N.

    Only files present in the snapshot are considered; commits touching more than
    ``max_files_per_commit`` such files are skipped (mass edits create dense false couplings) and
    counted. Counts only: no precision claim is attached (exploratory).
    """
    pair_support: Counter[tuple[str, str]] = Counter()
    skipped_large = 0
    used = 0
    for files in commit_sets:
        kept = [f for f in files if f in snapshot_files]
        if len(kept) < 2:
            continue
        if len(kept) > max_files_per_commit:
            skipped_large += 1
            continue
        used += 1
        for a, b in combinations(kept, 2):
            pair_support[(a, b)] += 1
    return {
        "max_files_per_commit": max_files_per_commit,
        "commits_used": used,
        "commits_skipped_too_large": skipped_large,
        "pairs_any_support": len(pair_support),
        "pairs_with_support_at_least": {
            str(n): sum(1 for v in pair_support.values() if v >= n) for n in thresholds
        },
    }
