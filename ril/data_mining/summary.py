"""Yield, selection and parse-failure tables of a mining run (stage M2 tables, no new data).

Implements ``docs/experiments/B.md`` E-MINE-PILOT. Everything here is computed from the stored
listings, the state log and the per-instance metadata of one run root; a table built from a run
made on recorded or synthetic responses is not a measurement and is labelled by the caller.

Kept compatible with Python 3.10 (the cluster's compute nodes).
"""

from __future__ import annotations

import hashlib
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


BOOTSTRAP_DRAWS = 2000
PROPERTIES: tuple[str, ...] = (
    "positives",
    "py_files_changed",
    "hunk_lines_touched",
    "corpus_units",
)


def _values(m: Mapping[str, Any]) -> dict[str, float]:
    c = m["counters"]
    return {
        "positives": float(c["positives"]),
        "py_files_changed": float(c["py_files_changed"]),
        "hunk_lines_touched": float(sum(p["hunk_lines_touched"] for p in m["positives"])),
        "corpus_units": float(c["corpus_units"]),
    }


def median_difference_interval(
    kept: Mapping[str, Sequence[float]], dropped: Mapping[str, Sequence[float]], seed: int = 0
) -> dict[str, Any]:
    """Median(kept) minus median(dropped) with a repository-clustered bootstrap interval.

    ``kept`` and ``dropped`` map a repository to the values of its mined pull requests. Each draw
    resamples the repositories (with replacement, from the SHA-256 stream keyed by ``seed``) and
    recomputes both medians from the pooled pull requests of the drawn repositories; a draw in
    which either group is empty is skipped and counted.
    """
    repos = sorted(set(kept) | set(dropped))
    k_all = [v for r in kept for v in kept[r]]
    d_all = [v for r in dropped for v in dropped[r]]
    out: dict[str, Any] = {"kept_n": len(k_all), "dropped_n": len(d_all)}
    if not k_all or not d_all:
        out.update(difference=None, interval=None, excludes_zero=None, draws_used=0)
        return out
    diffs: list[float] = []
    for b in range(BOOTSTRAP_DRAWS):
        kv: list[float] = []
        dv: list[float] = []
        for i in range(len(repos)):
            digest = hashlib.sha256(f"{seed}:{b}:{i}".encode()).digest()
            repo = repos[int.from_bytes(digest[:8], "big") % len(repos)]
            kv.extend(kept.get(repo, ()))
            dv.extend(dropped.get(repo, ()))
        if kv and dv:
            diffs.append(statistics.median(kv) - statistics.median(dv))
    diffs.sort()
    point = statistics.median(k_all) - statistics.median(d_all)
    out.update(kept_median=statistics.median(k_all), dropped_median=statistics.median(d_all))
    out["difference"] = point
    out["draws_used"] = len(diffs)
    if len(diffs) < 100:
        out.update(interval=None, excludes_zero=None)
        return out
    lo, hi = diffs[int(0.025 * len(diffs))], diffs[int(0.975 * len(diffs)) - 1]
    out["interval"] = [lo, hi]
    out["excludes_zero"] = bool(lo > 0 or hi < 0)
    return out


def selection_differences(
    kept: Sequence[Mapping[str, Any]], dropped: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Kept against dropped mined pull requests: median difference per property with intervals."""

    def by_repo(metas: Sequence[Mapping[str, Any]], prop: str) -> dict[str, list[float]]:
        out: dict[str, list[float]] = {}
        for m in metas:
            out.setdefault(str(m["repo"]), []).append(_values(m)[prop])
        return out

    return {
        prop: median_difference_interval(by_repo(kept, prop), by_repo(dropped, prop))
        for prop in PROPERTIES
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
        "differences": selection_differences(kept, dropped),
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
