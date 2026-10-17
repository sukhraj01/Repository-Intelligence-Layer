"""Edge recovery against a dynamic oracle (definition (b) of ADR-012) and the call-site shares (a).

Implements ``specs/parse_one_repo.md`` (edge recovery measured under several definitions, none
chosen). Inputs: the units and graph of one snapshot and a trace written by
``ril.evaluation.dynamic_trace`` while the repository's own test suite ran.

Mapping of trace events to units (decision D6, nested definitions fold into their parent):

* a code object whose first line is a unit's first line and whose name matches is that unit's
  *own* code;
* a code object inside a unit's span but not its own code (nested function, lambda) is
  attributed to the enclosing unit; a call to it from the same unit is not an edge;
* comprehension code objects, class bodies and module bodies are definition-time or inline
  execution, not calls, and are excluded from the pair set (counted separately).

A dynamic pair (caller unit, callee unit) counts as *recovered* when the static graph holds a
``resolved`` ``invoke`` edge between the two units, or (reported separately) an ``ambiguous`` edge
from the caller whose candidate set contains the callee. A resolved static edge to a class counts
for the class's ``__init__`` and ``__new__`` (found through the in-repository MRO), because the
interpreter reports instantiation as a call of those methods.

The oracle is a lower bound on what the code can do: it holds only the pairs the suite executed
(Total Recall: a test-based baseline can mis-state precision and recall, so the suite's function
coverage is reported next to every number).
"""

from __future__ import annotations

import bisect
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from ril.parsing.call_graph import GraphBuilder
from ril.parsing.code_unit import CodeUnit
from ril.parsing.repo_graph import RepoGraph
from ril.parsing.repository_parser import ParsedRepository

_COMPREHENSION_NAMES = frozenset({"<listcomp>", "<genexpr>", "<dictcomp>", "<setcomp>"})
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_IMPLICIT_DUNDERS = re.compile(r"^__\w+__$")


def terminal_name(text: str) -> str:
    """Last identifier of a call target as written (``a.b.c`` -> ``c``, ``f(x).g`` -> ``g``)."""
    names = _IDENT_RE.findall(text)
    return names[-1] if names else text


@dataclass
class UnitIndex:
    """Lookup from (file, first line, code name) to a unit."""

    own: dict[tuple[str, int], list[CodeUnit]] = field(default_factory=dict)
    spans: dict[str, list[tuple[int, int, str]]] = field(default_factory=dict)  # sorted by start
    starts: dict[str, list[int]] = field(default_factory=dict)
    units: dict[str, CodeUnit] = field(default_factory=dict)
    module_unit: dict[str, str] = field(default_factory=dict)
    method_spans: dict[str, list[tuple[int, int, str]]] = field(default_factory=dict)

    @classmethod
    def build(cls, units: Iterable[CodeUnit]) -> UnitIndex:
        idx = cls()
        by_file: dict[str, list[tuple[int, int, str]]] = defaultdict(list)
        for u in units:
            idx.units[u.id] = u
            if u.unit_type == "module":
                idx.module_unit[u.file] = u.id
                continue
            idx.own.setdefault((u.file, u.start_line), []).append(u)
            if u.unit_type != "method":
                by_file[u.file].append((u.start_line, u.end_line, u.id))
            else:
                owner = u.id.partition("::")[0] + "::" + u.qualified_name.rsplit(".", 1)[0]
                idx.method_spans.setdefault(owner, []).append((u.start_line, u.end_line, u.id))
        for spans_m in idx.method_spans.values():
            spans_m.sort()
        for f, spans in by_file.items():
            spans.sort()
            idx.spans[f] = spans
            idx.starts[f] = [s[0] for s in spans]
        return idx

    def locate(self, file: str, line: int, name: str) -> tuple[str, str] | None:
        """(unit id, kind) for a code object; kind in own | nested | module | classbody | comp."""
        if file not in self.module_unit:
            return None
        if name == "<module>":
            return self.module_unit[file], "module"
        cands = self.own.get((file, line), [])
        for u in cands:
            if u.name == name:
                return u.id, "classbody" if u.unit_type == "class" else "own"
        # inside a unit's span: nested definition, lambda, comprehension
        enclosing = self.enclosing(file, line)
        if enclosing is None:
            return self.module_unit[file], "comp" if name in _COMPREHENSION_NAMES else "nested"
        return enclosing, "comp" if name in _COMPREHENSION_NAMES else "nested"

    def enclosing(self, file: str, line: int) -> str | None:
        """Top-level unit whose span holds ``line`` (the innermost method of a class if any)."""
        spans = self.spans.get(file)
        if not spans:
            return None
        i = bisect.bisect_right(self.starts[file], line) - 1
        while i >= 0:
            s, e, uid = spans[i]
            if s <= line <= e:
                for ms, me, mid in self.method_spans.get(uid, ()):
                    if ms <= line <= me:
                        return mid
                return uid
            i -= 1
        return None


@dataclass
class DynamicPairs:
    """Dynamic caller -> callee unit pairs and what was excluded."""

    pairs: dict[tuple[str, str], int]  # callee is a unit's own code
    nested_callee: set[tuple[str, str]]  # callee is a nested function folded into its parent
    ext_py: set[tuple[str, str, str]]
    c_calls: set[tuple[str, str, str]]
    executed: set[str]
    excluded: Counter[str]


def map_trace(trace: dict[str, Any], idx: UnitIndex) -> DynamicPairs:
    """Map a trace to unit pairs (see the module docstring for the rules)."""
    excluded: Counter[str] = Counter()
    executed: set[str] = set()
    for file, line, name, _n in trace["entered"]:
        loc = idx.locate(file, line, name)
        if loc is not None and loc[1] in ("own", "module", "classbody"):
            executed.add(loc[0])
    pairs: Counter[tuple[str, str]] = Counter()
    nested_callee: set[tuple[str, str]] = set()
    for cf, cl, cn, ef, el, en, n in trace["pairs_py"]:
        caller = idx.locate(cf, cl, cn)
        callee = idx.locate(ef, el, en)
        if caller is None or callee is None:
            excluded["unmapped-file"] += n
            continue
        cuid, ckind = caller
        euid, ekind = callee
        if ekind == "comp":
            excluded["callee-comprehension"] += n
            continue
        if ekind in ("module", "classbody"):
            excluded[f"callee-{ekind}-execution"] += n
            continue
        if ekind == "nested":
            if euid == cuid:
                excluded["nested-callee-same-unit"] += n
                continue
            nested_callee.add((cuid, euid))
            continue
        pairs[(cuid, euid)] += n
    ext_py: set[tuple[str, str, str]] = set()
    for cf, cl, cn, mod, fn, _n in trace["pairs_ext_py"]:
        caller = idx.locate(cf, cl, cn)
        if caller is None:
            excluded["unmapped-file"] += 1
            continue
        ext_py.add((caller[0], mod, fn))
    c_calls: set[tuple[str, str, str]] = set()
    for cf, cl, cn, mod, fn, _n in trace["pairs_c"]:
        caller = idx.locate(cf, cl, cn)
        if caller is None:
            excluded["unmapped-file"] += 1
            continue
        c_calls.add((caller[0], mod, fn))
    nested_callee -= set(pairs)
    return DynamicPairs(dict(pairs), nested_callee, ext_py, c_calls, executed, excluded)


@dataclass
class StaticPairs:
    """The static graph viewed as unit pairs."""

    resolved: set[tuple[str, str]]
    ambiguous: set[tuple[str, str]]
    terminals: dict[str, set[str]]  # caller -> terminal names of non-resolved sites
    all_terminals: dict[str, set[str]]  # caller -> terminal names of every site
    instantiation_implied: int


def static_pairs(parsed: ParsedRepository, graph: RepoGraph, builder: GraphBuilder) -> StaticPairs:
    """Pairs from ``invoke`` edges; instantiation edges also imply ``__init__`` and ``__new__``."""
    units = parsed.unit_by_id()
    resolved: set[tuple[str, str]] = set()
    ambiguous: set[tuple[str, str]] = set()
    terminals: dict[str, set[str]] = defaultdict(set)
    all_terminals: dict[str, set[str]] = defaultdict(set)
    implied = 0
    for e in graph.edges:
        if e.type != "invoke":
            continue
        t = terminal_name(e.target_text)
        all_terminals[e.src].add(t)
        if e.status == "resolved":
            if e.src == e.dst:
                continue
            resolved.add((e.src, e.dst))
            dst = units[e.dst]
            if dst.unit_type == "class":
                for dunder in ("__init__", "__new__"):
                    found = builder.find_member(e.dst, dunder)
                    if found.kind == "func" and found.ref not in ("",):
                        if (e.src, found.ref) not in resolved:
                            implied += 1
                        resolved.add((e.src, found.ref))
        else:
            terminals[e.src].add(t)
            if e.status == "ambiguous":
                for c in e.candidates:
                    ambiguous.add((e.src, c))
    return StaticPairs(resolved, ambiguous, dict(terminals), dict(all_terminals), implied)


def _miss_category(
    caller: str,
    callee: str,
    units: dict[str, CodeUnit],
    decorators: dict[str, list[str]],
    sp: StaticPairs,
) -> str:
    u = units[callee]
    name = u.name
    if name in sp.terminals.get(caller, set()):
        return "site-present-not-recovered"
    if name in sp.all_terminals.get(caller, set()):
        return "site-present-other-target"
    if name in ("__init__", "__new__"):
        return "instantiation-no-site"
    if any(
        d.split("(")[0].split(".")[-1] in ("property", "cached_property")
        for d in decorators.get(callee, [])
    ):
        return "property-access"
    if _IMPLICIT_DUNDERS.match(name):
        return "implicit-protocol-dunder"
    return "no-call-site-for-callee-name"


def recovery_report(
    parsed: ParsedRepository,
    graph: RepoGraph,
    builder: GraphBuilder,
    trace: dict[str, Any],
) -> dict[str, Any]:
    """Recall and precision of the static graph against the dynamic pairs, with the coverage."""
    idx = UnitIndex.build(parsed.units)
    dp = map_trace(trace, idx)
    sp = static_pairs(parsed, graph, builder)
    units = parsed.unit_by_id()
    decorators: dict[str, list[str]] = {}
    for fs in parsed.files.values():
        decorators.update(fs.decorators)

    def share(a: int, b: int) -> float | None:
        return round(a / b, 4) if b else None

    def recall_view(pred: Any, label: str) -> dict[str, Any]:
        keys = [k for k in dp.pairs if pred(units[k[0]], units[k[1]])]
        hit_r = sum(1 for k in keys if k in sp.resolved)
        hit_a = sum(1 for k in keys if k not in sp.resolved and k in sp.ambiguous)
        misses = Counter(
            _miss_category(c, e, units, decorators, sp) for c, e in keys if k_not_hit(c, e, sp)
        )
        return {
            "view": label,
            "n_pairs": len(keys),
            "recovered_resolved": hit_r,
            "recovered_ambiguous_only": hit_a,
            "recall_resolved": share(hit_r, len(keys)),
            "recall_resolved_or_ambiguous": share(hit_r + hit_a, len(keys)),
            "missed_by_category": dict(sorted(misses.items())),
        }

    views = [
        recall_view(lambda c, e: True, "all in-repo pairs"),
        recall_view(lambda c, e: not e.is_test, "callee in non-test code"),
        recall_view(
            lambda c, e: not c.is_test and not e.is_test, "caller and callee in non-test code"
        ),
        recall_view(
            lambda c, e: not _IMPLICIT_DUNDERS.match(e.name) or e.name in ("__init__", "__new__"),
            "excluding implicit-protocol dunder callees",
        ),
    ]

    # with built-in and external callees: match by terminal name against the caller's other sites
    ext_hits = sum(1 for (c, _m, f) in dp.ext_py if f in sp.all_terminals.get(c, set()))
    c_hits = sum(
        1 for (c, _m, f) in dp.c_calls if terminal_name(f) in sp.all_terminals.get(c, set())
    )
    inrepo_hits = sum(1 for k in dp.pairs if k in sp.resolved)
    total_all = len(dp.pairs) + len(dp.ext_py) + len(dp.c_calls)
    hit_all = inrepo_hits + ext_hits + c_hits

    # precision among static edges whose caller executed
    nonself = {k for k in sp.resolved if units[k[1]].unit_type != "module"}
    exec_edges = {k for k in nonself if k[0] in dp.executed}
    both_exec = {k for k in exec_edges if k[1] in dp.executed}
    supported = {k for k in exec_edges if k in dp.pairs}
    supported_both = {k for k in both_exec if k in dp.pairs}

    cov: dict[str, Any] = {}
    for kind in ("function", "method", "class", "module"):
        non_test = [u for u in parsed.units if u.unit_type == kind and not u.is_test]
        ex = sum(1 for u in non_test if u.id in dp.executed)
        cov[kind] = {"units": len(non_test), "executed": ex, "share": share(ex, len(non_test))}
    callable_units = [
        u for u in parsed.units if u.unit_type in ("function", "method") and not u.is_test
    ]
    cov["function_or_method"] = {
        "units": len(callable_units),
        "executed": sum(1 for u in callable_units if u.id in dp.executed),
        "share": share(sum(1 for u in callable_units if u.id in dp.executed), len(callable_units)),
    }

    return {
        "dynamic": {
            "distinct_in_repo_pairs": len(dp.pairs),
            "distinct_nested_callee_pairs": len(dp.nested_callee),
            "distinct_external_python_callee_pairs": len(dp.ext_py),
            "distinct_builtin_c_callee_pairs": len(dp.c_calls),
            "excluded_event_counts": dict(sorted(dp.excluded.items())),
            "pytest_outcomes": trace.get("outcomes", {}),
            "pytest_exit_code": trace.get("pytest_exit_code"),
            "python": trace.get("python"),
        },
        "static": {
            "resolved_unit_pairs": len(sp.resolved),
            "ambiguous_unit_pairs": len(sp.ambiguous),
            "instantiation_implied_pairs": sp.instantiation_implied,
        },
        "recall_in_repo_callees": views,
        "recall_including_builtin_and_external_callees": {
            "n_pairs": total_all,
            "recovered": hit_all,
            "recall": share(hit_all, total_all),
            "in_repo": {"n": len(dp.pairs), "recovered_resolved": inrepo_hits},
            "external_python": {"n": len(dp.ext_py), "matched_by_terminal_name": ext_hits},
            "builtin_c": {"n": len(dp.c_calls), "matched_by_terminal_name": c_hits},
            "note": "external and builtin callees are matched by the callee's last name against "
            "the terminal names of the caller's invoke sites (any status); a hit does not prove "
            "the same function",
        },
        "precision_among_edges_whose_caller_executed": {
            "static_resolved_pairs_total": len(nonself),
            "caller_executed": len(exec_edges),
            "supported_by_a_dynamic_pair": len(supported),
            "precision": share(len(supported), len(exec_edges)),
            "caller_and_callee_executed": len(both_exec),
            "supported_among_both_executed": len(supported_both),
            "precision_both_executed": share(len(supported_both), len(both_exec)),
            "note": "an edge on an untaken branch of an executed caller counts as unsupported, "
            "so this is a lower bound on precision",
        },
        "suite_function_coverage_non_test_units": cov,
    }


def k_not_hit(caller: str, callee: str, sp: StaticPairs) -> bool:
    """True when neither a resolved nor an ambiguous static edge covers the pair."""
    return (caller, callee) not in sp.resolved and (caller, callee) not in sp.ambiguous


def run_recovery(root: str, repo_id: str, trace: dict[str, Any]) -> dict[str, Any]:
    """Build the graph of ``root``; report recovery against ``trace`` (definitions (a), (b))."""
    from ril.parsing.call_graph import GraphBuilder as _Builder
    from ril.parsing.report import invoke_shares
    from ril.parsing.repository_parser import parse_repository

    parsed = parse_repository(root, repo_id)
    builder = _Builder(parsed)
    graph = builder.build()
    report = recovery_report(parsed, graph, builder, trace)
    row = graph.status_table().get("invoke", {})
    report["definition_a_call_site_shares"] = {"invoke_status_counts": row, **invoke_shares(row)}
    report["graph_sha256"] = graph.digest()
    return report
