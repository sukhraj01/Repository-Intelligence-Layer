"""Reader-side policies for ``ambiguous`` invoke sites (open questions Q35 and Q36, exploratory).

The graph stores every call site with its status and, for an ``ambiguous`` site, the full
candidate set (``specs/repo_graph.md``, DRAFT v0). This module does not change the graph; it
applies a policy when the graph is read, so that the policies can be compared on one build
(``provisional: ADR-011``; the edge taxonomy and the policy are the engineer's decision).

Policies (applied to the ``invoke`` family only; resolved edges are always kept):

* ``keep``      every candidate of every ambiguous site is an edge (the set as stored);
* ``drop``      no ambiguous site contributes an edge (what pilot E3 read: resolved edges only);
* ``rebucket``  a site with receiver evidence that the receiver is not an in-repository object is
                read as ``external`` and dropped; the other ambiguous sites are kept;
* ``max3``      a site is kept only if its candidate set has at most three members.

Receiver evidence (a site may carry several kinds; only attribute calls ``r.m(...)`` have a
receiver). The rules are this module's operational reading of the four kinds named in Q35; each
is a syntactic test, not type inference:

* ``literal``             the receiver is a literal or display, or a name or ``self.<attr>`` that is
                          assigned one (or a call of a builtin container type) in the enclosing
                          function, at module level, or anywhere in the enclosing class (``None``
                          does not count: it is a placeholder for an object assigned later);
* ``kwargs``              the receiver is the enclosing function's ``*args`` or ``**kwargs`` name;
* ``annotated_external``  the receiver is a parameter or annotated name (or a class-level
                          annotated attribute read through ``self``) whose annotation, after
                          removing ``Optional``/``Union``/container wrappers, names only builtin
                          types or names imported from modules outside the repository;
* ``fixture_param``       the site is in a test file (decision D9 path rule), the enclosing
                          function is a test (``test*``) or a fixture (a decorator naming
                          ``fixture``), and the receiver is one of its un-annotated parameters.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import ast
import builtins
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from ril.parsing.path_rules import is_test_path
from ril.parsing.repo_graph import Edge, RepoGraph
from ril.parsing.repository_parser import FileSummary, ParsedRepository, read_source

POLICIES: tuple[str, ...] = ("keep", "drop", "rebucket", "max3")
EVIDENCE_KINDS: tuple[str, ...] = ("literal", "kwargs", "annotated_external", "fixture_param")
MAX_SET = 3
"""Largest candidate set kept by the ``max3`` policy."""

_BUILTIN_TYPES = frozenset(
    n for n in dir(builtins) if isinstance(getattr(builtins, n, None), type)
) - {"object"}
_CONTAINER_CALLS = frozenset(
    {"dict", "list", "set", "tuple", "str", "bytes", "frozenset", "bytearray", "sorted"}
)
_WRAPPERS = frozenset(
    {
        "Optional",
        "Union",
        "List",
        "Dict",
        "Set",
        "FrozenSet",
        "Tuple",
        "Sequence",
        "MutableSequence",
        "Mapping",
        "MutableMapping",
        "Iterable",
        "Iterator",
        "Collection",
        "Type",
        "ClassVar",
        "Final",
        "Annotated",
        "Awaitable",
        "Generator",
        "AsyncIterator",
        "AsyncIterable",
        "AsyncGenerator",
        "DefaultDict",
        "OrderedDict",
        "Deque",
        "Counter",
    }
)
_LITERAL_NODES = (
    ast.Constant,
    ast.JoinedStr,
    ast.List,
    ast.Dict,
    ast.Set,
    ast.Tuple,
    ast.ListComp,
    ast.DictComp,
    ast.SetComp,
    ast.GeneratorExp,
)
_FUNC = (ast.FunctionDef, ast.AsyncFunctionDef)

__all__ = [
    "EVIDENCE_KINDS",
    "MAX_SET",
    "POLICIES",
    "AmbiguousSite",
    "ambiguous_sites",
    "evidence_counts",
    "policy_pairs",
]


@dataclass(frozen=True)
class AmbiguousSite:
    """One ambiguous ``invoke`` site and the receiver evidence found for it."""

    src: str
    site: str
    target_text: str
    derivation: str
    candidates: tuple[str, ...]
    evidence: tuple[str, ...]

    @property
    def size(self) -> int:
        return len(self.candidates)


def keeps(site: AmbiguousSite, policy: str) -> bool:
    """Whether ``policy`` keeps the edges of ``site``."""
    if policy == "keep":
        return True
    if policy == "drop":
        return False
    if policy == "rebucket":
        return not site.evidence
    if policy == "max3":
        return site.size <= MAX_SET
    raise ValueError(f"unknown policy {policy!r}")


def policy_pairs(sites: Iterable[AmbiguousSite], policy: str) -> set[tuple[str, str]]:
    """(caller unit, candidate unit) pairs that ``policy`` adds to the resolved invoke edges."""
    out: set[tuple[str, str]] = set()
    for s in sites:
        if keeps(s, policy):
            out.update((s.src, c) for c in s.candidates if c != s.src)
    return out


def evidence_counts(sites: Iterable[AmbiguousSite]) -> dict[str, int]:
    """Sites per evidence kind, sites with any evidence, sites by set size bucket."""
    c: Counter[str] = Counter()
    for s in sites:
        c["sites"] += 1
        for k in s.evidence:
            c[k] += 1
        if s.evidence:
            c["any_evidence"] += 1
        c["size_le_3" if s.size <= MAX_SET else "size_gt_3"] += 1
    return dict(sorted(c.items()))


# --------------------------------------------------------------------------- evidence


def _in_repo_tops(parsed: ParsedRepository) -> set[str]:
    return {name.split(".")[0] for name in parsed.module_files if name}


def _import_module_of(name: str, fs: FileSummary, func: ast.AST | None) -> str | None:
    """Module a bound name was imported from ("." for a relative import), or None."""
    bindings = list(fs.imports)
    if func is not None:
        for sub in ast.walk(func):
            if isinstance(sub, ast.Import):
                for a in sub.names:
                    if (a.asname or a.name.split(".")[0]) == name:
                        return a.name
            elif isinstance(sub, ast.ImportFrom):
                for a in sub.names:
                    if (a.asname or a.name) == name:
                        return "." if sub.level else (sub.module or "")
    for b in bindings:
        if b.bound == name:
            if b.level:
                return "."
            return b.module
    return None


def _annotation_heads(node: ast.expr) -> list[ast.expr] | None:
    """Type expressions an annotation names after removing wrappers; None if not understood."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        try:
            parsed = ast.parse(node.value, mode="eval").body
        except SyntaxError:
            return None
        return _annotation_heads(parsed)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        left, right = _annotation_heads(node.left), _annotation_heads(node.right)
        return None if left is None or right is None else left + right
    if isinstance(node, ast.Constant) and node.value is None:
        return []
    if isinstance(node, ast.Subscript):
        head = node.value
        name = head.attr if isinstance(head, ast.Attribute) else getattr(head, "id", "")
        if name in _WRAPPERS:
            args = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
            if name == "Annotated":
                args = args[:1]
            out: list[ast.expr] = []
            for a in args:
                got = _annotation_heads(a)
                if got is None:
                    return None
                out += got
            return out
        return [head]
    if isinstance(node, ast.Name | ast.Attribute):
        return [node]
    return None


def _annotation_is_external(
    ann: ast.expr, fs: FileSummary, func: ast.AST | None, tops: set[str]
) -> bool:
    heads = _annotation_heads(ann)
    if not heads:
        return False
    for h in heads:
        root = h
        while isinstance(root, ast.Attribute):
            root = root.value
        if not isinstance(root, ast.Name):
            return False
        if isinstance(h, ast.Name) and h.id in _BUILTIN_TYPES and h.id not in fs.defs:
            continue
        module = _import_module_of(root.id, fs, func)
        if module is None or module == "." or module.split(".")[0] in tops:
            return False
        if module == "typing" and isinstance(h, ast.Name) and h.id in ("Any", "TypeVar"):
            return False
    return True


def _is_literalish(node: ast.expr | None) -> bool:
    if node is None:
        return False
    if isinstance(node, ast.Constant) and node.value is None:
        return False  # a ``None`` placeholder says nothing about the object assigned later
    if isinstance(node, _LITERAL_NODES):
        return True
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _CONTAINER_CALLS
    )


def _params(func: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.arg]:
    a = func.args
    return [*a.posonlyargs, *a.args, *a.kwonlyargs]


def _name_evidence(
    name: str,
    func: ast.FunctionDef | ast.AsyncFunctionDef | None,
    module: ast.Module,
    fs: FileSummary,
    tops: set[str],
    in_test_file: bool,
) -> set[str]:
    ev: set[str] = set()
    scope: ast.AST = func if func is not None else module
    if func is not None:
        a = func.args
        if (a.kwarg is not None and a.kwarg.arg == name) or (
            a.vararg is not None and a.vararg.arg == name
        ):
            ev.add("kwargs")
        params = _params(func)
        for i, p in enumerate(params):
            if p.arg != name:
                continue
            if p.annotation is not None:
                if _annotation_is_external(p.annotation, fs, func, tops):
                    ev.add("annotated_external")
            elif in_test_file and not (i == 0 and p.arg in ("self", "cls")):
                is_test_fn = func.name.startswith("test")
                is_fixture = any(
                    "fixture" in (ast.unparse(d) if isinstance(d, ast.AST) else "")
                    for d in func.decorator_list
                )
                if is_test_fn or is_fixture:
                    ev.add("fixture_param")
    for sub in ast.walk(scope):
        if isinstance(sub, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == name for t in sub.targets):
                if _is_literalish(sub.value):
                    ev.add("literal")
        elif isinstance(sub, ast.AnnAssign):
            if isinstance(sub.target, ast.Name) and sub.target.id == name:
                if _is_literalish(sub.value):
                    ev.add("literal")
                if _annotation_is_external(sub.annotation, fs, func, tops):
                    ev.add("annotated_external")
    return ev


def _self_attr_evidence(attr: str, cls: ast.ClassDef, fs: FileSummary, tops: set[str]) -> set[str]:
    ev: set[str] = set()
    for stmt in cls.body:  # class-level statements
        if isinstance(stmt, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == attr for t in stmt.targets
        ):
            if _is_literalish(stmt.value):
                ev.add("literal")
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            if stmt.target.id == attr:
                if _is_literalish(stmt.value):
                    ev.add("literal")
                if _annotation_is_external(stmt.annotation, fs, None, tops):
                    ev.add("annotated_external")
    for sub in ast.walk(cls):
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        ann: ast.expr | None = None
        if isinstance(sub, ast.Assign):
            targets, value = list(sub.targets), sub.value
        elif isinstance(sub, ast.AnnAssign):
            targets, value, ann = [sub.target], sub.value, sub.annotation
        for t in targets:
            if (
                isinstance(t, ast.Attribute)
                and t.attr == attr
                and isinstance(t.value, ast.Name)
                and t.value.id == "self"
            ):
                if _is_literalish(value):
                    ev.add("literal")
                if ann is not None and _annotation_is_external(ann, fs, None, tops):
                    ev.add("annotated_external")
    return ev


class _FileIndex:
    """Calls by position and the enclosing function and class of a line, for one file."""

    def __init__(self, tree: ast.Module) -> None:
        self.tree = tree
        self.calls: dict[tuple[int, int], list[ast.AST]] = {}
        self.funcs: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
        self.classes: list[ast.ClassDef] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call | ast.Attribute | ast.Name):
                self.calls.setdefault((node.lineno, node.col_offset), []).append(node)
            if isinstance(node, _FUNC):
                self.funcs.append(node)
            elif isinstance(node, ast.ClassDef):
                self.classes.append(node)

    @staticmethod
    def _innermost(nodes: Iterable[ast.stmt], line: int) -> ast.stmt | None:
        best: ast.stmt | None = None
        for n in nodes:
            start = min([n.lineno, *[d.lineno for d in getattr(n, "decorator_list", [])]])
            if start <= line <= (n.end_lineno or n.lineno):
                if best is None or n.lineno >= best.lineno:
                    best = n
        return best

    def call_at(self, line: int, col: int, text: str) -> ast.AST | None:
        found = self.calls.get((line, col), [])
        for n in found:
            if isinstance(n, ast.Call):
                try:
                    if " ".join(ast.unparse(n.func).split()).startswith(text[:60]):
                        return n
                except (ValueError, RecursionError):
                    continue
        return found[0] if found else None

    def enclosing_func(self, line: int) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
        got = self._innermost(self.funcs, line)
        return got if isinstance(got, _FUNC) else None

    def enclosing_class(self, line: int) -> ast.ClassDef | None:
        got = self._innermost(self.classes, line)
        return got if isinstance(got, ast.ClassDef) else None


def site_evidence(
    call: ast.AST,
    index: _FileIndex,
    fs: FileSummary,
    tops: set[str],
    in_test_file: bool,
) -> tuple[str, ...]:
    """Receiver evidence of one call site (sorted kinds; empty when there is none)."""
    func_expr = call.func if isinstance(call, ast.Call) else call
    if not isinstance(func_expr, ast.Attribute):
        return ()
    recv = func_expr.value
    line = getattr(call, "lineno", 0)
    ev: set[str] = set()
    if _is_literalish(recv):
        ev.add("literal")
    func = index.enclosing_func(line)
    if isinstance(recv, ast.Name):
        ev |= _name_evidence(recv.id, func, index.tree, fs, tops, in_test_file)
    elif (
        isinstance(recv, ast.Attribute)
        and isinstance(recv.value, ast.Name)
        and recv.value.id == "self"
    ):
        cls = index.enclosing_class(line)
        if cls is not None:
            ev |= _self_attr_evidence(recv.attr, cls, fs, tops)
    return tuple(k for k in EVIDENCE_KINDS if k in ev)


def ambiguous_sites(parsed: ParsedRepository, graph: RepoGraph) -> list[AmbiguousSite]:
    """Every ambiguous ``invoke`` site of ``graph`` with its receiver evidence (sorted by site)."""
    by_file: dict[str, list[Edge]] = {}
    for e in graph.edges:
        if e.type == "invoke" and e.status == "ambiguous":
            path = e.site.rsplit(":", 2)[0]
            by_file.setdefault(path, []).append(e)
    tops = _in_repo_tops(parsed)
    out: list[AmbiguousSite] = []
    for path in sorted(by_file):
        fs = parsed.files.get(path)
        index: _FileIndex | None = None
        if fs is not None:
            try:
                _, raw = read_source(f"{parsed.root}/{path}")
                index = _FileIndex(ast.parse(raw, filename=path))
            except (OSError, SyntaxError, ValueError):
                index = None
        in_test = is_test_path(path)
        for e in sorted(by_file[path], key=Edge.sort_key):
            evidence: tuple[str, ...] = ()
            if index is not None and fs is not None:
                _, line_s, col_s = e.site.rsplit(":", 2)
                call = index.call_at(int(line_s), int(col_s), e.target_text)
                if call is not None:
                    evidence = site_evidence(call, index, fs, tops, in_test)
            out.append(
                AmbiguousSite(e.src, e.site, e.target_text, e.derivation, e.candidates, evidence)
            )
    return out
