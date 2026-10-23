"""Tables for pilots E3 (graph signal), E4 (fitted edge weights) and E5 (recency prior).

Exploratory.

Reads the per-instance evaluation files written by ``ril.evaluation.e3_eval`` (metric matrices
only) and produces paired differences with percentile-bootstrap intervals over queries.

Conventions
-----------
* A *query* is an (instance, level) pair; L2 and L3 are always separate rows.
* ``micro`` averages over queries; ``macro_repo`` averages the per-repository means (the queries
  of every repository are resampled inside it, so the structure of the average is kept); ``cluster``
  is the micro mean with a repository-clustered interval (whole repositories resampled with
  replacement; decision D17's primary convention). With five or six repositories the clustered
  interval is wide and coarse, so the query-level (``micro``) interval is reported beside it.
* Differences are in percentage points of nDCG@10 and Recall@100; the intervals are 95%
  percentile bootstraps with a fixed seed (2,000 draws, one set of resamples shared by all
  columns of a group, which keeps the comparisons paired).
* Every expansion is compared with the BM25 ranking it started from (``d_bm25``) and with two
  chance controls of the same expansion size (``d_rand_whole``: random units of the snapshot;
  ``d_rand_files``: random units of the seeds' files), drawn three times per query and averaged.
"""

from __future__ import annotations

import glob
import os
from dataclasses import dataclass
from typing import Any

import numpy as np

from ril.evaluation.e3_eval import FAMILIES, control_key, graph_key, read_eval
from ril.evaluation.e3_prepare import READINGS

Record = dict[str, Any]
METRICS = ("ndcg10", "recall100")
COLUMN = {(r, m): 2 * i + j for i, r in enumerate(READINGS) for j, m in enumerate(METRICS)}
DRAWS = 2000
HANDSET_GAMMA = 0.5
"""The hand-set decay that a fitted weight set is compared with (E4); the mean weight of a fit
is scaled to it."""


@dataclass
class EvalTable:
    """All evaluation files of a directory as one metric tensor."""

    keys: list[str]
    index: dict[str, int]
    rows: list[Record]
    metrics: np.ndarray[Any, Any]  # (queries, keys, 4)
    aux_keys: list[str]
    aux: np.ndarray[Any, Any]  # (queries, aux keys, 3): size, hits (units), hits (units_all)

    def mask(self, **match: Any) -> np.ndarray[Any, Any]:
        """Boolean mask of the queries whose row fields equal the given values."""
        out = np.ones(len(self.rows), dtype=bool)
        for k, v in match.items():
            out &= np.asarray([r[k] == v for r in self.rows], dtype=bool)
        return out


def load_eval_dir(path: str) -> EvalTable:
    """Read every evaluation file under ``path``; all must share one key layout."""
    keys: list[str] | None = None
    aux_keys: list[str] | None = None
    rows: list[Record] = []
    blocks: list[np.ndarray[Any, Any]] = []
    aux_blocks: list[np.ndarray[Any, Any]] = []
    for name in sorted(glob.glob(os.path.join(path, "*.npz"))):
        info, arrays = read_eval(name)
        if not info["levels"]:  # no level with a located gold unit: nothing to score
            continue
        k = [str(x) for x in arrays["keys"]]
        ak = [str(x) for x in arrays["aux_keys"]]
        if keys is None:
            keys, aux_keys = k, ak
        elif k != keys or ak != aux_keys:
            raise ValueError(f"{name}: key layout differs from the other files")
        for level in sorted(info["levels"]):
            rows.append(
                {
                    "instance": info["instance"],
                    "level": level,
                    "repo": info["repo_id"],
                    "role": info["role"],
                    "dataset": info["dataset"],
                    "folder": info["folder"],
                    "units": info["units"],
                    "gold_units": info["levels"][level]["gold_units"],
                }
            )
            blocks.append(arrays[f"metrics_{level}"])
            aux_blocks.append(arrays[f"aux_{level}"])
    if keys is None or aux_keys is None:
        raise ValueError(f"no evaluation files under {path}")
    return EvalTable(
        keys,
        {k: i for i, k in enumerate(keys)},
        rows,
        np.stack(blocks),
        aux_keys,
        np.stack(aux_blocks) if aux_keys else np.zeros((len(rows), 0, 1 + len(READINGS))),
    )


# --------------------------------------------------------------------------- bootstrap


class Boot:
    """Resample weights for a fixed set of queries; one set shared by every column."""

    def __init__(self, repos: list[str], seed: int, draws: int = DRAWS) -> None:
        q = len(repos)
        rng = np.random.default_rng(seed)
        self.q = q
        idx = rng.integers(0, q, size=(draws, q))
        micro = np.zeros((draws, q))
        rows = np.repeat(np.arange(draws), q)
        np.add.at(micro, (rows, idx.ravel()), 1.0)
        self.micro = micro / q
        self.point_micro = np.full(q, 1.0 / q)
        blocks: dict[str, list[int]] = {}
        for i, r in enumerate(repos):
            blocks.setdefault(r, []).append(i)
        macro = np.zeros((draws, q))
        point = np.zeros(q)
        for members in blocks.values():
            m = np.asarray(members)
            sub = rng.integers(0, len(m), size=(draws, len(m)))
            counts = np.zeros((draws, len(m)))
            np.add.at(counts, (np.repeat(np.arange(draws), len(m)), sub.ravel()), 1.0)
            macro[:, m] = counts / len(m) / len(blocks)
            point[m] = 1.0 / len(m) / len(blocks)
        self.macro = macro
        self.point_macro = point
        # repository-clustered (decision D17): resample whole repositories with replacement, then
        # average over the queries of the drawn repositories (point estimate = the micro mean)
        names = sorted(blocks)
        repo_of_query = np.empty(q, dtype=np.int64)
        for j, name in enumerate(names):
            repo_of_query[blocks[name]] = j
        picks = rng.integers(0, len(names), size=(draws, len(names)))
        drawn = np.zeros((draws, len(names)))
        np.add.at(drawn, (np.repeat(np.arange(draws), len(names)), picks.ravel()), 1.0)
        cluster = drawn[:, repo_of_query]
        self.cluster = cluster / cluster.sum(axis=1, keepdims=True)

    def summarize(
        self, d: np.ndarray[Any, Any], average: str
    ) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any], np.ndarray[Any, Any]]:
        """Mean, 2.5% and 97.5% quantiles of every column of ``d`` (queries x columns)."""
        if average == "micro":
            w, p = self.micro, self.point_micro
        elif average == "cluster":
            w, p = self.cluster, self.point_micro
        else:
            w, p = self.macro, self.point_macro
        boots = w @ d
        lo, hi = np.quantile(boots, [0.025, 0.975], axis=0)
        return p @ d, lo, hi


# --------------------------------------------------------------------------- cells


@dataclass(frozen=True)
class Cell:
    """One real run, its labels, and the keys of its chance controls."""

    key: str
    labels: dict[str, Any]
    controls: dict[str, str]


def graph_cells(tab: EvalTable) -> list[Cell]:
    """Cells of hand-set-decay and weighted-edge runs found in the table."""
    cells: list[Cell] = []
    for key in tab.keys:
        parts = key.split("|")
        if parts[0] not in ("list", "rrf", "fz_list", "fz_rrf") or parts[1].startswith("rand_"):
            continue
        variant, subset, c, setting, h = parts[0], parts[1], parts[2], parts[3], parts[4]
        wname = setting[2:] if setting.startswith("w:") else ""
        controls = {
            ctrl: control_key(variant, ctrl, subset, int(c[1:]), int(h[1:]), wname)
            for ctrl in ("rand_whole", "rand_files")
        }
        if variant.startswith("fz_"):  # graph on top of BM25 + dense: compare with that fusion too
            controls["fused"] = "fused"
        elif wname:  # the hand-set decay at the same seeds and hops, when it was run
            controls["handset"] = graph_key(variant, subset, int(c[1:]), HANDSET_GAMMA, int(h[1:]))
        if subset == "all":  # leave-one-out: what the family adds to all the others
            for fam in FAMILIES:
                controls[f"minus_{fam}"] = f"{variant}|all-minus-{fam}|{c}|{setting}|{h}"
        controls = {k: v for k, v in controls.items() if v in tab.index}
        cells.append(
            Cell(
                key,
                {
                    "variant": variant,
                    "subset": subset,
                    "C": int(c[1:]),
                    "gamma": float(setting[1:]) if setting.startswith("g") else "",
                    "weights": wname,
                    "hops": int(h[1:]),
                },
                controls,
            )
        )
    return cells


def recency_cells(tab: EvalTable) -> list[Cell]:
    """Cells of recency-prior runs."""
    out: list[Cell] = []
    for key in tab.keys:
        if key.startswith("rec|"):
            _, lam, tau = key.split("|")
            out.append(Cell(key, {"lam": float(lam[3:]), "tau_days": float(tau[3:])}, {}))
    return out


def _fmt(x: float) -> float:
    return round(float(x), 3)


def compare(
    tab: EvalTable,
    mask: np.ndarray[Any, Any],
    group: str,
    level: str,
    cells: list[Cell],
    seed: int,
    averages: tuple[str, ...] = ("micro", "macro_repo"),
    chunk: int = 60,
) -> list[Record]:
    """Paired comparison of each cell with the BM25 ranking and its chance controls.

    One row per (cell, gold reading, metric, average). Values are percentages; differences are
    percentage points. A query without gold under a reading is not scored under that reading
    (``queries`` counts the scored ones).
    """
    level_mask = mask & np.asarray([r["level"] == level for r in tab.rows])
    base_i = tab.index["bm25"]
    out: list[Record] = []
    for reading in READINGS:
        valid = ~np.isnan(tab.metrics[:, base_i, COLUMN[(reading, "ndcg10")]])
        sel = np.flatnonzero(level_mask & valid)
        if len(sel) == 0:
            continue
        repos = [tab.rows[i]["repo"] for i in sel]
        boot = Boot(repos, seed)
        sub = tab.metrics[sel]
        for start in range(0, len(cells), chunk):
            part = cells[start : start + chunk]
            cols: list[np.ndarray[Any, Any]] = []
            meta: list[tuple[Cell, str, str]] = []
            for cell in part:
                x_all = sub[:, tab.index[cell.key], :]
                for metric in METRICS:
                    j = COLUMN[(reading, metric)]
                    x = x_all[:, j]
                    cols.append(100 * x)
                    meta.append((cell, metric, "value"))
                    cols.append(100 * (x - sub[:, base_i, j]))
                    meta.append((cell, metric, "bm25"))
                    for ctrl, ckey in cell.controls.items():
                        cols.append(100 * (x - sub[:, tab.index[ckey], j]))
                        meta.append((cell, metric, ctrl))
            d = np.stack(cols, axis=1)
            for avg in averages:
                mean, lo, hi = boot.summarize(d, avg)
                rows: dict[tuple[str, str], Record] = {}
                for i, (cell, metric, what) in enumerate(meta):
                    row = rows.setdefault(
                        (cell.key, metric),
                        {
                            "group": group,
                            "level": level,
                            "average": avg,
                            "queries": len(sel),
                            "repos": len(set(repos)),
                            "gold_reading": reading,
                            "metric": metric,
                            **cell.labels,
                        },
                    )
                    if what == "value":
                        row["value"] = _fmt(mean[i])
                    else:
                        name = "d_bm25" if what == "bm25" else f"d_{what}"
                        row[name] = _fmt(mean[i])
                        row[f"{name}_lo"] = _fmt(lo[i])
                        row[f"{name}_hi"] = _fmt(hi[i])
                w = boot.point_macro if avg.startswith("macro") else boot.point_micro
                for row in rows.values():
                    row["bm25"] = _fmt(100 * (w @ sub[:, base_i, COLUMN[(reading, row["metric"])]]))
                out.extend(rows.values())
    return out


def aux_rows(tab: EvalTable, mask: np.ndarray[Any, Any], group: str, level: str) -> list[Record]:
    """Mean expansion size and mean gold hits per expansion, per cell (queries with seeds only)."""
    sel = np.flatnonzero(mask & np.asarray([r["level"] == level for r in tab.rows]))
    out: list[Record] = []
    for j, key in enumerate(tab.aux_keys):
        _, subset, c, setting, h = key.split("|")
        vals = tab.aux[sel, j, :]
        has = vals[:, 0] > 0
        out.append(
            {
                "group": group,
                "level": level,
                "subset": subset,
                "C": int(c[1:]),
                "setting": setting,
                "hops": int(h[1:]),
                "queries": len(sel),
                "queries_with_expansion": int(has.sum()),
                "mean_size": _fmt(vals[:, 0].mean()) if len(sel) else "",
                "mean_hits_units": _fmt(vals[:, 1].mean()) if len(sel) else "",
                "share_with_hit_units": _fmt((vals[:, 1] > 0).mean()) if len(sel) else "",
                "hits_per_unit_units": _fmt(vals[:, 1].sum() / max(vals[:, 0].sum(), 1.0)),
            }
        )
    return out


# --------------------------------------------------------------------------- selection


def select_setting(
    rows: list[Record], subset: str, variant: str, reading: str = "units", average: str = "micro"
) -> Record | None:
    """The dev setting that maximises (L2 nDCG@10 gain + L3 Recall@100 gain) / 2 against BM25.

    Criterion fixed before any test run: for the given subset and variant over the cells of the
    grid, ``(d_bm25 of nDCG@10 at L2 + d_bm25 of Recall@100 at L3) / 2`` under the stated gold
    reading and average. Returns the best cell's labels and its score, or ``None``.
    """
    score: dict[tuple[Any, ...], dict[str, float]] = {}
    for r in rows:
        if (
            r["subset"] != subset
            or r["variant"] != variant
            or r["gold_reading"] != reading
            or r["average"] != average
        ):
            continue
        cell = (r["C"], r["gamma"], r["hops"])
        if r["level"] == "L2" and r["metric"] == "ndcg10":
            score.setdefault(cell, {})["L2"] = float(r["d_bm25"])
        if r["level"] == "L3" and r["metric"] == "recall100":
            score.setdefault(cell, {})["L3"] = float(r["d_bm25"])
    ok = {c: (v["L2"] + v["L3"]) / 2 for c, v in score.items() if "L2" in v and "L3" in v}
    if not ok:
        return None
    best = max(sorted(ok), key=lambda c: ok[c])
    return {
        "C": best[0],
        "gamma": best[1],
        "hops": best[2],
        "score": _fmt(ok[best]),
        "cells": len(ok),
    }


# --------------------------------------------------------------------------- held-out fits (E4)


def add_heldout_keys(tab: EvalTable, prefix: str = "loro_") -> list[str]:
    """Merge weight sets named ``loro_<repo>`` into one virtual set ``loro`` per key.

    A leave-one-repository-out fit is evaluated on the repository it was not fitted on: the virtual
    column of a query takes the value of the set named after that query's repository (the
    repository id with ``/`` written ``__``). Returns the virtual keys that were added.
    """
    groups: dict[str, dict[str, str]] = {}
    for key in tab.keys:
        marker = f"w:{prefix}"
        if marker not in key:
            continue
        head, rest = key.split(marker, 1)
        tag, tail = rest.split("|", 1)
        groups.setdefault(f"{head}w:loro|{tail}", {})[tag] = key
    added: list[str] = []
    tags = [r["repo"].replace("/", "__") for r in tab.rows]
    for virtual, by_tag in sorted(groups.items()):
        column = np.zeros((len(tab.rows), tab.metrics.shape[2]))
        for i, tag in enumerate(tags):
            src = by_tag.get(tag)
            column[i] = tab.metrics[i, tab.index[src], :] if src else np.nan
        tab.index[virtual] = len(tab.keys)
        tab.keys.append(virtual)
        tab.metrics = np.concatenate([tab.metrics, column[:, None, :]], axis=1)
        added.append(virtual)
    return added
