"""Resolver typing pilots (session A2b): each option against the stored resolver.

Three readings per option set (``ril.parsing.call_graph.ResolverOptions``):

* **static**, on any checkout: ``invoke`` sites by status, the number of unknown-receiver sites, and
  the graph-build time. A site moving to ``resolved`` is not yet a correct site.
* **receivers**: for the call sites whose receiver stays untyped, what that receiver is (an
  attribute chain on ``self`` or on another object, a local name and how it is bound, a call result,
  a subscript), under the combined options; this says which typing work would reach the most sites.
* **dynamic**, where a test-suite trace exists (decision D15): recall of the in-repository caller to
  callee pairs the suite executed, and the lower bound on precision among resolved pairs whose
  caller executed, both from ``ril.evaluation.edge_recovery.recovery_report``; and every resolved
  pair an option adds to the stored resolver, with what the trace says about it.

``summary`` reduces the stored logs to the totals and shares quoted in the ledger and the log.

The repository is parsed once; every option set builds its graph from the same parse.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import ast
import time
from collections import Counter
from typing import Any

from ril.evaluation.edge_recovery import (
    DynamicPairs,
    UnitIndex,
    map_trace,
    recovery_report,
    static_pairs,
)
from ril.parsing.call_graph import Ctx, GraphBuilder, ResolverOptions
from ril.parsing.repo_graph import Edge
from ril.parsing.repository_parser import parse_repository

_TYPED_RECEIVERS = frozenset({"inst", "class", "module", "nspkg", "super", "ext", "builtin"})

PILOTS: tuple[ResolverOptions, ...] = (
    ResolverOptions(),
    ResolverOptions(infer_returns=True),
    ResolverOptions(merge_locals=True),
    ResolverOptions(param_defaults=True),
    ResolverOptions(infer_returns=True, merge_locals=True, param_defaults=True),
)


def static_rows(root: str, repo_id: str) -> list[dict[str, Any]]:
    """Invoke-site counts and build time for every pilot on one checkout."""
    parsed = parse_repository(root, repo_id)
    rows = []
    for options in PILOTS:
        t0 = time.perf_counter()
        graph = GraphBuilder(parsed, options=options).build()
        seconds = time.perf_counter() - t0
        status: Counter[str] = Counter()
        unknown_receiver = 0
        for e in graph.edges:
            if e.type == "invoke":
                status[e.status] += 1
                unknown_receiver += e.derivation.startswith("unknown-receiver")
        rows.append(
            {
                "repo_id": repo_id,
                "options": options.label(),
                "graph_build_seconds": round(seconds, 3),
                "invoke_sites": sum(status.values()),
                **{f"invoke_{k}": status.get(k, 0) for k in ("resolved", "ambiguous")},
                **{f"invoke_{k}": status.get(k, 0) for k in ("unresolved", "external")},
                "unknown_receiver_sites": unknown_receiver,
            }
        )
    return rows


class _ReceiverCensus(GraphBuilder):
    """A resolver that also counts, per untyped receiver, what kind of expression it is."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.receivers: Counter[str] = Counter()

    def _classify(self, func: ast.expr, site_node: ast.AST, ctx: Ctx, deco: bool) -> Edge:
        if isinstance(func, ast.Attribute):
            base = func.value
            if self.eval_expr(base, ctx).kind not in _TYPED_RECEIVERS:
                self.receivers[_receiver_kind(base, ctx)] += 1
        return super()._classify(func, site_node, ctx, deco)


def _receiver_kind(base: ast.expr, ctx: Ctx) -> str:
    if isinstance(base, ast.Name):
        sc = ctx.locals
        if sc is None or base.id not in sc.sources:
            return "module-level name"
        kinds = set()
        for src in sc.sources[base.id]:
            if src.kind == "param":
                kinds.add("annotated parameter" if src.text else "unannotated parameter")
            else:
                kinds.add(src.kind)
        return "local: " + " + ".join(sorted(kinds))
    if isinstance(base, ast.Attribute):
        root: ast.expr = base
        while isinstance(root, ast.Attribute):
            root = root.value
        on_self = isinstance(root, ast.Name) and root.id in ("self", "cls")
        return "attribute chain on self" if on_self else "attribute chain on another object"
    if isinstance(base, ast.Call):
        return "call result"
    if isinstance(base, ast.Subscript):
        return "subscript"
    return "other expression"


def receiver_census(root: str, repo_id: str, options: ResolverOptions) -> dict[str, int]:
    """Untyped receivers of attribute calls by kind, under ``options``."""
    census = _ReceiverCensus(parse_repository(root, repo_id), options=options)
    census.build()
    return dict(census.receivers.most_common())


def dynamic_rows(root: str, repo_id: str, trace: dict[str, Any]) -> list[dict[str, Any]]:
    """Recall and precision against the test-suite trace for every pilot on one checkout."""
    parsed = parse_repository(root, repo_id)
    dp = map_trace(trace, UnitIndex.build(parsed.units))
    units = parsed.unit_by_id()
    stored: set[tuple[str, str]] = set()
    rows = []
    for options in PILOTS:
        builder = GraphBuilder(parsed, options=options)
        graph = builder.build()
        report = recovery_report(parsed, graph, builder, trace)
        resolved = static_pairs(parsed, graph, builder).resolved
        if not stored:
            stored = resolved
        view = report["recall_in_repo_callees"][0]
        prec = report["precision_among_edges_whose_caller_executed"]
        added = [
            {"caller": c, "callee": e, "trace": _trace_reading(c, e, dp, units[e].unit_type)}
            for c, e in sorted(resolved - stored)
        ]
        rows.append(
            {
                "repo_id": repo_id,
                "options": options.label(),
                "dynamic_pairs": view["n_pairs"],
                "recovered_resolved": view["recovered_resolved"],
                "recall_resolved": view["recall_resolved"],
                "recall_resolved_or_ambiguous": view["recall_resolved_or_ambiguous"],
                "static_resolved_pairs": report["static"]["resolved_unit_pairs"],
                "precision_lower_bound": prec["precision"],
                "precision_caller_executed_n": prec["caller_executed"],
                "missed_by_category": view["missed_by_category"],
                "removed_vs_stored": len(stored - resolved),
                "added_vs_stored": len(added),
                "added_by_trace_reading": dict(Counter(a["trace"] for a in added)),
                "added_pairs": added,
            }
        )
    return rows


def _trace_reading(caller: str, callee: str, dp: DynamicPairs, callee_type: str) -> str:
    """What the trace says about one resolved pair."""
    if (caller, callee) in dp.pairs:
        return "executed"
    if caller not in dp.executed:
        return "caller not executed"
    if callee_type == "class":
        return "class target (the trace records its __init__)"
    return "caller executed, pair not seen"


def _pct(part: float, whole: float) -> float | None:
    return round(100 * part / whole, 1) if whole else None


def summary(
    breakdown: dict[str, Any] | None, static: dict[str, Any] | None, dynamic: dict[str, Any] | None
) -> dict[str, Any]:
    """Totals and shares over the stored logs (invoke breakdown, static pilot, dynamic pilot)."""
    out: dict[str, Any] = {}
    if breakdown is not None:
        sites = failed = unknown = 0
        for repo in breakdown["repositories"]:
            for key, n in repo["invoke_by_status_and_rule"].items():
                status, _, rule = key.partition("|")
                sites += n
                if status in ("ambiguous", "unresolved"):
                    failed += n
                    unknown += n if rule.startswith("unknown-receiver") else 0
        out["invoke_breakdown"] = {
            "invoke_sites": sites,
            "ambiguous_or_unresolved": failed,
            "unknown_receiver_among_them": unknown,
            "unknown_receiver_share_pct": _pct(unknown, failed),
        }
    if static is not None:
        totals: dict[str, Counter[str]] = {}
        for row in static["static"]:
            c = totals.setdefault(row["options"], Counter())
            for k in ("invoke_sites", "invoke_resolved", "unknown_receiver_sites"):
                c[k] += row[k]
            c["graph_build_ms"] += round(1000 * row["graph_build_seconds"])
        base = totals["stored"]
        out["static_totals_over_repositories"] = {
            label: {
                **c,
                "resolved_gain": c["invoke_resolved"] - base["invoke_resolved"],
                "resolved_gain_pct": _pct(
                    c["invoke_resolved"] - base["invoke_resolved"], base["invoke_resolved"]
                ),
                "resolved_gain_pct_of_all_sites": _pct(
                    c["invoke_resolved"] - base["invoke_resolved"], c["invoke_sites"]
                ),
                "unknown_receiver_change_pct": _pct(
                    c["unknown_receiver_sites"] - base["unknown_receiver_sites"],
                    base["unknown_receiver_sites"],
                ),
                "graph_build_change_pct": _pct(
                    c["graph_build_ms"] - base["graph_build_ms"], base["graph_build_ms"]
                ),
            }
            for label, c in totals.items()
        }
        kinds: Counter[str] = Counter()
        for per_repo in static["untyped_receivers_combined_options"].values():
            kinds.update(per_repo)
        n = sum(kinds.values())
        chains = kinds["attribute chain on self"] + kinds["attribute chain on another object"]
        out["untyped_receivers_combined_options"] = {
            "receivers": n,
            "attribute_chain_pct": _pct(chains, n),
            "share_pct": {k: _pct(v, n) for k, v in kinds.most_common()},
        }
    if dynamic is not None:
        out["dynamic"] = {
            f"{row['repo_id']} {row['options']}": {
                "recall_resolved_pct": _pct(row["recovered_resolved"], row["dynamic_pairs"]),
                "precision_lower_bound_pct": _pct(row["precision_lower_bound"], 1),
                "added_vs_stored": row["added_vs_stored"],
                "added_executed_pct": _pct(
                    row["added_by_trace_reading"].get("executed", 0), row["added_vs_stored"]
                ),
            }
            for row in dynamic["dynamic"]
        }
    return out
