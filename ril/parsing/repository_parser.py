"""Parse a repository checkout into CodeUnits and per-file symbol summaries.

Implements ``specs/parse_one_repo.md`` and ``specs/code_unit.md`` (FROZEN v1): top-level
functions, methods and classes are units, nested definitions fold into their parent, decorators
are inside the span (D6), and one residual ``module`` unit per file holds the lines outside every
definition. Ids follow D11 (``path::Qual.name``, ``#2`` on collisions), ``is_test`` follows D9 and
``last_modified`` follows D8 (supplied by the caller from the commit history).

The parse is phase one of two: it emits the units and a compact :class:`FileSummary` per file
(imports, top-level names, class tables, attribute types) and discards the syntax trees. Phase two
(``ril.parsing.call_graph``) re-reads each file to resolve call sites against these summaries. Files
that cannot be read or parsed are counted and listed, never dropped silently.

The class unit's ``source`` (full class text or header only) is the open question Q28; it is an
option here and the default is recorded with every build (``provisional: ADR-013``).

Kept compatible with Python 3.10 so the same code runs on the cluster's compute nodes.
"""

from __future__ import annotations

import ast
import os
import tokenize
from collections import Counter
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from io import BytesIO

from ril.parsing.code_unit import CodeUnit
from ril.parsing.path_rules import is_test_path
from ril.parsing.repo_id import normalize_repo_id
from ril.parsing.unit_id import MODULE_UNIT_NAME, assign_ids, build_id

PARSER_VERSION = "ast-parser/v0"
"""Recorded with every build; part of the build's config hash."""

SKIP_DIR_NAMES: frozenset[str] = frozenset(
    {
        "__pycache__",
        ".git",
        ".hg",
        ".svn",
        ".tox",
        ".nox",
        ".venv",
        "venv",
        ".eggs",
        "node_modules",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "site-packages",
        "build",
        "dist",
    }
)
"""Directories that never hold project source (caches, environments, build output)."""

VENDORED_DIR_NAMES: frozenset[str] = frozenset(
    {"vendor", "vendored", "_vendor", "third_party", "third-party", "extern", "_extern"}
)
"""Directories that hold copies of other projects' code (vendored)."""

_GENERATED_MARKERS: tuple[bytes, ...] = (
    b"generated " + b"by the protocol buffer compiler",
    b"@generated",
    b"do not edit",
)
_GENERATED_NAME_SUFFIXES: tuple[str, ...] = ("_pb2.py", "_pb2_grpc.py")
_HEADER_BYTES = 400

_COMPOUND_FIELDS = ("body", "orelse", "finalbody", "handlers", "cases")


# --------------------------------------------------------------------------- data structures


@dataclass(frozen=True)
class ImportBinding:
    """One name bound by an import statement (one record per alias)."""

    kind: str  # "import" | "from"
    level: int  # leading dots of a relative import (0 for absolute)
    module: str  # dotted module text as written ("" for ``from . import x``)
    name: str  # imported name for "from"; "" for "import"; "*" for a star import
    asname: str  # alias or ""
    line: int
    col: int

    @property
    def bound(self) -> str:
        """The local name this alias binds ("" for a star import)."""
        if self.kind == "from":
            return "" if self.name == "*" else (self.asname or self.name)
        return self.asname or self.module.split(".")[0]


@dataclass
class ClassSummary:
    """What phase two needs to know about a top-level class."""

    unit_id: str
    name: str
    bases: list[str]  # base expressions as source text, in order
    methods: dict[str, list[str]] = field(default_factory=dict)  # name -> unit ids in order
    attr_types: dict[str, str] = field(default_factory=dict)  # attr -> type expression text
    decorators: list[str] = field(default_factory=list)


@dataclass
class FileSummary:
    """Symbols of one parsed file, enough to resolve names without the syntax tree."""

    path: str
    module_name: str
    is_package: bool
    module_unit: str
    imports: list[ImportBinding] = field(default_factory=list)  # module-level only
    defs: dict[str, list[str]] = field(default_factory=dict)  # top-level name -> unit ids
    classes: dict[str, ClassSummary] = field(default_factory=dict)  # unit id -> summary
    assigns: dict[str, str] = field(default_factory=dict)  # NAME -> expression text
    conflicting_assigns: set[str] = field(default_factory=set)
    annotated: set[str] = field(default_factory=set)
    all_names: list[str] | None = None
    returns: dict[str, str] = field(default_factory=dict)  # unit id -> return annotation text
    decorators: dict[str, list[str]] = field(default_factory=dict)  # unit id -> decorator text
    n_lines: int = 0


@dataclass
class ParsedRepository:
    """Result of phase one for one snapshot."""

    repo_id: str
    root: str
    units: list[CodeUnit]
    files: dict[str, FileSummary]
    unparseable: list[tuple[str, str]]  # (path, reason), sorted
    skipped: dict[str, int]  # reason -> count
    skipped_files: list[tuple[str, str]]  # (path, reason) for skipped files
    module_files: dict[str, str]  # dotted module name -> repo-relative path
    module_collisions: list[str]  # module names claimed by more than one file
    id_collisions: int  # units that received a "#n" suffix
    options: dict[str, str]

    def unit_by_id(self) -> dict[str, CodeUnit]:
        """Index of units by id."""
        return {u.id: u for u in self.units}


# --------------------------------------------------------------------------- file discovery


def _is_generated(head: bytes, name: str) -> bool:
    if name.endswith(_GENERATED_NAME_SUFFIXES):
        return True
    lowered = head.lower()
    return any(marker in lowered for marker in _GENERATED_MARKERS)


def discover_python_files(root: str) -> tuple[list[str], Counter[str], list[tuple[str, str]]]:
    """Return sorted repo-relative posix paths of Python files to parse, and skip counts.

    Skip rules: cache/environment/build directories, vendored directories, generated files
    (a marker in the first bytes, or a ``_pb2`` name), and paths the id scheme cannot carry.
    Skipped files are listed with their reason.
    """
    found: list[str] = []
    skipped: Counter[str] = Counter()
    skipped_files: list[tuple[str, str]] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        kept = []
        for d in sorted(dirnames):
            if d in SKIP_DIR_NAMES or d.endswith(".egg-info"):
                skipped["dir:cache-or-build"] += 1
            elif d in VENDORED_DIR_NAMES:
                skipped["dir:vendored"] += 1
            else:
                kept.append(d)
        dirnames[:] = kept
        rel_dir = os.path.relpath(dirpath, root)
        for fname in sorted(filenames):
            if not fname.endswith(".py"):
                continue
            rel = fname if rel_dir == "." else f"{rel_dir}/{fname}".replace(os.sep, "/")
            if "::" in rel or "\\" in rel:
                skipped["file:path-not-representable"] += 1
                skipped_files.append((rel, "path-not-representable"))
                continue
            full = os.path.join(dirpath, fname)
            if os.path.islink(full):
                skipped["file:symlink"] += 1
                skipped_files.append((rel, "symlink"))
                continue
            try:
                with open(full, "rb") as handle:
                    head = handle.read(_HEADER_BYTES)
            except OSError:
                found.append(rel)  # reported as unparseable later with the real error
                continue
            if _is_generated(head, fname):
                skipped["file:generated"] += 1
                skipped_files.append((rel, "generated"))
                continue
            found.append(rel)
    found.sort()
    skipped_files.sort()
    return found, skipped, skipped_files


# --------------------------------------------------------------------------- module names


def module_names(paths: list[str]) -> tuple[dict[str, str], dict[str, bool], list[str]]:
    """Map repo-relative paths to dotted module names.

    A file's module name is built from the chain of directories that carry an ``__init__.py``
    ending at its directory; a file outside any package is named by its stem. Returns
    (name by path, is-package by path, module names claimed by several files). On a collision
    the first path in sorted order keeps the name in the lookup built by the caller.
    """
    pkg_dirs = {
        p.rsplit("/", 1)[0] for p in paths if p.rsplit("/", 1)[-1] == "__init__.py" and "/" in p
    }
    root_has_init = "__init__.py" in paths
    names: dict[str, str] = {}
    is_pkg: dict[str, bool] = {}
    for p in paths:
        parts = p.split("/")
        fname = parts[-1]
        stem = fname[:-3]
        dirs = parts[:-1]
        chain: list[str] = []
        k = len(dirs)
        while k > 0 and "/".join(dirs[:k]) in pkg_dirs:
            chain.insert(0, dirs[k - 1])
            k -= 1
        if not dirs and root_has_init:
            chain = []
        if fname == "__init__.py":
            name = ".".join(chain) if chain else ""
            is_pkg[p] = True
            if not name:
                name = ""
        else:
            name = ".".join([*chain, stem])
            is_pkg[p] = False
        names[p] = name
    seen: dict[str, str] = {}
    collisions: set[str] = set()
    for p in paths:
        n = names[p]
        if not n:
            continue
        if n in seen:
            collisions.add(n)
        else:
            seen[n] = p
    return names, is_pkg, sorted(collisions)


# --------------------------------------------------------------------------- source handling


def read_source(full_path: str) -> tuple[str, bytes]:
    """Read a file; return (text, raw bytes). May raise ``OSError`` or ``UnicodeError``."""
    with open(full_path, "rb") as handle:
        raw = handle.read()
    encoding, _ = tokenize.detect_encoding(BytesIO(raw).readline)
    return raw.decode(encoding), raw


def split_lines(text: str) -> list[str]:
    """Split like the Python tokenizer counts lines (``\\n``, ``\\r\\n``, ``\\r`` only)."""
    norm = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = norm.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


# --------------------------------------------------------------------------- AST helpers

_DefNode = ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef


def iter_defs(body: list[ast.stmt]) -> Iterator[_DefNode]:
    """Yield definitions found in ``body`` in source order, descending into compound statements
    (``if``, ``try``, ``with``, loops, ``match``) but not into the definitions themselves."""
    for stmt in body:
        if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            yield stmt
            continue
        for fname in _COMPOUND_FIELDS:
            sub = getattr(stmt, fname, None)
            if not isinstance(sub, list):
                continue
            for item in sub:
                if isinstance(item, ast.stmt):
                    yield from iter_defs([item])
                elif isinstance(item, ast.ExceptHandler | ast.match_case):
                    yield from iter_defs(item.body)


def collect_entries(tree: ast.Module) -> list[tuple[str, str, _DefNode, str]]:
    """Definitions that become units, in source order: (qualified name, unit type, node,
    enclosing class name or ""). A class is followed by its methods; nested definitions are not
    listed (they fold into their parent, decision D6). Phase two replays this to match ids."""
    entries: list[tuple[str, str, _DefNode, str]] = []
    for node in iter_defs(tree.body):
        if isinstance(node, ast.ClassDef):
            entries.append((node.name, "class", node, ""))
            for sub in iter_defs(node.body):
                if isinstance(sub, ast.FunctionDef | ast.AsyncFunctionDef):
                    entries.append((f"{node.name}.{sub.name}", "method", sub, node.name))
        else:
            entries.append((node.name, "function", node, ""))
    return entries


def _unparse(node: ast.AST | None) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except (ValueError, RecursionError):  # pragma: no cover - pathological expressions
        return ""


def span_start(node: _DefNode) -> int:
    """First line of a definition, including its decorators (D6)."""
    lines = [node.lineno, *[d.lineno for d in node.decorator_list]]
    return min(lines)


def function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """``def name(args) -> ret`` rebuilt from the syntax tree (no body, no decorators)."""
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    text = f"{prefix} {node.name}({_unparse(node.args)})"
    if node.returns is not None:
        text += f" -> {_unparse(node.returns)}"
    return text


def class_signature(node: ast.ClassDef) -> str:
    """``class Name(bases, keywords)``."""
    parts = [_unparse(b) for b in node.bases] + [
        f"{k.arg}={_unparse(k.value)}" if k.arg else f"**{_unparse(k.value)}" for k in node.keywords
    ]
    return f"class {node.name}({', '.join(parts)})" if parts else f"class {node.name}"


def _docstring(node: ast.AST) -> str | None:
    try:
        return ast.get_docstring(node)  # type: ignore[arg-type]
    except TypeError:  # pragma: no cover - node without a docstring slot
        return None


def _is_string_expr(stmt: ast.stmt) -> bool:
    return (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
        and isinstance(stmt.value.value, str)
    )


def _annotation_text(node: ast.expr | None) -> str:
    return _unparse(node) if node is not None else ""


# --------------------------------------------------------------------------- phase one


@dataclass
class ParseOptions:
    """Options of the parse; ``class_source`` is open question Q28 (``provisional: ADR-013``)."""

    class_source: str = "full"  # "full" | "header"

    def __post_init__(self) -> None:
        if self.class_source not in ("full", "header"):
            raise ValueError("class_source must be 'full' or 'header'")


def _module_level_names(tree: ast.Module, summary: FileSummary) -> None:
    """Fill imports, simple assignments and ``__all__`` from module-level statements."""

    def visit(body: list[ast.stmt]) -> None:
        for stmt in body:
            if isinstance(stmt, ast.Import):
                for a in stmt.names:
                    summary.imports.append(
                        ImportBinding(
                            "import", 0, a.name, "", a.asname or "", stmt.lineno, stmt.col_offset
                        )
                    )
            elif isinstance(stmt, ast.ImportFrom):
                for a in stmt.names:
                    summary.imports.append(
                        ImportBinding(
                            "from",
                            stmt.level or 0,
                            stmt.module or "",
                            a.name,
                            a.asname or "",
                            stmt.lineno,
                            stmt.col_offset,
                        )
                    )
            elif isinstance(stmt, ast.Assign | ast.AnnAssign):
                targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
                value = stmt.value
                annotation = (
                    _annotation_text(stmt.annotation) if isinstance(stmt, ast.AnnAssign) else ""
                )
                for t in targets:
                    if not isinstance(t, ast.Name):
                        continue
                    if t.id == "__all__" and isinstance(value, ast.List | ast.Tuple):
                        names = [
                            e.value
                            for e in value.elts
                            if isinstance(e, ast.Constant) and isinstance(e.value, str)
                        ]
                        summary.all_names = (summary.all_names or []) + names
                    elif annotation:
                        # a declared type wins over the value: ``g: "Ctx" = LocalProxy(...)``
                        summary.assigns[t.id] = f"<annotation>{annotation}"
                        summary.annotated.add(t.id)
                        summary.conflicting_assigns.discard(t.id)
                    elif value is not None and t.id not in summary.annotated:
                        text = _unparse(value)
                        old = summary.assigns.get(t.id)
                        if old is None and t.id not in summary.conflicting_assigns:
                            summary.assigns[t.id] = text
                        elif old is not None and old != text:
                            summary.conflicting_assigns.add(t.id)
                            del summary.assigns[t.id]
            elif isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                continue
            else:
                for fname in _COMPOUND_FIELDS:
                    sub = getattr(stmt, fname, None)
                    if not isinstance(sub, list):
                        continue
                    for item in sub:
                        if isinstance(item, ast.stmt):
                            visit([item])
                        elif isinstance(item, ast.ExceptHandler | ast.match_case):
                            visit(item.body)

    visit(tree.body)


def _self_attr_types(method: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, str]:
    """Type expressions for ``self.x`` assigned in a method: a constructor call, an annotation,
    or a parameter that carries an annotation. Conflicting assignments are dropped later."""
    args = method.args.posonlyargs + method.args.args
    if not args:
        return {}
    self_name = args[0].arg
    param_ann = {
        a.arg: _annotation_text(a.annotation)
        for a in [*args, *method.args.kwonlyargs]
        if a.annotation is not None
    }
    out: dict[str, str] = {}
    for node in ast.walk(method):
        value: ast.expr | None
        if isinstance(node, ast.Assign):
            targets, value, ann = node.targets, node.value, None
        elif isinstance(node, ast.AnnAssign):
            targets, value, ann = [node.target], node.value, node.annotation
        else:
            continue
        for t in targets:
            if not (
                isinstance(t, ast.Attribute)
                and isinstance(t.value, ast.Name)
                and t.value.id == self_name
            ):
                continue
            if ann is not None:
                out[t.attr] = _annotation_text(ann)
            elif isinstance(value, ast.Call):
                out.setdefault(t.attr, f"<call>{_unparse(value.func)}")
            elif isinstance(value, ast.Name) and value.id in param_ann:
                out.setdefault(t.attr, param_ann[value.id])
    return out


def _class_level_types(node: ast.ClassDef) -> dict[str, str]:
    out: dict[str, str] = {}
    for stmt in node.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            out[stmt.target.id] = _annotation_text(stmt.annotation)
        elif isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call):
            for t in stmt.targets:
                if isinstance(t, ast.Name):
                    out.setdefault(t.id, f"<call>{_unparse(stmt.value.func)}")
    return out


def _make_unit(
    *,
    repo_id: str,
    path: str,
    uid: str,
    qual: str,
    name: str,
    unit_type: str,
    start: int,
    end: int,
    signature: str,
    docstring: str | None,
    source: str,
    last_modified: str,
) -> CodeUnit:
    loc = sum(1 for line in source.split("\n") if line.strip())
    return CodeUnit(
        id=uid,
        repo_id=repo_id,
        language="python",
        file=path,
        start_line=start,
        end_line=end,
        unit_type=unit_type,
        name=name,
        qualified_name=qual,
        signature=signature,
        docstring=docstring,
        source=source,
        calls=[],
        called_by=[],
        tests=[],
        configs=[],
        is_test=is_test_path(path),
        loc=loc,
        last_modified=last_modified,
    )


def parse_file(
    *,
    repo_id: str,
    path: str,
    text: str,
    tree: ast.Module,
    module_name: str,
    is_package: bool,
    last_modified: str,
    options: ParseOptions,
) -> tuple[list[CodeUnit], FileSummary]:
    """Units (module unit first, then definitions in source order) and the summary of one file."""
    lines = split_lines(text)
    n_lines = max(1, len(lines))
    entries = collect_entries(tree)
    ids = assign_ids(path, [e[0] for e in entries])
    module_uid = build_id(path, MODULE_UNIT_NAME)
    summary = FileSummary(
        path=path,
        module_name=module_name,
        is_package=is_package,
        module_unit=module_uid,
        n_lines=n_lines,
    )
    _module_level_names(tree, summary)

    covered = [False] * (n_lines + 2)
    units: list[CodeUnit] = []
    class_by_qual: dict[str, ClassSummary] = {}

    for (qual, utype, node, cls_qual), uid in zip(entries, ids, strict=True):
        start, end = span_start(node), node.end_lineno or node.lineno
        end = min(end, n_lines)
        start = min(start, end)
        if utype == "class":
            assert isinstance(node, ast.ClassDef)
            if options.class_source == "header":
                first_def = next(iter(iter_defs(node.body)), None)
                head_end = (span_start(first_def) - 1) if first_def is not None else end
                head_end = max(start, min(head_end, end))
                source = "\n".join(lines[start - 1 : head_end])
            else:
                source = "\n".join(lines[start - 1 : end])
            sig = class_signature(node)
            cs = ClassSummary(
                unit_id=uid,
                name=node.name,
                bases=[_unparse(b) for b in node.bases],
                attr_types=_class_level_types(node),
                decorators=[_unparse(d) for d in node.decorator_list],
            )
            summary.classes[uid] = cs
            class_by_qual[qual] = cs
            summary.defs.setdefault(node.name, []).append(uid)
        else:
            assert isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
            source = "\n".join(lines[start - 1 : end])
            sig = function_signature(node)
            if node.returns is not None:
                summary.returns[uid] = _annotation_text(node.returns)
            if utype == "method":
                cs = class_by_qual[cls_qual]
                cs.methods.setdefault(node.name, []).append(uid)
                for attr, texpr in _self_attr_types(node).items():
                    if attr in cs.attr_types and cs.attr_types[attr] != texpr:
                        cs.attr_types[attr] = ""  # conflicting types: unknown
                    else:
                        cs.attr_types.setdefault(attr, texpr)
            else:
                summary.defs.setdefault(node.name, []).append(uid)
        summary.decorators[uid] = [_unparse(d) for d in node.decorator_list]
        # coverage for the residual module unit is by top-level spans only (methods lie in classes)
        if utype != "method":
            for ln in range(start, end + 1):
                covered[ln] = True
        units.append(
            _make_unit(
                repo_id=repo_id,
                path=path,
                uid=uid,
                qual=qual,
                name=node.name,
                unit_type=utype,
                start=start,
                end=end,
                signature=sig,
                docstring=_docstring(node),
                source=source,
                last_modified=last_modified,
            )
        )

    residual = [lines[i - 1] for i in range(1, len(lines) + 1) if not covered[i]]
    module_unit = _make_unit(
        repo_id=repo_id,
        path=path,
        uid=module_uid,
        qual=MODULE_UNIT_NAME,
        name=MODULE_UNIT_NAME,
        unit_type="module",
        start=1,
        end=n_lines,
        signature="",
        docstring=_docstring(tree),
        source="\n".join(residual),
        last_modified=last_modified,
    )
    return [module_unit, *units], summary


def parse_repository(
    root: str,
    repo_id: str,
    *,
    last_modified: Mapping[str, str] | None = None,
    options: ParseOptions | None = None,
) -> ParsedRepository:
    """Phase one: discover files, parse each, emit units and summaries.

    ``last_modified`` maps a repo-relative path to ``YYYY-MM-DDTHH:MM:SSZ`` (decision D8); a path
    missing from the mapping gets ``""``. Output order is deterministic (sorted paths, source
    order within a file).
    """
    options = options or ParseOptions()
    rid = normalize_repo_id(repo_id)
    paths, skipped, skipped_files = discover_python_files(root)
    names, is_pkg, collisions = module_names(paths)
    history = last_modified or {}

    units: list[CodeUnit] = []
    files: dict[str, FileSummary] = {}
    unparseable: list[tuple[str, str]] = []
    id_collisions = 0
    for path in paths:
        full = os.path.join(root, path)
        try:
            text, raw = read_source(full)
            tree = ast.parse(raw, filename=path)
        except (OSError, SyntaxError, ValueError, UnicodeError, RecursionError, MemoryError) as exc:
            unparseable.append((path, f"{type(exc).__name__}: {str(exc)[:100]}"))
            continue
        file_units, summary = parse_file(
            repo_id=rid,
            path=path,
            text=text,
            tree=tree,
            module_name=names[path],
            is_package=is_pkg[path],
            last_modified=history.get(path, ""),
            options=options,
        )
        id_collisions += sum(1 for u in file_units if "#" in u.id.partition("::")[2])
        units.extend(file_units)
        files[path] = summary

    module_files: dict[str, str] = {}
    for path in paths:
        n = names[path]
        if n and path in files and n not in module_files:
            module_files[n] = path
    unparseable.sort()
    return ParsedRepository(
        repo_id=rid,
        root=root,
        units=units,
        files=files,
        unparseable=unparseable,
        skipped=dict(sorted(skipped.items())),
        skipped_files=skipped_files,
        module_files=module_files,
        module_collisions=collisions,
        id_collisions=id_collisions,
        options={"class_source": options.class_source},
    )
