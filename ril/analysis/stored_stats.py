"""Statistics for the stored-output analysis (E-STORED-ANALYSIS; exploratory, numpy only).

Four groups, all on aligned per-query arrays (see ``ril.analysis.stored_rows``):

* ``components`` / ``minimum_detectable``: method-of-moments variance components of a nested
  layout (repository, query within repository, seed crossed with query) and the minimum
  detectable difference at k seeds that follows from them;
* ``slice_gain``: mean per-query difference by slice with a repository-cluster bootstrap;
* ``complementarity``: per-query winners, the share of queries where the best other arm beats a
  reference by a threshold, and best-of-arms oracles (upper bounds, not methods);
* ``concentration``: how much of a total loss the worst queries carry.

Implements docs/experiments/B.md "E-STORED-ANALYSIS".
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]
Record = dict[str, Any]
Z_POWER = 1.959964 + 0.841621
"""z(0.975) + z(0.80): two-sided 5% test with 80% power (as in ``t5_tables``)."""
TIE = 1e-9


def repo_index(repos: Sequence[str]) -> IntArray:
    """Integer code per query for its repository (sorted names, stable)."""
    names = sorted(set(repos))
    code = {n: i for i, n in enumerate(names)}
    return np.array([code[r] for r in repos], dtype=np.int64)


def components(y: FloatArray, repo: IntArray) -> Record:
    """Variance components of ``y`` (seeds x queries) by moments; negative estimates become 0.

    ``s2_seedquery``: variance between seeds within a query. ``s2_query``: between queries within
    a repository (query means over seeds, minus ``s2_seedquery / S``). ``s2_repo``: between
    repositories (unbalanced layout, ``n0`` of the one-way random-effects ANOVA). ``s2_seed``:
    variance of the run means across seeds, minus ``s2_seedquery / n`` (needs S >= 2).
    ``seed_var_direct`` is the unadjusted variance of the run means (the quantity the earlier
    tables call the seed SD, squared). ``flags`` lists estimates that were negative.
    """
    s_n, n = y.shape
    flags: list[str] = []
    qm = y.mean(axis=0)
    s2_sq = float(((y - qm) ** 2).sum() / (n * (s_n - 1))) if s_n > 1 else math.nan
    codes = np.unique(repo)
    r_n = len(codes)
    ms_w = math.nan
    ms_b = math.nan
    n0 = math.nan
    s2_query = math.nan
    s2_repo = math.nan
    if n > r_n:
        grand = float(qm.mean())
        rm = np.array([qm[repo == c].mean() for c in codes])
        nr = np.array([(repo == c).sum() for c in codes], dtype=np.float64)
        ms_w = float(
            sum(((qm[repo == c] - rm[i]) ** 2).sum() for i, c in enumerate(codes)) / (n - r_n)
        )
        corr = s2_sq / s_n if s_n > 1 else 0.0
        s2_query = ms_w - corr
        if s2_query < 0:
            flags.append("s2_query<0")
            s2_query = 0.0
        if r_n > 1:
            ms_b = float((nr * (rm - grand) ** 2).sum() / (r_n - 1))
            n0 = float((n - (nr**2).sum() / n) / (r_n - 1))
            s2_repo = (ms_b - ms_w) / n0
            if s2_repo < 0:
                flags.append("s2_repo<0")
                s2_repo = 0.0
    seed_var = math.nan
    s2_seed = math.nan
    if s_n > 1:
        seed_var = float(y.mean(axis=1).var(ddof=1))
        s2_seed = seed_var - s2_sq / n
        if s2_seed < 0:
            flags.append("s2_seed<0")
            s2_seed = 0.0
    return {
        "n": n,
        "repos": r_n,
        "seeds": s_n,
        "s2_repo": s2_repo,
        "s2_query": s2_query,
        "s2_seedquery": s2_sq,
        "s2_seed": s2_seed,
        "seed_var_direct": seed_var,
        "flags": flags,
    }


def mean_components(parts: Sequence[Record]) -> Record:
    """Average of several components records (pooling cells), NaN-aware."""
    keys = ("s2_repo", "s2_query", "s2_seedquery", "s2_seed", "seed_var_direct")
    out: Record = {k: float(np.nanmean([p[k] for p in parts])) if parts else math.nan for k in keys}
    out["n"] = parts[0]["n"] if parts else 0
    out["repos"] = parts[0]["repos"] if parts else 0
    return out


def minimum_detectable(c: Record, seeds: int, with_repo: bool = True) -> float:
    """Minimum detectable paired difference at ``seeds`` seeds per arm (5% two-sided, 80% power).

    ``Z * sqrt(s2_repo / R + s2_query / n + (s2_seedquery / n + s2_seed) / k)`` on the per-query
    differences between two arms; the repository term is dropped for ``with_repo=False`` (the
    query-level reading of the earlier L3 intervals). The seed terms shrink with k, the
    query terms do not.
    """
    n, r_n = float(c["n"]), float(c["repos"])
    var = c["s2_query"] / n + (c["s2_seedquery"] / n + c["s2_seed"]) / seeds
    if with_repo and r_n > 1:
        var += c["s2_repo"] / r_n
    return Z_POWER * math.sqrt(var) if var == var and var >= 0 else math.nan


def old_style_seed_mdd(seed_vars: Sequence[float], seeds: int) -> tuple[float, float]:
    """The earlier tables' seed bound: pooled SD of run means and ``Z * SD * sqrt(2 / k)``."""
    sd = math.sqrt(float(np.nanmean(seed_vars)))
    return sd, Z_POWER * sd * math.sqrt(2.0 / seeds)


def cluster_resample(repo: IntArray, rng: np.random.Generator) -> IntArray:
    """Query indices of a bootstrap draw that resamples whole repositories with replacement."""
    codes = np.unique(repo)
    pick = rng.choice(codes, size=len(codes), replace=True)
    return np.concatenate([np.flatnonzero(repo == c) for c in pick])


def interval(values: Sequence[float]) -> tuple[float, float]:
    """95% percentile interval over finite draws (NaN when fewer than 20 finite draws)."""
    v = np.array([x for x in values if x == x], dtype=np.float64)
    if len(v) < 20:
        return math.nan, math.nan
    return float(np.quantile(v, 0.025)), float(np.quantile(v, 0.975))


def bootstrap(
    repo: IntArray,
    stat: Callable[[IntArray], float],
    draws: int,
    seed: int,
    clustered: bool = True,
) -> tuple[float, float]:
    """Interval of ``stat(query indices)``: repository-cluster resampling, or queries resampled
    independently (``clustered=False``, the L3 convention of the earlier tables: with two
    repositories the cluster bootstrap has only three distinct resamples)."""
    rng = np.random.default_rng(seed)
    out: list[float] = []
    for _ in range(draws):
        idx = (
            cluster_resample(repo, rng)
            if clustered
            else rng.choice(len(repo), size=len(repo), replace=True)
        )
        out.append(stat(idx))
    return interval(out)


def bootstrap_within(
    mask: npt.NDArray[np.bool_], stat: Callable[[IntArray], float], draws: int, seed: int
) -> tuple[float, float]:
    """Interval of ``stat`` over queries resampled with replacement inside ``mask``."""
    rng = np.random.default_rng(seed)
    pool = np.flatnonzero(mask)
    if len(pool) == 0:
        return math.nan, math.nan
    return interval([stat(rng.choice(pool, size=len(pool), replace=True)) for _ in range(draws)])


def slice_gain(
    gain: FloatArray,
    repo: IntArray,
    labels: Mapping[str, npt.NDArray[np.bool_]],
    draws: int,
    seed: int,
    stratum: bool = False,
    clustered: bool = True,
) -> list[Record]:
    """Mean of ``gain`` per slice (mask), with a cluster bootstrap over repositories.

    A draw in which the slice is empty is dropped. With ``stratum=True`` (slices that are
    repositories) the bootstrap resamples queries inside the slice instead. The overall mean is
    added as the first row. ``repos_in_slice`` counts distinct repositories.
    """
    rows: list[Record] = []
    every = np.ones(len(gain), dtype=bool)
    for name, mask in [("all", every), *labels.items()]:
        if not mask.any():
            continue

        def stat(idx: IntArray, mask: npt.NDArray[np.bool_] = mask) -> float:
            m = mask[idx]
            return float(gain[idx][m].mean()) if m.any() else math.nan

        if stratum and name != "all":
            lo, hi = bootstrap_within(mask, lambda idx: float(gain[idx].mean()), draws, seed)
        else:
            lo, hi = bootstrap(repo, stat, draws, seed, clustered)
        rows.append(
            {
                "slice": name,
                "queries": int(mask.sum()),
                "repos_in_slice": int(len(np.unique(repo[mask]))),
                "mean_gain": float(gain[mask].mean()),
                "lo": lo,
                "hi": hi,
                "share_positive": float((gain[mask] > TIE).mean()),
                "share_negative": float((gain[mask] < -TIE).mean()),
                "share_zero": float((np.abs(gain[mask]) <= TIE).mean()),
            }
        )
    return rows


def quartile_bins(values: FloatArray) -> list[tuple[str, npt.NDArray[np.bool_]]]:
    """Bins by quartile of ``values`` (right-closed; cut points merged where they coincide)."""
    cuts = sorted({float(q) for q in np.quantile(values, [0.25, 0.5, 0.75])})
    edges = [-math.inf, *cuts, math.inf]
    out: list[tuple[str, npt.NDArray[np.bool_]]] = []
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        m = (values > lo) & (values <= hi)
        if m.any():
            label = (
                f"<={hi:g}"
                if lo == -math.inf
                else (f">{lo:g}" if hi == math.inf else f"({lo:g},{hi:g}]")
            )
            out.append((label, m))
    return out


def complementarity(
    arms: Mapping[str, FloatArray],
    reference: str,
    thresholds: Sequence[float],
) -> Record:
    """Winners, margin shares and the best-of-arms oracle for per-query arm values (1-D each).

    ``wins`` counts the arm with the strictly largest value; queries where the top two are within
    ``TIE`` are counted in ``ties``. ``share_best_other_beats_ref[t]``: share of queries where the
    best arm other than ``reference`` exceeds it by more than ``t``. ``oracle`` is the mean of the
    per-query maximum over all arms: an upper bound that no deployable method reaches.
    """
    names = list(arms)
    m = np.vstack([arms[a] for a in names])
    top = m.max(axis=0)
    n_top = (m >= top - TIE).sum(axis=0)
    wins = {a: int(((m[i] >= top - TIE) & (n_top == 1)).sum()) for i, a in enumerate(names)}
    others = np.vstack([arms[a] for a in names if a != reference])
    margin = others.max(axis=0) - arms[reference]
    return {
        "queries": int(m.shape[1]),
        "wins": wins,
        "ties": int((n_top > 1).sum()),
        "share_best_other_beats_ref": {f"{t:g}": float((margin > t).mean()) for t in thresholds},
        "reference_mean": float(arms[reference].mean()),
        "oracle_mean": float(top.mean()),
        "oracle_minus_reference": float(top.mean() - arms[reference].mean()),
    }


def concentration(loss: FloatArray, fractions: Sequence[float]) -> Record:
    """Share of the total loss (and of the positive loss mass) carried by the worst fractions."""
    order = np.sort(loss)[::-1]
    total = float(loss.sum())
    pos = float(loss[loss > 0].sum())
    out: Record = {"total_loss": total, "positive_mass": pos}
    for f in fractions:
        k = max(1, int(math.ceil(f * len(loss))))
        top = float(order[:k].sum())
        out[f"share_total_{f:g}"] = top / total if total > TIE else math.nan
        out[f"share_positive_mass_{f:g}"] = (
            float(order[:k][order[:k] > 0].sum()) / pos if pos > TIE else math.nan
        )
    return out


def mean_stat(v: FloatArray) -> Callable[[IntArray], float]:
    """Statistic: mean of ``v`` over the drawn queries."""
    return lambda idx: float(v[idx].mean())


def share_stat(v: FloatArray, threshold: float) -> Callable[[IntArray], float]:
    """Statistic: share of drawn queries with ``v`` above ``threshold`` (strictly)."""
    return lambda idx: float((v[idx] > threshold).mean())


def concentration_stat(vec: FloatArray, fraction: float, key: str) -> Callable[[IntArray], float]:
    """Statistic: one entry of ``concentration`` on the drawn queries."""
    return lambda idx: float(concentration(vec[idx], [fraction])[key])
