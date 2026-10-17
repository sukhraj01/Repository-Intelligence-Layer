"""Summaries of one build: ten sample units, counts by type, per-status edge tables.

Implements the printed part of ``specs/parse_one_repo.md`` ("ten CodeUnits and the graph
statistics"). Selection is deterministic for a seed.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import random
from collections import Counter

from ril.parsing.build import BuildResult, co_change_summary
from ril.parsing.code_unit import CodeUnit
from ril.parsing.repo_graph import EDGE_TYPES, STATUSES


def select_units(units: list[CodeUnit], seed: int, n: int = 10) -> list[CodeUnit]:
    """``n`` units chosen by ``seed``: one module, one class, then functions and methods.

    Units from test files are used only when no other unit of the kind exists.
    """
    rng = random.Random(seed)
    pools: dict[str, list[CodeUnit]] = {}
    for kind in ("module", "class", "function", "method"):
        cands = [u for u in units if u.unit_type == kind and not u.is_test and u.loc >= 3]
        cands = cands or [u for u in units if u.unit_type == kind]
        pools[kind] = sorted(cands, key=lambda u: u.id)
    plan = {"module": 1, "class": 1, "function": 4, "method": 4}
    chosen: list[CodeUnit] = []
    for kind, k in plan.items():
        pool = pools[kind]
        chosen.extend(rng.sample(pool, min(k, len(pool))))
    leftovers = [u for u in sorted(units, key=lambda u: u.id) if u not in chosen]
    while len(chosen) < n and leftovers:
        chosen.append(leftovers.pop(rng.randrange(len(leftovers))))
    return chosen[:n]


def unit_summary(u: CodeUnit, max_source: int = 240) -> dict[str, object]:
    """A unit as a compact dict (source cut for display; the full unit is in ``units.jsonl``)."""
    d = u.to_dict()
    src = str(d["source"])
    d["source"] = src if len(src) <= max_source else src[:max_source] + f"... [{len(src)} chars]"
    return d


def build_stats(result: BuildResult) -> dict[str, object]:
    """Counts reported for every build (all numbers measured by the build itself)."""
    units = result.parsed.units
    by_type = Counter(u.unit_type for u in units)
    status = result.graph.status_table()
    invoke_rules = result.graph.rule_table("invoke")
    stats: dict[str, object] = {
        "repo_id": result.parsed.repo_id,
        "commit": result.commit,
        "files_parsed": len(result.parsed.files),
        "files_unparseable": len(result.parsed.unparseable),
        "unparseable": [list(x) for x in result.parsed.unparseable],
        "skipped": result.parsed.skipped,
        "skipped_files": [list(x) for x in result.parsed.skipped_files],
        "units": len(units),
        "units_by_type": dict(sorted(by_type.items())),
        "id_collisions": result.parsed.id_collisions,
        "module_name_collisions": result.parsed.module_collisions,
        "nodes": len(result.graph.nodes),
        "edges_by_type_and_status": status,
        "invoke_by_rule": invoke_rules,
        "import_by_rule": result.graph.rule_table("import"),
        "seconds": {k: round(v, 4) for k, v in result.seconds.items()},
        "class_source": result.parsed.options.get("class_source", ""),
        "graph_sha256": result.graph.digest(),
    }
    if result.tests is not None:
        stats["tests_exploratory"] = Counter(e.derivation for e in result.tests.edges)
    if result.configures is not None:
        stats["configures_exploratory"] = Counter(e.derivation for e in result.configures.edges)
    cc = co_change_summary(result)
    if cc:
        stats["co_change"] = cc
    return stats


def invoke_shares(status_row: dict[str, int]) -> dict[str, float]:
    """Definition (a) shares from one invoke status row: resolved over all sites, and over the
    sites that are not external (resolved + ambiguous + unresolved)."""
    total = sum(status_row.get(s, 0) for s in STATUSES)
    in_repo_directed = total - status_row.get("external", 0)
    resolved = status_row.get("resolved", 0)
    return {
        "resolved_over_all_sites": resolved / total if total else 0.0,
        "resolved_over_non_external": resolved / in_repo_directed if in_repo_directed else 0.0,
        "resolved_or_ambiguous_over_non_external": (resolved + status_row.get("ambiguous", 0))
        / in_repo_directed
        if in_repo_directed
        else 0.0,
    }


__all__ = ["EDGE_TYPES", "build_stats", "invoke_shares", "select_units", "unit_summary"]
