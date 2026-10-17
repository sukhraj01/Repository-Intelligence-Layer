"""Label-noise readings of positive chunks and units (pilot E2, exploratory).

Implements the two re-scorings of ``docs/EXPERIMENTS.md`` E-LABEL-NOISE:

* **content noise**: a located positive whose lines are only imports, only comments and
  docstrings, or that lies in a documentation file, is a weak edit location;
* **edit overlap**: a positive is kept only if its lines overlap a line the reference patch
  edits (in the base-commit coordinates), instead of merely lying in a patched file.

Both are classifications of the *labels*; they read the reference patch only to judge the
positives and never feed it to a retriever. A chunk or unit is classified from the snapshot
file at the base commit.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field

from ril.parsing.code_unit import CodeUnit

DOC_SUFFIXES = (".rst", ".md", ".txt", ".rst.txt", ".markdown")
NOISE_CLASSES = ("import_only", "comment_only", "docs_file")


@dataclass(frozen=True)
class LineKinds:
    """Line numbers (1-based) of a Python file by kind."""

    imports: frozenset[int] = field(default_factory=frozenset)
    comments: frozenset[int] = field(default_factory=frozenset)
    docstrings: frozenset[int] = field(default_factory=frozenset)


def line_kinds(source: str) -> LineKinds:
    """Import lines, comment-only lines and docstring lines of a Python source text.

    A file that does not parse yields empty sets for the syntax-based kinds (its comment lines
    are still found by a plain line test).
    """
    lines = source.splitlines()
    comments = frozenset(i for i, ln in enumerate(lines, 1) if ln.strip().startswith("#"))
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError):
        return LineKinds(frozenset(), comments, frozenset())
    imports: set[int] = set()
    docs: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import | ast.ImportFrom):
            imports.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
        body = getattr(node, "body", None)
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            if body and isinstance(body, list) and body:
                first = body[0]
                if (
                    isinstance(first, ast.Expr)
                    and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)
                ):
                    docs.update(range(first.lineno, (first.end_lineno or first.lineno) + 1))
    return LineKinds(frozenset(imports), comments, frozenset(docs))


def classify_span(
    path: str, kinds: LineKinds | None, lines: list[str], start: int, end: int
) -> str:
    """``import_only``, ``comment_only``, ``docs_file`` or ``other`` for the inclusive span.

    ``kinds`` and ``lines`` describe the file (``kinds`` is ``None`` for non-Python files).
    A span whose non-blank lines are all imports, comments or docstrings is ``import_only`` if
    it contains an import line, else ``comment_only``.
    """
    if kinds is None:
        return "docs_file" if path.lower().endswith(DOC_SUFFIXES) else "other"
    body = [i for i in range(start, end + 1) if i <= len(lines) and lines[i - 1].strip()]
    if not body:
        return "comment_only"
    allowed = kinds.imports | kinds.comments | kinds.docstrings
    if all(i in allowed for i in body):
        return "import_only" if any(i in kinds.imports for i in body) else "comment_only"
    return "other"


_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def edited_lines(patch: str) -> dict[str, frozenset[int]]:
    """Base-commit line numbers touched by a unified diff, per file path.

    A removed or changed line counts as edited. A pure insertion has no old line, so the two old
    lines around the insertion point count (the line before and the line after), which is the
    smallest reading that still marks where the patch acts. Files created by the patch (no old
    file) are omitted.
    """
    out: dict[str, set[int]] = {}
    path: str | None = None
    old_missing = False
    old_no = 0
    pending_insert = False
    rows = patch.splitlines()
    for i, raw in enumerate(rows):
        header = raw.startswith("--- ") and i + 1 < len(rows) and rows[i + 1].startswith("+++ ")
        if header:
            old_missing = raw[4:].strip() == "/dev/null"
            path = None if old_missing else raw[4:].strip().removeprefix("a/")
            continue
        if raw.startswith("+++ ") and i > 0 and rows[i - 1].startswith("--- "):
            continue
        m = _HUNK.match(raw)
        if m:
            old_no = int(m.group(1))
            pending_insert = False
            continue
        if path is None or old_missing:
            continue
        if raw.startswith("-"):
            out.setdefault(path, set()).add(old_no)
            old_no += 1
            pending_insert = True  # additions right after a removal replace it: no neighbours
        elif raw.startswith("+"):
            if not pending_insert:
                out.setdefault(path, set()).update({max(old_no - 1, 1), old_no})
                pending_insert = True
        elif raw.startswith(" ") or raw == "":
            old_no += 1
            pending_insert = False
    return {p: frozenset(v) for p, v in out.items()}


def span_overlaps(edited: frozenset[int], start: int, end: int) -> bool:
    """Whether any edited line lies in the inclusive span."""
    return any(start <= n <= end for n in edited)


def unit_overlaps_edit(unit: CodeUnit, edited: frozenset[int], file_units: list[CodeUnit]) -> bool:
    """Whether an edited line falls in the unit.

    A ``module`` unit stands for the lines outside every definition, so an edited line counts
    only if it lies outside all non-module units of the file.
    """
    if unit.unit_type != "module":
        return span_overlaps(edited, unit.start_line, unit.end_line)
    spans = [(u.start_line, u.end_line) for u in file_units if u.unit_type != "module"]
    return any(not any(a <= n <= z for a, z in spans) for n in edited)
