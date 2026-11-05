"""Copy a run root between node-local disk and a durable area at bounded intervals (decision D94).

Implements ``docs/experiments/B.md`` E-MINE-STORE. The full run mines on the node-local disk of a
compute node and keeps the de-duplicated store and the run state on a shared home. A node can be
lost, and a resubmitted job lands on another one, so completed work must reach the durable area
often and in an order that is consistent at every point:

1. ``cas/*/rows.gz``, ``digests.bin``, ``segments.jsonl`` (the commit record last);
2. ``pr/<dir>/`` (a directory is copied under a temporary name and renamed);
3. ``listing/*.json``;
4. the append-only logs, ``state.jsonl`` last of them;
5. the small mutable files (``run.json``, ``budget.json``, ``provenance.json``, ``summary.json``).

Whatever step a crash interrupts, the durable copy is a prefix of the local run in the sense that
the store opens (``cas.RepoRows.committed`` cuts back an unfinished append) and every state row
points at a complete directory. Append-only files are extended from the destination's size after
the last bytes of the destination are checked against the source; a destination that is longer
than the source, or whose tail differs, raises (two runs wrote to one area) instead of being
overwritten. Nothing is ever deleted.

Kept compatible with Python 3.10 (the cluster's compute nodes).
"""

from __future__ import annotations

import os
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ril.data_mining import cas

TAIL_CHECK_BYTES = 65536
APPEND_ONLY_ROOT = ("state.jsonl", "sessions.jsonl")
MUTABLE_ROOT = ("run.json", "budget.json", "provenance.json", "summary.json")
CHUNK = 8 << 20


class DivergedError(RuntimeError):
    """The destination holds bytes that the source does not (or is longer than it)."""


@dataclass
class SyncStats:
    """What one copy pass did."""

    appended_bytes: int = 0
    directories: int = 0
    files: int = 0
    seconds: float = 0.0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "appended_bytes": self.appended_bytes,
            "directories": self.directories,
            "files": self.files,
            "seconds": round(self.seconds, 1),
        }


def _append_only(src: str, dst: str, stats: SyncStats) -> None:
    if not os.path.exists(src):
        return
    size = os.path.getsize(src)
    have = os.path.getsize(dst) if os.path.exists(dst) else 0
    if have > size:
        raise DivergedError(f"{dst} ({have} bytes) is longer than {src} ({size} bytes)")
    if have == size:
        return
    with open(src, "rb") as s:
        if have:
            n = min(have, TAIL_CHECK_BYTES)
            s.seek(have - n)
            tail = s.read(n)
            with open(dst, "rb") as d:
                d.seek(have - n)
                if d.read(n) != tail:
                    raise DivergedError(f"{dst}: the last {n} bytes differ from {src}")
        else:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
        s.seek(have)
        with open(dst, "ab") as d:
            for block in iter(lambda: s.read(CHUNK), b""):
                d.write(block)
                stats.appended_bytes += len(block)
            d.flush()
            os.fsync(d.fileno())
    stats.files += 1


def _copy_file_atomic(src: str, dst: str, stats: SyncStats) -> None:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = dst + ".tmp"
    shutil.copyfile(src, tmp)
    with open(tmp, "rb") as handle:
        os.fsync(handle.fileno())
    os.replace(tmp, dst)
    stats.files += 1


def _same(a: str, b: str) -> bool:
    if not os.path.exists(b) or os.path.getsize(a) != os.path.getsize(b):
        return False
    with open(a, "rb") as x, open(b, "rb") as y:
        return x.read() == y.read()


def _copy_dir_once(src: str, dst: str, stats: SyncStats) -> None:
    tmp = dst + ".tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(src, tmp)
    for dirpath, _d, files in os.walk(tmp):
        for f in files:
            with open(os.path.join(dirpath, f), "rb") as handle:
                os.fsync(handle.fileno())
    os.replace(tmp, dst)
    stats.directories += 1


def copy_run(src_root: str, dst_root: str) -> SyncStats:
    """Copy what ``dst_root`` lacks of ``src_root``, in the order given in the module docstring."""
    t0 = time.perf_counter()
    stats = SyncStats()
    cas_src = os.path.join(src_root, cas.CAS_DIR)
    if os.path.isdir(cas_src):
        for repo in sorted(os.listdir(cas_src)):
            for fname in (cas.ROWS_FILE, cas.DIGESTS_FILE, cas.SEGMENTS_FILE):
                _append_only(
                    os.path.join(cas_src, repo, fname),
                    os.path.join(dst_root, cas.CAS_DIR, repo, fname),
                    stats,
                )
    pr_src = os.path.join(src_root, "pr")
    if os.path.isdir(pr_src):
        for name in cas.instance_names(src_root):
            dst = os.path.join(dst_root, "pr", name)
            if not os.path.exists(os.path.join(dst, "pr_meta.json")):
                _copy_dir_once(os.path.join(pr_src, name), dst, stats)
    lst_src = os.path.join(src_root, "listing")
    if os.path.isdir(lst_src):
        for fname in sorted(os.listdir(lst_src)):
            dst = os.path.join(dst_root, "listing", fname)
            if fname.endswith(".json") and not os.path.exists(dst):
                _copy_file_atomic(os.path.join(lst_src, fname), dst, stats)
    logs = sorted(
        f
        for f in (os.listdir(src_root) if os.path.isdir(src_root) else [])
        if f.endswith(".jsonl") and f not in APPEND_ONLY_ROOT
    )
    for fname in logs + list(APPEND_ONLY_ROOT):  # state.jsonl is the last append-only file
        _append_only(os.path.join(src_root, fname), os.path.join(dst_root, fname), stats)
    for fname in MUTABLE_ROOT:
        path = os.path.join(src_root, fname)
        if os.path.exists(path) and not _same(path, os.path.join(dst_root, fname)):
            _copy_file_atomic(path, os.path.join(dst_root, fname), stats)
    stats.seconds = time.perf_counter() - t0
    return stats


def restore(durable_root: str, local_root: str) -> SyncStats | None:
    """On a node with no run root yet, copy the durable one in; otherwise do nothing (``None``).

    A local root that already holds ``run.json`` is the run in progress on this node and is the
    authority; :func:`copy_run` then pushes what the durable area lacks.
    """
    if os.path.exists(os.path.join(local_root, "run.json")):
        return None
    if not os.path.exists(os.path.join(durable_root, "run.json")):
        return None
    return copy_run(durable_root, local_root)


class Syncer:
    """Pushes the local run root to the durable area every ``every`` outcomes or ``seconds``."""

    def __init__(
        self,
        local_root: str,
        durable_root: str,
        *,
        every: int,
        seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if every < 1 or seconds <= 0:
            raise ValueError("the sync interval must be at least one outcome and a positive time")
        self.local_root = local_root
        self.durable_root = durable_root
        self.every = every
        self.seconds = seconds
        self.clock = clock
        self._since = 0
        self._last = clock()
        self.passes: list[dict[str, Any]] = []

    def tick(self) -> None:
        """Call after each recorded outcome."""
        self._since += 1
        if self._since >= self.every or self.clock() - self._last >= self.seconds:
            self.flush()

    def flush(self) -> None:
        """Push now."""
        stats = copy_run(self.local_root, self.durable_root)
        self.passes.append(stats.to_dict())
        self._since = 0
        self._last = self.clock()
