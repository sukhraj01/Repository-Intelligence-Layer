"""Yield, selection and parse-failure tables of a mining run (stage M2 tables, no new data).

Implements ``docs/experiments/B.md`` E-MINE-PILOT. Everything here is computed from the stored
listings, the state log and the per-instance metadata of one run root; a table built from a run
made on recorded or synthetic responses is not a measurement and is labelled by the caller.

Kept compatible with Python 3.10 (the cluster's compute nodes).
"""

from __future__ import annotations

import json
import os
import statistics
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from ril.data_mining.links import PullRequest, multiplicity
from ril.data_mining.pack import list_dirs
from ril.data_mining.population import Population, selection_rows, selection_summary
from ril.data_mining.store import MiningStore, stage_counts


def load_metas(store: MiningStore) -> list[dict[str, Any]]:
    """The ``pr_meta.json`` of every mined instance, in directory order."""
    out: list[dict[str, Any]] = []
    for name in list_dirs(store.root):
        with open(os.path.join(store.pr_path(name), "pr_meta.json"), encoding="utf-8") as handle:
            out.append(json.load(handle))
    return out


def _desc(values: Sequence[float]) -> dict[str, float]:
    if not values:
        return {"n": 0}
    s = sorted(values)
    return {
        "n": len(s),
        "mean": round(statistics.fmean(s), 3),
        "median": float(statistics.median(s)),
        "p90": float(s[min(len(s) - 1, int(0.9 * len(s)))]),
        "max": float(s[-1]),
    }


def group_stats(metas: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Positives per PR, changed Python files and hunk lines of a group of mined instances."""
    pos = [float(m["counters"]["positives"]) for m in metas]
    files = [float(m["counters"]["py_files_changed"]) for m in metas]
    lines = [float(sum(p["hunk_lines_touched"] for p in m["positives"])) for m in metas]
    corpus = [float(m["counters"]["corpus_units"]) for m in metas]
    return {
        "prs": len(metas),
        "positives_per_pr": _desc(pos),
        "py_files_changed": _desc(files),
        "hunk_lines_touched": _desc(lines),
        "corpus_units": _desc(corpus),
    }


def selection_analysis(
    listings: Mapping[str, Sequence[PullRequest]],
    population: Population,
    metas: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Share of each repository's linked PRs that the published pool kept, and kept vs dropped.

    Repositories are listed by their linked pull request numbers; the pool's kept numbers come
    from the population. The kept and dropped groups are the *mined* instances (a sample of the
    linked pull requests), split by membership in the published pool.
    """
    linked = {r: [p.number for p in prs if p.issues] for r, prs in listings.items()}
    rows = selection_rows(linked, population.published)
    kept: list[Mapping[str, Any]] = []
    dropped: list[Mapping[str, Any]] = []
    for m in metas:
        in_pool = int(m["pr"]) in population.published.get(str(m["repo"]), frozenset())
        (kept if in_pool else dropped).append(m)
    return {
        "summary": selection_summary(rows),
        "per_repo": [
            {
                "repo": r.repo,
                "linked_prs": r.linked_prs,
                "kept_by_pool": r.kept_by_pool,
                "kept_share": round(r.kept_share, 4),
                "published_not_linked": r.published_in_selection,
            }
            for r in rows
        ],
        "kept_by_pool": group_stats(kept),
        "dropped_by_pool": group_stats(dropped),
    }


def parse_failures(
    state: Mapping[str, Mapping[str, Any]], metas: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Share of attempted PRs quarantined for an unparseable changed file, by cause (D64)."""
    attempted = len(state)
    changed = Counter(
        str(row["reason"]).split(":", 1)[1]
        for row in state.values()
        if str(row["reason"]).startswith("changed_file_unparseable:")
    )
    corpus: Counter[str] = Counter()
    for m in metas:
        corpus.update(m.get("parse_failure_causes") or {})
    return {
        "attempted": attempted,
        "quarantined_unparseable_changed_file": sum(changed.values()),
        "share_of_attempted": round(sum(changed.values()) / attempted, 4) if attempted else 0.0,
        "by_cause_changed_file": dict(sorted(changed.items())),
        "unparsed_corpus_files_by_cause_in_mined": dict(sorted(corpus.items())),
    }


def link_quality(
    listings: Mapping[str, Sequence[PullRequest]], metas: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Multiplicity of (issue, PR) pairs, regex recall beyond the closing references (D61) and
    the share of issues edited after the pull request was created (D62)."""
    prs = [p for lst in listings.values() for p in lst]
    linked = [p for p in prs if p.issues]
    regex_only = sum(
        1 for p in prs if set(p.regex_refs) - {i.number for i in p.issues if i.repo == p.repo}
    )
    pairs = [pair for m in metas for pair in m["pairs"]]
    edited = sum(1 for pair in pairs if pair["edited_after_pr_created"])
    return {
        "multiplicity": multiplicity(linked),
        "prs_with_regex_ref_not_in_closing_refs": regex_only,
        "prs_with_closing_refs_cut_at_limit": sum(
            1 for p in linked if p.closing_total > len(p.issues)
        ),
        "mined_pairs": len(pairs),
        "issue_edited_after_pr_created": edited,
        "issue_edited_share": round(edited / len(pairs), 4) if pairs else 0.0,
    }


def yield_table(store: MiningStore, listings: Mapping[str, list[PullRequest]]) -> dict[str, Any]:
    """Per-stage counts (repositories, PRs, linked, attempted, mined, positives per PR)."""
    state = store.load_state()
    counts = stage_counts(listings, state)
    metas = load_metas(store)
    counts["prs_mined"] = len(metas)
    counts["positives_total"] = sum(int(m["counters"]["positives"]) for m in metas)
    counts["added_function_defs_total"] = sum(
        int(m["counters"]["added_function_defs"]) for m in metas
    )
    return counts


def build_summary(
    store: MiningStore,
    listings: Mapping[str, list[PullRequest]],
    population: Population,
) -> dict[str, Any]:
    """All tables of one run root as one JSON-ready document."""
    state = store.load_state()
    metas = load_metas(store)
    return {
        "yield": yield_table(store, listings),
        "population": dict(population.counts),
        "selection": selection_analysis(listings, population, metas),
        "parse_failures": parse_failures(state, metas),
        "links": link_quality(listings, metas),
        "mined": group_stats(metas),
    }
