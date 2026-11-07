"""Edit blocks derived from a gold patch, to test the converter end to end (D110).

Procedure, one block per hunk of the gold patch:

1. SEARCH is the hunk's base-side lines (context and removed lines, in order), REPLACE its
   result-side lines (context and added lines). The context lines the patch carries (three on each
   side where the file allows) are kept, so a block is anchored the way a model's block is.
2. If the SEARCH text is not unique in the base file, context is added from the base file, one
   line on each side in turn, until it is unique or the file is exhausted; a block that is still
   not unique is a derivation limit and the instance has no derived edits.
3. A file the patch creates, deletes or renames has no non-empty SEARCH text at the base commit:
   a derivation limit (``unsupported``), reported, not worked around.

The derived edits are rendered in the pilot's reply format and read back with the pilot's own
parser, so the whole path (reply text, parser, converter) is the one a model's reply takes.
"""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass

from ril.agent.contracts import FileEdit
from ril.agent.providers.patch_format import parse_edits

_FILE = re.compile(r"^diff --git a/(\S+) b/(\S+)$")
_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


@dataclass(frozen=True)
class Hunk:
    path: str
    old_start: int
    before: tuple[str, ...]
    after: tuple[str, ...]


@dataclass(frozen=True)
class Derived:
    """Edits of one instance, or ``limit`` naming why none could be derived."""

    edits: tuple[FileEdit, ...] = ()
    limit: str = ""
    n_hunks: int = 0


def parse_hunks(patch: str) -> tuple[list[Hunk], str]:
    """Hunks of a unified diff and ``""``, or ``([], reason)`` for a patch that creates, deletes
    or renames a file or holds a binary change."""
    hunks: list[Hunk] = []
    path = ""
    lines = patch.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _FILE.match(line)
        if m:
            if m.group(1) != m.group(2):
                return [], "unsupported:rename"
            path = m.group(2)
        elif line.startswith(("new file mode", "--- /dev/null")):
            return [], "unsupported:new_file"
        elif line.startswith(("deleted file mode", "+++ /dev/null")):
            return [], "unsupported:deleted_file"
        elif line.startswith(("rename from", "GIT binary patch", "Binary files")):
            return [], "unsupported:rename_or_binary"
        else:
            h = _HUNK.match(line)
            if h and path:
                before: list[str] = []
                after: list[str] = []
                i += 1
                want_old = int(h.group(2)) if h.group(2) is not None else 1
                want_new = int(h.group(4)) if h.group(4) is not None else 1
                while i < len(lines) and (len(before) < want_old or len(after) < want_new):
                    row = lines[i]
                    if row.startswith("\\"):
                        i += 1
                        continue
                    tag, body = row[:1], row[1:]
                    if tag == " " or (
                        row == "" and len(before) < want_old and len(after) < want_new
                    ):
                        before.append(body)
                        after.append(body)
                    elif tag == "-":
                        before.append(body)
                    elif tag == "+":
                        after.append(body)
                    else:
                        break
                    i += 1
                hunks.append(Hunk(path, int(h.group(1)), tuple(before), tuple(after)))
                continue
        i += 1
    if not hunks:
        return [], "unsupported:no_hunk"
    return hunks, ""


def _unique(text: str, needle: str) -> bool:
    first = text.find(needle)
    return first != -1 and text.find(needle, first + 1) == -1


def derive_edits(patch: str, read_file: Callable[[str], str | None]) -> Derived:
    """Edits (one per hunk) whose application reproduces ``patch``, by the procedure above."""
    hunks, why = parse_hunks(patch)
    if why:
        return Derived(limit=why)
    edits: list[FileEdit] = []
    for h in hunks:
        text = read_file(h.path)
        if text is None:
            return Derived(limit="unsupported:file_missing", n_hunks=len(hunks))
        base_lines = text.split("\n")
        lo = h.old_start - 1
        hi = lo + len(h.before)
        before, after = list(h.before), list(h.after)
        if not before:  # a pure insertion without context cannot be anchored
            return Derived(limit="unsupported:no_anchor", n_hunks=len(hunks))
        if base_lines[lo:hi] != before:
            return Derived(limit="unsupported:hunk_not_at_base", n_hunks=len(hunks))
        while not _unique(text, "\n".join(before)):
            grew = False
            if lo > 0:
                lo -= 1
                before.insert(0, base_lines[lo])
                after.insert(0, base_lines[lo])
                grew = True
            if hi < len(base_lines) - 1:
                before.append(base_lines[hi])
                after.append(base_lines[hi])
                hi += 1
                grew = True
            if not grew:
                return Derived(limit="unsupported:not_unique", n_hunks=len(hunks))
        edits.append(FileEdit(h.path, "\n".join(before), "\n".join(after)))
    try:
        render_reply(tuple(edits))
    except ValueError:
        return Derived(limit="unsupported:reply_format", n_hunks=len(hunks))
    return Derived(edits=tuple(edits), n_hunks=len(hunks))


def render_reply(edits: tuple[FileEdit, ...]) -> str:
    """The reply text of an edit set, in the pilot's format; read back by ``parse_edits``."""
    parts = [
        f"FILE: {e.path}\n<<<<<<< SEARCH\n{e.old}\n=======\n{e.new}\n>>>>>>> REPLACE\n"
        for e in edits
    ]
    reply = "\n".join(parts)
    back, code = parse_edits(reply)
    if code is not None or back != edits:
        raise ValueError("derived edits do not survive the reply format")
    return reply


def tree_after(mirror: str, commit: str, patch: str, scratch: str) -> str | None:
    """Tree id that results from applying ``patch`` to ``commit``; ``None`` if it does not apply.

    Uses a temporary index inside ``scratch`` (no checkout, the mirror is not modified apart from
    the tree object written), so two patches can be compared by tree id alone.
    """
    env = {
        **os.environ,
        "GIT_INDEX_FILE": os.path.join(scratch, f"index_{abs(hash((commit, patch)))}"),
    }
    patch_file = env["GIT_INDEX_FILE"] + ".patch"
    with open(patch_file, "w", encoding="utf-8", newline="") as fh:
        fh.write(patch if patch.endswith("\n") else patch + "\n")

    def git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", mirror, *args], capture_output=True, text=True, env=env, check=False
        )

    try:
        if git("read-tree", commit).returncode != 0:
            return None
        if git("apply", "--cached", "--whitespace=nowarn", patch_file).returncode != 0:
            return None
        done = git("write-tree")
        return done.stdout.strip() if done.returncode == 0 else None
    finally:
        for f in (env["GIT_INDEX_FILE"], patch_file):
            if os.path.exists(f):
                os.remove(f)
