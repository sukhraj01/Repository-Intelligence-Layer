"""Map the old-side changes of a patch onto the units of the base commit (design D63).

Implements ``docs/experiments/B.md`` E-MINE-PILOT. A changed old line belongs to its *innermost*
unit: the smallest function, method or class whose span holds it, else the file's residual
``module`` unit (the module unit's span is the whole file, so a literal span overlap would make it
positive for every edit; the parser defines it as the lines no top-level definition covers, D6).
A pure insertion belongs to the unit that strictly contains the gap, or, at a unit's edge, to the
unit it visibly extends: added decorator lines above a definition, or added lines indented deeper
than the definition's own line directly after its last line. Added functions do not exist at the
base commit and are never positives; they are counted separately.

Nothing retriever-dependent is computed here.
"""

from __future__ import annotations

import ast
import textwrap
from collections.abc import Sequence
from dataclasses import dataclass

from ril.data_mining.diff import FileChange, FilePatch, Insertion
from ril.parsing.code_unit import CodeUnit

DEFINITION_KINDS = ("function", "method", "class")


@dataclass
class UnitHit:
    """One base-commit unit touched by the change, with how much of it was touched."""

    unit: CodeUnit
    removed_lines: int = 0
    insertion_runs: int = 0
    inserted_lines: int = 0
    whole_file_deleted: bool = False

    @property
    def hunk_lines_touched(self) -> int:
        """Old-side lines removed or rewritten inside the unit, plus inserted lines it received."""
        return self.removed_lines + self.inserted_lines


@dataclass(frozen=True)
class FileMapping:
    """Result of mapping one changed Python file."""

    path: str
    hits: tuple[UnitHit, ...]
    added_defs: tuple[str, ...]
    removed_defs: tuple[str, ...]
    status: str


def _span(unit: CodeUnit) -> int:
    return unit.end_line - unit.start_line


def innermost(units: Sequence[CodeUnit], line: int) -> CodeUnit | None:
    """Smallest definition whose span holds ``line`` (later start wins a tie); ``None`` if none."""
    best: CodeUnit | None = None
    for u in units:
        if u.unit_type not in DEFINITION_KINDS:
            continue
        if u.start_line <= line <= u.end_line and (
            best is None or (_span(u), -u.start_line) < (_span(best), -best.start_line)
        ):
            best = u
    return best


def _def_indent(unit: CodeUnit) -> int:
    """Indentation of the ``def``/``class`` line itself (decorator lines are skipped)."""
    for text in unit.source.split("\n"):
        stripped = text.lstrip()
        if stripped and not stripped.startswith("@"):
            return len(text) - len(stripped)
    return 0


def _first_code_line(lines: Sequence[str]) -> str | None:
    for text in lines:
        stripped = text.strip()
        if stripped and not stripped.startswith("#"):
            return text
    return None


def only_definitions(lines: Sequence[str]) -> bool:
    """Whether added lines are nothing but complete function or class definitions.

    Such an insertion adds units; it does not edit an existing one, so it makes neither the
    module residual nor the enclosing class a positive. Text that does not parse on its own
    (a decorator line, a statement inside a body) is an edit.
    """
    try:
        tree = ast.parse(textwrap.dedent("\n".join(lines)))
    except (SyntaxError, ValueError, RecursionError):
        return False
    return bool(tree.body) and all(
        isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) for n in tree.body
    )


def owner_of_insertion(units: Sequence[CodeUnit], ins: Insertion) -> CodeUnit | None:
    """The unit an insertion belongs to, or ``None`` for the module residual."""
    a = ins.after_old_line
    inside = [
        u
        for u in units
        if u.unit_type in DEFINITION_KINDS and u.start_line <= a and a + 1 <= u.end_line
    ]
    if inside:
        return min(inside, key=lambda u: (_span(u), -u.start_line))
    first = _first_code_line(ins.lines)
    if first is None:
        return None
    if first.lstrip().startswith("@"):
        decorated = [u for u in units if u.unit_type in DEFINITION_KINDS and u.start_line == a + 1]
        if decorated:
            return min(decorated, key=lambda u: (_span(u), -u.start_line))
    indent = len(first) - len(first.lstrip())
    tail = [
        u
        for u in units
        if u.unit_type in DEFINITION_KINDS and u.end_line == a and indent > _def_indent(u)
    ]
    if tail:
        return min(tail, key=lambda u: (_span(u), -u.start_line))
    return None


def module_unit(units: Sequence[CodeUnit]) -> CodeUnit | None:
    """The residual module unit of a file's units, if present."""
    for u in units:
        if u.unit_type == "module":
            return u
    return None


def map_change(units: Sequence[CodeUnit], change: FileChange) -> FileMapping:
    """Units of the old file (``change.old_path``) touched by ``change``, hits in unit order.

    ``units`` are the base-commit units of that one file. A deleted file touches every unit of
    it. An added file touches none (nothing existed at the base commit). A renamed file is mapped
    through its old path; a pure rename touches nothing.
    """
    patch: FilePatch | None = change.patch
    added = patch.added_defs if patch else ()
    removed_defs = patch.removed_defs if patch else ()
    if change.status == "removed":
        hits = [UnitHit(u, removed_lines=_span(u) + 1, whole_file_deleted=True) for u in units]
        return FileMapping(change.old_path, tuple(hits), added, removed_defs, change.status)
    if change.status == "added" or patch is None:
        return FileMapping(change.old_path, (), added, removed_defs, change.status)

    by_id: dict[str, UnitHit] = {}
    module = module_unit(units)

    def hit_for(owner: CodeUnit | None) -> UnitHit | None:
        target = owner if owner is not None else module
        if target is None:
            return None
        return by_id.setdefault(target.id, UnitHit(target))

    for line in patch.removed:
        h = hit_for(innermost(units, line))
        if h is not None:
            h.removed_lines += 1
    for ins in patch.insertions:
        owner = owner_of_insertion(units, ins)
        if (owner is None or owner.unit_type == "class") and only_definitions(ins.lines):
            continue  # a new definition at module or class level: added, not edited
        h = hit_for(owner)
        if h is not None:
            h.insertion_runs += 1
            h.inserted_lines += len(ins.lines)
    order = {u.id: i for i, u in enumerate(units)}
    ordered = sorted(by_id.values(), key=lambda h: order.get(h.unit.id, 0))
    return FileMapping(change.old_path, tuple(ordered), added, removed_defs, change.status)
