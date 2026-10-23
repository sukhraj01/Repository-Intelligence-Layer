"""Two readers of the call-site buckets that are not the build author's judgement (Q35, Q36).

Exploratory. Measures, per policy of ``ril.parsing.ambiguity_policy``, how right the edges are:

* **Dynamic oracle** (flask; trace and line coverage of the repository's own test suite at one
  commit, ``ril.evaluation.dynamic_trace``, ``edge_recovery.map_trace``). Pair level: the precision
  of the static invoke pairs whose caller executed (a pair on an untaken branch counts as
  unsupported, so this is a lower bound) and the recall of the dynamic in-repository pairs, with
  and without implicit-protocol dunder callees (decision D15), per policy. Site level, for sites
  whose line executed (coverage.py): a resolved site is supported if its pair was observed; an
  ambiguous site is *in-repository* if some candidate was observed being called from the caller,
  else *not observed* (the call went outside the repository, or to a nested or unmapped target).
  Ambiguous sites in files the coverage run did not measure (the test files) are judged at caller
  level (the caller executed) and kept in separate ``|caller-level`` buckets.
* **Jedi** (a second static resolver; no dependencies installed, so third-party receivers are
  unknown to it). A stratified sample of sites per repository: resolved, external, unresolved,
  ambiguous with receiver evidence, ambiguous without evidence and a candidate set of at most three,
  and without evidence and more than three. Jedi's answer is three-way: in-repository definitions
  (inside or outside the candidate set), only definitions outside the repository, or nothing.

Neither reader is ground truth: the oracle sees only what the suite executed, and Jedi has its own
failures. They are reported side by side, each with its denominator.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import ast
import os
import random
from collections import Counter
from typing import Any

from ril.evaluation.edge_recovery import (
    _IMPLICIT_DUNDERS,
    UnitIndex,
    map_trace,
    static_pairs,
    terminal_name,
)
from ril.evaluation.jedi_agreement import Site, jedi_units_for
from ril.parsing.ambiguity_policy import POLICIES, AmbiguousSite, ambiguous_sites, keeps
from ril.parsing.call_graph import GraphBuilder
from ril.parsing.repo_graph import Edge, RepoGraph
from ril.parsing.repository_parser import ParsedRepository

Record = dict[str, Any]
STRATA: tuple[str, ...] = (
    "resolved",
    "external",
    "unresolved",
    "ambiguous_evidence",
    "ambiguous_le3",
    "ambiguous_gt3",
)
FILL_ORDER: tuple[str, ...] = ("ambiguous_le3", "ambiguous_gt3", "unresolved", "resolved")
"""Strata that take up the quota a short stratum leaves, in this order."""


def _share(a: int, b: int) -> float | None:
    return round(a / b, 4) if b else None


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """Wilson score interval (95%) of a proportion k / n; None for n = 0."""
    if n == 0:
        return None
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / denom
    return round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)


# --------------------------------------------------------------------------- dynamic oracle


def site_line_executed(site: str, coverage: Record) -> bool | None:
    """Whether the site's line executed under coverage.py; None if the file is not covered."""
    path, line_s, _ = site.rsplit(":", 2)
    f = coverage.get("files", {}).get(path)
    if f is None:
        return None
    return int(line_s) in set(f.get("executed_lines", []))


def oracle_policy_report(
    parsed: ParsedRepository,
    graph: RepoGraph,
    builder: GraphBuilder,
    trace: Record,
    coverage: Record,
) -> Record:
    """Pair-level precision and recall per policy, and site-level bucket support (see module)."""
    idx = UnitIndex.build(parsed.units)
    dp = map_trace(trace, idx)
    sp = static_pairs(parsed, graph, builder)
    units = parsed.unit_by_id()
    sites = ambiguous_sites(parsed, graph)
    dyn = set(dp.pairs)
    explicit = {
        k
        for k in dyn
        if not _IMPLICIT_DUNDERS.match(units[k[1]].name)
        or units[k[1]].name in ("__init__", "__new__")
    }

    def pair_view(pairs: set[tuple[str, str]]) -> Record:
        nonmod = {k for k in pairs if units[k[1]].unit_type != "module" and k[0] != k[1]}
        ex = {k for k in nonmod if k[0] in dp.executed}
        sup = {k for k in ex if k in dyn}
        return {
            "pairs": len(nonmod),
            "caller_executed": len(ex),
            "supported": len(sup),
            "precision": _share(len(sup), len(ex)),
        }

    policies: dict[str, Record] = {}
    all_amb = {(s.src, c) for s in sites for c in s.candidates if c != s.src}
    for policy in POLICIES:
        added = {(s.src, c) for s in sites if keeps(s, policy) for c in s.candidates if c != s.src}
        added -= sp.resolved
        edges = sp.resolved | added
        dropped = (all_amb - sp.resolved) - added
        policies[policy] = {
            "edges": pair_view(edges),
            "ambiguous_pairs_added": pair_view(added),
            "ambiguous_pairs_dropped": pair_view(dropped),
            "recall_all": {
                "n": len(dyn),
                "hit": len(dyn & edges),
                "recall": _share(len(dyn & edges), len(dyn)),
            },
            "recall_without_implicit_dunders": {
                "n": len(explicit),
                "hit": len(explicit & edges),
                "recall": _share(len(explicit & edges), len(explicit)),
            },
        }

    # site level, for executed sites
    by_caller_names: dict[str, set[str]] = {}
    for caller, callee in dyn:
        by_caller_names.setdefault(caller, set()).add(units[callee].name)
    buckets: dict[str, Counter[str]] = {}

    def tally(bucket: str, outcome: str) -> None:
        buckets.setdefault(bucket, Counter())[outcome] += 1

    for e in graph.edges:
        if e.type != "invoke" or e.status == "ambiguous":
            continue
        executed = site_line_executed(e.site, coverage)
        if not executed or e.src not in dp.executed:
            tally(e.status, "site-not-executed")
            continue
        name = terminal_name(e.target_text)
        if e.status == "resolved":
            if e.src == e.dst:
                tally("resolved", "self-or-nested")
                continue
            ok = (e.src, e.dst) in sp.resolved and (e.src, e.dst) in dyn
            if not ok and units[e.dst].unit_type == "class":
                ok = any(
                    (e.src, x) in dyn
                    for x in units
                    if x.startswith(e.dst + ".") and units[x].name in ("__init__", "__new__")
                )
            tally("resolved", "supported" if ok else "not-observed")
        else:
            tally(
                e.status,
                "in-repo-callee-of-that-name-observed"
                if name in by_caller_names.get(e.src, set())
                else "no-in-repo-callee-of-that-name",
            )
    for s in sites:
        executed = site_line_executed(s.site, coverage)
        # files outside the coverage run (tests): judged at caller level, in separate buckets
        suffix = "" if executed is not None else "|caller-level"
        if executed is False or s.src not in dp.executed:
            tally("ambiguous" + suffix, "site-not-executed")
            continue
        hit = any((s.src, c) in dyn for c in s.candidates)
        outcome = "candidate-observed" if hit else "no-candidate-observed"
        tally("ambiguous" + suffix, outcome)
        tally(("ambiguous_evidence" if s.evidence else "ambiguous_no_evidence") + suffix, outcome)
        for k in s.evidence:
            tally(f"ambiguous_evidence:{k}{suffix}", outcome)
        tally(("ambiguous_le3" if s.size <= 3 else "ambiguous_gt3") + suffix, outcome)
    site_table = {
        b: {**dict(sorted(c.items())), "n": sum(c.values())} for b, c in sorted(buckets.items())
    }
    return {
        "dynamic_in_repo_pairs": len(dyn),
        "dynamic_pairs_without_implicit_dunders": len(explicit),
        "ambiguous_sites": len(sites),
        "policies": policies,
        "sites": site_table,
        "note": "pair precision counts a pair whose caller executed but whose call was not taken "
        "as unsupported (lower bound); site outcomes use executed lines only",
    }


# --------------------------------------------------------------------------- Jedi


def stratum_of(edge: Edge, site: AmbiguousSite | None) -> str:
    """Stratum of an invoke edge (see :data:`STRATA`)."""
    if edge.status != "ambiguous":
        return edge.status
    assert site is not None
    if site.evidence:
        return "ambiguous_evidence"
    return "ambiguous_le3" if site.size <= 3 else "ambiguous_gt3"


def draw_policy_sites(
    graph: RepoGraph, amb: dict[str, AmbiguousSite], per_repo: int, seed: int, label: str
) -> list[tuple[str, Edge]]:
    """Stratified draw of ``per_repo`` sites (equal quotas; a short stratum's remainder goes to
    the strata of :data:`FILL_ORDER`). Returns (stratum, edge) pairs in a stable order."""
    pools: dict[str, list[Edge]] = {s: [] for s in STRATA}
    for e in sorted(graph.edges, key=Edge.sort_key):
        if e.type != "invoke":
            continue
        pools[stratum_of(e, amb.get(e.site + "|" + e.target_text))].append(e)
    base, extra = divmod(per_repo, len(STRATA))
    quota = {s: base + (1 if i < extra else 0) for i, s in enumerate(STRATA)}
    picked: dict[str, list[Edge]] = {}
    short = 0
    for s in STRATA:
        rng = random.Random(f"{seed}:{label}:{s}")
        take = min(quota[s], len(pools[s]))
        short += quota[s] - take
        picked[s] = rng.sample(pools[s], take)
    for s in FILL_ORDER:
        if short <= 0:
            break
        rest = [e for e in pools[s] if e not in set(picked[s])]
        rng = random.Random(f"{seed}:{label}:{s}:fill")
        more = rng.sample(rest, min(short, len(rest)))
        picked[s] += more
        short -= len(more)
    return [(s, e) for s in STRATA for e in sorted(picked[s], key=Edge.sort_key)]


def jedi_outcome(stratum: str, edge: Edge, units: tuple[str, ...], n_total: int, error: str) -> str:
    """Three-way reading of Jedi's answer for a site of a stratum."""
    if error:
        return "jedi-no-answer"
    j = set(units)
    if not j:
        return "jedi-external-only" if n_total > 0 else "jedi-nothing"
    if stratum == "resolved":
        return "jedi-in-repo-same" if edge.dst in j else "jedi-in-repo-other"
    if stratum.startswith("ambiguous"):
        return (
            "jedi-in-repo-in-set"
            if j <= set(edge.candidates)
            else (
                "jedi-in-repo-overlaps-set"
                if j & set(edge.candidates)
                else "jedi-in-repo-outside-set"
            )
        )
    return "jedi-in-repo"


def jedi_policy_sample(
    repos: dict[str, tuple[str, str]], per_repo: int, seed: int
) -> tuple[list[Record], Record]:
    """Draw, ask Jedi, summarize; ``repos`` maps a label to (checkout directory, repo id)."""
    import jedi

    from ril.parsing.repository_parser import parse_repository

    rows: list[Record] = []
    for label, (root, rid) in sorted(repos.items()):
        parsed = parse_repository(root, rid)
        graph = GraphBuilder(parsed).build()
        amb = {s.site + "|" + s.target_text: s for s in ambiguous_sites(parsed, graph)}
        idx = UnitIndex.build(parsed.units)
        extra = [os.path.join(root, d) for d in ("src",) if os.path.isdir(os.path.join(root, d))]
        project = jedi.Project(path=root, added_sys_path=extra)
        cache: dict[str, tuple[str, ast.AST]] = {}
        for stratum, e in draw_policy_sites(graph, amb, per_repo, seed, label):
            out = jedi_units_for(Site(label, e), root, idx, project, cache)
            s = amb.get(e.site + "|" + e.target_text)
            rows.append(
                {
                    "repo": label,
                    "stratum": stratum,
                    "site": e.site,
                    "status": e.status,
                    "rule": e.derivation,
                    "set_size": len(e.candidates),
                    "evidence": "|".join(s.evidence) if s else "",
                    "jedi_in_repo_units": len(out.units),
                    "jedi_total": out.n_total,
                    "outcome": jedi_outcome(stratum, e, out.units, out.n_total, out.error),
                }
            )
    return rows, summarize_jedi(rows, jedi.__version__, seed)


def summarize_jedi(rows: list[Record], version: str, seed: int) -> Record:
    """Outcome counts per stratum (pooled and per repository) and the bucket readings."""

    def table(sel: list[Record]) -> Record:
        out: Record = {}
        for s in STRATA:
            c = Counter(r["outcome"] for r in sel if r["stratum"] == s)
            n = sum(c.values())
            answered = n - c.get("jedi-no-answer", 0) - c.get("jedi-nothing", 0)
            in_repo = sum(v for k, v in c.items() if k.startswith("jedi-in-repo"))
            row: Record = {"n": n, "answered": answered, **dict(sorted(c.items()))}
            ext = c.get("jedi-external-only", 0)
            if s == "resolved":
                same = c.get("jedi-in-repo-same", 0)
                row["agree_share_of_answered"] = _share(same, answered)
                row["agree_ci95"] = wilson(same, answered)
            elif s in ("external", "unresolved", "ambiguous_evidence"):
                # read as "not in the repository" by the bucket (or by the re-bucketing rule)
                row["jedi_external_share_of_answered"] = _share(ext, answered)
                row["jedi_external_ci95"] = wilson(ext, answered)
                row["jedi_in_repo_share_of_answered"] = _share(in_repo, answered)
            else:
                in_set = c.get("jedi-in-repo-in-set", 0) + c.get("jedi-in-repo-overlaps-set", 0)
                row["jedi_in_set_share_of_answered"] = _share(in_set, answered)
                row["jedi_in_set_ci95"] = wilson(in_set, answered)
                row["jedi_external_share_of_answered"] = _share(ext, answered)
            out[s] = row
        return out

    by_kind: Record = {}
    for kind in ("literal", "kwargs", "annotated_external", "fixture_param"):
        sel = [r for r in rows if kind in str(r["evidence"]).split("|")]
        c = Counter(r["outcome"] for r in sel)
        answered = len(sel) - c.get("jedi-no-answer", 0) - c.get("jedi-nothing", 0)
        by_kind[kind] = {
            "n": len(sel),
            "answered": answered,
            "jedi_external": c.get("jedi-external-only", 0),
            "jedi_external_ci95": wilson(c.get("jedi-external-only", 0), answered),
        }
    summary: Record = {
        "evidence_kinds": by_kind,
        "jedi_version": version,
        "seed": seed,
        "sites": len(rows),
        "pooled": table(rows),
    }
    for repo in sorted({r["repo"] for r in rows}):
        summary[f"repo:{repo}"] = table([r for r in rows if r["repo"] == repo])
    return summary
