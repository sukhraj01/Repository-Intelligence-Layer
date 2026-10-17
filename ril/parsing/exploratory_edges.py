"""Exploratory edge families: ``tests`` and ``configures`` (``co_change`` is counts only).

Implements the exploratory part of ``specs/parse_one_repo.md`` and the ``tests`` / ``configures``
cards of ``specs/repo_graph.md``. Everything here is labelled exploratory: the edges are written
to their own file, never enter the CodeUnit projections, and their precision is a sampled
estimate (the sample is drawn by ``ril.evaluation.edge_samples``).

``tests``: a test unit (``is_test`` and a name starting with ``test``) is linked to a unit under
test by one of three rules: (1) its body invokes the unit through a resolved ``invoke`` edge,
(2) the test's name carries the unit's name (``test_foo`` and ``foo``, ``TestFoo.test_bar`` and
``Foo.bar``) without a body call (``name-convention``). The snapshot is the base commit, so tests
added by a later change cannot appear.

``configures``: a configuration artifact (``setup.py``, ``setup.cfg``, ``pyproject.toml``,
``tox.ini``, ``*.ini``, ``*.cfg``, ``*.toml``, ``*.yaml``, ``*.yml``, ``MANIFEST.in``) names a
module
or definition of the repository: an entry point ``pkg.mod:func``, a dotted module path, or a
repository file path. Text matching only; no file is executed.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import os
import re
from collections import defaultdict

from ril.parsing.call_graph import GraphBuilder
from ril.parsing.repo_graph import Edge, RepoGraph
from ril.parsing.repository_parser import SKIP_DIR_NAMES, VENDORED_DIR_NAMES, ParsedRepository

CONFIG_FILE_NAMES: frozenset[str] = frozenset(
    {"setup.py", "setup.cfg", "pyproject.toml", "tox.ini", "MANIFEST.in", "tox.toml", "noxfile.py"}
)
CONFIG_SUFFIXES: tuple[str, ...] = (".ini", ".cfg", ".toml", ".yaml", ".yml")
MAX_CONFIG_BYTES = 200_000
MAX_NAME_CONVENTION_CANDIDATES = 10

_ENTRY_RE = re.compile(r"([A-Za-z_][\w]*(?:\.[A-Za-z_]\w*)*):([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)")
_DOTTED_RE = re.compile(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+")
_PATH_RE = re.compile(r"[\w./-]+\.py\b")


def is_config_path(path: str) -> bool:
    """True for a file the ``configures`` scan reads."""
    name = path.rsplit("/", 1)[-1]
    if name in CONFIG_FILE_NAMES or name.endswith(CONFIG_SUFFIXES):
        return True
    return path.startswith(".github/workflows/") and name.endswith((".yml", ".yaml"))


def discover_config_files(root: str) -> list[str]:
    """Sorted repo-relative paths of configuration artifacts (same skip rules as the parser)."""
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(
            d
            for d in dirnames
            if d not in SKIP_DIR_NAMES
            and d not in VENDORED_DIR_NAMES
            and not d.endswith(".egg-info")
        )
        rel_dir = os.path.relpath(dirpath, root)
        for fname in sorted(filenames):
            rel = fname if rel_dir == "." else f"{rel_dir}/{fname}".replace(os.sep, "/")
            if (
                is_config_path(rel)
                and os.path.getsize(os.path.join(dirpath, fname)) <= MAX_CONFIG_BYTES
            ):
                out.append(rel)
    return sorted(out)


def _unit_tokens(name: str) -> str:
    return name.lower().lstrip("_")


def tests_edges(parsed: ParsedRepository, graph: RepoGraph) -> list[Edge]:
    """Exploratory ``tests`` edges (test unit -> unit under test)."""
    units = parsed.unit_by_id()
    edges: list[Edge] = []
    seen: set[tuple[str, str, str]] = set()
    by_name: dict[str, list[str]] = defaultdict(list)
    by_qual: dict[str, list[str]] = defaultdict(list)
    for u in parsed.units:
        if not u.is_test and u.unit_type in ("function", "method"):
            by_name[u.name].append(u.id)
            by_qual[u.qualified_name].append(u.id)

    test_units = [
        u
        for u in parsed.units
        if u.is_test and u.unit_type in ("function", "method") and u.name.lower().startswith("test")
    ]
    test_ids = {u.id for u in test_units}
    for e in graph.edges:
        if e.type != "invoke" or e.status != "resolved" or e.src not in test_ids:
            continue
        dst = units.get(e.dst)
        if dst is None or dst.is_test or dst.unit_type == "module":
            continue
        t = units[e.src]
        key = (e.src, e.dst, "body")
        if key in seen:
            continue
        seen.add(key)
        stem = _unit_tokens(dst.name)
        matches = len(stem) >= 3 and stem in _unit_tokens(t.name)
        rule = "tests:body-invokes+name" if matches else "tests:body-invokes"
        edges.append(Edge("tests", e.src, e.dst, "resolved", rule, (), e.site, e.target_text))

    for t in test_units:
        stem = re.sub(r"^test_?", "", t.name, flags=re.IGNORECASE)
        if not stem:
            continue
        found: list[str] = []
        rule = "tests:name-convention"
        if "." in t.qualified_name:
            cls_name = t.qualified_name.split(".")[0]
            cls_stem = re.sub(r"^test_?", "", cls_name, flags=re.IGNORECASE)
            if cls_stem:
                found = by_qual.get(f"{cls_stem}.{stem}", [])
                if found:
                    rule = "tests:class-name-convention"
        if not found:
            found = by_name.get(stem, [])
        if not found or len(found) > MAX_NAME_CONVENTION_CANDIDATES:
            continue
        site = f"{t.file}:{t.start_line}:0"
        if len(found) == 1:
            edges.append(Edge("tests", t.id, found[0], "resolved", rule, (), site, stem))
        else:
            edges.append(
                Edge("tests", t.id, "", "ambiguous", rule, tuple(sorted(found)), site, stem)
            )
    edges.sort(key=Edge.sort_key)
    return edges


def configures_edges(parsed: ParsedRepository, builder: GraphBuilder) -> list[Edge]:
    """Exploratory ``configures`` edges (configuration artifact -> module or definition)."""
    edges: list[Edge] = []
    seen: set[tuple[str, str, str]] = set()
    top_packages = {
        name.split(".")[0]
        for name in parsed.module_files
        if "." in name or _is_package(parsed, name)
    }
    top_packages.discard("tests")
    top_packages.discard("test")
    files = set(parsed.files)

    def add(cfg: str, dst: str, rule: str, line: int, text: str) -> None:
        key = (cfg, dst, rule)
        if key in seen:
            return
        seen.add(key)
        edges.append(Edge("configures", cfg, dst, "resolved", rule, (), f"{cfg}:{line}:0", text))

    def resolve_dotted(dotted: str, exact: bool = False) -> str:
        """Unit named by a dotted path: a module, or a definition of a module. With ``exact`` the
        whole path must be consumed (module or module.member); a longer tail is not a match."""
        parts = dotted.split(".")
        for k in range(len(parts), 0, -1):
            mod = ".".join(parts[:k])
            path = parsed.module_files.get(mod)
            if path is None:
                continue
            if k < len(parts):
                v = builder.member_of_module(path, parts[k])
                if k + 1 == len(parts) and v.kind in ("func", "class") and not v.cands:
                    return v.ref
                if exact:
                    return ""
            return parsed.files[path].module_unit
        return ""

    for cfg in discover_config_files(parsed.root):
        try:
            with open(os.path.join(parsed.root, cfg), encoding="utf-8", errors="replace") as handle:
                lines = handle.read().split("\n")
        except OSError:
            continue
        for n, line in enumerate(lines, start=1):
            for m in _ENTRY_RE.finditer(line):
                dst = (
                    resolve_dotted(f"{m.group(1)}.{m.group(2)}")
                    if m.group(1).split(".")[0] in top_packages
                    else ""
                )
                if dst and builder.units[dst].unit_type != "module":
                    add(cfg, dst, "configures:entry-point", n, m.group(0))
                elif m.group(1).split(".")[0] in top_packages:
                    mod_unit = resolve_dotted(m.group(1))
                    if mod_unit:
                        add(cfg, mod_unit, "configures:entry-point", n, m.group(0))
            for m in _DOTTED_RE.finditer(line):
                text = m.group(0)
                if text.split(".")[0] not in top_packages:
                    continue
                if "://" in line[: m.start()] or line[max(0, m.start() - 1) : m.start()] in (
                    "@",
                    "/",
                ):
                    continue  # a host name or path inside a URL, not a module path
                dst = resolve_dotted(text, exact=True)
                if dst:
                    add(cfg, dst, "configures:dotted-name", n, text)
            for m in _PATH_RE.finditer(line):
                p = m.group(0).lstrip("./")
                if p in files:
                    add(cfg, parsed.files[p].module_unit, "configures:file-path", n, m.group(0))
    edges.sort(key=Edge.sort_key)
    return edges


def _is_package(parsed: ParsedRepository, module_name: str) -> bool:
    path = parsed.module_files.get(module_name, "")
    return path.endswith("__init__.py")
