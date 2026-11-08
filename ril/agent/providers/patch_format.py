"""The pilot's prompt and its fixed edit format. Implements ``docs/RQ3_PILOT.md`` ("Scaffold").

One prompt per instance holds the issue text and the assembled context (byte-identical across arms,
``specs/assembly.md``). The reply is a list of search-and-replace blocks::

    FILE: relative/path.py
    <<<<<<< SEARCH
    exact old text
    =======
    new text
    >>>>>>> REPLACE

The parser checks the format only (and that each path is one the context showed); whether a SEARCH
text applies to the repository is decided by the grader, not here. Every function is pure, so the
prompt bytes depend only on the inputs and ``TEMPLATE_VERSION``.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence

from ril.agent.contracts import FileEdit, validate_path

TEMPLATE_VERSION = "rq3-pilot-prompt/v1"

_HEAD = (
    "You are fixing a bug in a Python repository. Below are an issue report and excerpts of "
    "the repository that a retrieval step selected. Propose the smallest change that resolves the "
    "issue.\n\n"
    "Reply with edit blocks only, in exactly this format, one block per change:\n\n"
    "FILE: relative/path.py\n"
    "<<<<<<< SEARCH\n"
    "exact old text, copied from the excerpts\n"
    "=======\n"
    "new text\n"
    ">>>>>>> REPLACE\n\n"
    "Use paths exactly as they appear in the excerpt headers. The SEARCH text must match the "
    "repository character for character and must not be empty.\n"
)

REASONS = {
    "no_edit_block": "it contained no edit block in the required format",
    "unterminated_block": "an edit block was not closed with '>>>>>>> REPLACE'",
    "empty_search": "an edit block had an empty SEARCH section",
    "bad_path": "a FILE line did not name a relative repository path",
    "empty_reply": "it was empty",
    "path_not_in_context": "a FILE line named a path that was not among the excerpts",
}


def build_prompt(issue: str, context: str) -> str:
    """The first user message. Deterministic in its arguments."""
    return f"{_HEAD}\n## Issue\n\n{issue.strip()}\n\n## Repository excerpts\n\n{context}\n"


def reask_message(code: str) -> str:
    """The fixed follow-up after an unusable reply, naming only the format fault."""
    return (
        f"Your previous reply could not be used: {REASONS[code]}. Reply again with edit blocks "
        "only, in the required format."
    )


def parse_edits(
    text: str, allowed_paths: Collection[str] | None = None
) -> tuple[tuple[FileEdit, ...], str | None]:
    """Edits of a reply, or ``((), code)`` with a key of ``REASONS`` when the format is violated."""
    lines = text.splitlines()
    edits: list[FileEdit] = []
    path: str | None = None
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("FILE:"):
            path = line[len("FILE:") :].strip().strip("`")
            i += 1
            continue
        if line == "<<<<<<< SEARCH" and path is not None:
            try:
                sep = lines.index("=======", i + 1)
                end = next(
                    j for j in range(sep + 1, len(lines)) if lines[j].strip() == ">>>>>>> REPLACE"
                )
            except (ValueError, StopIteration):
                return (), "unterminated_block"
            old = "\n".join(lines[i + 1 : sep])
            new = "\n".join(lines[sep + 1 : end])
            if not old.strip():
                return (), "empty_search"
            try:
                validate_path(path)
            except ValueError:
                return (), "bad_path"
            if allowed_paths is not None and path not in allowed_paths:
                return (), "path_not_in_context"
            edits.append(FileEdit(path, old, new))
            i = end + 1
            continue
        i += 1
    if not edits:
        return (), "no_edit_block"
    return tuple(edits), None


def edits_key(edits: Sequence[FileEdit]) -> str:
    """Canonical text of a patch, for comparing runs (whitespace inside blocks is significant)."""
    return "\n".join(f"{e.path}\x00{e.old}\x00{e.new}" for e in edits)
