"""Python files of one repository at one commit, as a sparse directory (design D63).

Implements ``docs/experiments/B.md`` E-MINE-PILOT. The parser needs the ``.py`` files of the base
commit and nothing else, so only those are written: a shallow fetch of the one commit into a bare
repository, then walk of the commit's tree for regular ``*.py`` blobs. The fetch goes to the git
endpoint, not the REST API, so it does not use the API rate limit. :class:`SnapshotProvider` is the
seam the miner depends on; tests substitute an in-memory provider.

Kept compatible with Python 3.10 (the cluster's compute nodes).
"""

from __future__ import annotations

import os
import posixpath
import shutil
import subprocess
import time
from collections.abc import Mapping
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Protocol

from ril.util.log import get_logger

log = get_logger("data_mining.snapshot")
GIT_TIMEOUT_S = 900
FETCH_ATTEMPTS = 3


class SnapshotError(RuntimeError):
    """The commit could not be fetched or unpacked (the pull request is quarantined)."""


class SnapshotProvider(Protocol):
    """Writes the Python files of ``repo`` at ``sha`` under ``dest`` (created by the caller)."""

    def materialize(self, repo: str, sha: str, dest: str) -> int: ...

    def prefetch(self, repo: str, sha: str) -> None:
        """Hint that ``sha`` is needed soon (a provider may start fetching it)."""
        ...

    def close(self) -> None:
        """Release background work."""
        ...


def safe_member_path(name: str) -> str | None:
    """Normalised relative posix path of a tar member, or ``None`` if it escapes the root."""
    norm = posixpath.normpath(name)
    if norm.startswith("/") or norm == ".." or norm.startswith("../") or norm == ".":
        return None
    return norm


class GitSnapshots:
    """Fetch a commit shallowly and unpack its Python files.

    ``remote`` is a template with ``{repo}`` (``owner/name``). Each commit gets its own bare
    repository under ``work`` (a shallow fetch of one commit shares nothing with another, and
    separate repositories let fetches of several commits run side by side without lock
    contention); it is removed when the commit has been unpacked. :meth:`prefetch` starts a fetch
    in a worker thread so the network wait of the next pull requests overlaps the parsing of the
    current one; the files written are the same with or without it.
    """

    def __init__(
        self, work: str, remote: str = "https://github.com/{repo}.git", workers: int = 4
    ) -> None:
        self.work = work
        self.remote = remote
        self.workers = workers
        self._pool: ThreadPoolExecutor | None = None
        self._pending: dict[tuple[str, str], Future[None]] = {}

    def _bare(self, repo: str, sha: str) -> str:
        return os.path.join(self.work, f"{repo.replace('/', '__')}__{sha[:16]}.git")

    def _git(self, repo: str, sha: str, *args: str) -> subprocess.CompletedProcess[bytes]:
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_ASKPASS="true")
        return subprocess.run(
            ["git", "-C", self._bare(repo, sha), *args],
            capture_output=True,
            timeout=GIT_TIMEOUT_S,
            env=env,
            check=False,
        )

    def _fetch(self, repo: str, sha: str) -> None:
        """Shallow-fetch ``sha`` into its own bare repository (retried; raises SnapshotError)."""
        bare = self._bare(repo, sha)
        shutil.rmtree(bare, ignore_errors=True)
        os.makedirs(self.work, exist_ok=True)
        done = subprocess.run(
            ["git", "init", "--bare", "--quiet", bare], capture_output=True, check=False
        )
        if done.returncode != 0:
            raise SnapshotError(f"git init failed: {done.stderr.decode()[:200]}")
        url = self.remote.format(repo=repo)
        err = ""
        for attempt in range(FETCH_ATTEMPTS):
            done = self._git(repo, sha, "fetch", "--depth", "1", "--no-tags", "--quiet", url, sha)
            if done.returncode == 0:
                return
            err = done.stderr.decode("utf-8", "replace")[:200]
            time.sleep(2 * (attempt + 1))
        raise SnapshotError(f"fetch of {sha[:12]} failed: {err}")

    def prefetch(self, repo: str, sha: str) -> None:
        """Start fetching ``sha`` in the background (a no-op if it is already under way)."""
        key = (repo, sha)
        if key in self._pending:
            return
        if self._pool is None:
            self._pool = ThreadPoolExecutor(max_workers=self.workers)
        self._pending[key] = self._pool.submit(self._fetch, repo, sha)

    def close(self) -> None:
        """Stop background fetches and remove the repositories they made."""
        if self._pool is not None:
            self._pool.shutdown(wait=True, cancel_futures=True)
            self._pool = None
        for repo, sha in list(self._pending):
            shutil.rmtree(self._bare(repo, sha), ignore_errors=True)
        self._pending.clear()

    def materialize(self, repo: str, sha: str, dest: str) -> int:
        """Write the ``*.py`` files of the commit under ``dest``; return how many."""
        try:
            pending = self._pending.pop((repo, sha), None)
            if pending is not None:
                pending.result()
            else:
                self._fetch(repo, sha)
            return self._write_python_files(repo, sha, dest)
        finally:
            shutil.rmtree(self._bare(repo, sha), ignore_errors=True)

    def _write_python_files(self, repo: str, sha: str, dest: str) -> int:
        """Write the regular ``*.py`` blobs of the commit's tree under ``dest``.

        The tree is read with ``ls-tree`` and ``cat-file --batch`` rather than ``git archive``,
        because ``git archive`` honours ``export-ignore`` in the repository's attributes and would
        silently leave out files (tests, documentation) that the repository has at that commit.
        """
        listing = self._git(repo, sha, "ls-tree", "-r", "-z", "--full-tree", sha)
        if listing.returncode != 0:
            raise SnapshotError(
                f"ls-tree failed: {listing.stderr.decode('utf-8', 'replace')[:200]}"
            )
        wanted: list[tuple[str, str]] = []  # (blob id, relative path)
        for entry in listing.stdout.split(b"\0"):
            if not entry:
                continue
            meta, _, raw_name = entry.partition(b"\t")
            mode, kind, blob = meta.decode("ascii", "replace").split(" ")
            name = raw_name.decode("utf-8", "surrogateescape")
            if kind != "blob" or mode not in ("100644", "100755") or not name.endswith(".py"):
                continue  # symlinks (120000), submodules (commit) and non-Python files
            rel = safe_member_path(name)
            if rel is not None:
                wanted.append((blob, rel))
        if not wanted:
            return 0
        proc = subprocess.run(
            ["git", "-C", self._bare(repo, sha), "cat-file", "--batch"],
            input="".join(f"{blob}\n" for blob, _ in wanted).encode("ascii"),
            capture_output=True,
            timeout=GIT_TIMEOUT_S,
            env=dict(os.environ, GIT_TERMINAL_PROMPT="0"),
            check=False,
        )
        if proc.returncode != 0:
            raise SnapshotError(f"cat-file failed: {proc.stderr.decode('utf-8', 'replace')[:200]}")
        data, pos, written = proc.stdout, 0, 0
        for blob, rel in wanted:
            end = data.index(b"\n", pos)
            header = data[pos:end].decode("ascii", "replace").split(" ")
            if len(header) != 3 or header[0] != blob or header[1] != "blob":
                raise SnapshotError(f"unexpected cat-file reply for {blob[:12]}: {header}")
            size = int(header[2])
            body = data[end + 1 : end + 1 + size]
            pos = end + 1 + size + 1
            target = os.path.join(dest, *rel.split("/"))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as out:
                out.write(body)
            written += 1
        return written


class MemorySnapshots:
    """Test provider: ``{(repo, sha): {path: source}}`` written to disk on request."""

    def __init__(self, trees: Mapping[tuple[str, str], Mapping[str, str]]) -> None:
        self.trees = trees
        self.calls: list[tuple[str, str]] = []
        self.prefetched: list[tuple[str, str]] = []
        self.closed = False

    def prefetch(self, repo: str, sha: str) -> None:
        self.prefetched.append((repo, sha))

    def close(self) -> None:
        self.closed = True

    def materialize(self, repo: str, sha: str, dest: str) -> int:
        self.calls.append((repo, sha))
        tree = self.trees.get((repo, sha))
        if tree is None:
            raise SnapshotError(f"no such commit {sha[:12]}")
        for path, text in tree.items():
            target = os.path.join(dest, *path.split("/"))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as out:
                out.write(text)
        return len(tree)
