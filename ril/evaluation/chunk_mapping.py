"""Locate benchmark chunks in a repository snapshot and map their spans to code units.

Implements decision D7 (``specs/code_unit.md``): the link between a retrieval chunk and the
code units is a mapping built by the evaluation side at the snapshot commit, not a field of the
unit. The released chunk rows carry an id and the text only, so the mapping is found by text.

Two steps, both pure functions of the snapshot files and the parsed units:

1. :func:`locate_chunk` finds the chunk text in the snapshot, trying four tiers in order (exact
   text; text with surrounding whitespace trimmed; line endings unified; every whitespace run
   collapsed to one space) and returns every location at the first tier that matches, so that a
   text occurring in several places is reported as such and never silently resolved.
2. :func:`map_span` turns the line span of a location into units by line overlap, under the
   frozen CodeUnit rules (top-level functions, methods and classes are units, nested definitions
   fold into their parent, one residual ``module`` unit per file, decision D6).

:func:`wave1_style_category` recomputes the categories of the first label sample's mapping
(nested definitions counted as separate leaf units), so that the two definitions can be compared
on the same positives.

Chunk text is never stored or logged by this module; only offsets, lines, tiers and unit ids.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import ast
import bisect
import os
import re
import tokenize
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from io import BytesIO

from ril.parsing.code_unit import CodeUnit
from ril.parsing.exploratory_edges import is_config_path
from ril.parsing.path_rules import is_test_path

TIERS: tuple[str, ...] = ("exact", "trimmed", "eol_normalised", "whitespace_normalised")
"""Matching tiers in the order they are tried."""

CATEGORIES: tuple[str, ...] = ("one_unit", "several_units", "class_only", "module_residual", "none")
"""Span-to-unit categories (the vocabulary of the pilot brief)."""

KINDS: tuple[str, ...] = (
    "function",
    "method",
    "class",
    "module_residual",
    "test_unit",
    "non_python_docs",
    "non_python_config",
    "non_python_data",
    "python_not_parsed",
    "unmatched",
)
"""Kinds of a positive chunk, mutually exclusive."""

MAX_FILE_BYTES = 8_000_000
"""Files larger than this are not searched (counted)."""

_LINE_BREAK = re.compile(r"\r\n|\r|\n")
_WS_RUN = re.compile(r"\s+")
_DOC_SUFFIXES = (".rst", ".md", ".txt", ".ipynb", ".markdown")
_CONFIG_SUFFIXES = (".cfg", ".ini", ".toml", ".yaml", ".yml", ".in", ".json", ".conf")
_MIN_DIAGNOSTIC_LINE = 15


# --------------------------------------------------------------------------- snapshot files


def decode_source(raw: bytes) -> str:
    """Decode like the parser does (declared encoding), falling back to UTF-8 then Latin-1."""
    try:
        encoding, _ = tokenize.detect_encoding(BytesIO(raw).readline)
        return raw.decode(encoding)
    except (SyntaxError, UnicodeError, LookupError):
        try:
            return raw.decode("utf-8")
        except UnicodeError:
            return raw.decode("latin-1")


def load_snapshot(root: str) -> tuple[dict[str, str], Counter[str]]:
    """Read every text file under ``root`` (not ``.git``) into ``{posix path: text}``.

    Files with a NUL byte in the first 8 KiB are binary and skipped; files above
    :data:`MAX_FILE_BYTES` are skipped. The skip counts are returned for the log.
    """
    files: dict[str, str] = {}
    skipped: Counter[str] = Counter()
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d != ".git")
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if os.path.islink(full):
                skipped["symlink"] += 1
                continue
            try:
                if os.path.getsize(full) > MAX_FILE_BYTES:
                    skipped["too_large"] += 1
                    continue
                with open(full, "rb") as handle:
                    raw = handle.read()
            except OSError:
                skipped["unreadable"] += 1
                continue
            if b"\x00" in raw[:8192]:
                skipped["binary"] += 1
                continue
            files[rel] = decode_source(raw)
    return files, skipped


# --------------------------------------------------------------------------- line arithmetic


class LineIndex:
    """Offset to 1-based line number (line ends as in the parser: LF, CRLF, CR)."""

    def __init__(self, text: str) -> None:
        self._ends = [m.end() for m in _LINE_BREAK.finditer(text)]

    def line_of(self, offset: int) -> int:
        """Line holding the character at ``offset``."""
        return bisect.bisect_right(self._ends, offset) + 1


@dataclass(frozen=True)
class Location:
    """One place a chunk text occurs: offsets in the original file text and the line span."""

    path: str
    start: int
    end: int
    start_line: int
    end_line: int


@dataclass(frozen=True)
class LocateResult:
    """Outcome of looking one chunk up in a snapshot.

    ``status`` is ``found`` (one or more locations at ``tier``), ``not_found`` or ``empty``
    (nothing to look for). ``reason`` explains a ``not_found``.
    """

    status: str
    tier: str
    locations: tuple[Location, ...]
    reason: str = ""

    @property
    def n_locations(self) -> int:
        return len(self.locations)


def _find_all(haystack: str, needle: str) -> Iterator[int]:
    i = haystack.find(needle)
    while i >= 0:
        yield i
        i = haystack.find(needle, i + 1)


def _normalise(text: str, pattern: re.Pattern[str], repl: str) -> tuple[str, list[int]]:
    """Replace every match of ``pattern`` by ``repl``; return the new text and, for each new
    character, the offset of the original character it stands for."""
    out: list[str] = []
    offsets: list[int] = []
    pos = 0
    for m in pattern.finditer(text):
        if m.start() > pos:
            out.append(text[pos : m.start()])
            offsets.extend(range(pos, m.start()))
        out.append(repl)
        offsets.append(m.start())
        pos = m.end()
    if pos < len(text):
        out.append(text[pos:])
        offsets.extend(range(pos, len(text)))
    return "".join(out), offsets


def _locations_in(
    path: str, original: str, lines: LineIndex, norm: str, offsets: list[int] | None, needle: str
) -> list[Location]:
    found: list[Location] = []
    for i in _find_all(norm, needle):
        if offsets is None:
            start, end = i, i + len(needle)
        else:
            start, end = offsets[i], offsets[i + len(needle) - 1] + 1
        found.append(Location(path, start, end, lines.line_of(start), lines.line_of(end - 1)))
    return found


def locate_chunk(text: str, files: dict[str, str]) -> LocateResult:
    """Find ``text`` in the snapshot ``files``; every location at the first tier that matches.

    A text that matches several times (in one file or in several) is returned with all its
    locations, in path and offset order. The caller decides what to do with an ambiguous chunk.
    """
    if not text.strip():
        return LocateResult("empty", "", (), "empty-chunk")
    index: dict[str, LineIndex] = {}

    def lines_of(path: str) -> LineIndex:
        if path not in index:
            index[path] = LineIndex(files[path])
        return index[path]

    paths = sorted(files)
    for tier in TIERS:
        found: list[Location] = []
        if tier == "exact":
            needle = text
        elif tier == "trimmed":
            needle = text.strip()
            if needle == text:
                continue
        elif tier == "eol_normalised":
            needle = _LINE_BREAK.sub("\n", text).strip()
        else:
            needle = _WS_RUN.sub(" ", text).strip()
        for path in paths:
            original = files[path]
            if tier in ("exact", "trimmed"):
                found += _locations_in(path, original, lines_of(path), original, None, needle)
            elif tier == "eol_normalised":
                if "\r" not in original:
                    norm, offs = original, None
                else:
                    norm, offs = _normalise(original, _LINE_BREAK, "\n")
                if needle in norm:
                    found += _locations_in(path, original, lines_of(path), norm, offs, needle)
            else:
                norm, offs = _normalise(original, _WS_RUN, " ")
                if needle in norm:
                    found += _locations_in(path, original, lines_of(path), norm, offs, needle)
        if found:
            return LocateResult("found", tier, tuple(found))
    return LocateResult("not_found", "", (), diagnose_not_found(text, files))


def diagnose_not_found(text: str, files: dict[str, str]) -> str:
    """Why a chunk is absent: some long line of it exists in the snapshot, or none does.

    ``partial_text_present`` points at a different chunker, an edit between the chunked commit
    and this one, or a text window that joins pieces; ``no_line_present`` points at a different
    snapshot or a file this loader does not read.
    """
    candidates = [ln.strip() for ln in _LINE_BREAK.split(text)]
    candidates = [ln for ln in candidates if len(ln) >= _MIN_DIAGNOSTIC_LINE]
    if not candidates:
        return "no_line_long_enough_to_test"
    blob = "\n".join(files[p] for p in sorted(files))
    for ln in candidates:
        if ln in blob:
            return "partial_text_present"
    return "no_line_present"


# --------------------------------------------------------------------------- span to units


@dataclass(frozen=True)
class SpanMapping:
    """A line span mapped to the units of one file (decision D6 units)."""

    category: str
    units: tuple[str, ...]  # ids used downstream: leaf units, else classes, else the module unit
    leaf_ids: tuple[str, ...]
    class_ids: tuple[str, ...]
    overlaps_residual: bool  # some line of the span lies outside every top-level definition
    primary_id: str  # largest line overlap among leaf units, else class, else module
    primary_type: str  # unit_type of ``primary_id`` ("" when category is none)


def _overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> int:
    return max(0, min(a_end, b_end) - max(a_start, b_start) + 1)


def _residual_overlap(top_spans: list[tuple[int, int]], start: int, end: int) -> bool:
    """True if some line in [start, end] is outside every (start, end) in ``top_spans``."""
    pos = start
    for s, e in sorted(top_spans):
        if e < pos:
            continue
        if s > pos:
            return True
        pos = max(pos, e + 1)
        if pos > end:
            return False
    return pos <= end


def map_span(file_units: list[CodeUnit], start_line: int, end_line: int) -> SpanMapping:
    """Map the inclusive line span to units by line overlap.

    ``one_unit`` / ``several_units``: the span overlaps one / several functions or methods
    (nested definitions are inside their parent's span, so they never count twice).
    ``class_only``: no function or method, but a class (header, docstring, attributes).
    ``module_residual``: only lines outside every definition (imports, module-level code).
    ``none``: no unit of the file overlaps (an empty or unparsed file).
    """
    leaves: list[tuple[int, int, CodeUnit]] = []
    classes: list[tuple[int, int, CodeUnit]] = []
    module: CodeUnit | None = None
    top_spans: list[tuple[int, int]] = []
    for u in file_units:
        if u.unit_type == "module":
            module = u
            continue
        if u.unit_type != "method":
            top_spans.append((u.start_line, u.end_line))
        ov = _overlap(start_line, end_line, u.start_line, u.end_line)
        if ov == 0:
            continue
        if u.unit_type in ("function", "method"):
            leaves.append((ov, -u.start_line, u))
        elif u.unit_type == "class":
            classes.append((ov, -u.start_line, u))
    residual = module is not None and _residual_overlap(top_spans, start_line, end_line)
    leaves.sort(key=lambda t: (-t[0], -t[1]))
    classes.sort(key=lambda t: (-t[0], -t[1]))
    leaf_ids = tuple(u.id for _, _, u in sorted(leaves, key=lambda t: t[2].start_line))
    class_ids = tuple(u.id for _, _, u in sorted(classes, key=lambda t: t[2].start_line))
    if leaves:
        category = "one_unit" if len(leaves) == 1 else "several_units"
        units, primary = leaf_ids, leaves[0][2]
    elif classes:
        category, units, primary = "class_only", class_ids, classes[0][2]
    elif residual and module is not None:
        category, units, primary = "module_residual", (module.id,), module
    else:
        return SpanMapping("none", (), (), (), False, "", "")
    return SpanMapping(
        category=category,
        units=units,
        leaf_ids=leaf_ids,
        class_ids=class_ids,
        overlaps_residual=bool(residual),
        primary_id=primary.id,
        primary_type=primary.unit_type,
    )


def wave1_style_category(text: str, start_line: int, end_line: int) -> str:
    """Category under the first label sample's rule, for a comparison on the same positives.

    Every function or method at any nesting depth is a leaf unit (decision D6 folds nested ones
    into their parent instead); a class counts only when no leaf overlaps. Categories:
    ``one_leaf_unit``, ``two_plus_leaf_units``, ``class_only``, ``zero_units``, and
    ``unparseable`` when the file does not parse.
    """
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return "unparseable"
    leaves = classes = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        first = min([node.lineno] + [d.lineno for d in node.decorator_list])
        last = node.end_lineno or node.lineno
        if _overlap(start_line, end_line, first, last) == 0:
            continue
        if isinstance(node, ast.ClassDef):
            classes += 1
        else:
            leaves += 1
    if leaves == 1:
        return "one_leaf_unit"
    if leaves > 1:
        return "two_plus_leaf_units"
    return "class_only" if classes else "zero_units"


def prefix_span(loc: Location, original: str, chars: int) -> tuple[int, int]:
    """Line span of the first ``chars`` characters of the location (the first label sample
    matched only the first 200 characters of a long chunk)."""
    end = min(loc.end, loc.start + chars)
    lines = LineIndex(original)
    return lines.line_of(loc.start), lines.line_of(max(loc.start, end - 1))


# --------------------------------------------------------------------------- positive kinds


def non_python_kind(path: str) -> str:
    """``non_python_docs`` / ``non_python_config`` / ``non_python_data`` for a non-.py path."""
    lower = path.lower()
    if lower.endswith(_DOC_SUFFIXES):
        return "non_python_docs"
    if is_config_path(path) or lower.endswith(_CONFIG_SUFFIXES):
        return "non_python_config"
    return "non_python_data"


def positive_kind(path: str, mapping: SpanMapping | None, parsed_paths: set[str]) -> str:
    """Kind of a located positive (see :data:`KINDS`); ``unmatched`` when it was not located.

    A positive in a test file (decision D9 path rule) is a ``test_unit`` whatever its structural
    type; the structural type stays available as ``mapping.primary_type``.
    """
    if mapping is None:
        return "unmatched"
    if not path.endswith(".py"):
        return non_python_kind(path)
    if path not in parsed_paths:
        return "python_not_parsed"
    if is_test_path(path):
        return "test_unit"
    if mapping.category == "none":
        return "python_not_parsed"
    if mapping.category == "module_residual":
        return "module_residual"
    return {"function": "function", "method": "method", "class": "class"}[mapping.primary_type]
