"""Units edited by the reference patch, for the failure breakdown (E-RQ3-FAILURE-BREAKDOWN).

Implements ``docs/experiments/B.md`` E-RQ3-FAILURE-BREAKDOWN, section "Definitions". The gold unit
set of an instance is what the existing patch-to-unit rule (``ril.data_mining.mapping``, D63)
credits for the reference patch against the base-commit units of the files it edits: a removed or
rewritten old line belongs to its innermost definition (else the file's module unit), a pure
insertion to the unit it visibly extends. Added definitions do not exist at the base commit and are
never gold units; a created file contributes nothing. Only the files of the patch are parsed, one
by one, so no repository snapshot is needed; unit ids depend on the file alone, so they equal the
ids of a snapshot parse.

Nothing retriever-dependent is computed here.
"""

from __future__ import annotations

import re
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from ril.data_mining.diff import FileChange, PatchError, parse_patch
from ril.data_mining.mapping import map_change
from ril.parsing.code_unit import CodeUnit
from ril.parsing.repository_parser import parse_repository

_DIFF_HEADER = re.compile(r"^diff --git a/(\S+) b/(\S+)$")
GOLD_UNITS_VERSION = "rq3-gold-units/v1"

ReadBase = Callable[[str], str | None]


def split_patch(patch: str) -> list[FileChange]:
    """One :class:`FileChange` per ``diff --git`` block of a unified diff.

    Status is ``added`` after ``new file mode``, ``removed`` after ``deleted file mode``,
    ``renamed`` after ``rename from`` and ``modified`` otherwise. A block with hunks gets its
    patch parsed; a block without (pure rename, mode change) has none.
    """
    blocks: list[tuple[str, str, list[str]]] = []
    for line in patch.splitlines():
        m = _DIFF_HEADER.match(line)
        if m:
            blocks.append((m.group(1), m.group(2), []))
        elif blocks:
            blocks[-1][2].append(line)
    out: list[FileChange] = []
    for old, new, lines in blocks:
        status = "modified"
        for ln in lines:
            if ln.startswith("@@"):
                break
            if ln.startswith("new file mode"):
                status = "added"
            elif ln.startswith("deleted file mode"):
                status = "removed"
            elif ln.startswith("rename from"):
                status = "renamed"
        first = next((i for i, ln in enumerate(lines) if ln.startswith("@@")), None)
        body = "\n".join(lines[first:]) if first is not None else ""
        fp = parse_patch(body) if body and old.endswith(".py") else None
        out.append(
            FileChange(
                path=new,
                old_path=old,
                status=status,
                is_python=old.endswith(".py") or new.endswith(".py"),
                patch=fp,
                patch_missing=False,
            )
        )
    return out


def parse_units(repo_id: str, files: Mapping[str, str]) -> dict[str, list[CodeUnit]]:
    """Units of the given ``{path: text}`` files, parsed alone (ids depend on the path only)."""
    with tempfile.TemporaryDirectory(prefix="ril_gold_") as tmp:
        root = Path(tmp)
        for path, text in files.items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        parsed = parse_repository(str(root), repo_id)
    by_file: dict[str, list[CodeUnit]] = {}
    for u in parsed.units:
        by_file.setdefault(u.file, []).append(u)
    return by_file


def gold_units(patch: str, repo_id: str, read_base: ReadBase) -> dict[str, Any]:
    """Gold unit ids of one reference patch and the reasons some files give none.

    ``read_base(path)`` returns the base-commit text of an old-side path or ``None``. The result
    holds ``units`` (sorted ids), ``files`` (python files with a base version, sorted),
    ``notes`` (per path: ``created``, ``missing_at_base``, ``unparseable``, ``no_unit_hit``,
    ``not_python``) and ``removed_lines`` / ``inserted_lines`` per unit.
    """
    try:
        changes = split_patch(patch)
    except PatchError as exc:
        return {"units": [], "files": [], "notes": {"*": f"patch_error:{exc}"}, "detail": {}}
    notes: dict[str, str] = {}
    texts: dict[str, str] = {}
    for ch in changes:
        if not ch.is_python:
            notes[ch.old_path] = "not_python"
        elif ch.status == "added":
            notes[ch.old_path] = "created"
        else:
            text = read_base(ch.old_path)
            if text is None:
                notes[ch.old_path] = "missing_at_base"
            else:
                texts[ch.old_path] = text
    by_file = parse_units(repo_id, texts) if texts else {}
    units: set[str] = set()
    detail: dict[str, dict[str, int]] = {}
    for ch in changes:
        if ch.old_path not in texts:
            continue
        mine = by_file.get(ch.old_path)
        if mine is None:
            notes[ch.old_path] = "unparseable"
            continue
        fm = map_change(mine, ch)
        if not fm.hits:
            notes[ch.old_path] = "no_unit_hit"
        for h in fm.hits:
            units.add(h.unit.id)
            detail[h.unit.id] = {"removed": h.removed_lines, "inserted": h.inserted_lines}
    return {
        "units": sorted(units),
        "files": sorted(texts),
        "notes": dict(sorted(notes.items())),
        "detail": dict(sorted(detail.items())),
    }


def gold_units_all(
    patches: Mapping[str, tuple[str, str]], reader: Callable[[str, str], ReadBase]
) -> dict[str, dict[str, Any]]:
    """``{instance: gold_units(...)}`` for ``patches[instance] = (repo_id, patch)``.

    ``reader(instance, repo_id)`` builds the base-file reader of one instance.
    """
    return {
        iid: gold_units(patch, repo, reader(iid, repo))
        for iid, (repo, patch) in sorted(patches.items())
    }


def summarise(rows: Mapping[str, Mapping[str, Any]], instances: Sequence[str]) -> dict[str, Any]:
    """Counts for the entry: instances with at least one gold unit, and the note tally."""
    tally: dict[str, int] = {}
    for iid in instances:
        for note in rows[iid]["notes"].values():
            tally[note] = tally.get(note, 0) + 1
    return {
        "instances": len(instances),
        "with_gold_unit": sum(1 for i in instances if rows[i]["units"]),
        "without_gold_unit": sum(1 for i in instances if not rows[i]["units"]),
        "file_notes": dict(sorted(tally.items())),
    }
