"""Tables for the X1 structure measurements (class-unit source, ambiguous-site policy). Exploratory.

Reads the per-variant evaluation directories written by ``ril.evaluation.x1_eval`` (metric
matrices only) and the X1 extras (sizes, times, ambiguous-site counts), and writes:

* ``<prefix>_cells.csv``: every graph cell of every variant against its own BM25 ranking and the
  two chance controls (``ril.analysis.e3_tables.compare``);
* ``<prefix>_variants.csv``: each variant against the reference variant, key by key (BM25 alone
  and each graph cell), paired over the same queries;
* ``<prefix>_selection.json``: the result of the selection rule stated in the configuration.

Averages: the mean over queries with two 95% intervals (decision D17 and the pushback beside it):
``cluster`` resamples whole repositories (D17's primary convention; with five or six
repositories it is coarse) and ``micro`` resamples queries. Values are percentages, differences
percentage points; 2,000 draws with a fixed seed, one set of resamples per group and level, so the
comparisons inside a group are paired.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from typing import Any

import numpy as np

from ril.analysis.e1_tables import write_csv
from ril.analysis.e3_tables import (
    COLUMN,
    METRICS,
    Boot,
    EvalTable,
    compare,
    graph_cells,
    load_eval_dir,
)
from ril.evaluation.e3_prepare import READINGS, read_cache

Record = dict[str, Any]
AVERAGES: tuple[str, ...] = ("micro", "cluster")


def load_variants(out_dir: str, names: Iterable[str]) -> dict[str, EvalTable]:
    """One table per variant; all must hold the same queries in the same order and the same keys."""
    tabs = {n: load_eval_dir(os.path.join(out_dir, n)) for n in names}
    ref: EvalTable | None = None
    for name, tab in tabs.items():
        if ref is None:
            ref = tab
            continue
        same_rows = [(r["instance"], r["level"]) for r in tab.rows] == [
            (r["instance"], r["level"]) for r in ref.rows
        ]
        if not same_rows or tab.keys != ref.keys:
            raise ValueError(f"variant {name}: queries or keys differ from the first variant")
    return tabs


def _fmt(x: float) -> float:
    return round(float(x), 3)


def variant_diffs(
    tabs: dict[str, EvalTable],
    reference: str,
    keys: list[str],
    mask: np.ndarray[Any, Any],
    group: str,
    level: str,
    seed: int,
    averages: tuple[str, ...] = AVERAGES,
) -> list[Record]:
    """Paired difference (variant minus reference) of each key, per gold reading and metric."""
    ref = tabs[reference]
    level_mask = mask & np.asarray([r["level"] == level for r in ref.rows])
    base_i = ref.index["bm25"]
    out: list[Record] = []
    for reading in READINGS:
        valid = ~np.isnan(ref.metrics[:, base_i, COLUMN[(reading, "ndcg10")]])
        sel = np.flatnonzero(level_mask & valid)
        if len(sel) == 0:
            continue
        repos = [ref.rows[i]["repo"] for i in sel]
        boot = Boot(repos, seed)
        cols: list[np.ndarray[Any, Any]] = []
        meta: list[tuple[str, str, str, str]] = []
        for name, tab in tabs.items():
            for key in keys:
                for metric in METRICS:
                    j = COLUMN[(reading, metric)]
                    x = tab.metrics[sel, tab.index[key], j]
                    cols.append(100 * x)
                    meta.append((name, key, metric, "value"))
                    if name != reference:
                        cols.append(100 * (x - ref.metrics[sel, ref.index[key], j]))
                        meta.append((name, key, metric, "diff"))
        d = np.stack(cols, axis=1)
        for avg in averages:
            mean, lo, hi = boot.summarize(d, avg)
            rows: dict[tuple[str, str, str], Record] = {}
            for i, (name, key, metric, what) in enumerate(meta):
                row = rows.setdefault(
                    (name, key, metric),
                    {
                        "group": group,
                        "level": level,
                        "average": avg,
                        "queries": len(sel),
                        "repos": len(set(repos)),
                        "gold_reading": reading,
                        "metric": metric,
                        "variant": name,
                        "reference": reference,
                        "key": key,
                    },
                )
                if what == "value":
                    row["value"] = _fmt(mean[i])
                else:
                    row["d_ref"], row["d_ref_lo"], row["d_ref_hi"] = (
                        _fmt(mean[i]),
                        _fmt(lo[i]),
                        _fmt(hi[i]),
                    )
            out.extend(rows.values())
    return out


def select_variant(rows: list[Record], rule: Record) -> Record:
    """Apply a stated selection rule to ``variant_diffs`` rows (pooled dev group).

    Rule: among ``candidates``, the variant with the largest mean of (L2 nDCG@10 difference, L3
    Recall@100 difference) against the reference for ``key`` and ``reading`` (``micro``) replaces
    the reference only if that mean is positive, at least one of the two micro intervals lies
    above zero and neither lies below zero; otherwise the reference stays.
    """

    def get(variant: str, level: str, metric: str) -> Record:
        hits = [
            r
            for r in rows
            if r["variant"] == variant
            and r["level"] == level
            and r["metric"] == metric
            and r["key"] == rule["key"]
            and r["gold_reading"] == rule["reading"]
            and r["average"] == "micro"
            and r["group"] == rule.get("group", "dev_all")
        ]
        if len(hits) != 1:
            raise ValueError(f"selection: {len(hits)} rows for {variant} {level} {metric}")
        return hits[0]

    scored: list[tuple[float, str, Record]] = []
    for cand in rule["candidates"]:
        l2, l3 = get(cand, "L2", "ndcg10"), get(cand, "L3", "recall100")
        combined = (l2["d_ref"] + l3["d_ref"]) / 2
        above = l2["d_ref_lo"] > 0 or l3["d_ref_lo"] > 0
        below = l2["d_ref_hi"] < 0 or l3["d_ref_hi"] < 0
        scored.append(
            (
                combined,
                cand,
                {
                    "combined": _fmt(combined),
                    "L2_ndcg10": [l2["d_ref"], l2["d_ref_lo"], l2["d_ref_hi"]],
                    "L3_recall100": [l3["d_ref"], l3["d_ref_lo"], l3["d_ref_hi"]],
                    "eligible": bool(combined > 0 and above and not below),
                },
            )
        )
    scored.sort(key=lambda t: (-t[0], t[1]))
    eligible = [c for _, c, info in scored if info["eligible"]]
    return {
        "rule": rule,
        "candidates": {c: info for _, c, info in scored},
        "winner": eligible[0] if eligible else rule["reference"],
    }


def size_rows(x1_cache: str, roles: tuple[str, ...]) -> list[Record]:
    """Per repository and form: units, class units, index size and build time (medians, sums)."""
    per: dict[str, list[Record]] = {}
    for name in sorted(os.listdir(x1_cache)):
        if not name.endswith(".npz"):
            continue
        _, meta = read_cache(os.path.join(x1_cache, name))
        if meta["role"] in roles:
            per.setdefault(meta["repo_id"], []).append(meta)
    out: list[Record] = []
    forms = ("full", "header", "header_sigs")
    for repo in [*sorted(per), "all"]:
        metas = [m for ms in per.values() for m in ms] if repo == "all" else per[repo]
        for form in forms:
            sizes = [m["index_size"][form] for m in metas]
            build = [
                m["seconds"][f"parse_{form}"] + m["seconds"][f"bm25_index_{form}"] for m in metas
            ]
            out.append(
                {
                    "repo": repo,
                    "form": form,
                    "instances": len(metas),
                    "units_median": float(np.median([m["units"] for m in metas])),
                    "class_units_median": float(np.median([m["class_units"] for m in metas])),
                    "source_chars_median": float(
                        np.median([m["source_chars"][form] for m in metas])
                    ),
                    "tokens_median": float(np.median([s["tokens"] for s in sizes])),
                    "postings_median": float(np.median([s["postings"] for s in sizes])),
                    "index_array_bytes_median": float(np.median([s["array_bytes"] for s in sizes])),
                    "parse_s_median": _fmt(
                        np.median([m["seconds"][f"parse_{form}"] for m in metas])
                    ),
                    "bm25_index_s_median": _fmt(
                        np.median([m["seconds"][f"bm25_index_{form}"] for m in metas])
                    ),
                    "build_s_p50": _fmt(np.percentile(build, 50)),
                    "build_s_p95": _fmt(np.percentile(build, 95)),
                    "build_s_sum": _fmt(sum(build)),
                }
            )
    return out


def ambiguity_rows(x1_cache: str, roles: tuple[str, ...]) -> list[Record]:
    """Per repository: ambiguous sites, evidence kinds and set sizes (medians over snapshots)."""
    per: dict[str, list[Record]] = {}
    for name in sorted(os.listdir(x1_cache)):
        if not name.endswith(".npz"):
            continue
        _, meta = read_cache(os.path.join(x1_cache, name))
        if meta["role"] in roles:
            per.setdefault(meta["repo_id"], []).append(meta)
    out: list[Record] = []
    fields = (
        "sites",
        "any_evidence",
        "literal",
        "kwargs",
        "annotated_external",
        "fixture_param",
        "size_le_3",
        "size_gt_3",
    )
    for repo in sorted(per):
        metas = per[repo]
        row: Record = {"repo": repo, "snapshots": len(metas)}
        for f in fields:
            row[f"{f}_median"] = float(np.median([m["ambiguous"].get(f, 0) for m in metas]))
        row["resolved_invoke_pairs_median"] = float(
            np.median([m["resolved_invoke_pairs"] for m in metas])
        )
        st = [m["invoke_status"] for m in metas]
        for s in ("resolved", "ambiguous", "unresolved", "external"):
            row[f"invoke_{s}_median"] = float(np.median([x.get(s, 0) for x in st]))
        out.append(row)
    return out


def write_x1_tables(cfg: Record, out_dir: str, prefix: str, seed: int = 0) -> Record:
    """Write the tables of one evaluation configuration; return a short summary."""
    names = sorted(cfg["variants"])
    tabs = load_variants(out_dir, names)
    reference = str(cfg["reference"])
    ref = tabs[reference]
    roles = sorted({r["role"] for r in ref.rows})
    masks: dict[str, np.ndarray[Any, Any]] = {f"{role}_all": ref.mask(role=role) for role in roles}
    repo_masks = {
        f"repo:{repo}": ref.mask(repo=repo) for repo in sorted({r["repo"] for r in ref.rows})
    }
    cells = graph_cells(ref)
    keys = ["bm25", *[c.key for c in cells]]
    cell_rows: list[Record] = []
    diff_rows: list[Record] = []
    for group, mask in {**masks, **repo_masks}.items():
        avgs = AVERAGES if not group.startswith("repo:") else ("micro",)
        for level in ("L2", "L3"):
            for name, tab in tabs.items():
                for r in compare(tab, mask, group, level, cells, seed, averages=avgs):
                    r["variant"] = name
                    cell_rows.append(r)
            diff_rows += variant_diffs(tabs, reference, keys, mask, group, level, seed, avgs)
    write_csv(f"{prefix}_cells.csv", cell_rows)
    write_csv(f"{prefix}_variants.csv", diff_rows)
    summary: Record = {
        "queries": len(ref.rows),
        "variants": names,
        "cells_rows": len(cell_rows),
        "variant_rows": len(diff_rows),
    }
    selections = {
        name: select_variant(diff_rows, rule) for name, rule in cfg.get("selection", {}).items()
    }
    if selections:
        summary["selection"] = selections
        with open(f"{prefix}_selection.json", "w", encoding="utf-8") as handle:
            json.dump(selections, handle, indent=1, sort_keys=True)
            handle.write("\n")
    return summary
