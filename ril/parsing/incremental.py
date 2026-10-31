"""Incremental graph update: given a new commit, re-read only what it changed.

A full build (``ril.parsing.build``) parses every file and resolves every call site. Between two
nearby commits most files are unchanged, so an update keeps, per file, the units, the symbol
summary and the ``import``/``invoke`` edges of the previous build and redoes three things only:

1. **Phase one for changed files.** A file is re-parsed when its bytes, its module name or its
   package flag changed (a module name changes when an ``__init__.py`` appears or disappears
   above it). A file whose only change is its D8 ``last_modified`` keeps its units with the new
   timestamp.
2. **Structure edges for all classes.** ``contain``, ``inherit`` and ``override`` are rebuilt from
   the summaries alone (no file is read), which is cheap and keeps the MRO exact.
3. **Phase two for dirty files.** The resolver of one file reads the summaries of the modules it
   imports, transitively through re-exports and base classes, and the repository-wide index of
   method names. A file is therefore re-resolved when (a) it changed; (b) it imports, directly or
   through a chain of imports, a module whose summary changed (an edit inside a function body
   leaves the summary, positions aside, unchanged and reaches no other file); or (c) it uses an
   attribute name whose in-repository method set changed. The import dependencies are read from
   every ``import`` statement in the file, function-level ones included; a submodule below an
   imported package counts only when its name occurs in the file.

The rule is conservative: it may re-resolve a file whose edges do not change, never the reverse.
Correctness is checked by building the same commit both ways and comparing the graph digest and
the unit bytes (``tests/unit/test_incremental_graph.py``; ``scripts/a_incremental_graph.py`` on
real histories). Exploratory families (``tests``, ``configures``) are not built here; they are
off in the first stored graph (D19).

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import ast
import hashlib
import os
import subprocess
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field, replace

from ril.parsing.build import BuildConfig, git_head
from ril.parsing.call_graph import GraphBuilder, apply_projections
from ril.parsing.code_unit import CodeUnit, units_to_jsonl
from ril.parsing.git_history import format_utc, iter_commits, read_history
from ril.parsing.repo_graph import Edge, RepoGraph
from ril.parsing.repo_id import normalize_repo_id
from ril.parsing.repository_parser import (
    FileSummary,
    ParsedRepository,
    ParseOptions,
    discover_python_files,
    module_names,
    parse_file,
    read_source,
)

INCREMENTAL_VERSION = "incremental/v0"


@dataclass
class FileRecord:
    """What the previous build kept for one Python file."""

    sha: str  # SHA-256 of the raw bytes
    module_name: str
    is_package: bool
    last_modified: str
    units: list[CodeUnit]  # [] when the file is unparseable
    summary: FileSummary | None  # None when the file is unparseable
    error: str = ""  # reason when unparseable
    edges: list[Edge] = field(default_factory=list)  # import and invoke edges of the file
    deps_exact: frozenset[str] = frozenset()  # modules whose own summary the file reads
    deps_prefix: frozenset[str] = frozenset()  # modules bound by name (submodules reachable)
    attrs: frozenset[str] = frozenset()  # attribute and plain names used in the file


@dataclass
class GraphState:
    """A built snapshot plus what an update needs to reuse it."""

    root: str
    config: BuildConfig
    commit: str
    records: dict[str, FileRecord]
    history: dict[str, str]  # every path ever touched -> D8 timestamp (with_history only)
    parsed: ParsedRepository
    graph: RepoGraph
    methods_by_name: dict[str, list[str]]


@dataclass
class UpdateStats:
    """Counts and stage times of one update."""

    commit: str
    files_total: int
    files_changed: int  # bytes, module name or package flag changed, or new
    files_deleted: int
    files_reparsed: int
    files_reresolved: int
    dirty_by_import: int
    dirty_by_method_name: int
    seconds: dict[str, float]


class _RecordingBuilder(GraphBuilder):
    """A resolver that returns each file's edges and import dependencies separately."""

    def resolve_file(
        self, fs: FileSummary
    ) -> tuple[list[Edge], frozenset[str], frozenset[str], frozenset[str]]:
        full = os.path.join(self.parsed.root, fs.path)
        _, raw = read_source(full)
        tree = ast.parse(raw, filename=fs.path)
        start = len(self.edges)
        self.process_tree(fs, tree)
        edges = self.edges[start:]
        exact: set[str] = set()
        prefix: set[str] = set()
        attrs: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    # ``import a.b`` binds ``a`` (every ``a.*`` is reachable); ``as`` binds ``a.b``
                    prefix.add(a.name if a.asname else a.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                base = self.abs_module(node.level or 0, node.module or "", fs)
                if base is None:
                    continue
                if base:
                    exact.add(base)
                for a in node.names:
                    if a.name == "*":
                        prefix.add(base)
                    else:
                        prefix.add(f"{base}.{a.name}" if base else a.name)
            elif isinstance(node, ast.Attribute):
                attrs.add(node.attr)
            elif isinstance(node, ast.Name):  # names reached through a star import
                attrs.add(node.id)
        return edges, frozenset(exact), frozenset(prefix), frozenset(attrs)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _summary_key(fs: FileSummary) -> dict[str, object]:
    """What another file's resolver can read of ``fs``: the summary without source positions.

    Import positions only place the file's own import edges; line counts are not read by the
    resolver at all. Two files with equal keys resolve every other file's names the same way.
    """
    key = asdict(fs)
    key["imports"] = [(i.kind, i.level, i.module, i.name, i.asname) for i in fs.imports]
    del key["n_lines"]
    return key


def _prefixes(name: str) -> list[str]:
    parts = name.split(".")
    return [".".join(parts[: i + 1]) for i in range(len(parts))]


def _is_ancestor(root: str, old: str, new: str) -> bool:
    done = subprocess.run(
        ["git", "-C", root, "merge-base", "--is-ancestor", old, new],
        capture_output=True,
        check=False,
        timeout=60,
    )
    return done.returncode == 0


def _history_update(root: str, old: str, new: str, previous: dict[str, str]) -> dict[str, str]:
    """D8 timestamps at ``new`` from those at ``old`` plus the commits in ``old..new``.

    Equal to a full read at ``new`` when ``old`` is an ancestor of ``new`` (the ancestors of
    ``new`` are those of ``old`` plus the range); otherwise the full read is done.
    """
    if not old or not _is_ancestor(root, old, new):
        return read_history(root, new).last_modified
    out = dict(previous)
    for c in iter_commits(root, f"{old}..{new}"):
        stamp = format_utc(c.timestamp)
        for p in c.paths:
            if out.get(p, "") < stamp:
                out[p] = stamp
    return dict(sorted(out.items()))


def _assemble_parsed(
    root: str,
    repo_id: str,
    options: ParseOptions,
    paths: list[str],
    names: dict[str, str],
    collisions: list[str],
    records: dict[str, FileRecord],
    skipped: dict[str, int],
    skipped_files: list[tuple[str, str]],
) -> ParsedRepository:
    """The same :class:`ParsedRepository` a full parse of the snapshot returns."""
    units: list[CodeUnit] = []
    files: dict[str, FileSummary] = {}
    unparseable: list[tuple[str, str]] = []
    id_collisions = 0
    for path in paths:
        rec = records[path]
        if rec.summary is None:
            unparseable.append((path, rec.error))
            continue
        id_collisions += sum(1 for u in rec.units if "#" in u.id.partition("::")[2])
        units.extend(rec.units)
        files[path] = rec.summary
    module_files: dict[str, str] = {}
    for path in paths:
        n = names[path]
        if n and path in files and n not in module_files:
            module_files[n] = path
    unparseable.sort()
    return ParsedRepository(
        repo_id=repo_id,
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


def _parse_one(
    root: str,
    repo_id: str,
    path: str,
    raw: bytes | None,
    read_error: str,
    module_name: str,
    is_package: bool,
    last_modified: str,
    options: ParseOptions,
) -> FileRecord:
    sha = _sha(raw) if raw is not None else ""
    if raw is None:
        return FileRecord(sha, module_name, is_package, last_modified, [], None, read_error)
    try:
        text, _ = read_source(os.path.join(root, path))
        tree = ast.parse(raw, filename=path)
    except (OSError, SyntaxError, ValueError, UnicodeError, RecursionError, MemoryError) as exc:
        reason = f"{type(exc).__name__}: {str(exc)[:100]}"
        return FileRecord(sha, module_name, is_package, last_modified, [], None, reason)
    units, summary = parse_file(
        repo_id=repo_id,
        path=path,
        text=text,
        tree=tree,
        module_name=module_name,
        is_package=is_package,
        last_modified=last_modified,
        options=options,
    )
    return FileRecord(sha, module_name, is_package, last_modified, units, summary)


def _read(full: str) -> tuple[bytes | None, str]:
    try:
        with open(full, "rb") as handle:
            return handle.read(), ""
    except OSError as exc:
        return None, f"{type(exc).__name__}: {str(exc)[:100]}"


def _snapshot(
    root: str,
    config: BuildConfig,
    previous: GraphState | None,
) -> tuple[GraphState, UpdateStats]:
    """Build the snapshot checked out at ``root``, reusing ``previous`` where it still holds."""
    seconds: dict[str, float] = {}
    options = ParseOptions(class_source=config.class_source)
    repo_id = normalize_repo_id(config.repo_id)
    commit = git_head(root)

    t0 = time.perf_counter()
    history: dict[str, str] = {}
    if config.with_history and commit:
        if previous is not None and previous.config.with_history:
            history = _history_update(root, previous.commit, commit, previous.history)
        else:
            history = read_history(root, commit).last_modified
    seconds["history"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    paths, skipped, skipped_files = discover_python_files(root)
    names, is_pkg, collisions = module_names(paths)
    old = previous.records if previous is not None else {}
    records: dict[str, FileRecord] = {}
    changed: set[str] = set()
    reparsed = 0
    for path in paths:
        raw, err = _read(os.path.join(root, path))
        lm = history.get(path, "")
        rec = old.get(path)
        same = (
            rec is not None
            and raw is not None
            and rec.sha == _sha(raw)
            and rec.module_name == names[path]
            and rec.is_package == is_pkg[path]
        )
        if same and rec is not None:
            if rec.last_modified != lm:
                rec = replace(
                    rec,
                    last_modified=lm,
                    units=[replace(u, last_modified=lm) for u in rec.units],
                )
            records[path] = rec
            continue
        records[path] = _parse_one(
            root, repo_id, path, raw, err, names[path], is_pkg[path], lm, options
        )
        reparsed += 1
        changed.add(path)
    deleted = sorted(set(old) - set(records))
    parsed = _assemble_parsed(
        root,
        repo_id,
        options,
        paths,
        names,
        collisions,
        records,
        dict(skipped),
        skipped_files,
    )
    seconds["parse"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    builder = _RecordingBuilder(parsed, config.max_candidates)
    nodes, structure = builder.structure_edges()

    # (b) files that import a changed module, closed over chains of imports
    changed_modules: set[str] = set()
    for path in [*changed, *deleted]:
        before, after = old.get(path), records.get(path)
        if (
            before is not None
            and after is not None
            and before.summary is not None
            and after.summary is not None
            and _summary_key(before.summary) == _summary_key(after.summary)
        ):
            continue  # a body-only edit: what other files can read of it is unchanged
        for rec in (before, after):
            if rec is None or not rec.module_name:
                continue
            new_or_gone = path not in old or path not in records
            changed_modules.update(_prefixes(rec.module_name) if new_or_gone else [rec.module_name])
    by_exact: dict[str, set[str]] = defaultdict(set)
    by_prefix: dict[str, set[str]] = defaultdict(set)
    for path, rec in records.items():
        if path in changed or rec.summary is None:
            continue
        for d in rec.deps_exact:
            by_exact[d].add(path)
        for d in rec.deps_prefix:
            by_prefix[d].add(path)
    dirty_import: set[str] = set()
    frontier = sorted(changed_modules)
    seen_modules: set[str] = set()
    while frontier:
        m = frontier.pop()
        if m in seen_modules:
            continue
        seen_modules.add(m)
        hit = set(by_exact.get(m, ()))
        parts = m.split(".")
        for i in range(1, len(parts) + 1):
            # a submodule below an imported module is reached through attribute access, so every
            # further name on the way down must occur as an attribute in the importing file
            rest = frozenset(parts[i:])
            for path in by_prefix.get(".".join(parts[:i]), ()):
                if rest <= records[path].attrs:
                    hit.add(path)
        for path in hit - dirty_import:
            dirty_import.add(path)
            name = records[path].module_name
            if name:
                frontier.append(name)

    # (c) files that use an attribute name whose in-repository method set changed
    dirty_method: set[str] = set()
    if previous is not None:
        old_index, new_index = previous.methods_by_name, builder.methods_by_name
        names_changed = {
            n for n in set(old_index) | set(new_index) if old_index.get(n) != new_index.get(n)
        }
        if names_changed:
            for path, rec in records.items():
                if path not in changed and rec.summary is not None and rec.attrs & names_changed:
                    dirty_method.add(path)

    dirty = changed | dirty_import | dirty_method if previous is not None else set(records)
    edges: list[Edge] = list(structure)
    for path in sorted(parsed.files):
        rec = records[path]
        if path in dirty:
            assert rec.summary is not None
            file_edges, exact, prefix, attrs = builder.resolve_file(rec.summary)
            rec = replace(rec, edges=file_edges, deps_exact=exact, deps_prefix=prefix, attrs=attrs)
            records[path] = rec
        edges.extend(rec.edges)
    seconds["graph_build"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    for u in parsed.units:  # reused units carry the previous projections; the hash is taken before
        u.calls, u.called_by = [], []
    graph = builder.assemble(nodes, edges, commit, {"config_hash": config.config_hash()})
    apply_projections(parsed.units, graph)
    seconds["assemble"] = time.perf_counter() - t0

    state = GraphState(
        root=root,
        config=config,
        commit=commit,
        records=records,
        history=history,
        parsed=parsed,
        graph=graph,
        methods_by_name=builder.methods_by_name,
    )
    stats = UpdateStats(
        commit=commit,
        files_total=len(paths),
        files_changed=len(changed),
        files_deleted=len(deleted),
        files_reparsed=reparsed,
        files_reresolved=len(dirty & set(parsed.files)),
        dirty_by_import=len(dirty_import - changed),
        dirty_by_method_name=len(dirty_method - changed - dirty_import),
        seconds=seconds,
    )
    return state, stats


def full_state(root: str, config: BuildConfig) -> GraphState:
    """Build every file of the checkout at ``root`` and keep what an update reuses."""
    state, _ = _snapshot(root, config, None)
    return state


def update_state(state: GraphState, root: str | None = None) -> tuple[GraphState, UpdateStats]:
    """Bring ``state`` to the commit now checked out at its root (or at ``root``)."""
    return _snapshot(root or state.root, state.config, state)


def state_digest(state: GraphState) -> tuple[str, str]:
    """(graph digest, SHA-256 of the unit bytes): equal for equal snapshots."""
    return state.graph.digest(), _sha(units_to_jsonl(state.parsed.units))


__all__ = [
    "INCREMENTAL_VERSION",
    "FileRecord",
    "GraphState",
    "UpdateStats",
    "full_state",
    "state_digest",
    "update_state",
]
