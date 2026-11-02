"""Unified-diff parsing for the PR-mined set: changed lines on the old side, per file.

Implements ``docs/experiments/B.md`` E-MINE-PILOT, design D63: the compare endpoint returns one
``patch`` per file; positives are the units of the *base* commit, so only the old side of each hunk
matters. This module turns a patch into the old-side line numbers that were removed or rewritten,
the pure insertions (a gap between two old lines plus the inserted text), and the names of
functions the patch defines or removes. Nothing here reads a repository.

Kept compatible with Python 3.10 (the cluster's compute nodes).
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
DEF_RE = re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_][A-Za-z_0-9]*)")
COMPARE_FILE_CAP = 300
"""The compare endpoint lists at most 300 files; a list that long may be cut short."""


class PatchError(ValueError):
    """A patch that does not follow the unified-diff grammar (never repaired silently)."""


@dataclass(frozen=True)
class Insertion:
    """Lines added between old line ``after_old_line`` and the next one (0 = before the first)."""

    after_old_line: int
    lines: tuple[str, ...]


@dataclass(frozen=True)
class FilePatch:
    """What one patch changes on the old side, and the functions it defines or removes."""

    removed: tuple[int, ...]
    """Old-side line numbers that were removed or rewritten (1-based, sorted, distinct)."""
    insertions: tuple[Insertion, ...]
    """Pure insertions (a run of added lines with no removed line next to it), in file order."""
    added_defs: tuple[str, ...]
    """Names defined by added lines and not removed by the same patch (multiset difference)."""
    removed_defs: tuple[str, ...]
    hunks: int


def parse_patch(patch: str) -> FilePatch:
    """Parse one file's ``patch`` text (hunks only, no file header).

    A run of ``+`` lines directly after a ``-`` line is a rewrite (the ``-`` lines own it); any
    other run is a pure insertion at the old position it follows. Raises :class:`PatchError` when
    a hunk is cut short or a line has no valid marker.
    """
    removed: list[int] = []
    insertions: list[Insertion] = []
    plus_defs: Counter[str] = Counter()
    minus_defs: Counter[str] = Counter()
    hunks = 0
    old_pos = 0  # last old line consumed
    old_left = new_left = 0
    pending: list[str] = []
    prev = ""  # marker of the previous diff line within the hunk

    def flush() -> None:
        nonlocal pending
        if pending and prev != "-":
            insertions.append(Insertion(old_pos, tuple(pending)))
        pending = []

    for raw in patch.split("\n"):
        if old_left <= 0 and new_left <= 0:
            m = HUNK_RE.match(raw)
            if m is None:
                if raw.strip() == "" or raw.startswith("\\"):
                    continue
                raise PatchError(f"line outside a hunk: {raw[:60]!r}")
            hunks += 1
            old_start = int(m.group(1))
            old_n = int(m.group(2)) if m.group(2) is not None else 1
            new_n = int(m.group(4)) if m.group(4) is not None else 1
            # a zero-length old range names the line *before* the gap
            old_pos = old_start if old_n == 0 else old_start - 1
            old_left, new_left = old_n, new_n
            prev = ""
            pending = []
            continue
        marker, text = raw[:1], raw[1:]
        if marker == "\\":
            continue
        if marker == " " or (marker == "" and raw == ""):
            flush()
            old_pos += 1
            old_left -= 1
            new_left -= 1
            prev = " "
        elif marker == "-":
            flush()
            old_pos += 1
            old_left -= 1
            removed.append(old_pos)
            hit = DEF_RE.match(text)
            if hit:
                minus_defs[hit.group(1)] += 1
            prev = "-"
        elif marker == "+":
            new_left -= 1
            pending.append(text)
            hit = DEF_RE.match(text)
            if hit:
                plus_defs[hit.group(1)] += 1
            # ``prev`` is left alone: the run is judged by the marker that came before it
        else:
            raise PatchError(f"unknown line marker {marker!r}")
    if pending and prev != "-":
        insertions.append(Insertion(old_pos, tuple(pending)))
    if old_left > 0 or new_left > 0:
        raise PatchError("patch ends inside a hunk")
    added = plus_defs - minus_defs
    gone = minus_defs - plus_defs
    return FilePatch(
        removed=tuple(sorted(set(removed))),
        insertions=tuple(insertions),
        added_defs=tuple(sorted(added.elements())),
        removed_defs=tuple(sorted(gone.elements())),
        hunks=hunks,
    )


@dataclass(frozen=True)
class FileChange:
    """One entry of the compare ``files`` list, with its patch parsed when it is Python."""

    path: str
    old_path: str
    status: str
    is_python: bool
    patch: FilePatch | None
    patch_missing: bool
    additions: int = 0
    deletions: int = 0
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Comparison:
    """The parsed compare response of one pull request."""

    merge_base: str
    head: str
    files: tuple[FileChange, ...]
    files_listed: int
    truncated: bool
    """The list reached the endpoint's 300-file cap; the diff may be incomplete."""

    def python_files(self) -> tuple[FileChange, ...]:
        """Changed Python files, in the order the endpoint listed them."""
        return tuple(f for f in self.files if f.is_python)


def is_python_path(path: str) -> bool:
    """Only ``.py`` files are units (the parser's rule); stubs and notebooks are not."""
    return path.endswith(".py")


def parse_comparison(doc: Mapping[str, Any]) -> Comparison:
    """Parse a compare-endpoint response (``merge_base_commit``, ``commits``, ``files``).

    A Python file without a ``patch`` that was not just renamed or added empty is flagged
    ``patch_missing`` (binary, or too large for the endpoint to inline): the caller quarantines
    the pull request rather than guess its hunks.
    """
    base = doc.get("merge_base_commit") or {}
    merge_base = str(base.get("sha") or "")
    if not merge_base:
        raise PatchError("compare response has no merge_base_commit")
    commits = doc.get("commits") or []
    head = str(commits[-1]["sha"]) if commits else str(doc.get("head_sha") or "")
    entries: list[FileChange] = []
    raw_files: Sequence[Mapping[str, Any]] = doc.get("files") or []
    for f in raw_files:
        path = str(f["filename"])
        status = str(f.get("status") or "")
        old_path = str(f.get("previous_filename") or path)
        py = is_python_path(path) or is_python_path(old_path)
        patch_text = f.get("patch")
        patch: FilePatch | None = None
        missing = False
        notes: list[str] = []
        if py:
            if isinstance(patch_text, str) and patch_text != "":
                patch = parse_patch(patch_text)
            elif status != "removed" and int(f.get("changes") or 0) > 0:
                missing = True  # a deleted file needs no patch: every unit of it is gone
            if status == "renamed" and patch is None and not missing:
                notes.append("renamed-only")
        entries.append(
            FileChange(
                path=path,
                old_path=old_path,
                status=status,
                is_python=py,
                patch=patch,
                patch_missing=missing,
                additions=int(f.get("additions") or 0),
                deletions=int(f.get("deletions") or 0),
                notes=tuple(notes),
            )
        )
    return Comparison(
        merge_base=merge_base,
        head=head,
        files=tuple(entries),
        files_listed=len(entries),
        truncated=len(entries) >= COMPARE_FILE_CAP,
    )


def merge_pages(pages: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Join the paginated compare responses: first page's metadata, files of all pages in order."""
    out: dict[str, Any] = {}
    files: list[Any] = []
    for i, page in enumerate(pages):
        if i == 0:
            out = {k: v for k, v in page.items() if k != "files"}
        files.extend(page.get("files") or [])
    out["files"] = files
    return out
