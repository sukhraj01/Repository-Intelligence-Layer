"""Resolver typing pilots (session A2b): each option against the stored resolver.

Three readings per option set (``ril.parsing.call_graph.ResolverOptions``):

* **static**, on any checkout: ``invoke`` sites by status, the number of unknown-receiver sites, and
  the graph-build time. A site moving to ``resolved`` is not yet a correct site.
* **receivers**: for the call sites whose receiver stays untyped, what that receiver is (an
  attribute chain on ``self`` or on another object, a local name and how it is bound, a call result,
  a subscript), under the combined options; this says which typing work would reach the most sites.
* **dynamic**, where a test-suite trace exists (decision D15): recall of the in-repository caller to
  callee pairs the suite executed, and the lower bound on precision among resolved pairs whose
  caller executed, both from ``ril.evaluation.edge_recovery.recovery_report``.

The repository is parsed once; every option set builds its graph from the same parse.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import ast
import time
from collections import Counter
from typing import Any

from ril.evaluation.edge_recovery import recovery_report
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
    rows = []
    for options in PILOTS:
        builder = GraphBuilder(parsed, options=options)
        graph = builder.build()
        report = recovery_report(parsed, graph, builder, trace)
        view = report["recall_in_repo_callees"][0]
        prec = report["precision_among_edges_whose_caller_executed"]
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
            }
        )
    return rows
