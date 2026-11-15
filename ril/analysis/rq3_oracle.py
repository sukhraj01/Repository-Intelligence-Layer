"""Analysis of the oracle calibration arm (RQ3, E-RQ3-ORACLE, D168). Exploratory, descriptive.

Reads stored result rows only. The unit of analysis is the instance, as in
``ril.analysis.rq3_results`` (D113): an arm's score on an instance is the fraction of its repeats
that resolve. The oracle arm has two adjacent repeats, the registered arms three; the contrasts
use each arm's own repeats (the registered form) and, as a sensitivity, the registered arms
restricted to the same first two repeats. Contrasts are estimates by the registered method (paired
difference of the mean score, paired bootstrap interval, sign-flip permutation p) with no
adjustment and no decision. The retrieval-versus-reasoning view is the oracle arm's resolved
fraction among the instances where the contexts of the registered arms contained none of the
files the gold patch modifies.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from ril.analysis.rq3_results import (
    Rows,
    any_of_k,
    bootstrap_means,
    paired_contrast,
    percentile_interval,
    score_matrix,
)

ORACLE = "oracle"
Table = list[dict[str, Any]]


def arm_scores(
    rows: Rows, instances: Sequence[str], arm: str, runs: Sequence[int], reading: str
) -> Any:
    """Per-instance score vector of one arm over its own ``runs``."""
    return score_matrix(rows, instances, [arm], runs, reading).values[:, 0]


def _contrast(
    a: Any, b: Any, first: str, second: str, label: str, reading: str, seed: int, resamples: int
) -> dict[str, Any]:
    res = paired_contrast(a, b, seed, resamples, resamples, test=reading == "exact")
    anyk = paired_contrast(any_of_k(a), any_of_k(b), seed + 7, resamples, resamples, test=False)
    return {
        "first": first,
        "second": second,
        "k_form": label,
        "reading": reading,
        "role": "exploratory_estimate",
        **res,
        "any_of_k_difference": anyk.get("difference"),
        "any_of_k_ci_low": anyk.get("ci_low"),
        "any_of_k_ci_high": anyk.get("ci_high"),
    }


def contrasts(
    rows: Rows,
    instances: Sequence[str],
    arms: Mapping[str, Sequence[int]],
    *,
    seed: int = 0,
    resamples: int = 10_000,
) -> Table:
    """oracle minus every other arm, in the registered form and at matched k, both readings.

    ``arms`` maps an arm name to its repeats; the oracle must be in it. Differences are in
    resolved-fraction units (multiply by 100 for points).
    """
    out: Table = []
    oracle_runs = tuple(arms[ORACLE])
    for reading in ("exact", "tolerant"):
        o = arm_scores(rows, instances, ORACLE, oracle_runs, reading)
        for other, runs in arms.items():
            if other == ORACLE:
                continue
            own = arm_scores(rows, instances, other, runs, reading)
            out.append(
                _contrast(
                    o,
                    own,
                    ORACLE,
                    other,
                    f"own k ({len(oracle_runs)} vs {len(runs)})",
                    reading,
                    seed + 100,
                    resamples,
                )
            )
            if tuple(runs) != oracle_runs:
                matched = arm_scores(rows, instances, other, oracle_runs, reading)
                out.append(
                    _contrast(
                        o,
                        matched,
                        ORACLE,
                        other,
                        f"matched k ({len(oracle_runs)} vs {len(oracle_runs)})",
                        reading,
                        seed + 100,
                        resamples,
                    )
                )
    return out


def arm_rows(
    rows: Rows,
    instances: Sequence[str],
    arms: Mapping[str, Sequence[int]],
    reading: str = "exact",
    seed: int = 0,
) -> Table:
    out: Table = []
    for n, (arm, runs) in enumerate(arms.items()):
        s = arm_scores(rows, instances, arm, runs, reading)
        ok = s[~np.isnan(s)]
        lo, hi = percentile_interval(bootstrap_means(ok, seed + n))
        per_run = []
        for k in runs:
            v = arm_scores(rows, instances, arm, [k], reading)
            per_run.append(float(np.nanmean(v)))
        out.append(
            {
                "arm": arm,
                "reading": reading,
                "instances": int(ok.size),
                "runs_per_instance": len(runs),
                "resolved_score": float(ok.mean()),
                "ci_low": lo,
                "ci_high": hi,
                "resolved_by_repeat": per_run,
                "any_of_k_share": float(any_of_k(ok).mean()),
            }
        )
    return out


def gold_miss(
    context_files: Mapping[str, Mapping[str, Sequence[str]]],
    gold_files: Mapping[str, Sequence[str]],
    instances: Sequence[str],
) -> dict[str, dict[str, Any]]:
    """Per instance and arm: how many gold-patch files occur among the files of the arm's context.

    ``context_files[arm][instance]`` is the file list of the arm's 8,000-token context. An arm with
    no entry for an instance is recorded as ``None`` (unknown), never as a miss.
    """
    out: dict[str, dict[str, Any]] = {}
    for iid in instances:
        want = set(gold_files.get(iid, ()))
        row: dict[str, Any] = {"n_gold_files": len(want)}
        for arm, by_inst in context_files.items():
            files = by_inst.get(iid)
            row[f"{arm}_files_in"] = None if files is None else len(want & set(files))
        out[iid] = row
    return out


def retrieval_vs_reasoning(
    rows: Rows,
    instances: Sequence[str],
    arms: Mapping[str, Sequence[int]],
    miss: Mapping[str, Mapping[str, Any]],
    sets: Mapping[str, Sequence[str]],
    *,
    seed: int = 0,
    resamples: int = 10_000,
) -> Table:
    """Per named set of registered arms: instances where none of them held any gold file.

    For each set: the number of instances, the oracle's resolved fraction and every other arm's
    on those instances, and the paired oracle-minus-arm differences as estimates. An instance with
    no gold file in the patch (n_gold_files 0) is not a miss and is left out.
    """
    out: Table = []
    index = {iid: i for i, iid in enumerate(instances)}
    for label, members in sets.items():
        chosen = [
            iid
            for iid in instances
            if miss[iid]["n_gold_files"] > 0
            and all(miss[iid].get(f"{m}_files_in") == 0 for m in members)
        ]
        row: dict[str, Any] = {
            "set": label,
            "arms_missing_all_gold": "+".join(members),
            "instances": len(chosen),
        }
        if chosen:
            sel = [index[i] for i in chosen]
            o = arm_scores(rows, instances, ORACLE, arms[ORACLE], "exact")[sel]
            row["oracle_resolved"] = float(np.nanmean(o))
            for other, runs in arms.items():
                if other == ORACLE:
                    continue
                v = arm_scores(rows, instances, other, runs, "exact")[sel]
                row[f"{other}_resolved"] = float(np.nanmean(v))
                c = paired_contrast(o, v, seed + 300, resamples, resamples, test=False)
                row[f"oracle_minus_{other}"] = c.get("difference")
                row[f"oracle_minus_{other}_ci_low"] = c.get("ci_low")
                row[f"oracle_minus_{other}_ci_high"] = c.get("ci_high")
        out.append(row)
    return out


def mdd_rows(
    mdd: Sequence[Mapping[str, Any]], rate: float = 0.4, runs: Sequence[int] = (2, 3)
) -> Table:
    """Stored minimum detectable differences (E-RQ3-RUN-AGREEMENT, N = 327) at ``rate``, for the
    given numbers of repeats, every scenario and kappa as stored (no recomputation).

    k = 2 is this arm's, k = 3 the registered arms'. A blank stored value stays blank.
    """
    keep = {int(k) for k in runs}
    return [dict(r) for r in mdd if abs(float(r["rate"]) - rate) < 1e-9 and int(r["runs"]) in keep]


def nan_to_none(x: Any) -> Any:
    if isinstance(x, float) and math.isnan(x):
        return None
    return x
