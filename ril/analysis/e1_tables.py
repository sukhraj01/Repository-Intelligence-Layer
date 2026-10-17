"""Tables for pilot E1 (BM25 reproduction and granularity) and E2 (label noise), exploratory.

Reads the run records written by ``ril.evaluation.e1_run`` (ranks, ids, paths and lines only) and
turns them into counts, means with percentile-bootstrap intervals over queries, paired
differences, and a "does a conclusion flip" table. Nothing here touches chunk or issue text.

Conventions
-----------
* A *reading* of the chunk-level ranking is ``protocol`` (cut to the first 10,000 documents of the
  whole-folder ranking, then restricted to the query's candidates, as the released toolkit does) or
  ``filter_first`` (only the query's candidates are ranked).
* A *label set* is a rule that keeps or removes positives: ``base`` (all), ``clean_content``
  (no import-only, comment-only or documentation-file positive), ``edit_overlap`` (only positives
  whose lines overlap a line the reference patch edits; at unit level only gold units that overlap
  an edited line), ``clean_both`` (both rules).
* A *treatment* says what happens to a removed positive in the ranked list: ``neg`` (it stays and
  counts as not relevant) or ``ignored`` (it leaves the list; ranks below it move up).
* Queries whose label set becomes empty are dropped from that label set, and counted.
"""

from __future__ import annotations

import csv
import glob
import json
import os
from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from typing import Any

import numpy as np

from ril.evaluation.metrics import (
    Rank,
    drop_from_ranking,
    first_rank,
    mean_ci,
    ndcg_at_k,
    paired_diff_ci,
    recall_at_k,
)

Record = dict[str, Any]
READINGS = ("protocol", "filter_first")
LABEL_SETS = ("base", "clean_content", "edit_overlap", "clean_both")
TREATMENTS = ("neg", "ignored")
VARIANTS = ("with_module", "without_module")
GOLD_READINGS = ("units", "units_all")
NOISE = ("import_only", "comment_only", "docs_file")
PAPER_REFERENCE = {  # paper_reported, Table 17 (nDCG@10, Recall@100 in percent)
    ("verified12", "L2"): (11.9, 46.7),
    ("verified12", "L3"): (22.2, 33.9),
}
CARD_L2_AVERAGE = (13.0, 38.8)  # paper_reported, all L2 queries
SIX = (
    "astropy__astropy",
    "matplotlib__matplotlib",
    "mwaskom__seaborn",
    "pallets__flask",
    "psf__requests",
    "pydata__xarray",
)
SAMPLE3 = ("mwaskom__seaborn", "pallets__flask", "psf__requests")


# --------------------------------------------------------------------------- loading


def _read_all(pattern: str) -> list[Record]:
    out: list[Record] = []
    for path in sorted(glob.glob(pattern)):
        with open(path, encoding="utf-8") as handle:
            doc = json.load(handle)
        if isinstance(doc, dict):
            out.append(doc)
    return out


def load_chunk_runs(out_dir: str) -> list[Record]:
    """Chunk-level run documents (one per folder and level)."""
    return _read_all(os.path.join(out_dir, "chunk", "*.json"))


def load_unit_runs(out_dir: str) -> list[Record]:
    """Unit-level instance documents."""
    return _read_all(os.path.join(out_dir, "units", "*.json"))


def table_name(folder: str) -> str:
    """Folder name as written in tables and configs: a dot becomes %2E (see ``load_config``)."""
    return folder.replace(".", "%2E")


def groups_of(folder: str, role: str, dataset: str) -> list[str]:
    """Reporting groups a folder belongs to."""
    out = [f"folder:{table_name(folder)}"]
    if role == "test":
        out.append("verified12")
        if folder in SIX:
            out.append("verified6")
        if folder in SAMPLE3:
            out.append("sample3")
    else:
        out += ["dev_all", "dev_pro" if dataset == "SWE-bench_Pro" else "dev_live"]
    return out


# --------------------------------------------------------------------------- scoring


def scores_of(ranks: Sequence[Rank], n_relevant: int) -> tuple[float, float]:
    """(nDCG@10, Recall@100) from the ranks of the relevant documents."""
    return ndcg_at_k(ranks, 10, n_relevant), recall_at_k(ranks, 100, n_relevant)


def _fmt(x: float) -> float:
    return round(float(x), 4)


def ci_cells(values: Sequence[float], seed: int, draws: int) -> dict[str, float]:
    """Mean and 95% interval as percent-scaled cells."""
    m, lo, hi = mean_ci(values, draws=draws, seed=seed)
    return {"mean": _fmt(100 * m), "lo": _fmt(100 * lo), "hi": _fmt(100 * hi)}


# --------------------------------------------------------------------------- chunk level


def chunk_query_rows(chunk_runs: Iterable[Record]) -> list[Record]:
    """One row per (folder, level, query): ranks of the positives under both readings."""
    rows: list[Record] = []
    for run in chunk_runs:
        for r in run["records"]:
            rows.append(
                {
                    "folder": run["folder"],
                    "dataset": run["dataset"],
                    "role": run["role"],
                    "level": run["level"],
                    "query_id": r["query_id"],
                    "n_positives": r["n_positives"],
                    "n_candidates": r["n_candidates"],
                    "positives": r["positives"],
                }
            )
    return rows


def reading_ranks(row: Record, reading: str, key: str | None = None) -> list[Rank]:
    """Ranks of all positives of a row under a reading (missing positives count as not found)."""
    k = key or reading
    ranks: list[Rank] = [p[k] for p in row["positives"].values()]
    ranks += [None] * (row["n_positives"] - len(ranks))
    return ranks


def chunk_summary(rows: list[Record], seed: int, draws: int) -> list[Record]:
    """E1 chunk-level table: per group, level and reading, with intervals and the reference."""
    by_group: dict[tuple[str, str], list[Record]] = defaultdict(list)
    for r in rows:
        for g in groups_of(r["folder"], r["role"], r["dataset"]):
            by_group[(g, r["level"])].append(r)
    out: list[Record] = []
    for (group, level), rs in sorted(by_group.items()):
        for reading in READINGS:
            sc = [scores_of(reading_ranks(r, reading), r["n_positives"]) for r in rs]
            nd = ci_cells([s[0] for s in sc], seed, draws)
            rc = ci_cells([s[1] for s in sc], seed, draws)
            ref = PAPER_REFERENCE.get((group, level))
            out.append(
                {
                    "group": group,
                    "level": level,
                    "reading": reading,
                    "queries": len(rs),
                    "ndcg10": nd["mean"],
                    "ndcg10_lo": nd["lo"],
                    "ndcg10_hi": nd["hi"],
                    "recall100": rc["mean"],
                    "recall100_lo": rc["lo"],
                    "recall100_hi": rc["hi"],
                    "paper_ndcg10": ref[0] if ref else "",
                    "paper_recall100": ref[1] if ref else "",
                }
            )
    return out


def protocol_vs_filter(rows: list[Record], seed: int, draws: int) -> list[Record]:
    """Paired protocol - filter_first, truncation share, and tie sensitivity."""
    by_group: dict[tuple[str, str], list[Record]] = defaultdict(list)
    for r in rows:
        for g in groups_of(r["folder"], r["role"], r["dataset"]):
            by_group[(g, r["level"])].append(r)
    out: list[Record] = []
    for (group, level), rs in sorted(by_group.items()):
        pr = [scores_of(reading_ranks(r, "protocol"), r["n_positives"]) for r in rs]
        ff = [scores_of(reading_ranks(r, "filter_first"), r["n_positives"]) for r in rs]
        lo = [scores_of(reading_ranks(r, "filter_first", "lo"), r["n_positives"]) for r in rs]
        hi = [scores_of(reading_ranks(r, "filter_first", "hi"), r["n_positives"]) for r in rs]
        total = sum(len(r["positives"]) for r in rs)
        cut = sum(
            1
            for r in rs
            for p in r["positives"].values()
            if p["protocol"] is None and p["filter_first"] is not None
        )
        d_n = paired_diff_ci([a[0] for a in pr], [b[0] for b in ff], draws=draws, seed=seed)
        d_r = paired_diff_ci([a[1] for a in pr], [b[1] for b in ff], draws=draws, seed=seed)
        out.append(
            {
                "group": group,
                "level": level,
                "queries": len(rs),
                "positives": total,
                "positives_beyond_prefilter": cut,
                "share_beyond_prefilter": _fmt(cut / total) if total else "",
                "d_ndcg10": _fmt(100 * d_n[0]),
                "d_ndcg10_lo": _fmt(100 * d_n[1]),
                "d_ndcg10_hi": _fmt(100 * d_n[2]),
                "d_recall100": _fmt(100 * d_r[0]),
                "d_recall100_lo": _fmt(100 * d_r[1]),
                "d_recall100_hi": _fmt(100 * d_r[2]),
                "tie_best_ndcg10": _fmt(100 * float(np.mean([s[0] for s in lo]))),
                "tie_worst_ndcg10": _fmt(100 * float(np.mean([s[0] for s in hi]))),
                "tie_best_recall100": _fmt(100 * float(np.mean([s[1] for s in lo]))),
                "tie_worst_recall100": _fmt(100 * float(np.mean([s[1] for s in hi]))),
            }
        )
    return out


# --------------------------------------------------------------------------- label sets


def keep_positive(flags: Record | None, label_set: str) -> bool:
    """Whether a positive (given its label flags) is kept by a label set."""
    if flags is None or flags.get("status") != "found":
        return True  # an unlocated positive cannot be judged; it stays
    noisy = flags["noise_class"] in NOISE
    edited = bool(flags.get("edit_overlap"))
    if label_set == "base":
        return True
    if label_set == "clean_content":
        return not noisy
    if label_set == "edit_overlap":
        return edited
    if label_set == "clean_both":
        return (not noisy) and edited
    raise ValueError(label_set)


def chunk_scores_under(
    row: Record, flags: dict[str, Record], reading: str, label_set: str, treatment: str
) -> tuple[float, float, Rank, int] | None:
    """(nDCG@10, Recall@100, first rank, kept positives) or ``None`` if nothing is left."""
    kept: list[Rank] = []
    removed: list[Rank] = []
    for cid, p in row["positives"].items():
        (kept if keep_positive(flags.get(cid), label_set) else removed).append(p[reading])
    n_unseen = row["n_positives"] - len(row["positives"])  # positives absent from the corpus
    n_kept = len(kept) + n_unseen
    if n_kept == 0:
        return None
    ranks = kept + [None] * n_unseen
    if treatment == "ignored":
        ranks = drop_from_ranking(ranks, removed)
    nd, rc = scores_of(ranks, n_kept)
    return nd, rc, first_rank(ranks), n_kept


# --------------------------------------------------------------------------- unit level


def unit_query_rows(unit_runs: Iterable[Record]) -> list[Record]:
    """One row per (instance, level) with located positives that map to some unit."""
    rows: list[Record] = []
    for run in unit_runs:
        levels = sorted({p["level"] for p in run["positives"]})
        for level in levels:
            pos = [p for p in run["positives"] if p["level"] == level]
            rows.append(
                {
                    "instance": run["instance"],
                    "folder": run["folder"],
                    "dataset": run["dataset"],
                    "role": run["role"],
                    "level": level,
                    "positives": pos,
                    "unit_ranks": run["unit_ranks"].get(level, {}),
                    "unit_edit": run["unit_edit_overlap"],
                    "units_total": run["snapshot"]["units"],
                    "module_units": run["snapshot"]["module_units"],
                }
            )
    return rows


def unit_gold(row: Record, reading: str, label_set: str) -> set[str]:
    """Gold unit ids of a row under a gold reading and a label set (module units included)."""
    flags = {p["corpus_id"]: p for p in row["positives"]}
    gold: set[str] = set()
    pos_filter = label_set in ("clean_content", "clean_both")
    edit_filter = label_set in ("edit_overlap", "clean_both")
    for p in row["positives"]:
        if p["status"] != "found":
            continue
        if pos_filter and flags[p["corpus_id"]]["noise_class"] in NOISE:
            continue
        for uid in p[reading]:
            if edit_filter and not row["unit_edit"].get(uid, False):
                continue
            gold.add(uid)
    return gold


def _is_module(unit_id: str) -> bool:
    return unit_id.endswith("::<module>")


def unit_scores_under(
    row: Record,
    variant: str,
    reading: str,
    label_set: str,
    treatment: str,
    *,
    non_module_gold: bool = False,
) -> tuple[float, float, Rank, int] | None:
    """Unit-level scores for one index variant; ``None`` when the gold set is empty.

    The gold set is the same for both indexes: a module unit in the gold set simply cannot be
    retrieved from the index without module units (it counts as a miss). With
    ``non_module_gold`` the module units leave the gold set, which isolates the cost of having
    the module unit in the index as a distractor.
    """
    gold = unit_gold(row, reading, label_set)
    base = unit_gold(row, reading, "base")
    if non_module_gold:
        gold = {u for u in gold if not _is_module(u)}
        base = {u for u in base if not _is_module(u)}
    if not gold:
        return None
    ranks_tab = row["unit_ranks"].get(variant, {})
    kept: list[Rank] = [ranks_tab[u]["rank"] if u in ranks_tab else None for u in sorted(gold)]
    if treatment == "ignored":
        removed = [ranks_tab[u]["rank"] if u in ranks_tab else None for u in sorted(base - gold)]
        kept = drop_from_ranking(kept, removed)
    nd, rc = scores_of(kept, len(gold))
    return nd, rc, first_rank(kept), len(gold)


def unit_summary(rows: list[Record], seed: int, draws: int) -> list[Record]:
    """E1 unit-level table: both indexes on the same gold, and on the non-module gold only."""
    by_group: dict[tuple[str, str], list[Record]] = defaultdict(list)
    for r in rows:
        for g in groups_of(r["folder"], r["role"], r["dataset"]):
            by_group[(g, r["level"])].append(r)
    out: list[Record] = []
    for (group, level), rs in sorted(by_group.items()):
        for reading in GOLD_READINGS:
            for nm in (False, True):
                ev = [
                    r
                    for r in rs
                    if unit_scores_under(
                        r, "with_module", reading, "base", "neg", non_module_gold=nm
                    )
                ]
                if not ev:
                    continue
                for variant in VARIANTS:
                    sc = [
                        unit_scores_under(r, variant, reading, "base", "neg", non_module_gold=nm)
                        for r in ev
                    ]
                    vals = [(x[0], x[1]) for x in sc if x is not None]
                    nd = ci_cells([v[0] for v in vals], seed, draws)
                    rc = ci_cells([v[1] for v in vals], seed, draws)
                    out.append(
                        {
                            "group": group,
                            "level": level,
                            "gold_reading": reading,
                            "gold": "non_module_units" if nm else "all_gold_units",
                            "index": variant,
                            "queries": len(vals),
                            "ndcg10": nd["mean"],
                            "ndcg10_lo": nd["lo"],
                            "ndcg10_hi": nd["hi"],
                            "recall100": rc["mean"],
                            "recall100_lo": rc["lo"],
                            "recall100_hi": rc["hi"],
                        }
                    )
    return out


def module_effect(rows: list[Record], seed: int, draws: int) -> list[Record]:
    """Paired with_module - without_module on the same gold.

    ``all_gold_units``: what the module unit buys (gold in residual lines becomes reachable);
    ``non_module_units``: what it costs as a distractor when the gold has no module unit.
    """
    by_group: dict[tuple[str, str], list[Record]] = defaultdict(list)
    for r in rows:
        for g in groups_of(r["folder"], r["role"], r["dataset"]):
            by_group[(g, r["level"])].append(r)
    out: list[Record] = []
    for (group, level), rs in sorted(by_group.items()):
        for reading in GOLD_READINGS:
            for nm in (False, True):
                a_n: list[float] = []
                b_n: list[float] = []
                a_r: list[float] = []
                b_r: list[float] = []
                module_only = 0
                for r in rs:
                    a = unit_scores_under(
                        r, "with_module", reading, "base", "neg", non_module_gold=nm
                    )
                    b = unit_scores_under(
                        r, "without_module", reading, "base", "neg", non_module_gold=nm
                    )
                    if a is None or b is None:
                        continue
                    a_n.append(a[0])
                    b_n.append(b[0])
                    a_r.append(a[1])
                    b_r.append(b[1])
                    if not nm and all(_is_module(u) for u in unit_gold(r, reading, "base")):
                        module_only += 1
                if not a_n:
                    continue
                dn = paired_diff_ci(a_n, b_n, draws=draws, seed=seed)
                dr = paired_diff_ci(a_r, b_r, draws=draws, seed=seed)
                out.append(
                    {
                        "group": group,
                        "level": level,
                        "gold_reading": reading,
                        "gold": "non_module_units" if nm else "all_gold_units",
                        "queries": len(a_n),
                        "queries_gold_only_module_units": module_only,
                        "d_ndcg10": _fmt(100 * dn[0]),
                        "d_ndcg10_lo": _fmt(100 * dn[1]),
                        "d_ndcg10_hi": _fmt(100 * dn[2]),
                        "d_recall100": _fmt(100 * dr[0]),
                        "d_recall100_lo": _fmt(100 * dr[1]),
                        "d_recall100_hi": _fmt(100 * dr[2]),
                    }
                )
    return out


# --------------------------------------------------------------------------- positives


def positive_tables(unit_runs: Sequence[Record]) -> tuple[list[Record], list[Record]]:
    """Counts of located positives by kind, mapping category and noise class, per level/role."""
    kinds: dict[tuple[str, str, str], int] = defaultdict(int)
    noise: dict[tuple[str, str, str], int] = defaultdict(int)
    for run in unit_runs:
        for p in run["positives"]:
            kinds[(run["role"], p["level"], p["kind"])] += 1
            noise[
                (
                    run["role"],
                    p["level"],
                    p["noise_class"] + ("+edit" if p.get("edit_overlap") else ""),
                )
            ] += 1
    k_rows = [
        {"role": a, "level": b, "kind": c, "positives": n} for (a, b, c), n in sorted(kinds.items())
    ]
    n_rows = [
        {"role": a, "level": b, "noise_class_and_edit": c, "positives": n}
        for (a, b, c), n in sorted(noise.items())
    ]
    return k_rows, n_rows


# --------------------------------------------------------------------------- E2


def noise_tables(
    chunk_rows: list[Record],
    unit_runs: Sequence[Record],
    unit_rows: list[Record],
    seed: int,
    draws: int,
) -> dict[str, list[Record]]:
    """E2: scores under each label set, rank changes, and the conclusion table."""
    flags: dict[str, dict[str, Record]] = {}
    for run in unit_runs:
        for p in run["positives"]:
            flags.setdefault(run["instance"], {})[p["corpus_id"]] = p
    scored = [r for r in chunk_rows if r["query_id"] in flags and r["level"] == "L2"]
    chunk_out: list[Record] = []
    flips_in: dict[tuple[Any, ...], dict[str, tuple[float, float, float, float, float, float]]] = {}
    for group in ("verified6", "dev_all"):
        rs = [r for r in scored if group in groups_of(r["folder"], r["role"], r["dataset"])]
        for reading in READINGS:
            for treatment in TREATMENTS:
                base_all = {
                    r["query_id"]: chunk_scores_under(
                        r, flags[r["query_id"]], reading, "base", treatment
                    )
                    for r in rs
                }
                for ls in LABEL_SETS:
                    res = {
                        r["query_id"]: chunk_scores_under(
                            r, flags[r["query_id"]], reading, ls, treatment
                        )
                        for r in rs
                    }
                    ids = [q for q in res if res[q] is not None and base_all[q] is not None]
                    cur = [res[q] for q in ids]
                    bas = [base_all[q] for q in ids]
                    assert all(c is not None for c in cur) and all(b is not None for b in bas)
                    nd = ci_cells([c[0] for c in cur if c], seed, draws)
                    rc = ci_cells([c[1] for c in cur if c], seed, draws)
                    dn = paired_diff_ci(
                        [c[0] for c in cur if c], [b[0] for b in bas if b], draws=draws, seed=seed
                    )
                    dr = paired_diff_ci(
                        [c[1] for c in cur if c], [b[1] for b in bas if b], draws=draws, seed=seed
                    )
                    fr_b = [b[2] for b in bas if b]
                    fr_c = [c[2] for c in cur if c]
                    moved = sum(1 for x, y in zip(fr_b, fr_c, strict=True) if x != y)
                    med_shift = (
                        float(
                            np.median(
                                [
                                    (y or 10_001) - (x or 10_001)
                                    for x, y in zip(fr_b, fr_c, strict=True)
                                ]
                            )
                        )
                        if ids
                        else 0.0
                    )
                    chunk_out.append(
                        {
                            "group": group,
                            "reading": reading,
                            "treatment": treatment,
                            "label_set": ls,
                            "queries_total": len(rs),
                            "queries_kept": len(ids),
                            "ndcg10": nd["mean"],
                            "ndcg10_lo": nd["lo"],
                            "ndcg10_hi": nd["hi"],
                            "recall100": rc["mean"],
                            "recall100_lo": rc["lo"],
                            "recall100_hi": rc["hi"],
                            "d_ndcg10_vs_base_same_queries": _fmt(100 * dn[0]),
                            "d_ndcg10_lo": _fmt(100 * dn[1]),
                            "d_ndcg10_hi": _fmt(100 * dn[2]),
                            "d_recall100_vs_base_same_queries": _fmt(100 * dr[0]),
                            "d_recall100_lo": _fmt(100 * dr[1]),
                            "d_recall100_hi": _fmt(100 * dr[2]),
                            "queries_first_rank_changed": moved,
                            "median_first_rank_shift": med_shift,
                        }
                    )
    unit_out: list[Record] = []
    for group in ("verified6", "dev_all"):
        rs = [
            r
            for r in unit_rows
            if r["level"] == "L2" and group in groups_of(r["folder"], r["role"], r["dataset"])
        ]
        for variant in VARIANTS:
            for reading in GOLD_READINGS:
                for treatment in TREATMENTS:
                    ubase = {
                        r["instance"]: unit_scores_under(r, variant, reading, "base", treatment)
                        for r in rs
                    }
                    for ls in LABEL_SETS:
                        ucur = {
                            r["instance"]: unit_scores_under(r, variant, reading, ls, treatment)
                            for r in rs
                        }
                        ids = [q for q in ucur if ucur[q] is not None and ubase[q] is not None]
                        if not ids:
                            continue
                        uc = [ucur[q] for q in ids]
                        ub = [ubase[q] for q in ids]
                        nd = ci_cells([x[0] for x in uc if x], seed, draws)
                        rc = ci_cells([x[1] for x in uc if x], seed, draws)
                        dn = paired_diff_ci(
                            [x[0] for x in uc if x], [y[0] for y in ub if y], draws=draws, seed=seed
                        )
                        dr = paired_diff_ci(
                            [x[1] for x in uc if x], [y[1] for y in ub if y], draws=draws, seed=seed
                        )
                        moved = sum(
                            1 for x, y in zip(ub, uc, strict=True) if x and y and x[2] != y[2]
                        )
                        unit_out.append(
                            {
                                "group": group,
                                "index": variant,
                                "gold_reading": reading,
                                "treatment": treatment,
                                "label_set": ls,
                                "queries_total": len(rs),
                                "queries_kept": len(ids),
                                "ndcg10": nd["mean"],
                                "ndcg10_lo": nd["lo"],
                                "ndcg10_hi": nd["hi"],
                                "recall100": rc["mean"],
                                "recall100_lo": rc["lo"],
                                "recall100_hi": rc["hi"],
                                "d_ndcg10_vs_base_same_queries": _fmt(100 * dn[0]),
                                "d_ndcg10_lo": _fmt(100 * dn[1]),
                                "d_ndcg10_hi": _fmt(100 * dn[2]),
                                "d_recall100_vs_base_same_queries": _fmt(100 * dr[0]),
                                "d_recall100_lo": _fmt(100 * dr[1]),
                                "d_recall100_hi": _fmt(100 * dr[2]),
                                "queries_first_rank_changed": moved,
                            }
                        )
    del flips_in
    return {"chunk": chunk_out, "unit": unit_out}


def conclusion_table(
    chunk_rows: list[Record],
    unit_runs: Sequence[Record],
    unit_rows: list[Record],
    seed: int,
    draws: int,
) -> list[Record]:
    """Three comparisons under every label set; ``flip`` marks a change against ``base``.

    C1 protocol vs filter-first (chunk level); C2 with vs without the module unit (units);
    C3 unit level (with module) vs chunk level (filter-first) on the same queries.
    A flip is a change of the sign of the difference or of whether its interval excludes zero.
    """
    flags: dict[str, dict[str, Record]] = {}
    for run in unit_runs:
        for p in run["positives"]:
            flags.setdefault(run["instance"], {})[p["corpus_id"]] = p
    chunk_by_q = {
        r["query_id"]: r for r in chunk_rows if r["level"] == "L2" and r["query_id"] in flags
    }
    unit_by_q = {r["instance"]: r for r in unit_rows if r["level"] == "L2"}
    out: list[Record] = []
    status: dict[tuple[str, str, str, str, str], str] = {}

    def verdict(diff: tuple[float, float, float]) -> str:
        m, lo, hi = diff
        if lo > 0:
            return "positive"
        if hi < 0:
            return "negative"
        return "indistinguishable" if m == m else "undefined"

    for group in ("verified6", "dev_all"):
        qs = [
            q
            for q, r in chunk_by_q.items()
            if group in groups_of(r["folder"], r["role"], r["dataset"]) and q in unit_by_q
        ]
        for treatment in TREATMENTS:
            for ls in LABEL_SETS:
                comps: dict[str, tuple[list[float], list[float], list[float], list[float]]] = {}
                for cname in (
                    "C1_protocol_minus_filter_first",
                    "C2_with_minus_without_module",
                    "C3_unit_minus_chunk",
                ):
                    a_n: list[float] = []
                    b_n: list[float] = []
                    a_r: list[float] = []
                    b_r: list[float] = []
                    for q in qs:
                        cr, ur, fl = chunk_by_q[q], unit_by_q[q], flags[q]
                        if cname.startswith("C1"):
                            a = chunk_scores_under(cr, fl, "protocol", ls, treatment)
                            b = chunk_scores_under(cr, fl, "filter_first", ls, treatment)
                        elif cname.startswith("C2"):
                            a = unit_scores_under(ur, "with_module", "units", ls, treatment)
                            b = unit_scores_under(ur, "without_module", "units", ls, treatment)
                        else:
                            a = unit_scores_under(ur, "with_module", "units", ls, treatment)
                            b = chunk_scores_under(cr, fl, "filter_first", ls, treatment)
                        if a is None or b is None:
                            continue
                        a_n.append(a[0])
                        b_n.append(b[0])
                        a_r.append(a[1])
                        b_r.append(b[1])
                    comps[cname] = (a_n, b_n, a_r, b_r)
                for cname, (a_n, b_n, a_r, b_r) in comps.items():
                    if not a_n:
                        continue
                    dn = paired_diff_ci(a_n, b_n, draws=draws, seed=seed)
                    dr = paired_diff_ci(a_r, b_r, draws=draws, seed=seed)
                    vn, vr = verdict(dn), verdict(dr)
                    status[(group, treatment, cname, ls, "ndcg")] = vn
                    status[(group, treatment, cname, ls, "recall")] = vr
                    out.append(
                        {
                            "group": group,
                            "treatment": treatment,
                            "comparison": cname,
                            "label_set": ls,
                            "queries": len(a_n),
                            "d_ndcg10": _fmt(100 * dn[0]),
                            "d_ndcg10_lo": _fmt(100 * dn[1]),
                            "d_ndcg10_hi": _fmt(100 * dn[2]),
                            "ndcg10_verdict": vn,
                            "d_recall100": _fmt(100 * dr[0]),
                            "d_recall100_lo": _fmt(100 * dr[1]),
                            "d_recall100_hi": _fmt(100 * dr[2]),
                            "recall100_verdict": vr,
                        }
                    )
    for row in out:
        flips = []
        for metric, key in (("ndcg", "ndcg10_verdict"), ("recall", "recall100_verdict")):
            base = status.get((row["group"], row["treatment"], row["comparison"], "base", metric))
            if base is not None and row[key] != base:
                flips.append(f"{metric}:{base}->{row[key]}")
        row["flip_vs_base"] = ";".join(flips)
    return out


# --------------------------------------------------------------------------- output


def write_csv(path: str, rows: Sequence[Record]) -> None:
    """Write dict rows as CSV (columns of the first row; empty file for no rows)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        if not rows:
            return
        cols: list[str] = []
        for r in rows:
            for k in r:
                if k not in cols:
                    cols.append(k)
        w = csv.DictWriter(handle, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def per_folder_counts(chunk_runs: Sequence[Record]) -> list[Record]:
    """Counts per folder and level (corpus chunks, queries, dropped, timings)."""
    return [
        {
            "role": r["role"],
            "dataset": r["dataset"],
            "folder": table_name(r["folder"]),
            "level": r["level"],
            "corpus_chunks": r["corpus_chunks"],
            "queries": r["queries"],
            "dropped_queries_without_qrels": r["dropped_queries_without_qrels"],
            "total_seconds": r["total_seconds"],
        }
        for r in chunk_runs
    ]


# --------------------------------------------------------------------------- sweep


def sweep_table(
    sweep_dir: str, default: tuple[float, float], seed: int, draws: int
) -> list[Record]:
    """Dev-set sweep of (k1, b): pooled nDCG@10 and Recall@100 over all dev queries.

    The criterion stated before the run is the mean nDCG@10 over all dev queries (L2 and L3
    pooled); ``paired_vs_default`` is the paired difference to the default cell on the same queries.
    """
    cells: dict[tuple[float, float], list[Record]] = {}
    for sub in sorted(glob.glob(os.path.join(sweep_dir, "sweep_k1_*_b_*"))):
        name = os.path.basename(sub).split("_")
        k1, b = float(name[2]), float(name[4])
        cells[(k1, b)] = chunk_query_rows(load_chunk_runs(sub))
    if default not in cells:
        return []

    def vec(rows: list[Record]) -> tuple[list[str], list[float], list[float]]:
        keyed = sorted(rows, key=lambda r: (r["level"], r["folder"], r["query_id"]))
        sc = [scores_of(reading_ranks(r, "protocol"), r["n_positives"]) for r in keyed]
        return (
            [f"{r['level']}/{r['folder']}/{r['query_id']}" for r in keyed],
            [s[0] for s in sc],
            [s[1] for s in sc],
        )

    base_ids, base_n, _ = vec(cells[default])
    out: list[Record] = []
    for (k1, b), rows in sorted(cells.items()):
        ids, nd, rc = vec(rows)
        if ids != base_ids:
            continue
        m = ci_cells(nd, seed, draws)
        r = ci_cells(rc, seed, draws)
        d = paired_diff_ci(nd, base_n, draws=draws, seed=seed)
        l2 = [x for x, i in zip(nd, ids, strict=True) if i.startswith("L2/")]
        l3 = [x for x, i in zip(nd, ids, strict=True) if i.startswith("L3/")]
        out.append(
            {
                "k1": k1,
                "b": b,
                "queries": len(ids),
                "ndcg10_pooled": m["mean"],
                "ndcg10_lo": m["lo"],
                "ndcg10_hi": m["hi"],
                "recall100_pooled": r["mean"],
                "ndcg10_l2": _fmt(100 * float(np.mean(l2))),
                "ndcg10_l3": _fmt(100 * float(np.mean(l3))),
                "paired_vs_default": _fmt(100 * d[0]),
                "paired_lo": _fmt(100 * d[1]),
                "paired_hi": _fmt(100 * d[2]),
                "is_default": (k1, b) == default,
            }
        )
    return out


# --------------------------------------------------------------------------- aggregation


def _per_query_scores(
    rows: list[Record], reading: str
) -> dict[tuple[str, str], np.ndarray[Any, Any]]:
    by: dict[tuple[str, str], list[tuple[float, float]]] = defaultdict(list)
    for r in rows:
        by[(r["dataset"], r["folder"])].append(
            scores_of(reading_ranks(r, reading), r["n_positives"])
        )
    return {k: np.asarray(v, dtype=np.float64) for k, v in by.items()}


def _aggregates(
    per_folder: dict[tuple[str, str], np.ndarray[Any, Any]],
) -> dict[str, np.ndarray[Any, Any]]:
    """Four ways of averaging per-query scores (two metrics each), as percent."""
    all_q = np.vstack(list(per_folder.values()))
    fold_means = {k: v.mean(axis=0) for k, v in per_folder.items()}
    by_ds: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for k in per_folder:
        by_ds[k[0]].append(k)
    ds_micro = [np.vstack([per_folder[k] for k in ks]).mean(axis=0) for ks in by_ds.values()]
    ds_macro = [np.mean([fold_means[k] for k in ks], axis=0) for ks in by_ds.values()]
    return {
        "micro_over_queries": 100 * all_q.mean(axis=0),
        "macro_over_folders": 100 * np.mean(list(fold_means.values()), axis=0),
        "mean_of_dataset_micro": 100 * np.mean(ds_micro, axis=0),
        "mean_of_dataset_macro_over_folders": 100 * np.mean(ds_macro, axis=0),
    }


def aggregation_table(
    rows: list[Record],
    sets: dict[str, Callable[[Record], bool]],
    reference: dict[tuple[str, str], tuple[float, float]],
    seed: int,
    draws: int,
) -> list[Record]:
    """The four averaging conventions side by side, with a within-folder query bootstrap.

    ``sets`` maps a name to a row filter; ``reference`` maps (set name, level) to the published
    (nDCG@10, Recall@100) in percent. The bootstrap resamples the queries of every folder, so
    the structure of the average (folders, datasets) is kept.
    """
    out: list[Record] = []
    rng = np.random.default_rng(seed)
    for name, keep in sets.items():
        for level in ("L2", "L3"):
            sel = [r for r in rows if r["level"] == level and keep(r)]
            if not sel:
                continue
            pf = _per_query_scores(sel, "protocol")
            point = _aggregates(pf)
            boots: dict[str, list[np.ndarray[Any, Any]]] = {k: [] for k in point}
            for _ in range(draws):
                resampled = {k: v[rng.integers(0, len(v), size=len(v))] for k, v in pf.items()}
                for k, val in _aggregates(resampled).items():
                    boots[k].append(val)
            ref = reference.get((name, level))
            for conv, val in point.items():
                arr = np.asarray(boots[conv])
                lo = np.quantile(arr, 0.025, axis=0)
                hi = np.quantile(arr, 0.975, axis=0)
                out.append(
                    {
                        "set": name,
                        "level": level,
                        "folders": len(pf),
                        "queries": int(sum(len(v) for v in pf.values())),
                        "convention": conv,
                        "ndcg10": _fmt(val[0]),
                        "ndcg10_lo": _fmt(lo[0]),
                        "ndcg10_hi": _fmt(hi[0]),
                        "recall100": _fmt(val[1]),
                        "recall100_lo": _fmt(lo[1]),
                        "recall100_hi": _fmt(hi[1]),
                        "paper_ndcg10": ref[0] if ref else "",
                        "paper_recall100": ref[1] if ref else "",
                    }
                )
    return out


def _qkey(r: Record) -> tuple[str, str, str]:
    return (r["level"], r["folder"], r["query_id"])


def confirm_paired(
    default_rows: list[Record], other_rows: list[Record], seed: int, draws: int
) -> list[Record]:
    """Paired nDCG@10 and Recall@100 difference (other - default) on the test folders."""
    a = {_qkey(r): r for r in default_rows if r["role"] == "test"}
    b = {_qkey(r): r for r in other_rows if r["role"] == "test"}
    out: list[Record] = []
    for level in ("L2", "L3"):
        ks = sorted(k for k in a if k in b and k[0] == level)
        sa = [scores_of(reading_ranks(a[k], "protocol"), a[k]["n_positives"]) for k in ks]
        sb = [scores_of(reading_ranks(b[k], "protocol"), b[k]["n_positives"]) for k in ks]
        dn = paired_diff_ci([x[0] for x in sb], [x[0] for x in sa], draws=draws, seed=seed)
        dr = paired_diff_ci([x[1] for x in sb], [x[1] for x in sa], draws=draws, seed=seed)
        out.append(
            {
                "level": level,
                "queries": len(ks),
                "d_ndcg10": _fmt(100 * dn[0]),
                "d_ndcg10_lo": _fmt(100 * dn[1]),
                "d_ndcg10_hi": _fmt(100 * dn[2]),
                "d_recall100": _fmt(100 * dr[0]),
                "d_recall100_lo": _fmt(100 * dr[1]),
                "d_recall100_hi": _fmt(100 * dr[2]),
            }
        )
    return out
