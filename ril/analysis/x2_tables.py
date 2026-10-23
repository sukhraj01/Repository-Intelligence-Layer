"""Tables of the dense and fusion measurements X2: paired comparisons with two kinds of interval.

Exploratory. Every row gives the mean over queries (decision D17) with a query-level bootstrap
interval and a repository-clustered bootstrap interval (resample repositories, then their queries'
mean; ``ril.analysis.e3_tables.Boot``), for the value and for the paired difference against a stated
reference. At development L3 only two repositories carry qrels, so the clustered interval there is
not informative (Q47) and the query-level one is quoted.

Selection rules (stated in the configurations before any dense number was seen) are implemented
here:
cut (512 vs 1024 tokens), RRF k, the strongest first stage, and the graph setting to confirm.

Values are percentages; differences percentage points.
"""

from __future__ import annotations

import glob
import json
import math
import os
from collections.abc import Sequence
from typing import Any

import numpy as np

from ril.analysis.e3_tables import COLUMN, DRAWS, Boot, EvalTable
from ril.evaluation.e3_prepare import READINGS
from ril.evaluation.metrics import ndcg_at_k, recall_at_k

Record = dict[str, Any]
Arr = np.ndarray[Any, Any]
PRIMARY = "units_all_nomod"
BESIDE = "units_all"
LEVEL_METRIC = {"L2": "ndcg10", "L3": "recall100"}


def _r(x: float) -> float:
    return round(float(x), 2)


def paired_rows(
    values: Arr,
    repos: Sequence[str],
    names: Sequence[str],
    refs: Sequence[str | None],
    labels: Record,
    seed: int,
    draws: int = DRAWS,
) -> list[Record]:
    """Rows for columns of ``values`` (queries x columns, fractions; NaN-free) and their references.

    ``refs[j]`` names the reference column of column ``j`` (or ``None``).
    """
    if values.shape[0] == 0:
        return []
    boot = Boot(list(repos), seed, draws)
    idx = {n: j for j, n in enumerate(names)}
    cols = [100 * values[:, j] for j in range(len(names))]
    diffs = [
        100 * (values[:, j] - values[:, idx[r]]) if r is not None else np.zeros(len(repos))
        for j, r in enumerate(refs)
    ]
    d = np.stack(cols + diffs, axis=1)
    mean, qlo, qhi = boot.summarize(d, "micro")
    _, clo, chi = boot.summarize(d, "cluster")
    out: list[Record] = []
    m = len(names)
    for j, name in enumerate(names):
        row: Record = {
            **labels,
            "name": name,
            "queries": int(values.shape[0]),
            "repos": len(set(repos)),
            "value": _r(mean[j]),
            "q_lo": _r(qlo[j]),
            "q_hi": _r(qhi[j]),
            "c_lo": _r(clo[j]),
            "c_hi": _r(chi[j]),
            "ref": refs[j] or "",
        }
        if refs[j] is not None:
            row.update(
                d=_r(mean[m + j]),
                d_q_lo=_r(qlo[m + j]),
                d_q_hi=_r(qhi[m + j]),
                d_c_lo=_r(clo[m + j]),
                d_c_hi=_r(chi[m + j]),
            )
        out.append(row)
    return out


def unit_rows(
    tab: EvalTable,
    group: str,
    columns: Sequence[tuple[str, str, str | None]],
    seed: int,
    readings: Sequence[str] = (PRIMARY, BESIDE),
) -> list[Record]:
    """Paired rows for ``(name, key, reference name)`` columns, per level, reading and metric.

    Every reference must itself be a listed column. A query enters a reading only when it has gold
    under it (every key is then scored).
    """
    names = [n for n, _, _ in columns]
    for _, k, ref in columns:
        if k not in tab.index:
            raise KeyError(f"key not in the table: {k}")
        if ref is not None and ref not in names:
            raise KeyError(f"reference {ref} is not a listed column")
    idx = [tab.index[k] for _, k, _ in columns]
    refs = [r for _, _, r in columns]
    out: list[Record] = []
    for level in ("L2", "L3"):
        lmask = np.asarray([r["level"] == level for r in tab.rows]) & tab.mask(role=group)
        for reading in readings:
            for metric in ("ndcg10", "recall100"):
                mat = tab.metrics[:, idx, COLUMN[(reading, metric)]]
                sel = np.flatnonzero(lmask & ~np.isnan(mat).any(axis=1))
                out += paired_rows(
                    mat[sel],
                    [tab.rows[i]["repo"] for i in sel],
                    names,
                    refs,
                    {"group": group, "level": level, "reading": reading, "metric": metric},
                    seed,
                )
    return out


# --------------------------------------------------------------------------- chunk level


def load_chunk_dir(path: str) -> tuple[list[Record], dict[str, Arr]]:
    """Per-query metrics of every chunk-level record file: rows and ``{column: (queries, 2)}``.

    Columns: ``bm25``, each dense variant, ``rrf<k>__<variant>``; metrics nDCG@10 and Recall@100
    under binary gain over the positives that are in the query's candidate list (filter-first).
    """
    rows: list[Record] = []
    cols: dict[str, list[tuple[float, float]]] = {}
    for name in sorted(glob.glob(os.path.join(path, "*.json"))):
        with open(name, encoding="utf-8") as handle:
            doc = json.load(handle)
        for rec in doc["records"]:
            npos = rec["n_positives_in_candidates"]
            if npos == 0:
                continue
            rows.append(
                {
                    "level": doc["level"],
                    "role": doc["role"],
                    "repo": doc["repo"],
                    "folder": doc["folder"],
                    "query_id": rec["query_id"],
                }
            )
            for k, ranks in rec.items():
                if not isinstance(ranks, list):
                    continue
                cols.setdefault(k, []).append(
                    (ndcg_at_k(ranks, 10, npos), recall_at_k(ranks, 100, npos))
                )
    lens = {len(v) for v in cols.values()}
    if len(lens) > 1:
        raise ValueError("chunk columns differ in length (a variant is missing in some folder)")
    return rows, {k: np.asarray(v) for k, v in cols.items()}


def chunk_rows(
    rows: list[Record],
    cols: dict[str, Arr],
    group: str,
    columns: Sequence[tuple[str, str, str | None]],
    seed: int,
) -> list[Record]:
    """Paired rows at chunk level, per level and metric."""
    out: list[Record] = []
    for level in ("L2", "L3"):
        sel = np.flatnonzero([r["level"] == level and r["role"] == group for r in rows])
        for m, metric in enumerate(("ndcg10", "recall100")):
            mat = np.stack([cols[k][sel, m] for _, k, _ in columns], axis=1)
            names = [n for n, _, _ in columns]
            refs = [r for _, _, r in columns]
            out += paired_rows(
                mat,
                [rows[i]["repo"] for i in sel],
                names,
                refs,
                {"group": group, "level": level, "reading": "chunks", "metric": metric},
                seed,
            )
    return out


# --------------------------------------------------------------------------- selection rules


def objective(rows: list[Record], name: str, reading: str = PRIMARY) -> float:
    """(L2 nDCG@10 + L3 Recall@100) / 2 of a named column (mean over queries)."""
    got: dict[str, float] = {}
    for r in rows:
        if (
            r["name"] == name
            and r["reading"] == reading
            and r["metric"] == LEVEL_METRIC[r["level"]]
        ):
            got[r["level"]] = float(r["value"])
    if set(got) != {"L2", "L3"}:
        return -math.inf
    return (got["L2"] + got["L3"]) / 2


def select_best(rows: list[Record], names: Sequence[str], reading: str = PRIMARY) -> Record:
    """The name with the highest objective (ties: first in ``names``)."""
    scored = [(objective(rows, n, reading), -i, n) for i, n in enumerate(names)]
    best = max(scored)
    return {"name": best[2], "objective": _r(best[0]), "candidates": len(names)}


def select_cut(rows: list[Record], long_name: str, reading: str = PRIMARY) -> Record:
    """1024 is selected when its paired query-level interval against 512 lies above zero for L2
    nDCG@10 or L3 Recall@100 and lies wholly below zero for neither; otherwise 512."""
    better = worse = False
    detail: Record = {}
    for r in rows:
        if r["name"] != long_name or r["reading"] != reading:
            continue
        if r["metric"] != LEVEL_METRIC[r["level"]]:
            continue
        detail[r["level"]] = [r["d"], r["d_q_lo"], r["d_q_hi"]]
        better |= float(r["d_q_lo"]) > 0
        worse |= float(r["d_q_hi"]) < 0
    return {"selected": 1024 if better and not worse else 512, "diff_vs_512": detail}


def write_csv(path: str, rows: list[Record]) -> None:
    """Rows as CSV with the union of their fields (first-seen order)."""
    import csv

    fields: list[str] = []
    for r in rows:
        for k in r:
            if k not in fields:
                fields.append(k)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)


__all__ = [
    "READINGS",
    "chunk_rows",
    "load_chunk_dir",
    "objective",
    "paired_rows",
    "select_best",
    "select_cut",
    "unit_rows",
    "write_csv",
]
