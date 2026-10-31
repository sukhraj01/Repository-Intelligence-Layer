"""Build the RepoGraph of one snapshot: contain, import, invoke, inherit and override edges.

Implements ``specs/parse_one_repo.md`` and ``specs/repo_graph.md`` (DRAFT v0). Phase two of the
parse: it re-reads each file, finds every call site and resolves it against the summaries of
phase one with an own ``ast`` resolver (``provisional: ADR-011``; the resolver per family is
open question Q-G13). Every call site becomes one ``invoke`` edge carrying a status:

* ``resolved``   exactly one in-repository unit
* ``ambiguous``  several in-repository candidates (the full set, up to ``max_candidates``)
* ``external``   outside the repository (builtin, standard library or third party)
* ``unresolved`` expected to point inside the repository but not determined (dynamic dispatch,
                 ``getattr``, a call through a local name, an unknown receiver with too many
                 name matches, an attribute missing from a fully known class)

Nothing is dropped: a dynamic call that cannot be resolved is an ``unresolved`` edge and counts as
unrecovered. Nested definitions fold into their parent unit (D6): calls inside them belong to the
enclosing unit. Decorator applications and default arguments belong to the enclosing scope.

The resolver is flow-insensitive and context-insensitive. It tracks the type of ``self``, of
parameters with a class annotation, of variables assigned from a constructor call, of module
variables and of ``self.x`` attributes assigned a constructor call or carrying an annotation. It
follows ``from m import n`` through re-exports and star imports and orders methods by a C3
linearisation of the in-repository bases. It does not infer return types except from annotations.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import ast
import builtins
import os
import platform
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

from ril.parsing.code_unit import CODEUNIT_SCHEMA_VERSION, CodeUnit, units_to_jsonl
from ril.parsing.repo_graph import REPO_GRAPH_SCHEMA_VERSION, Edge, RepoGraph
from ril.parsing.repository_parser import (
    ClassSummary,
    FileSummary,
    ImportBinding,
    ParsedRepository,
    collect_entries,
    iter_defs,
    read_source,
)
from ril.parsing.unit_id import assign_ids

RESOLVER_NAME = "own-ast-resolver"
RESOLVER_VERSION = "v0"
MAX_CANDIDATES = 50
"""Above this many name matches an unknown-receiver call is ``unresolved``, not ``ambiguous``."""

_BUILTIN_NAMES = frozenset(dir(builtins))
_TEXT_LIMIT = 120
_BUILTIN_VALUE_TYPES = frozenset(
    {"str", "bytes", "int", "float", "bool", "dict", "list", "set", "frozenset", "tuple", "object"}
)
_TYPING_PREFIXES = ("typing.", "typing_extensions.", "collections.abc.", "abc.")
_DEF_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
_PROPERTY_DECORATORS = (
    "property",
    "cached_property",
    "functools.cached_property",
    "cached_class_property",
)


# --------------------------------------------------------------------------- values


@dataclass(frozen=True)
class Val:
    """What an expression denotes, as far as the resolver can tell.

    kinds: ``module`` (ref = path), ``nspkg`` (ref = dotted name of a directory package),
    ``class`` / ``inst`` / ``func`` (ref = unit id; ``cands`` holds all ids when a name has
    several definitions), ``super`` (ref = class id), ``nested`` (a function defined inside the
    current unit), ``ext`` / ``builtin`` (outside the repository), ``local`` (a local name of
    unknown value), ``undefined``, ``unknown``, ``unknown_attr`` (attribute of an unknown value;
    ref = attribute name) and ``missing_attr`` (attribute absent from a known class or module).
    """

    kind: str
    ref: str = ""
    cands: tuple[str, ...] = ()
    text: str = ""


UNKNOWN = Val("unknown")
_NOT_FOUND = Val("not_found")


@dataclass
class MroInfo:
    """Linearised in-repository ancestors of a class and what could not be resolved."""

    order: tuple[str, ...]
    external: bool  # some base is outside the repository (other than ``object``)
    unresolved: bool  # some base expression could not be resolved


@dataclass
class _Source:
    kind: str  # param | assign | ann | import | def | other
    node: ast.expr | None = None
    text: str = ""
    role: str = ""  # self | cls | ""
    binding: ImportBinding | None = None


@dataclass
class LocalScope:
    """Names bound inside one unit (flow-insensitive; nested scopes merged)."""

    sources: dict[str, list[_Source]]
    globals_declared: set[str]
    cache: dict[str, Val] = field(default_factory=dict)
    in_progress: set[str] = field(default_factory=set)


@dataclass
class Ctx:
    """Where an expression is evaluated."""

    fs: FileSummary
    unit_id: str
    class_id: str  # enclosing class unit id for methods, else ""
    locals: LocalScope | None


# --------------------------------------------------------------------------- helpers


def _unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except (ValueError, RecursionError):  # pragma: no cover
        return ""


def _short(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= _TEXT_LIMIT else text[: _TEXT_LIMIT - 3] + "..."


def _site(path: str, node: ast.AST) -> str:
    return f"{path}:{getattr(node, 'lineno', 0)}:{getattr(node, 'col_offset', 0)}"


def _target_names(target: ast.expr) -> list[str]:
    return [
        n.id for n in ast.walk(target) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
    ]


def _decorator_roles(decorators: list[str]) -> str:
    """Role of the first parameter: ``self``, ``cls`` or ``"""
    names = {d.split("(")[0].split(".")[-1] for d in decorators}
    if "staticmethod" in names:
        return ""
    if "classmethod" in names:
        return "cls"
    return "self"


def collect_local_scope(
    node: ast.FunctionDef | ast.AsyncFunctionDef, first_param_role: str
) -> LocalScope:
    """Everything bound anywhere inside a function (nested scopes merged, flow-insensitive)."""
    sources: dict[str, list[_Source]] = defaultdict(list)
    globals_declared: set[str] = set()
    own_args = node.args.posonlyargs + node.args.args

    def add_args(args: ast.arguments, own: bool) -> None:
        allargs = [*args.posonlyargs, *args.args, *args.kwonlyargs]
        for i, a in enumerate(allargs):
            role = first_param_role if own and i == 0 and own_args and a is own_args[0] else ""
            ann = _unparse(a.annotation) if a.annotation is not None else ""
            sources[a.arg].append(_Source("param", text=ann, role=role))
        if args.vararg:
            sources[args.vararg.arg].append(_Source("param", role="varargs"))
        if args.kwarg:
            sources[args.kwarg.arg].append(_Source("param", role="kwargs"))

    add_args(node.args, True)
    for sub in ast.walk(node):
        if sub is node or sub is node.args:
            continue
        if isinstance(sub, ast.arguments):
            add_args(sub, False)
        elif isinstance(sub, ast.Assign):
            for t in sub.targets:
                if isinstance(t, ast.Name):
                    sources[t.id].append(_Source("assign", node=sub.value))
                else:
                    for n in _target_names(t):
                        sources[n].append(_Source("other"))
        elif isinstance(sub, ast.AnnAssign):
            if isinstance(sub.target, ast.Name):
                sources[sub.target.id].append(_Source("ann", text=_unparse(sub.annotation)))
                if sub.value is not None:
                    sources[sub.target.id].append(_Source("assign", node=sub.value))
        elif isinstance(sub, ast.NamedExpr):
            sources[sub.target.id].append(_Source("assign", node=sub.value))
        elif isinstance(sub, ast.AugAssign):
            for n in _target_names(sub.target):
                sources[n].append(_Source("other"))
        elif isinstance(sub, ast.For | ast.AsyncFor | ast.comprehension):
            for n in _target_names(sub.target):
                sources[n].append(_Source("other"))
        elif isinstance(sub, ast.withitem):
            if sub.optional_vars is not None:
                for n in _target_names(sub.optional_vars):
                    sources[n].append(_Source("other"))
        elif isinstance(sub, ast.ExceptHandler):
            if sub.name:
                sources[sub.name].append(_Source("other"))
        elif isinstance(sub, ast.Import):
            for a in sub.names:
                b = ImportBinding(
                    "import", 0, a.name, "", a.asname or "", sub.lineno, sub.col_offset
                )
                sources[b.bound].append(_Source("import", binding=b))
        elif isinstance(sub, ast.ImportFrom):
            for a in sub.names:
                b = ImportBinding(
                    "from",
                    sub.level or 0,
                    sub.module or "",
                    a.name,
                    a.asname or "",
                    sub.lineno,
                    sub.col_offset,
                )
                if b.bound:
                    sources[b.bound].append(_Source("import", binding=b))
        elif isinstance(sub, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            sources[sub.name].append(_Source("def"))
        elif isinstance(sub, ast.Global | ast.Nonlocal):
            if isinstance(sub, ast.Global):
                globals_declared.update(sub.names)
    return LocalScope(dict(sources), globals_declared)


# --------------------------------------------------------------------------- the builder


class GraphBuilder:
    """Resolves names and call sites over a :class:`ParsedRepository`."""

    def __init__(self, parsed: ParsedRepository, max_candidates: int = MAX_CANDIDATES) -> None:
        self.parsed = parsed
        self.max_candidates = max_candidates
        self.units: dict[str, CodeUnit] = {u.id: u for u in parsed.units}
        self.module_files = parsed.module_files
        self.module_prefixes: set[str] = set()
        for name in self.module_files:
            parts = name.split(".")
            for i in range(1, len(parts)):
                self.module_prefixes.add(".".join(parts[:i]))
        self.class_info: dict[str, ClassSummary] = {}
        self.class_file: dict[str, FileSummary] = {}
        self.method_class: dict[str, str] = {}
        methods_by_name: dict[str, list[str]] = defaultdict(list)
        for fs in parsed.files.values():
            for cid, cs in fs.classes.items():
                self.class_info[cid] = cs
                self.class_file[cid] = fs
                for name, ids in cs.methods.items():
                    for mid in ids:
                        self.method_class[mid] = cid
                        methods_by_name[name].append(mid)
        self.methods_by_name = {k: sorted(v) for k, v in methods_by_name.items()}
        self._imports_by_bound: dict[str, dict[str, list[ImportBinding]]] = {}
        self._star_imports: dict[str, list[ImportBinding]] = {}
        for path, fs in parsed.files.items():
            by: dict[str, list[ImportBinding]] = defaultdict(list)
            stars: list[ImportBinding] = []
            for ib in fs.imports:
                if ib.kind == "from" and ib.name == "*":
                    stars.append(ib)
                elif ib.bound:
                    by[ib.bound].append(ib)
            self._imports_by_bound[path] = dict(by)
            self._star_imports[path] = stars
        self._member_cache: dict[tuple[str, str], Val] = {}
        self._member_in_progress: set[tuple[str, str]] = set()
        self._mro_cache: dict[str, MroInfo] = {}
        self._mro_in_progress: set[str] = set()
        self._expr_cache: dict[str, ast.expr | None] = {}
        self._text_cache: dict[tuple[str, str], Val] = {}
        self._text_in_progress: set[tuple[str, str]] = set()
        # Results computed while a cycle was cut short depend on where the lookup started, so
        # they are not cached: every file's edges are then a function of the summaries alone,
        # whatever order files are resolved in (needed by incremental updates).
        self._cycle_cuts = 0
        self.edges: list[Edge] = []

    # ------------------------------------------------------------------ modules and imports

    def abs_module(self, level: int, module: str, fs: FileSummary) -> str | None:
        """Absolute dotted name of a (possibly relative) import target, or ``None``."""
        if level == 0:
            return module
        pkg = fs.module_name if fs.is_package else fs.module_name.rpartition(".")[0]
        parts = pkg.split(".") if pkg else []
        up = level - 1
        if up > len(parts):
            return None
        parts = parts[: len(parts) - up] if up else parts
        base = ".".join(parts)
        if module:
            base = f"{base}.{module}" if base else module
        return base

    def module_val(self, dotted: str) -> Val:
        path = self.module_files.get(dotted)
        if path is not None:
            return Val("module", path)
        if dotted in self.module_prefixes:
            return Val("nspkg", dotted)
        return Val("ext", dotted)

    def _def_val(self, ids: list[str]) -> Val:
        first = ids[0]
        kind = "class" if self.units[first].unit_type == "class" else "func"
        return Val(kind, first, tuple(ids) if len(ids) > 1 else ())

    def import_val(self, ib: ImportBinding, fs: FileSummary) -> Val:
        """The value an import alias binds."""
        if ib.kind == "import":
            target = ib.module if ib.asname else ib.module.split(".")[0]
            return self.module_val(target)
        base = self.abs_module(ib.level, ib.module, fs)
        if base is None:
            return UNKNOWN
        mpath = self.module_files.get(base)
        if mpath is not None:
            v = self.member_of_module(mpath, ib.name)
            if v is not _NOT_FOUND:
                return v
            sub = self.module_files.get(f"{base}.{ib.name}")
            if sub is not None:
                return Val("module", sub)
            return UNKNOWN
        if base in self.module_prefixes:
            return (
                self.module_val(f"{base}.{ib.name}")
                if f"{base}.{ib.name}" in self.module_files
                or f"{base}.{ib.name}" in self.module_prefixes
                else UNKNOWN
            )
        return Val("ext", f"{base}.{ib.name}" if base else ib.name)

    def member_of_module(self, path: str, name: str) -> Val:
        """A top-level name of a module: definition, import (followed), alias or star import."""
        key = (path, name)
        hit = self._member_cache.get(key)
        if hit is not None:
            return hit
        if key in self._member_in_progress:
            self._cycle_cuts += 1
            return _NOT_FOUND
        cuts = self._cycle_cuts
        self._member_in_progress.add(key)
        try:
            val = self._member_uncached(path, name)
        finally:
            self._member_in_progress.discard(key)
        if self._cycle_cuts == cuts:
            self._member_cache[key] = val
        return val

    def _member_uncached(self, path: str, name: str) -> Val:
        fs = self.parsed.files[path]
        ids = fs.defs.get(name)
        if ids:
            return self._def_val(ids)
        for ib in self._imports_by_bound[path].get(name, ()):
            v = self.import_val(ib, fs)
            if v.kind != "unknown":
                return v
        text = fs.assigns.get(name)
        if text is not None:
            v = self.value_of_text(text, fs)
            if v.kind not in ("unknown", "undefined"):
                return v
        for ib in self._star_imports[path]:
            base = self.abs_module(ib.level, ib.module, fs)
            if base is None:
                continue
            mpath = self.module_files.get(base)
            if mpath is None or mpath == path:
                continue
            v = self.member_of_module(mpath, name)
            if v is not _NOT_FOUND:
                return v
        return _NOT_FOUND

    # ------------------------------------------------------------------ expressions

    def _parse_expr(self, text: str) -> ast.expr | None:
        if text in self._expr_cache:
            return self._expr_cache[text]
        try:
            node: ast.expr | None = ast.parse(text, mode="eval").body
        except (SyntaxError, ValueError, RecursionError):
            node = None
        self._expr_cache[text] = node
        return node

    def value_of_text(self, text: str, fs: FileSummary) -> Val:
        """Value of a module-level expression kept as text (``<call>``/``<annotation>`` forms)."""
        key = (fs.path, text)
        if key in self._text_cache:
            return self._text_cache[key]
        if key in self._text_in_progress:
            self._cycle_cuts += 1
            return UNKNOWN
        cuts = self._cycle_cuts
        self._text_in_progress.add(key)
        try:
            ctx = Ctx(fs, fs.module_unit, "", None)
            if text.startswith("<call>"):
                node = self._parse_expr(text[len("<call>") :])
                v = self.eval_expr(node, ctx) if node is not None else UNKNOWN
                val = self._instance_of_call(v)
            elif text.startswith("<annotation>"):
                val = self.annotation_val(text[len("<annotation>") :], ctx)
            else:
                node = self._parse_expr(text)
                val = self.eval_expr(node, ctx) if node is not None else UNKNOWN
        finally:
            self._text_in_progress.discard(key)
        if self._cycle_cuts == cuts:
            self._text_cache[key] = val
        return val

    def annotation_val(self, text: str, ctx: Ctx) -> Val:
        """Instance of the class an annotation names (peeling Optional/Union/``| None``/quotes)."""
        if not text:
            return UNKNOWN
        node = self._parse_expr(text)
        if node is None:
            return UNKNOWN
        return self._annotation_node(node, ctx, 0)

    def _annotation_node(self, node: ast.expr, ctx: Ctx, depth: int) -> Val:
        if depth > 4:
            return UNKNOWN
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            inner = self._parse_expr(node.value)
            return self._annotation_node(inner, ctx, depth + 1) if inner is not None else UNKNOWN
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            for side in (node.left, node.right):
                v = self._annotation_node(side, ctx, depth + 1)
                if v.kind == "inst":
                    return v
            return UNKNOWN
        if isinstance(node, ast.Subscript):
            head = _unparse(node.value).split(".")[-1]
            if head in ("Optional", "Union", "Annotated", "Final", "ClassVar"):
                elts = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
                for e in elts:
                    v = self._annotation_node(e, ctx, depth + 1)
                    if v.kind == "inst":
                        return v
            return UNKNOWN
        if isinstance(node, ast.Name | ast.Attribute):
            v = self.eval_expr(node, ctx)
            if v.kind == "class":
                return Val("inst", v.ref)
            if v.kind == "builtin" and v.ref in _BUILTIN_VALUE_TYPES:
                return Val("builtin", v.ref)
            if v.kind == "ext" and not v.ref.startswith(_TYPING_PREFIXES):
                return Val("ext", v.ref)
        return UNKNOWN

    def _instance_of_call(self, f: Val) -> Val:
        if f.kind == "class":
            return Val("inst", f.ref)
        return UNKNOWN

    def lookup_name(self, name: str, ctx: Ctx) -> Val:
        sc = ctx.locals
        if sc is not None and name in sc.sources and name not in sc.globals_declared:
            return self.local_val(name, ctx)
        v = self.member_of_module(ctx.fs.path, name)
        if v is not _NOT_FOUND:
            return v
        if name in _BUILTIN_NAMES:
            return Val("builtin", name)
        return Val("undefined", name)

    def local_val(self, name: str, ctx: Ctx) -> Val:
        sc = ctx.locals
        assert sc is not None
        if name in sc.cache:
            return sc.cache[name]
        if name in sc.in_progress:
            return Val("local", name)
        sc.in_progress.add(name)
        try:
            vals: list[Val] = []
            for src in sc.sources[name]:
                vals.append(self._source_val(src, name, ctx))
        finally:
            sc.in_progress.discard(name)
        first = vals[0]
        if all(v == first for v in vals) and first.kind not in ("unknown", "local"):
            result = first
        else:
            informative = {v for v in vals if v.kind not in ("unknown", "local")}
            result = (
                next(iter(informative))
                if len(informative) == 1 and len(vals) == 1
                else Val("local", name)
            )
        sc.cache[name] = result
        return result

    def _source_val(self, src: _Source, name: str, ctx: Ctx) -> Val:
        if src.kind == "param":
            if src.role == "varargs":
                return Val("builtin", "tuple")
            if src.role == "kwargs":
                return Val("builtin", "dict")
            if src.role == "self" and ctx.class_id:
                return Val("inst", ctx.class_id)
            if src.role == "cls" and ctx.class_id:
                return Val("class", ctx.class_id)
            if src.text:
                v = self.annotation_val(src.text, ctx)
                if v.kind != "unknown":
                    return v
            return Val("local", name)
        if src.kind == "ann":
            v = self.annotation_val(src.text, ctx)
            return v if v.kind != "unknown" else Val("local", name)
        if src.kind == "assign" and src.node is not None:
            v = self.eval_expr(src.node, ctx)
            if v.kind in ("inst", "class", "func", "module", "ext", "builtin"):
                return v
            return Val("local", name)
        if src.kind == "import" and src.binding is not None:
            v = self.import_val(src.binding, ctx.fs)
            return v if v.kind != "unknown" else Val("local", name)
        if src.kind == "def":
            return Val("nested", name)
        return Val("local", name)

    def eval_expr(self, node: ast.expr | None, ctx: Ctx) -> Val:
        """Value of an expression; never raises on unusual syntax."""
        if node is None:
            return UNKNOWN
        if isinstance(node, ast.Name):
            return self.lookup_name(node.id, ctx)
        if isinstance(node, ast.Attribute):
            return self.attribute_of(self.eval_expr(node.value, ctx), node.attr)
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and f.id == "super":
                shadowed = ctx.locals is not None and "super" in ctx.locals.sources
                if not shadowed and ctx.class_id:
                    return Val("super", ctx.class_id)
            fv = self.eval_expr(f, ctx)
            if fv.kind == "class":
                return Val("inst", fv.ref)
            if fv.kind == "func" and not fv.cands:
                ret = self._return_annotation(fv.ref)
                if ret:
                    owner_fs = self.parsed.files[self.units[fv.ref].file]
                    return self.annotation_val(ret, Ctx(owner_fs, fv.ref, "", None))
                return UNKNOWN
            if fv.kind in ("ext", "builtin"):
                return Val("ext", fv.ref + "()")
            return UNKNOWN
        if isinstance(node, ast.Await):
            return self.eval_expr(node.value, ctx)
        if isinstance(
            node,
            ast.Constant
            | ast.JoinedStr
            | ast.List
            | ast.Dict
            | ast.Set
            | ast.Tuple
            | ast.ListComp
            | ast.DictComp
            | ast.SetComp
            | ast.GeneratorExp,
        ):
            return Val("builtin", "literal")
        if isinstance(node, ast.Subscript):
            base = self.eval_expr(node.value, ctx)
            return Val("ext", base.ref) if base.kind in ("ext", "builtin") else UNKNOWN
        return UNKNOWN

    def _return_annotation(self, uid: str) -> str:
        fs = self.parsed.files.get(self.units[uid].file)
        return fs.returns.get(uid, "") if fs else ""

    # ------------------------------------------------------------------ classes

    def mro(self, cid: str) -> MroInfo:
        """C3 linearisation over in-repository bases (DFS order if C3 fails)."""
        hit = self._mro_cache.get(cid)
        if hit is not None:
            return hit
        if cid in self._mro_in_progress:
            self._cycle_cuts += 1
            return MroInfo((cid,), False, True)
        cuts = self._cycle_cuts
        self._mro_in_progress.add(cid)
        try:
            cs = self.class_info[cid]
            fs = self.class_file[cid]
            ctx = Ctx(fs, cid, "", None)
            external = False
            unresolved = False
            parents: list[MroInfo] = []
            parent_ids: list[str] = []
            for text in cs.bases:
                node = self._parse_expr(text)
                if isinstance(node, ast.Subscript):
                    node = node.value
                v = self.eval_expr(node, ctx) if node is not None else UNKNOWN
                if v.kind == "class":
                    if v.cands:
                        unresolved = True
                    if v.ref == cid:
                        unresolved = True
                        continue
                    parent_ids.append(v.ref)
                    parents.append(self.mro(v.ref))
                elif v.kind == "builtin" and v.ref == "object":
                    continue
                elif v.kind in ("builtin", "ext"):
                    external = True
                else:
                    unresolved = True
            seqs = [list(p.order) for p in parents] + [list(parent_ids)]
            order = self._c3(cid, seqs)
            for p in parents:
                external = external or p.external
                unresolved = unresolved or p.unresolved
            info = MroInfo(tuple(order), external, unresolved)
        finally:
            self._mro_in_progress.discard(cid)
        if self._cycle_cuts == cuts:
            self._mro_cache[cid] = info
        return info

    @staticmethod
    def _c3(cid: str, seqs: list[list[str]]) -> list[str]:
        result = [cid]
        work = [list(s) for s in seqs if s]
        while work:
            for seq in work:
                cand = seq[0]
                if not any(cand in other[1:] for other in work):
                    break
            else:
                # inconsistent hierarchy: fall back to depth-first order without repeats
                for seq in work:
                    for c in seq:
                        if c not in result:
                            result.append(c)
                return result
            result.append(cand)
            work = [[c for c in s if c != cand] for s in work]
            work = [s for s in work if s]
        return result

    def find_member(self, cid: str, name: str, skip_self: bool = False) -> Val:
        """Method or typed attribute ``name`` along the MRO of ``cid``; ``_NOT_FOUND`` if absent."""
        info = self.mro(cid)
        order = info.order[1:] if skip_self else info.order
        for k in order:
            cs = self.class_info[k]
            ids = cs.methods.get(name)
            if ids:
                if len(ids) == 1 and any(
                    d.split("(")[0].split(".")[-1] in ("property", "cached_property")
                    for d in self.parsed.files[self.units[ids[0]].file].decorators.get(ids[0], [])
                ):
                    ret = self._return_annotation(ids[0])
                    if ret:
                        fs = self.class_file[k]
                        return self.annotation_val(ret, Ctx(fs, ids[0], k, None))
                    return Val("unknown_attr", name)
                return Val("func", ids[0], tuple(ids) if len(ids) > 1 else ())
            text = cs.attr_types.get(name)
            if text is not None:
                if text == "":
                    return Val("unknown_attr", name)
                v = self.value_of_text(text, self.class_file[k])
                if v.kind in ("inst", "class", "func"):
                    return v
                return Val("unknown_attr", name)
        return _NOT_FOUND

    def attribute_of(self, base: Val, attr: str) -> Val:
        k = base.kind
        if k == "module":
            v = self.member_of_module(base.ref, attr)
            if v is not _NOT_FOUND:
                return v
            fs = self.parsed.files[base.ref]
            sub = self.module_files.get(f"{fs.module_name}.{attr}")
            if sub is not None:
                return Val("module", sub)
            return Val("missing_attr", base.ref, text=attr)
        if k == "nspkg":
            name = f"{base.ref}.{attr}"
            if name in self.module_files or name in self.module_prefixes:
                return self.module_val(name)
            return Val("missing_attr", base.ref, text=attr)
        if k in ("class", "inst"):
            v = self.find_member(base.ref, attr)
            if v is _NOT_FOUND:
                return Val("missing_attr", base.ref, text=attr)
            return v
        if k == "super":
            v = self.find_member(base.ref, attr, skip_self=True)
            if v is _NOT_FOUND:
                return Val("missing_attr", base.ref, text=attr, cands=("super",))
            return v
        if k in ("ext", "builtin"):
            return Val("ext", f"{base.ref}.{attr}")
        return Val("unknown_attr", attr)

    # ------------------------------------------------------------------ call sites

    def _cap(self, ids: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(ids))

    def classify_call(self, call: ast.Call, ctx: Ctx, deco: bool = False) -> Edge:
        """The ``invoke`` edge of one call site."""
        return self._classify(call.func, call, ctx, deco)

    def _classify(self, func: ast.expr, site_node: ast.AST, ctx: Ctx, deco: bool) -> Edge:
        text = _short(_unparse(func))
        site = _site(ctx.fs.path, site_node)
        prefix = "deco:" if deco else ""
        src = ctx.unit_id

        def edge(status: str, rule: str, dst: str = "", cands: tuple[str, ...] = ()) -> Edge:
            return Edge("invoke", src, dst, status, prefix + rule, cands, site, text)

        # a call whose callee is the result of getattr(...) is dynamic dispatch
        if (
            isinstance(func, ast.Call)
            and isinstance(func.func, ast.Name)
            and func.func.id in ("getattr", "__import__", "import_module")
        ):
            return edge("unresolved", "expr:dynamic-getattr")
        label = "expr"
        if isinstance(func, ast.Name):
            label = "name"
            v = self.lookup_name(func.id, ctx)
        elif isinstance(func, ast.Attribute):
            base = self.eval_expr(func.value, ctx)
            self_like = isinstance(func.value, ast.Name) and func.value.id in ("self", "cls")
            label = {
                "inst": "self" if self_like else "instance",
                "class": "self" if self_like else "class",
                "module": "module",
                "nspkg": "module",
                "super": "super",
                "ext": "external-receiver",
                "builtin": "external-receiver",
            }.get(base.kind, "unknown-receiver")
            v = self.attribute_of(base, func.attr)
        else:
            v = self.eval_expr(func, ctx)

        k = v.kind
        if k == "func":
            if v.cands:
                return edge("ambiguous", f"{label}:multiple-definitions", cands=self._cap(v.cands))
            return edge("resolved", f"{label}:function", v.ref)
        if k == "class":
            if v.cands:
                return edge("ambiguous", f"{label}:multiple-definitions", cands=self._cap(v.cands))
            return edge("resolved", f"{label}:class-instantiation", v.ref)
        if k == "inst":
            found = self.find_member(v.ref, "__call__")
            if found.kind == "func" and not found.cands:
                return edge("resolved", f"{label}:callable-instance", found.ref)
            return edge("unresolved", f"{label}:instance-call-unknown")
        if k == "nested":
            return edge("resolved", f"{label}:nested-def", ctx.unit_id)
        if k in ("ext", "builtin"):
            return edge("external", f"{label}:external")
        if k == "local":
            return edge("unresolved", f"{label}:call-through-local-name")
        if k == "undefined":
            return edge("unresolved", f"{label}:undefined-name")
        if k == "missing_attr":
            return self._missing(v, label, edge)
        if k == "unknown_attr":
            return self._by_method_name(v.ref, label, edge)
        return edge("unresolved", f"{label}:callee-expression")

    def _missing(self, v: Val, label: str, edge: Callable[..., Edge]) -> Edge:
        if v.cands == ("super",) or (v.ref in self.class_info):
            info = self.mro(v.ref)
            if v.cands == ("super",):
                # super() looks past the class itself
                if not info.order[1:] and not info.external and not info.unresolved:
                    return edge("external", f"{label}:object-method")
            if info.external:
                return edge("external", f"{label}:inherited-from-external-base")
            if info.unresolved:
                return edge("unresolved", f"{label}:attribute-with-unresolved-base")
            return edge("unresolved", f"{label}:attribute-not-in-mro")
        return edge("unresolved", f"{label}:module-attribute-missing")

    def _by_method_name(self, name: str, label: str, edge: Callable[..., Edge]) -> Edge:
        cands = self.methods_by_name.get(name, ())
        if not cands:
            return edge("external", f"{label}:no-in-repo-method-of-that-name")
        if len(cands) > self.max_candidates:
            return edge("unresolved", f"{label}:too-many-name-matches")
        return edge("ambiguous", f"{label}:name-match", cands=tuple(cands))

    # ------------------------------------------------------------------ the walk

    def _unit_ids_for(self, path: str, tree: ast.Module) -> dict[int, str]:
        entries = collect_entries(tree)
        ids = assign_ids(path, [e[0] for e in entries])
        return {id(e[2]): uid for e, uid in zip(entries, ids, strict=True)}

    def process_file(self, fs: FileSummary) -> None:
        """Import edges and call-site edges of one file."""
        full = os.path.join(self.parsed.root, fs.path)
        _, raw = read_source(full)
        tree = ast.parse(raw, filename=fs.path)
        self.process_tree(fs, tree)

    def process_tree(self, fs: FileSummary, tree: ast.Module) -> None:
        """Import edges and call-site edges of one file's syntax tree."""
        node_unit = self._unit_ids_for(fs.path, tree)
        self._import_edges(tree, fs)
        module_ctx = Ctx(fs, fs.module_unit, "", None)
        self._visit_scope(tree.body, module_ctx, node_unit)

    def _collect_calls(self, node: ast.AST, ctx: Ctx) -> None:
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                self.edges.append(self.classify_call(sub, ctx))

    def _header(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef, ctx: Ctx
    ) -> None:
        """Decorators, bases, keywords and default values: evaluated by the enclosing scope."""
        for d in node.decorator_list:
            if not isinstance(d, ast.Call):
                self.edges.append(self._classify(d, d, ctx, True))
            self._collect_calls(d, ctx)
        if isinstance(node, ast.ClassDef):
            for b in node.bases:
                self._collect_calls(b, ctx)
            for kw in node.keywords:
                self._collect_calls(kw.value, ctx)
        else:
            for dv in [*node.args.defaults, *[x for x in node.args.kw_defaults if x is not None]]:
                self._collect_calls(dv, ctx)

    def _visit_scope(self, stmts: list[ast.stmt], ctx: Ctx, node_unit: dict[int, str]) -> None:
        """Module or class body: statements belong to ``ctx``; definitions open new scopes."""
        for stmt in stmts:
            if isinstance(stmt, _DEF_TYPES):
                uid = node_unit.get(id(stmt))
                self._header(stmt, ctx)
                if uid is None:
                    # a definition that is not a unit here (cannot happen at module/class level)
                    self._collect_calls(stmt, ctx)
                    continue
                if isinstance(stmt, ast.ClassDef):
                    cctx = Ctx(ctx.fs, uid, "", None)
                    self._visit_scope(stmt.body, cctx, node_unit)
                else:
                    deco_names = ctx.fs.decorators.get(uid, [])
                    role = _decorator_roles(deco_names) if ctx.unit_id in self.class_info else ""
                    scope = collect_local_scope(stmt, role)
                    fctx = Ctx(
                        ctx.fs, uid, ctx.unit_id if ctx.unit_id in self.class_info else "", scope
                    )
                    for body_stmt in stmt.body:
                        self._collect_calls(body_stmt, fctx)
                continue
            for _name, value in ast.iter_fields(stmt):
                if (
                    isinstance(value, list)
                    and value
                    and all(
                        isinstance(x, ast.stmt | ast.excepthandler | ast.match_case) for x in value
                    )
                ):
                    for item in value:
                        if isinstance(item, ast.stmt):
                            self._visit_scope([item], ctx, node_unit)
                        else:
                            self._visit_handler(item, ctx, node_unit)
                elif isinstance(value, ast.expr):
                    self._collect_calls(value, ctx)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, ast.AST) and not isinstance(item, ast.stmt):
                            self._collect_calls(item, ctx)

    def _visit_handler(
        self, item: ast.excepthandler | ast.match_case, ctx: Ctx, node_unit: dict[int, str]
    ) -> None:
        for _name, value in ast.iter_fields(item):
            if isinstance(value, list) and value and all(isinstance(x, ast.stmt) for x in value):
                self._visit_scope(value, ctx, node_unit)
            elif isinstance(value, ast.AST):
                self._collect_calls(value, ctx)

    # ------------------------------------------------------------------ import edges

    def _import_edges(self, tree: ast.Module, fs: FileSummary) -> None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    self.edges.append(
                        self._import_edge(
                            ImportBinding(
                                "import",
                                0,
                                a.name,
                                "",
                                a.asname or "",
                                node.lineno,
                                node.col_offset,
                            ),
                            fs,
                        )
                    )
            elif isinstance(node, ast.ImportFrom):
                for a in node.names:
                    self.edges.append(
                        self._import_edge(
                            ImportBinding(
                                "from",
                                node.level or 0,
                                node.module or "",
                                a.name,
                                a.asname or "",
                                node.lineno,
                                node.col_offset,
                            ),
                            fs,
                        )
                    )

    def _import_edge(self, ib: ImportBinding, fs: FileSummary) -> Edge:
        src = fs.module_unit
        site = f"{fs.path}:{ib.line}:{ib.col}"
        if ib.kind == "import":
            text = ib.module
            path = self.module_files.get(ib.module)
            if path is not None:
                return Edge(
                    "import",
                    src,
                    self.parsed.files[path].module_unit,
                    "resolved",
                    "import:module",
                    (),
                    site,
                    text,
                )
            if ib.module in self.module_prefixes:
                return Edge(
                    "import",
                    src,
                    "",
                    "unresolved",
                    "import:in-repo-package-without-init",
                    (),
                    site,
                    text,
                )
            top = ib.module.split(".")[0]
            if top in self.module_files or top in self.module_prefixes:
                return Edge(
                    "import", src, "", "unresolved", "import:in-repo-module-missing", (), site, text
                )
            return Edge("import", src, "", "external", "import:external", (), site, text)
        base = self.abs_module(ib.level, ib.module, fs)
        text = f"{'.' * ib.level}{ib.module}:{ib.name}"
        if base is None:
            return Edge(
                "import", src, "", "unresolved", "from-import:relative-beyond-top", (), site, text
            )
        mpath = self.module_files.get(base)
        if mpath is not None:
            mod_unit = self.parsed.files[mpath].module_unit
            if ib.name == "*":
                return Edge("import", src, mod_unit, "resolved", "from-import:star", (), site, text)
            v = self.member_of_module(mpath, ib.name)
            if v.kind in ("func", "class"):
                if v.cands:
                    return Edge(
                        "import",
                        src,
                        "",
                        "ambiguous",
                        "from-import:multiple-definitions",
                        self._cap(v.cands),
                        site,
                        text,
                    )
                return Edge(
                    "import", src, v.ref, "resolved", "from-import:definition", (), site, text
                )
            if v.kind == "module":
                return Edge(
                    "import",
                    src,
                    self.parsed.files[v.ref].module_unit,
                    "resolved",
                    "from-import:module",
                    (),
                    site,
                    text,
                )
            sub = self.module_files.get(f"{base}.{ib.name}")
            if sub is not None:
                return Edge(
                    "import",
                    src,
                    self.parsed.files[sub].module_unit,
                    "resolved",
                    "from-import:submodule",
                    (),
                    site,
                    text,
                )
            if v.kind in ("ext", "builtin"):
                return Edge(
                    "import", src, "", "external", "from-import:reexported-external", (), site, text
                )
            return Edge(
                "import",
                src,
                mod_unit,
                "resolved",
                "from-import:name-not-a-definition",
                (),
                site,
                text,
            )
        if base in self.module_prefixes:
            sub_name = f"{base}.{ib.name}"
            if sub_name in self.module_files:
                return Edge(
                    "import",
                    src,
                    self.parsed.files[self.module_files[sub_name]].module_unit,
                    "resolved",
                    "from-import:submodule",
                    (),
                    site,
                    text,
                )
            return Edge(
                "import",
                src,
                "",
                "unresolved",
                "from-import:in-repo-package-without-init",
                (),
                site,
                text,
            )
        top = base.split(".")[0]
        if top in self.module_files or top in self.module_prefixes:
            return Edge(
                "import",
                src,
                "",
                "unresolved",
                "from-import:in-repo-module-missing",
                (),
                site,
                text,
            )
        return Edge("import", src, "", "external", "from-import:external", (), site, text)

    # ------------------------------------------------------------------ structure edges

    def structure_edges(self) -> tuple[dict[str, tuple[str, str]], list[Edge]]:
        """Nodes, and ``contain``, ``inherit`` and ``override`` edges."""
        nodes: dict[str, tuple[str, str]] = {}
        edges: list[Edge] = []
        dirs: set[str] = {"./"}
        for u in self.parsed.units:
            if u.unit_type == "module":
                nodes[u.id] = ("file", u.file)
            elif u.unit_type == "class":
                nodes[u.id] = ("class", u.file)
            elif u.unit_type == "method":
                nodes[u.id] = ("method", u.file)
            else:
                nodes[u.id] = ("function", u.file)
        for path, fs in self.parsed.files.items():
            parent = "./"
            parts = path.split("/")[:-1]
            for i in range(len(parts)):
                d = "/".join(parts[: i + 1]) + "/"
                if d not in dirs:
                    dirs.add(d)
                    edges.append(Edge("contain", parent, d, "resolved", "tree", (), "", ""))
                parent = d
            edges.append(Edge("contain", parent, fs.module_unit, "resolved", "tree", (), "", ""))
        for d in sorted(dirs):
            nodes[d] = ("directory", "" if d == "./" else d.rstrip("/"))
        for u in self.parsed.units:
            if u.unit_type in ("function", "class"):
                edges.append(
                    Edge(
                        "contain",
                        self.parsed.files[u.file].module_unit,
                        u.id,
                        "resolved",
                        "tree",
                        (),
                        "",
                        "",
                    )
                )
            elif u.unit_type == "method":
                edges.append(
                    Edge("contain", self.method_class[u.id], u.id, "resolved", "tree", (), "", "")
                )

        for cid in sorted(self.class_info):
            cs = self.class_info[cid]
            fs = self.class_file[cid]
            ctx = Ctx(fs, cid, "", None)
            unit = self.units[cid]
            site = f"{fs.path}:{unit.start_line}:0"
            for text in cs.bases:
                node = self._parse_expr(text)
                if isinstance(node, ast.Subscript):
                    node = node.value
                v = self.eval_expr(node, ctx) if node is not None else UNKNOWN
                short = _short(text)
                if v.kind == "class":
                    if v.cands:
                        edges.append(
                            Edge(
                                "inherit",
                                cid,
                                "",
                                "ambiguous",
                                "base-name:multiple-definitions",
                                self._cap(v.cands),
                                site,
                                short,
                            )
                        )
                    else:
                        edges.append(
                            Edge("inherit", cid, v.ref, "resolved", "base-name", (), site, short)
                        )
                elif v.kind in ("builtin", "ext"):
                    edges.append(
                        Edge("inherit", cid, "", "external", "base-name:external", (), site, short)
                    )
                else:
                    edges.append(
                        Edge(
                            "inherit",
                            cid,
                            "",
                            "unresolved",
                            "base-name:unresolved",
                            (),
                            site,
                            short,
                        )
                    )
            info = self.mro(cid)
            for name, mids in sorted(cs.methods.items()):
                for base_cid in info.order[1:]:
                    base_ids = self.class_info[base_cid].methods.get(name)
                    if base_ids:
                        for mid in mids:
                            m = self.units[mid]
                            edges.append(
                                Edge(
                                    "override",
                                    mid,
                                    base_ids[0],
                                    "resolved",
                                    "mro-name",
                                    (),
                                    f"{fs.path}:{m.start_line}:0",
                                    name,
                                )
                            )
                        break
        return nodes, edges

    def build(
        self, snapshot_commit: str = "", extra_meta: dict[str, object] | None = None
    ) -> RepoGraph:
        """Run phase two over all files and assemble the graph."""
        nodes, edges = self.structure_edges()
        for path in sorted(self.parsed.files):
            self.process_file(self.parsed.files[path])
        return self.assemble(nodes, edges + self.edges, snapshot_commit, extra_meta)

    def assemble(
        self,
        nodes: dict[str, tuple[str, str]],
        all_edges: list[Edge],
        snapshot_commit: str = "",
        extra_meta: dict[str, object] | None = None,
    ) -> RepoGraph:
        """The graph and its metadata from nodes and every edge (shared with incremental builds)."""
        meta: dict[str, object] = {
            "repo_id": self.parsed.repo_id,
            "snapshot_commit": snapshot_commit,
            "repo_graph_schema_version": REPO_GRAPH_SCHEMA_VERSION,
            "codeunit_schema_version": CODEUNIT_SCHEMA_VERSION,
            "resolver": f"{RESOLVER_NAME}/{RESOLVER_VERSION}",
            "max_candidates": self.max_candidates,
            "parser_options": self.parsed.options,
            "unit_set_sha256": _sha(units_to_jsonl(self.parsed.units)),
            "python": platform.python_version(),
            "n_units": len(self.parsed.units),
            "n_files": len(self.parsed.files),
        }
        if extra_meta:
            meta.update(extra_meta)
        graph = RepoGraph(meta=meta, nodes=nodes, edges=all_edges)
        graph.sort()
        return graph


def _sha(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def build_graph(
    parsed: ParsedRepository,
    snapshot_commit: str = "",
    max_candidates: int = MAX_CANDIDATES,
    extra_meta: dict[str, object] | None = None,
) -> RepoGraph:
    """Phase two for a parsed repository."""
    return GraphBuilder(parsed, max_candidates).build(snapshot_commit, extra_meta)


def apply_projections(units: list[CodeUnit], graph: RepoGraph) -> None:
    """Fill ``calls`` and ``called_by`` from resolved ``invoke`` edges (decision D4).

    Self-loops (recursion, nested-definition calls) are left out; ``tests`` and ``configs`` stay
    ``[]`` ("not computed", D10) because those families are exploratory in this build.
    """
    calls: dict[str, set[str]] = defaultdict(set)
    called_by: dict[str, set[str]] = defaultdict(set)
    for e in graph.edges:
        if e.type == "invoke" and e.status == "resolved" and e.src != e.dst:
            calls[e.src].add(e.dst)
            called_by[e.dst].add(e.src)
    for u in units:
        u.calls = sorted(calls.get(u.id, ()))
        u.called_by = sorted(called_by.get(u.id, ()))


__all__ = [
    "MAX_CANDIDATES",
    "RESOLVER_NAME",
    "RESOLVER_VERSION",
    "GraphBuilder",
    "Val",
    "apply_projections",
    "build_graph",
    "iter_defs",
]
