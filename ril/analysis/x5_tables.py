"""Tables of the edited-function follow-up of the contamination scan (E-CONTAM-EDITED).

Exploratory; not part of the frozen evaluation (ADR-005 addendum, decision D23). Joins the hashes
of the functions a reference patch edits (``ril.training.contamination_edited``) with the matched
syntax-tree hashes of the full scan and with each instance's set of base-commit function hashes, at
the size floors fixed in ``configs/experiments/x4_contam_scan.yaml`` (20, 50, 100 nodes).

Comparison: the share of distinct *edited* functions that occur in the corpus against the share of
(i) all other base-commit functions above the floor and (ii) the unedited functions of the same
patched files, distinct within a repository, pooled over repositories, difference with a
repository-clustered bootstrap interval (D17). The edited functions are read before the patch
(base commit) and, for changed ones, after it. A hit means a function with that exact syntax tree
occurs as the ``document`` of a corpus row; it is not evidence that any model was trained on a
pair that contains it.
"""

from __future__ import annotations

import random
from collections.abc import Collection, Mapping
from typing import Any

from ril.analysis.x4_tables import wilson

Record = dict[str, Any]

BUCKETS = ((20, 50), (50, 100), (100, 10**9))


def _share(k: int, n: int) -> float | None:
    return None if n == 0 else round(k / n, 6)


def _iv(k: int, n: int) -> list[float] | None:
    if n == 0:
        return None
    lo, hi = wilson(k, n)
    return [round(lo, 6), round(hi, 6)]


def _sets(
    edited: Mapping[str, Record],
    inst: Mapping[str, tuple[str, Mapping[str, int]]],
    floor: int,
    hi: int = 10**9,
) -> dict[str, dict[str, set[str]]]:
    """Per repository the distinct hash sets of each group, all with nodes in ``[floor, hi)``.

    ``pre``: edited functions as they are at the base commit; ``post``: the post-patch version of
    each changed edited function; ``other``: base-commit functions that no patch of that repository
    edits; ``file``: unedited functions of the patched files. Distinct within a repository, because
    a function that survives many base commits would otherwise be counted once per instance and a
    patch-edited function once (pair weighting makes the unedited share look higher).
    """
    out: dict[str, dict[str, set[str]]] = {}
    all_edit: dict[str, set[str]] = {}
    for iid, (repo, _) in inst.items():
        rec = edited.get(iid)
        if rec is not None:
            all_edit.setdefault(repo, set()).update(
                e["pre_hash"] for e in rec["edited"] if e["pre_hash"] is not None
            )
    for iid, (repo, hashes) in inst.items():
        rec = edited.get(iid)
        if rec is None:
            continue
        g = out.setdefault(repo, {"pre": set(), "post": set(), "other": set(), "file": set()})
        for e in rec["edited"]:
            if e["pre_hash"] is not None and floor <= e["pre_nodes"] < hi:
                g["pre"].add(e["pre_hash"])
            if (
                e["post_known"]
                and e["post_hash"] is not None
                and e["post_hash"] != e["pre_hash"]
                and floor <= (e["post_nodes"] or 0) < hi
            ):
                g["post"].add(e["post_hash"])
        g["other"].update(
            h for h, n in hashes.items() if floor <= n < hi and h not in all_edit[repo]
        )
        g["file"].update(
            h for h, n in rec["same_file_unedited"] if floor <= n < hi and h not in all_edit[repo]
        )
    return out


def _counts(
    sets: Mapping[str, Mapping[str, set[str]]], docs: Collection[str], a: str, b: str
) -> list[list[int]]:
    rows = []
    for repo in sorted(sets):
        x, y = sets[repo][a], sets[repo][b]
        rows.append(
            [sum(1 for h in x if h in docs), len(x), sum(1 for h in y if h in docs), len(y)]
        )
    return rows


def _diff(rows: list[list[int]]) -> float | None:
    ke = sum(r[0] for r in rows)
    ne = sum(r[1] for r in rows)
    ko = sum(r[2] for r in rows)
    no = sum(r[3] for r in rows)
    if ne == 0 or no == 0:
        return None
    return ke / ne - ko / no


def clustered_diff(rows: list[list[int]], draws: int = 2000, seed: int = 0) -> Record:
    """Group A share minus group B share, pooled; interval resamples repositories.

    ``rows`` holds ``[A matched, A n, B matched, B n]`` per repository; percentile interval over
    ``draws`` resamples of the repositories with replacement (decision D17).
    """
    point = _diff(rows)
    rng = random.Random(seed)
    vals: list[float] = []
    for _ in range(draws):
        d = _diff([rows[rng.randrange(len(rows))] for _ in rows]) if rows else None
        if d is not None:
            vals.append(d)
    vals.sort()
    ci = None
    if vals:
        ci = [
            round(vals[int(0.025 * (len(vals) - 1))], 6),
            round(vals[int(0.975 * (len(vals) - 1))], 6),
        ]
    ke, ne = sum(r[0] for r in rows), sum(r[1] for r in rows)
    ko, no = sum(r[2] for r in rows), sum(r[3] for r in rows)
    return {
        "a_matched": ke,
        "a_n": ne,
        "a_share": _share(ke, ne),
        "a_ci95_descriptive": _iv(ke, ne),
        "b_matched": ko,
        "b_n": no,
        "b_share": _share(ko, no),
        "b_ci95_descriptive": _iv(ko, no),
        "difference_a_minus_b": None if point is None else round(point, 6),
        "difference_ci95_repo_clustered": ci,
        "repositories": len(rows),
        "bootstrap_draws": len(vals),
        "seed": seed,
    }


def floor_table(
    edited: Mapping[str, Record],
    inst: Mapping[str, tuple[str, Mapping[str, int]]],
    docs: Collection[str],
    floor: int,
) -> Record:
    """All counts of one floor (denominators stated; see the module docstring)."""
    sets = _sets(edited, inst, floor)
    comparisons = {
        "pre_vs_other": _counts(sets, docs, "pre", "other"),
        "pre_vs_same_file": _counts(sets, docs, "pre", "file"),
        "post_vs_other": _counts(sets, docs, "post", "other"),
        "post_vs_same_file": _counts(sets, docs, "post", "file"),
    }
    all_h = {h for _, hs in inst.values() for h, n in hs.items() if n >= floor}

    inst_with_edit = inst_with_hit = 0
    for iid in inst:
        rec = edited.get(iid)
        if rec is None:
            continue
        e = {
            e["pre_hash"]
            for e in rec["edited"]
            if e["pre_hash"] is not None and e["pre_nodes"] >= floor
        }
        if e:
            inst_with_edit += 1
            inst_with_hit += any(h in docs for h in e)

    # changed edited functions (distinct per instance): pre and post both looked up
    both = [0, 0, 0, 0]  # pre&post, pre only, post only, neither (pre nodes >= floor)
    changed_n = post_gone = 0
    for iid, rec in edited.items():
        if iid not in inst:
            continue
        seen: set[tuple[str | None, str | None]] = set()
        for e in rec["edited"]:
            if e["pre_hash"] is None or e["pre_nodes"] < floor or not e["post_known"]:
                continue
            if e["post_hash"] == e["pre_hash"] or (e["pre_hash"], e["post_hash"]) in seen:
                continue
            seen.add((e["pre_hash"], e["post_hash"]))
            changed_n += 1
            if e["post_hash"] is None:
                post_gone += 1
                continue
            pre = e["pre_hash"] in docs
            post = e["post_hash"] in docs
            both[0 if pre and post else 1 if pre else 2 if post else 3] += 1

    added = {
        (iid, a["hash"])
        for iid, rec in edited.items()
        if iid in inst
        for a in rec["added"]
        if a["hash"] is not None and a["nodes"] >= floor
    }

    strata = []
    for lo, hi in BUCKETS:
        if hi <= floor:
            continue
        lo = max(lo, floor)
        b = _sets(edited, inst, lo, hi)
        strata.append(
            {
                "nodes": [lo, None if hi >= 10**9 else hi - 1],
                **clustered_diff(_counts(b, docs, "pre", "other")),
            }
        )

    return {
        "floor_nodes": floor,
        "instances": len(inst),
        "instances_with_edited_function_above_floor": inst_with_edit,
        "instances_with_a_matched_edited_function": inst_with_hit,
        "instances_with_a_matched_edited_function_ci95": _iv(inst_with_hit, inst_with_edit),
        "all_base_commit_functions_matched": sum(1 for h in all_h if h in docs),
        "all_base_commit_functions_n": len(all_h),
        "all_base_commit_functions_share": _share(sum(1 for h in all_h if h in docs), len(all_h)),
        **{name: clustered_diff(rows) for name, rows in comparisons.items()},
        "changed_pre_and_post_looked_up": changed_n - post_gone,
        "changed_pre_and_post_match": both[0],
        "changed_pre_only_match": both[1],
        "changed_post_only_match": both[2],
        "changed_neither_match": both[3],
        "changed_post_function_removed": post_gone,
        "added_functions_n": len(added),
        "added_functions_matched": sum(1 for _, h in added if h in docs),
        "by_size_pre_vs_other": strata,
        "by_repo": {
            repo: {
                "pre_matched": sum(1 for h in g["pre"] if h in docs),
                "pre_n": len(g["pre"]),
                "other_matched": sum(1 for h in g["other"] if h in docs),
                "other_n": len(g["other"]),
                "file_matched": sum(1 for h in g["file"] if h in docs),
                "file_n": len(g["file"]),
                "post_matched": sum(1 for h in g["post"] if h in docs),
                "post_n": len(g["post"]),
            }
            for repo, g in sorted(sets.items())
        },
    }


def diagnostics(edited: Mapping[str, Record]) -> Record:
    """Completeness of the edited-function extraction."""
    ne = [len(r["edited"]) for r in edited.values()]
    return {
        "instances": len(edited),
        "patch_applied": sum(1 for r in edited.values() if r["patch_applied"]),
        "patch_not_applied": sorted(i for i, r in edited.items() if not r["patch_applied"]),
        "unparseable_pre_files": sum(r["unparseable_pre"] for r in edited.values()),
        "unparseable_post_files": sum(r["unparseable_post"] for r in edited.values()),
        "instances_without_python_file_edit": sum(
            1 for r in edited.values() if r["patched_py_files"] == 0
        ),
        "instances_without_edited_function": sum(1 for n in ne if n == 0),
        "edited_functions": sum(ne),
        "edited_functions_without_ast_hash": sum(
            1 for r in edited.values() for e in r["edited"] if e["pre_hash"] is None
        ),
        "added_functions": sum(len(r["added"]) for r in edited.values()),
    }


COMPARISONS = ("pre_vs_other", "pre_vs_same_file", "post_vs_other", "post_vs_same_file")


def summary_rows(result: Mapping[str, Any]) -> list[Record]:
    """One row per floor and comparison from the output of the join (for the CSV table)."""
    rows: list[Record] = []
    for floor, tab in result["per_floor"].items():
        for name in COMPARISONS:
            c = tab[name]
            rows.append(
                {
                    "floor_nodes": int(floor),
                    "comparison": name,
                    "a_matched": c["a_matched"],
                    "a_n": c["a_n"],
                    "a_share": c["a_share"],
                    "a_ci95_descriptive": c["a_ci95_descriptive"],
                    "b_matched": c["b_matched"],
                    "b_n": c["b_n"],
                    "b_share": c["b_share"],
                    "difference_a_minus_b": c["difference_a_minus_b"],
                    "difference_ci95_repo_clustered": c["difference_ci95_repo_clustered"],
                    "repositories": c["repositories"],
                }
            )
    return rows
