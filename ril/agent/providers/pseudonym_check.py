"""Round-trip checks of the prompt pseudonymisation on real prompts. ``docs/RQ3_PILOT.md`` (D120).

Two checks over the prepared prompts, none of which calls a model (the third, that restoring a
prompt gives back the prompt built from the original issue and context byte for byte, is made for
every prompt by ``rq3_prompts.prepare_screened``, which refuses a prompt that fails it):

* ``excerpt_round_trip``: for every excerpt line that carries a placeholder, an edit block that
  quotes the line the way a model would, restored and converted against the base-commit file,
  must select the original line (``applied``), or be reported as not unique (``multiple_matches``,
  a property of the file, not of the transform); ``no_match`` is a transform defect.
* ``gold_round_trip``: the edit blocks derived from the instance's gold patch (``gold_edits``),
  with the prompt's own addresses and user names put in placeholder form, restored and converted,
  must give the tree of the gold patch. ``overlap`` says whether any gold-derived block contained
  a substituted string at all; if none does, the check is trivially true and is reported so.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from ril.agent.contracts import FileEdit
from ril.agent.providers.patch_convert import convert_reply
from ril.agent.providers.pseudonymise import (
    PLACEHOLDER_EMAIL,
    PLACEHOLDER_PATH,
    PseudonymMap,
    quote_text,
    restore_text,
)
from ril.evaluation.gold_edits import Derived, derive_edits, render_reply, tree_after

ReadFile = Callable[[str], str | None]
_HEADER = re.compile(r"^### (?P<file>.+?):\d+-\d+ \S+ ")
EXCERPT_MARK = "## Repository excerpts"


def placeholder_lines(prompt: str) -> list[tuple[str, str]]:
    """``(excerpt file, line)`` of every excerpt line that holds a placeholder, as in the prompt."""
    _, mark, tail = prompt.partition(EXCERPT_MARK)
    if not mark:
        return []
    out: list[tuple[str, str]] = []
    file = ""
    for line in tail.split("\n"):
        h = _HEADER.match(line)
        if h:
            file = h.group("file")
            continue
        if file and (PLACEHOLDER_EMAIL.search(line) or PLACEHOLDER_PATH.search(line)):
            out.append((file, line))
    return out


def excerpt_round_trip(
    prompt: str, mapping: PseudonymMap, read_file: ReadFile
) -> list[dict[str, Any]]:
    """One row per placeholder-bearing excerpt line: the outcome of quote, restore and convert."""
    rows: list[dict[str, Any]] = []
    for file, line in placeholder_lines(prompt):
        reply = f"FILE: {file}\n<<<<<<< SEARCH\n{line}\n=======\n{line}  # r\n>>>>>>> REPLACE\n"
        conv = convert_reply(restore_text(reply, mapping), read_file)
        row: dict[str, Any] = {"file": file, "outcome": conv.outcome}
        if conv.failure is None and conv.diff:
            original = restore_text(line, mapping)
            row["writes_original"] = (
                f"+{original}  # r" in conv.diff and f"-{original}\n" in conv.diff
            )
        rows.append(row)
    return rows


def overlaps(edits: Sequence[FileEdit], mapping: PseudonymMap) -> bool:
    """Whether any block text holds an address or path user name that the prompt substituted."""
    return any(quote_text(t, mapping) != t for e in edits for t in (e.old, e.new))


def gold_round_trip(
    gold_patch: str,
    mapping: PseudonymMap,
    read_file: ReadFile,
    mirror: str,
    commit: str,
    scratch: str,
    derived: Derived | None = None,
) -> dict[str, Any]:
    """Outcome of the gold-derived round trip of one instance (see the module text)."""
    if derived is None:
        derived = derive_edits(gold_patch, read_file)
    if derived.limit:
        return {"outcome": "derivation_limit", "detail": derived.limit, "overlap": False}
    overlap = overlaps(derived.edits, mapping)
    quoted = tuple(
        FileEdit(e.path, quote_text(e.old, mapping), quote_text(e.new, mapping))
        for e in derived.edits
    )
    reply = render_reply(quoted)
    conv = convert_reply(restore_text(reply, mapping), read_file)
    if conv.failure is not None or not conv.diff:
        detail = conv.failure.kind if conv.failure else "empty_diff"
        return {"outcome": "conversion_failed", "detail": detail, "overlap": overlap}
    gold_tree = tree_after(mirror, commit, gold_patch, scratch)
    new_tree = tree_after(mirror, commit, conv.diff, scratch)
    same = bool(gold_tree) and gold_tree == new_tree
    return {"outcome": "tree_equal" if same else "tree_differs", "detail": "", "overlap": overlap}


def summarise(rows: Sequence[Mapping[str, Any]], key: str = "outcome") -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        out[str(r[key])] = out.get(str(r[key]), 0) + 1
    return dict(sorted(out.items()))
