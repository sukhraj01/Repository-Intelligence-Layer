"""Encoder numbers E7: dense class-unit source form and the paired encoder comparison (exploratory).

Implements the CPU half of ``docs/EXPERIMENTS.md`` E-ENCODER-NUMBERS.

* ``form_table`` rescores the dev instances with the class-unit text in each stored form
  (``full``, ``header``): BM25 on that form (the X1 cache), the dense scores of the same texts (the
  X2 scoring already wrote ``dense_<level>__<form>``), and RRF of the two at a *fixed* k and cut per
  encoder (the dev selections of E-DENSE-FUSION; nothing is re-tuned per form). Ids, spans and gold
  are identical across forms, so only the text of class units differs.
* ``encoder_pair_rows`` gives the paired RRF(BM25, Qwen3) minus RRF(BM25, CodeRankEmbed)
  difference per gold reading and level with query-level and repository-clustered intervals, and
  the per-repository means of the difference.

Metrics are those of ``ril.evaluation.x2_eval`` (nDCG@10 at L2, Recall@100 at L3; ties by lower
index). Values are percentages; differences percentage points.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import glob
import math
import os
from collections.abc import Sequence
from typing import Any

import numpy as np

from ril.analysis.e3_tables import COLUMN, EvalTable
from ril.evaluation.e3_prepare import READINGS, read_cache
from ril.evaluation.x2_eval import _Scorer, positions, rrf_scores

Record = dict[str, Any]
Arr = np.ndarray[Any, Any]
ENCODERS_FIXED: dict[str, tuple[str, int]] = {
    "coderankembed": ("coderankembed__t1024", 100),
    "qwen3-embedding-0.6b": ("qwen3-embedding-0.6b__t512", 20),
}
"""Variant and RRF k per encoder: the dev selections of E-DENSE-FUSION."""


def form_keys(encoder: str, form: str) -> list[str]:
    """Key names written for one encoder and class form."""
    return [f"bm25|{form}", f"dense|{encoder}|{form}", f"rrf|{encoder}|{form}"]


def form_table(
    e3_cache: str,
    x1_cache: str,
    dense_root: str,
    role: str,
    forms: Sequence[str] = ("full", "header"),
) -> EvalTable:
    """Metric tensor of every (instance, level) of ``role`` for each form and encoder."""
    keys: list[str] = []
    for f in forms:
        keys.append(f"bm25|{f}")
        for enc in ENCODERS_FIXED:
            keys += [f"dense|{enc}|{f}", f"rrf|{enc}|{f}"]
    rows: list[Record] = []
    blocks: list[Arr] = []
    for path in sorted(glob.glob(os.path.join(e3_cache, "*.npz"))):
        arrays, meta = read_cache(path)
        if meta["role"] != role:
            continue
        name = os.path.basename(path)
        x1, x1meta = read_cache(os.path.join(x1_cache, name))
        n = int(meta["units"])
        if int(x1meta["units"]) != n:
            raise ValueError(f"{name}: unit counts differ between the E3 and X1 caches")
        dense: dict[str, dict[str, Arr]] = {}
        for enc, (variant, _) in ENCODERS_FIXED.items():
            with np.load(os.path.join(dense_root, variant, name), allow_pickle=False) as dz:
                dense[enc] = {k: dz[k] for k in dz.files if k.startswith("dense_")}
        for level in meta["levels"]:
            golds = {r: arrays[f"gold_{level}_{r}"] for r in READINGS}
            if not any(len(g) for g in golds.values()):
                continue
            if not np.array_equal(x1[f"scores_{level}_full"], arrays[f"scores_{level}"]):
                raise ValueError(f"{name}: X1 full BM25 differs from the E3 cache")
            sc = _Scorer(golds)
            for f in forms:
                bm = x1[f"scores_{level}_{f}"].astype(np.float64)
                sc.add(f"bm25|{f}", bm)
                pb = positions(bm)
                for enc, (_, k) in ENCODERS_FIXED.items():
                    dk = f"dense_{level}" if f == "full" else f"dense_{level}__{f}"
                    d = dense[enc][dk].astype(np.float64)
                    if len(d) != n:
                        raise ValueError(f"{name}: dense scores have {len(d)} units, cache {n}")
                    sc.add(f"dense|{enc}|{f}", d)
                    sc.add(f"rrf|{enc}|{f}", rrf_scores([pb, positions(d)], k))
            if sc.keys != keys:
                raise RuntimeError("key order")
            rows.append(
                {
                    "instance": meta["instance"],
                    "level": level,
                    "repo": meta["repo_id"],
                    "role": meta["role"],
                    "dataset": meta["dataset"],
                    "folder": meta["folder"],
                    "units": n,
                    "gold_units": int(len(golds["units"])),
                }
            )
            blocks.append(np.asarray(sc.rows, dtype=np.float64))
    return EvalTable(
        keys,
        {k: i for i, k in enumerate(keys)},
        rows,
        np.stack(blocks),
        [],
        np.zeros((len(rows), 0, 1 + len(READINGS))),
    )


def per_repo_diff(
    tab: EvalTable, group: str, a: str, b: str, level: str, reading: str, metric: str
) -> list[Record]:
    """Per-repository mean of ``a - b`` (points) for one level, reading and metric."""
    col = COLUMN[(reading, metric)]
    mat = tab.metrics[:, [tab.index[a], tab.index[b]], col]
    lm = np.asarray([r["level"] == level for r in tab.rows]) & tab.mask(role=group)
    sel = np.flatnonzero(lm & ~np.isnan(mat).any(axis=1))
    by: dict[str, list[float]] = {}
    for i in sel:
        by.setdefault(tab.rows[i]["repo"], []).append(100 * float(mat[i, 0] - mat[i, 1]))
    return [
        {
            "group": group,
            "level": level,
            "reading": reading,
            "metric": metric,
            "repo": r,
            "queries": len(v),
            "d": round(float(np.mean(v)), 2),
        }
        for r, v in sorted(by.items())
    ]


def finite(x: float) -> bool:
    """Whether ``x`` is a finite number."""
    return not (math.isnan(x) or math.isinf(x))
