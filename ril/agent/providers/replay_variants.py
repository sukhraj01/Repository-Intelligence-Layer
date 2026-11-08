"""Deliberately broken variants of an edit set, for the driver's replay test. ``docs/RQ3_PILOT.md``.

Each variant takes a reply that applies (the gold-derived edit blocks of an instance) and breaks it
in one named way, so the driver's outcome class for it is known in advance:

* ``no_match``: a SEARCH text altered so that it occurs nowhere in the file
  (expected ``apply_failed:no_match``);
* ``multiple_matches``: a SEARCH text cut to a line fragment that occurs more than once in the file
  (expected ``apply_failed:multiple_matches``);
* ``breaks_code``: one block that keeps a whole top-level import line and adds a module-level
  ``raise`` after it, which is valid syntax and makes the module fail on import
  (expected ``executed_unresolved``).

All functions are pure; the file text comes from a reader.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from ril.agent.contracts import FileEdit
from ril.evaluation.gold_edits import render_reply


def _occurrences(text: str, needle: str) -> list[int]:
    """Start offsets of every occurrence of ``needle``, overlapping ones included."""
    out: list[int] = []
    at = text.find(needle)
    while at != -1:
        out.append(at)
        at = text.find(needle, at + 1)
    return out


VARIANTS: dict[str, str] = {
    "no_match": "apply_failed:no_match",
    "multiple_matches": "apply_failed:multiple_matches",
    "breaks_code": "executed_unresolved",
}
MIN_FRAGMENT = 8
BREAK_LINE = "raise RuntimeError('replay: deliberately broken edit')"


def alter_search(edits: Sequence[FileEdit]) -> str | None:
    """The reply with the first block's SEARCH text altered so that it matches nothing."""
    if not edits:
        return None
    first = edits[0]
    broken = FileEdit(first.path, first.old + "\n# replay-marker: not in the file", first.new)
    return render_reply((broken, *edits[1:]))


def ambiguous_fragment(text: str) -> str | None:
    """A stripped line of ``text`` (at least ``MIN_FRAGMENT`` characters) that occurs twice or more
    as a substring; the first such line in file order, ``None`` if there is none."""
    seen: set[str] = set()
    for raw in text.split("\n"):
        frag = raw.strip()
        if len(frag) < MIN_FRAGMENT or frag in seen:
            continue
        seen.add(frag)
        if len(_occurrences(text, frag)) >= 2 and "\n" not in frag:
            return frag
    return None


def ambiguous_search(edits: Sequence[FileEdit], read: Callable[[str], str | None]) -> str | None:
    """A one-block reply on the first edited file whose SEARCH text occurs more than once."""
    for e in edits:
        text = read(e.path)
        frag = ambiguous_fragment(text) if text is not None else None
        if frag is not None:
            return render_reply((FileEdit(e.path, frag, frag + "  # ambiguous"),))
    return None


def import_line(text: str) -> str | None:
    """The first top-level ``import`` or ``from ... import`` line that is complete on one line
    (no open bracket or continuation) and occurs once in the file, so it can be a SEARCH text."""
    for raw in text.split("\n"):
        if raw[:7] == "import " or (raw[:5] == "from " and " import " in raw):
            if raw.rstrip() == raw and raw[-1:] not in "(\\," and "(" not in raw:
                if len(_occurrences(text, raw)) == 1:
                    return raw
    return None


def breaking_reply(edits: Sequence[FileEdit], read: Callable[[str], str | None]) -> str | None:
    """A one-block reply that appends a module-level ``raise`` after a top-level import line of the
    first edited file that has one; the SEARCH text is that whole line."""
    for e in edits:
        text = read(e.path)
        line = import_line(text) if text is not None else None
        if line is not None:
            return render_reply((FileEdit(e.path, line, line + "\n" + BREAK_LINE),))
    return None


def make_variant(
    kind: str, edits: Sequence[FileEdit], read: Callable[[str], str | None]
) -> str | None:
    """The broken reply of ``kind`` for an edit set, or ``None`` if the files offer no way to."""
    if kind == "no_match":
        return alter_search(edits)
    if kind == "multiple_matches":
        return ambiguous_search(edits, read)
    if kind == "breaks_code":
        return breaking_reply(edits, read)
    raise ValueError(f"unknown variant {kind!r}")


GOLD_ARM = "gold"
PLAN: tuple[tuple[str, int], ...] = (("no_match", 4), ("multiple_matches", 3), ("breaks_code", 3))
"""Variants of the replay test and how many of each (ten in all)."""


def build_replay_set(
    instance_ids: Sequence[str],
    gold_edits: Mapping[str, Sequence[FileEdit]],
    readers: Mapping[str, Callable[[str], str | None]],
    plan: Sequence[tuple[str, int]] = PLAN,
) -> tuple[list[dict[str, Any]], dict[tuple[str, str, int], str]]:
    """(items, replies) of the replay test: the gold-derived reply of every instance (expected
    ``resolved``) and the variants of ``plan``, each on a distinct instance where the files allow.

    Items carry ``expected``; replies are keyed by (instance, arm, 0). An instance is offered to
    the kinds in turn, starting at a different offset per kind so that the variants spread over
    the drawn repositories.
    """
    ids = sorted(instance_ids)
    items: list[dict[str, Any]] = []
    replies: dict[tuple[str, str, int], str] = {}
    for iid in ids:
        edits = tuple(gold_edits[iid])
        items.append({"instance_id": iid, "arm": GOLD_ARM, "paths": None, "expected": "resolved"})
        replies[(iid, GOLD_ARM, 0)] = render_reply(edits)
    used: set[str] = set()
    for k, (kind, count) in enumerate(plan):
        offset = (k * 7) % max(1, len(ids))
        order = ids[offset:] + ids[:offset]
        taken = 0
        for pool in (False, True):  # first instances not used by another variant, then any
            for iid in order:
                if taken == count:
                    break
                arm = f"broken_{kind}"
                if (iid, arm, 0) in replies or (not pool and iid in used):
                    continue
                reply = make_variant(kind, gold_edits[iid], readers[iid])
                if reply is None:
                    continue
                items.append(
                    {"instance_id": iid, "arm": arm, "paths": None, "expected": VARIANTS[kind]}
                )
                replies[(iid, arm, 0)] = reply
                used.add(iid)
                taken += 1
    return items, replies
