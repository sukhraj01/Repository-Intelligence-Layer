"""Analysis of RQ3 result rows. Implements ``docs/RQ3_PILOT.md`` (D113).

Unit of analysis: the instance. An arm's score on an instance is the fraction of its ``k`` runs
that resolve; an unusable reply, an edit set that does not apply and an executed patch that leaves
tests failing all count as unresolved (D109, D110). Primary contrast: one named pair of arms
(RAW against the untrained encoder) on the confirmatory instances, as the paired difference in mean
score with a paired bootstrap interval over instances and a paired sign-flip permutation test; every
other contrast is an estimate with an interval and no test. Both patch readings are tabulated
(exact primary, tolerant sensitivity). Resamples use a fixed seed.

Secondary reading (D121, exploratory): beside the mean resolved fraction every arm reports the
any-of-k resolved share, the share of instances with at least one resolving run among their ``k``
(no extra calls), with a bootstrap interval over instances, and every contrast carries the paired
difference of that share as an estimate. It is labelled secondary and exploratory (``SECONDARY``)
and never enters the primary contrast or its test.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt

Rows = Sequence[Mapping[str, Any]]
Arr = npt.NDArray[np.float64]
Table = list[dict[str, Any]]

READINGS = ("exact", "tolerant")
BOOTSTRAP_RESAMPLES = 10_000
PERMUTATIONS = 10_000
SECONDARY = "secondary_exploratory"
OUTCOME_CLASSES = ("resolved", "executed_unresolved", "apply_failed", "unusable", "exec_error")


def outcome_group(outcome: str) -> str:
    """``apply_failed:no_match`` -> ``apply_failed``, ``exec_error:x`` -> ``exec_error``."""
    return outcome.split(":", 1)[0]


def latest(rows: Rows) -> list[Mapping[str, Any]]:
    """The last row of each (instance, arm, run); a rerun of an ``exec_error`` replaces it."""
    last: dict[tuple[str, str, int], Mapping[str, Any]] = {}
    for r in rows:
        last[(str(r["instance_id"]), str(r["arm"]), int(r["run"]))] = r
    return [last[k] for k in sorted(last)]


def resolved_flag(row: Mapping[str, Any], reading: str) -> bool:
    return bool(row["resolved" if reading == "exact" else "resolved_tolerant"])


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float, float]:
    """(share, low, high) Wilson interval; (nan, nan, nan) for n = 0."""
    if n == 0:
        return math.nan, math.nan, math.nan
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, max(0.0, centre - half), min(1.0, centre + half)


@dataclass(frozen=True)
class Scores:
    """Per-instance score matrix: ``values[i, a]`` for ``instances[i]`` and ``arms[a]``."""

    instances: tuple[str, ...]
    arms: tuple[str, ...]
    values: Arr
    runs: dict[str, int]
    missing: list[tuple[str, str, int]]


def score_matrix(
    rows: Rows,
    instances: Sequence[str],
    arms: Sequence[str],
    runs: Sequence[int],
    reading: str = "exact",
) -> Scores:
    """Fraction of ``runs`` that resolve per (instance, arm). A (instance, arm, run) with no row is
    listed in ``missing`` and left out of that fraction; an instance with no run of an arm at all
    has score ``nan``."""
    got = {(str(r["instance_id"]), str(r["arm"]), int(r["run"])): r for r in latest(rows)}
    values = np.full((len(instances), len(arms)), math.nan)
    missing: list[tuple[str, str, int]] = []
    for i, iid in enumerate(instances):
        for a, arm in enumerate(arms):
            flags = []
            for k in runs:
                row = got.get((iid, arm, k))
                if row is None:
                    missing.append((iid, arm, k))
                else:
                    flags.append(resolved_flag(row, reading))
            if flags:
                values[i, a] = sum(flags) / len(flags)
    return Scores(tuple(instances), tuple(arms), values, {arm: len(runs) for arm in arms}, missing)


def bootstrap_means(x: Arr, seed: int, resamples: int = BOOTSTRAP_RESAMPLES) -> Arr:
    """Means of ``resamples`` resamples of the entries of ``x`` (rows of ``x`` are resampled
    together when ``x`` is two-dimensional)."""
    rng = np.random.default_rng(seed)
    n = x.shape[0]
    out = np.empty((resamples,) + x.shape[1:])
    step = max(1, 2_000_000 // max(n, 1))
    for lo in range(0, resamples, step):
        hi = min(resamples, lo + step)
        idx = rng.integers(0, n, size=(hi - lo, n))
        out[lo:hi] = x[idx].mean(axis=1)
    return out


def percentile_interval(means: Arr, level: float = 0.95) -> tuple[float, float]:
    a = (1 - level) / 2
    return float(np.quantile(means, a)), float(np.quantile(means, 1 - a))


def sign_flip_p(d: Arr, seed: int, permutations: int = PERMUTATIONS) -> float:
    """Two-sided paired sign-flip permutation p-value of the mean of ``d`` (Monte Carlo, with the
    observed statistic counted among the permutations)."""
    rng = np.random.default_rng(seed)
    n = d.shape[0]
    observed = abs(float(d.mean()))
    hits = 0
    step = max(1, 2_000_000 // max(n, 1))
    for lo in range(0, permutations, step):
        hi = min(permutations, lo + step)
        signs = rng.integers(0, 2, size=(hi - lo, n)) * 2.0 - 1.0
        stats = np.abs(signs @ d) / n
        hits += int(np.sum(stats >= observed - 1e-12))
    return (hits + 1) / (permutations + 1)


def paired_contrast(
    a: Arr,
    b: Arr,
    seed: int,
    resamples: int = BOOTSTRAP_RESAMPLES,
    permutations: int = PERMUTATIONS,
    test: bool = False,
) -> dict[str, Any]:
    """Difference ``mean(a) - mean(b)`` over paired instances with a bootstrap interval; the
    permutation p-value only when ``test`` is set (the one primary contrast)."""
    ok = ~(np.isnan(a) | np.isnan(b))
    d = (a - b)[ok]
    out: dict[str, Any] = {
        "n_pairs": int(ok.sum()),
        "mean_a": float(a[ok].mean()) if ok.any() else math.nan,
        "mean_b": float(b[ok].mean()) if ok.any() else math.nan,
        "difference": float(d.mean()) if ok.any() else math.nan,
    }
    if ok.any():
        lo, hi = percentile_interval(bootstrap_means(d, seed, resamples))
        out["ci_low"], out["ci_high"] = lo, hi
        out["p_permutation"] = sign_flip_p(d, seed + 1, permutations) if test else None
    return out


def any_of_k(col: Arr) -> Arr:
    """1.0 where at least one run of the instance resolved, 0.0 where none did, ``nan`` kept.
    An instance with a missing run counts only its stored runs (they are listed in ``missing``)."""
    out = np.where(col > 0, 1.0, 0.0)
    out[np.isnan(col)] = math.nan
    return out


def arm_table(scores: Scores, seed: int, reading: str) -> Table:
    table: Table = []
    for a, arm in enumerate(scores.arms):
        col = scores.values[:, a]
        ok = col[~np.isnan(col)]
        row: dict[str, Any] = {
            "arm": arm,
            "reading": reading,
            "instances": int(ok.size),
            "runs_per_instance": scores.runs[arm],
        }
        if ok.size:
            lo, hi = percentile_interval(bootstrap_means(ok, seed + a))
            row.update(resolved_score=float(ok.mean()), ci_low=lo, ci_high=hi)
            anyk = any_of_k(ok)
            alo, ahi = percentile_interval(bootstrap_means(anyk, seed + a + 1000))
            row.update(
                any_of_k_share=float(anyk.mean()),
                any_of_k_ci_low=alo,
                any_of_k_ci_high=ahi,
                any_of_k_status=SECONDARY,
            )
        table.append(row)
    return table


def _secondary_contrast(a: Arr, b: Arr, seed: int, resamples: int) -> dict[str, Any]:
    """Paired difference of the any-of-k shares with an interval and no test (D121)."""
    res = paired_contrast(any_of_k(a), any_of_k(b), seed, resamples, test=False)
    return {
        "any_of_k_difference": res["difference"],
        "any_of_k_ci_low": res.get("ci_low", math.nan),
        "any_of_k_ci_high": res.get("ci_high", math.nan),
        "any_of_k_status": SECONDARY,
    }


def discordance(a: Arr, b: Arr) -> dict[str, Any]:
    """Counts of instances resolved by both, only the first, only the second, neither, at the two
    levels ``any`` (some run resolves) and ``all`` (every run resolves)."""
    ok = ~(np.isnan(a) | np.isnan(b))
    out: dict[str, Any] = {"n_pairs": int(ok.sum())}
    for level, ra, rb in (("any", a[ok] > 0, b[ok] > 0), ("all", a[ok] >= 1.0, b[ok] >= 1.0)):
        out[f"{level}_both"] = int(np.sum(ra & rb))
        out[f"{level}_only_first"] = int(np.sum(ra & ~rb))
        out[f"{level}_only_second"] = int(np.sum(~ra & rb))
        out[f"{level}_neither"] = int(np.sum(~ra & ~rb))
        n = max(1, int(ok.sum()))
        out[f"{level}_discordance"] = (out[f"{level}_only_first"] + out[f"{level}_only_second"]) / n
    return out


def outcome_table(
    rows: Rows, instances: Sequence[str], repo_of: Mapping[str, str], by_repo: bool
) -> Table:
    """Shares of each outcome class by arm (and repository), both readings, Wilson intervals."""
    keep = set(instances)
    latest_rows = [r for r in latest(rows) if str(r["instance_id"]) in keep]
    cells: dict[tuple[str, str, str], Counter[str]] = {}
    for r in latest_rows:
        repos = ["all"] + ([repo_of.get(str(r["instance_id"]), "unknown")] if by_repo else [])
        for reading in READINGS:
            key = "outcome" if reading == "exact" else "outcome_tolerant"
            group = outcome_group(str(r[key]))
            for repo in repos:
                cells.setdefault((str(r["arm"]), repo, reading), Counter())[group] += 1
    table: Table = []
    for (arm, repo, reading), counts in sorted(cells.items()):
        n = sum(counts.values())
        row: dict[str, Any] = {"arm": arm, "repository": repo, "reading": reading, "runs": n}
        for cls in OUTCOME_CLASSES:
            share, lo, hi = wilson(counts.get(cls, 0), n)
            row[f"{cls}_n"] = counts.get(cls, 0)
            row[f"{cls}_share"] = share
            row[f"{cls}_low"] = lo
            row[f"{cls}_high"] = hi
        usable = n - counts.get("unusable", 0)
        row["resolved_among_usable"] = counts.get("resolved", 0) / usable if usable else math.nan
        table.append(row)
    return table


def apply_failure_classes(rows: Rows, instances: Sequence[str]) -> Table:
    """Runs by exact-reading apply-failure class and arm."""
    keep = set(instances)
    counts: Counter[tuple[str, str]] = Counter()
    for r in latest(rows):
        if str(r["instance_id"]) in keep and str(r["outcome"]).startswith("apply_failed"):
            counts[(str(r["arm"]), str(r["outcome"]))] += 1
    return [{"arm": arm, "class": cls, "runs": n} for (arm, cls), n in sorted(counts.items())]


def repository_scores(
    rows: Rows,
    instances: Sequence[str],
    repo_of: Mapping[str, str],
    arms: Sequence[str],
    runs: Sequence[int],
    reading: str,
) -> Table:
    """Mean score by repository and arm (no interval: repositories have few instances)."""
    s = score_matrix(rows, instances, arms, runs, reading)
    table: Table = []
    for repo in sorted({repo_of.get(i, "unknown") for i in instances}):
        idx = [k for k, i in enumerate(instances) if repo_of.get(i, "unknown") == repo]
        for a, arm in enumerate(arms):
            col = s.values[idx, a]
            ok = col[~np.isnan(col)]
            table.append(
                {
                    "repository": repo,
                    "arm": arm,
                    "reading": reading,
                    "instances": int(ok.size),
                    "resolved_score": float(ok.mean()) if ok.size else math.nan,
                }
            )
    return table


@dataclass(frozen=True)
class Plan:
    """What is compared: the arms, the one primary pair, the other estimates, the runs."""

    arms: tuple[str, ...]
    primary: tuple[str, str]
    estimates: tuple[tuple[str, str], ...]
    runs: tuple[int, ...]
    seed: int = 0


def analyse(
    rows: Rows,
    instances: Sequence[str],
    repo_of: Mapping[str, str],
    plan: Plan,
    resamples: int = BOOTSTRAP_RESAMPLES,
    permutations: int = PERMUTATIONS,
) -> dict[str, Table]:
    """All tables of D113 for the given (confirmatory) instances."""
    tables: dict[str, Table] = {"arms": [], "contrasts": [], "discordance": [], "repository": []}
    keep = set(instances)
    pending = [
        {"instance_id": r["instance_id"], "arm": r["arm"], "run": r["run"], "outcome": r["outcome"]}
        for r in latest(rows)
        if str(r["instance_id"]) in keep and str(r["outcome"]).startswith("exec_error")
    ]
    tables["exec_errors"] = pending
    for reading in READINGS:
        s = score_matrix(rows, instances, plan.arms, plan.runs, reading)
        tables["arms"] += arm_table(s, plan.seed, reading)
        tables["repository"] += repository_scores(
            rows, instances, repo_of, plan.arms, plan.runs, reading
        )
        col = {arm: s.values[:, k] for k, arm in enumerate(plan.arms)}
        pairs = [(plan.primary, True)] + [(p, False) for p in plan.estimates if p != plan.primary]
        for (first, second), primary in pairs:
            res = paired_contrast(
                col[first],
                col[second],
                plan.seed + 100,
                resamples,
                permutations,
                test=primary and reading == "exact",
            )
            tables["contrasts"].append(
                {
                    "first": first,
                    "second": second,
                    "reading": reading,
                    "role": "primary" if primary else "estimate",
                    **res,
                    **_secondary_contrast(col[first], col[second], plan.seed + 200, resamples),
                }
            )
            tables["discordance"].append(
                {"first": first, "second": second, "reading": reading}
                | discordance(col[first], col[second])
            )
        if reading == "exact":
            tables["missing"] = [{"instance_id": i, "arm": a, "run": k} for i, a, k in s.missing]
    tables["outcomes"] = outcome_table(rows, instances, repo_of, by_repo=False)
    tables["outcomes_by_repository"] = outcome_table(rows, instances, repo_of, by_repo=True)
    tables["apply_failure_classes"] = apply_failure_classes(rows, instances)
    return tables
