"""Edit blocks to a unified diff at the base commit. Implements ``docs/RQ3_PILOT.md`` (D110).

The pilot's reply format (``patch_format.py``) is a list of SEARCH/REPLACE blocks. The executor
(``ril/evaluation/executor``) takes a unified diff. This module is the single place where the two
meet, so the rule for applying a block is fixed once and is the same for every arm:

* ``exact`` (primary): a block's SEARCH text must occur in the file as an exact string, exactly
  once, counting overlapping occurrences.
* ``tolerant`` (labelled sensitivity): the same rule after normalising line endings and trailing
  whitespace on every line and ignoring blank lines at the start and end of the SEARCH text.
  Still exactly one match; the replacement is inserted as given. No fuzzy matching, no
  indentation repair, no edit-distance search.

An edit set is atomic: if any block fails, there is no diff. Blocks are applied in the order of
the reply, each to the text of its file as the earlier blocks left it (so a block may match text an
earlier block produced, and a repeated block fails with ``no_match``); the diff is taken between
the base-commit text and the final text of each file. ``blocks_overlap_in_base`` tells whether the
SEARCH regions of two blocks of one file overlap in the base text (a stricter reading, reported as
a sensitivity, never used for grading).
"""

from __future__ import annotations

import difflib
import subprocess
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from ril.agent.contracts import FileEdit
from ril.agent.providers.patch_format import parse_edits

Reading = Literal["exact", "tolerant"]
READINGS: tuple[Reading, ...] = ("exact", "tolerant")
FAILURES = ("file_missing", "no_match", "multiple_matches", "parse")
NO_NEWLINE = "\\ No newline at end of file\n"


@dataclass(frozen=True)
class Failure:
    """Why an edit set has no diff: a class of ``FAILURES``, the first failing block, a detail."""

    kind: str
    block: int = -1
    path: str = ""
    detail: str = ""


@dataclass(frozen=True)
class Conversion:
    """Either ``diff`` (possibly empty when every block replaces text by itself) or ``failure``."""

    diff: str | None = None
    failure: Failure | None = None
    n_blocks: int = 0

    @property
    def applied(self) -> bool:
        return self.failure is None

    @property
    def outcome(self) -> str:
        """``applied``, ``applied_empty`` (no-op edit set) or the failure class."""
        if self.failure is not None:
            return self.failure.kind
        return "applied" if self.diff else "applied_empty"


def _occurrences(text: str, needle: str) -> list[int]:
    """Start offsets of every occurrence of ``needle``, overlapping ones included."""
    out: list[int] = []
    at = text.find(needle)
    while at != -1:
        out.append(at)
        at = text.find(needle, at + 1)
    return out


def _lines(text: str) -> list[str]:
    """Split on ``\\n`` only, keeping the terminator (``str.splitlines`` also splits on form feeds
    and other separators that occur inside Python source)."""
    parts = text.split("\n")
    out = [p + "\n" for p in parts[:-1]]
    if parts[-1]:
        out.append(parts[-1])
    return out


def _normalise_block(old: str) -> str:
    rows = [r.rstrip() for r in old.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while rows and not rows[0]:
        rows.pop(0)
    while rows and not rows[-1]:
        rows.pop()
    return "\n".join(rows)


def _normalised_file(text: str) -> tuple[str, list[int]]:
    """Normalised text of a file and, for each offset of it, the offset in the original.

    Trailing whitespace (including a carriage return) is removed from every line; the map has one
    entry more than the text so that an end offset can be mapped too.
    """
    out: list[str] = []
    back: list[int] = []
    pos = 0
    rows = text.split("\n")
    for k, row in enumerate(rows):
        body = row.rstrip()
        for j in range(len(body)):
            back.append(pos + j)
        out.append(body)
        pos += len(row)
        if k < len(rows) - 1:
            back.append(pos)  # the "\n" itself
            out.append("\n")
            pos += 1
    back.append(pos)
    return "".join(out), back


def _spans(text: str, old: str, reading: Reading) -> list[tuple[int, int]]:
    """Every ``(start, end)`` of the original text that the SEARCH text selects."""
    if reading == "exact":
        return [(a, a + len(old)) for a in _occurrences(text, old)]
    needle = _normalise_block(old)
    if not needle:
        return []
    norm, back = _normalised_file(text)
    return [(back[a], back[a + len(needle) - 1] + 1) for a in _occurrences(norm, needle)]


def unified_diff(path: str, before: str, after: str) -> str:
    """``git``-style diff of one file; handles a missing final newline on either side."""
    if before == after:
        return ""
    body: list[str] = []
    for line in difflib.unified_diff(
        _lines(before), _lines(after), f"a/{path}", f"b/{path}", n=3, lineterm="\n"
    ):
        body.append(line if line.endswith("\n") else line + "\n" + NO_NEWLINE)
    return f"diff --git a/{path} b/{path}\n" + "".join(body)


def convert_edits(
    edits: Sequence[FileEdit],
    read_file: Callable[[str], str | None],
    reading: Reading = "exact",
) -> Conversion:
    """Diff of the whole edit set at the base commit, or the first failure (atomic).

    ``read_file`` returns the base-commit text of a repository path, ``None`` when the path does
    not exist there. Files are visited in the order of their first block.
    """
    if reading not in READINGS:
        raise ValueError(f"unknown reading {reading!r}")
    if not edits:
        return Conversion(failure=Failure("parse", detail="no_edit_block"))
    order: list[str] = []
    by_file: dict[str, list[tuple[int, FileEdit]]] = {}
    for i, e in enumerate(edits):
        if e.path not in by_file:
            order.append(e.path)
            by_file[e.path] = []
        by_file[e.path].append((i, e))
    pieces: list[str] = []
    for path in order:
        base = read_file(path)
        if base is None:
            first = by_file[path][0][0]
            return Conversion(failure=Failure("file_missing", first, path), n_blocks=len(edits))
        text = base
        for i, e in by_file[path]:
            spans = _spans(text, e.old, reading)
            if not spans:
                return Conversion(failure=Failure("no_match", i, path), n_blocks=len(edits))
            if len(spans) > 1:
                return Conversion(
                    failure=Failure("multiple_matches", i, path, str(len(spans))),
                    n_blocks=len(edits),
                )
            text = text[: spans[0][0]] + e.new + text[spans[0][1] :]
        pieces.append(unified_diff(path, base, text))
    return Conversion(diff="".join(pieces), n_blocks=len(edits))


def blocks_overlap_in_base(
    edits: Sequence[FileEdit],
    read_file: Callable[[str], str | None],
    reading: Reading = "exact",
) -> bool:
    """Whether two blocks of one file select overlapping regions of the base text, or one of them
    does not select exactly one region there.

    Sensitivity only; ``convert_edits`` does not use it.
    """
    by_file: dict[str, list[FileEdit]] = {}
    for e in edits:
        by_file.setdefault(e.path, []).append(e)
    for path, blocks in by_file.items():
        text = read_file(path)
        if text is None:
            return True
        chosen: list[tuple[int, int]] = []
        for e in blocks:
            spans = _spans(text, e.old, reading)
            if len(spans) != 1:
                return True
            chosen.append(spans[0])
        chosen.sort()
        if any(b[0] < a[1] for a, b in zip(chosen, chosen[1:], strict=False)):
            return True
    return False


def convert_reply(
    reply: str,
    read_file: Callable[[str], str | None],
    reading: Reading = "exact",
    allowed_paths: Collection[str] | None = None,
) -> Conversion:
    """Parse a reply with the pilot's parser, then convert.

    A reply the parser refuses is a ``parse`` failure whose detail is the parser's code (an
    unusable reply, not an apply failure).
    """
    edits, code = parse_edits(reply, allowed_paths)
    if code is not None:
        return Conversion(failure=Failure("parse", detail=code))
    return convert_edits(edits, read_file, reading)


def git_reader(mirror: str, commit: str) -> Callable[[str], str | None]:
    """Reader of file texts at ``commit`` in a (bare) repository, via ``git cat-file``.

    Returns ``None`` for a path that is not a blob at that commit. A repository or commit that
    cannot be read raises ``ValueError`` here, so a missing mirror is never mistaken for a missing
    file. Text that is not UTF-8 raises ``UnicodeDecodeError`` (the caller decides).
    """
    have = subprocess.run(
        ["git", "-C", mirror, "cat-file", "-e", f"{commit}^{{commit}}"],
        capture_output=True,
        check=False,
    )
    if have.returncode != 0:
        raise ValueError(f"commit {commit} is not readable in {mirror}")

    def read(path: str) -> str | None:
        proc = subprocess.run(
            ["git", "-C", mirror, "cat-file", "blob", f"{commit}:{path}"],
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            return None
        return proc.stdout.decode("utf-8")

    return read


def reader_of(files: Mapping[str, str | None]) -> Callable[[str], str | None]:
    """Reader over an in-memory mapping (tests and stored snapshots)."""
    return files.get
