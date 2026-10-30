"""Shared retrieval statistics and minimum-detectable-effect calculations.

Implements the power part of ``docs/EXPERIMENTS.md`` (E-POWER) and the "RQ3 power" rule of its
pre-registered interpretation section. Numbers only: nothing here chooses a design. Every function
takes its assumptions as arguments and the table builders record them.

Models (all two-sided, alpha 0.05 unless stated):

* **Paired binary outcome (resolved or not), exact McNemar.** n instances, two conditions.
  ``d`` is the probability that the two conditions disagree on an instance (discordance), ``e`` the
  difference in resolved rate (second minus first). Then P(only second resolves) = (d + e) / 2 and
  P(only first resolves) = (d - e) / 2. The test is conditional on the number m of disagreeing
  instances: the count won by the second condition is Binomial(m, 1/2) under the null, and the
  p-value is min(1, 2 * P(X <= min(b, m - b))) (the doubled-tail exact test). The baseline resolved
  rate does not enter the power; it only limits which (d, e) pairs exist (:func:`feasible`).
* **Run-to-run noise.** The resolved rate of one full pass of a condition varies between passes
  with standard deviation ``sigma`` (percentage points). Averaging r passes per condition leaves a
  difference of means with standard deviation ``sigma * sqrt(2 / r)``; the normal-approximation
  minimum detectable effect is ``(z_{1-alpha/2} + z_{power}) * sigma * sqrt(2 / r)``.
* **Paired bootstrap of a per-query metric (nDCG@10).** Per-query scores of two systems have the
  same standard deviation ``sd`` and correlation ``rho``; the paired difference then has standard
  deviation ``sd * sqrt(2 * (1 - rho))``. The percentile bootstrap interval of the mean difference
  excludes zero at about ``z_{1-alpha/2} * sd_diff / sqrt(n)``; the minimum detectable difference at
  a power target adds ``z_{power}``. Scores are treated as normal; the bootstrap is checked by
  simulation (:func:`simulate_bootstrap_power`).
* **Seeds.** A comparison of two arms with ``k`` training seeds each by a two-sample t-test (equal
  variance, df = 2k - 2) or a paired t-test across shared seeds (df = k - 1, per-seed correlation
  rho), with the seed-to-seed standard deviation ``s`` in the metric. The minimum detectable
  difference is reported in units
  of ``s`` and found by simulation.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from functools import cache
from statistics import NormalDist
from typing import Any

import numpy as np
import numpy.typing as npt

POWER_VERSION = "power/v1"
ALPHA = 0.05
POWER_TARGET = 0.80


def _log_pmf(k: int, m: int, q: float) -> float:
    """log of the Binomial(m, q) probability of k, with the q in {0, 1} edge cases."""
    if k < 0 or k > m:
        return -math.inf
    if q <= 0.0:
        return 0.0 if k == 0 else -math.inf
    if q >= 1.0:
        return 0.0 if k == m else -math.inf
    return (
        math.lgamma(m + 1)
        - math.lgamma(k + 1)
        - math.lgamma(m - k + 1)
        + k * math.log(q)
        + (m - k) * math.log1p(-q)
    )


def binom_cdf(k: int, m: int, q: float) -> float:
    """P(X <= k) for X ~ Binomial(m, q)."""
    if k < 0:
        return 0.0
    if k >= m:
        return 1.0
    return min(1.0, sum(math.exp(_log_pmf(i, m, q)) for i in range(k + 1)))


@cache
def critical_value(m: int, alpha: float = ALPHA) -> int:
    """Largest ``c`` with 2 * P(X <= c) <= alpha for X ~ Binomial(m, 1/2); -1 if none.

    The exact test rejects when ``min(b, m - b) <= c``, ``b`` being the count won by one side.
    """
    c = -1
    cum = 0.0
    for k in range(m // 2 + 1):
        cum += math.exp(_log_pmf(k, m, 0.5))
        if 2.0 * cum <= alpha + 1e-12:
            c = k
        else:
            break
    return c


def exact_mcnemar_p(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value from the discordant counts (doubled tail, capped at 1)."""
    if any(isinstance(x, bool) or not isinstance(x, (int, np.integer)) or x < 0 for x in (b, c)):
        raise ValueError("counts must be non-negative integers")
    m = b + c
    if m == 0:
        return 1.0
    return min(1.0, 2.0 * binom_cdf(min(b, c), m, 0.5))


def discordant_probs(d: float, e: float) -> tuple[float, float]:
    """(P(only second resolves), P(only first resolves)) for discordance ``d`` and effect ``e``."""
    if not math.isfinite(d) or not math.isfinite(e) or d < 0 or d > 1:
        raise ValueError("discordance must be in [0, 1]")
    if abs(e) > d + 1e-12:
        raise ValueError("effect cannot exceed discordance")
    return (d + e) / 2.0, (d - e) / 2.0


def feasible(baseline: float, d: float, e: float) -> bool:
    """Whether a joint distribution with the given baseline rate, discordance and effect exists.

    With first-condition rate ``baseline``: P(only first) <= baseline and P(only second) <= 1 -
    baseline, and the second rate ``baseline + e`` must lie in [0, 1].
    """
    if abs(e) > d + 1e-12 or not 0.0 <= baseline + e <= 1.0:
        return False
    p_second, p_first = discordant_probs(d, e)
    return p_first <= baseline + 1e-12 and p_second <= 1.0 - baseline + 1e-12


def mcnemar_power(n: int, d: float, e: float, alpha: float = ALPHA) -> float:
    """Exact power of the two-sided exact McNemar test (see module docstring)."""
    if isinstance(n, bool) or not isinstance(n, (int, np.integer)) or n <= 0:
        raise ValueError("n must be a positive integer")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be in (0, 1)")
    p_second, p_first = discordant_probs(d, e)
    if d == 0.0:
        return 0.0
    q = p_second / d
    total = 0.0
    sd = math.sqrt(n * d * (1 - d))
    lo = max(0, int(n * d - 9 * sd))
    hi = min(n, int(n * d + 9 * sd) + 1)
    for m in range(lo, hi + 1):
        w = math.exp(_log_pmf(m, n, d))
        if w < 1e-18:
            continue
        c = critical_value(m, alpha)
        if c < 0:
            continue
        reject = binom_cdf(c, m, q) + (1.0 - binom_cdf(m - c - 1, m, q))
        total += w * reject
    return min(1.0, total)


def mde_mcnemar(
    n: int,
    d: float,
    alpha: float = ALPHA,
    target: float = POWER_TARGET,
    step: float = 0.0025,
) -> float | None:
    """Smallest effect on a ``step`` grid from which power stays at least ``target`` up to ``d``.

    The exact test is conservative and its power is not monotone in the effect (it saws with the
    discrete rejection region), so the first grid value is taken after which power never drops
    below the target again. ``None`` if even ``e = d`` does not reach it.
    """
    # Validate even when the grid is empty. Measured discordance is usually not grid aligned.
    mcnemar_power(n, d, 0.0, alpha)
    if not math.isfinite(step) or step <= 0 or not 0 < target < 1:
        raise ValueError("step must be finite and positive; target in (0, 1)")
    if d == 0:
        return None
    grid = [round(i * step, 10) for i in range(1, int(math.floor(d / step + 1e-10)) + 1)]
    grid = [e for e in grid if e <= d]
    if not grid or abs(grid[-1] - d) > 1e-10:
        grid.append(d)
    powers = [mcnemar_power(n, d, e, alpha) for e in grid]
    last_bad = -1
    for i, p in enumerate(powers):
        if p < target:
            last_bad = i
    if last_bad == len(grid) - 1:
        return None
    return grid[last_bad + 1]


def simulate_mcnemar_power(
    n: int, d: float, e: float, reps: int, seed: int, alpha: float = ALPHA
) -> tuple[float, float]:
    """Monte Carlo power of the same test (multinomial draws), with its standard error.

    Used to validate :func:`mcnemar_power`; it uses the p-value function, not the critical values,
    so a mistake in the closed form cannot cancel out.
    """
    p_second, p_first = discordant_probs(d, e)
    rng = np.random.default_rng(seed)
    draws = rng.multinomial(n, [p_second, p_first, 1.0 - d], size=reps)
    hits = sum(1 for b, c, _ in draws if exact_mcnemar_p(int(b), int(c)) <= alpha)
    p = hits / reps
    return p, math.sqrt(p * (1 - p) / reps)


def z(p: float) -> float:
    """Standard normal quantile."""
    return NormalDist().inv_cdf(p)


def mde_run_noise(
    sigma: float, runs: int, alpha: float = ALPHA, target: float = POWER_TARGET
) -> float:
    """Minimum detectable difference of two conditions from run-to-run noise (unit of sigma)."""
    if runs < 1 or sigma < 0:
        raise ValueError("runs must be at least 1 and sigma non-negative")
    return (z(1 - alpha / 2) + z(target)) * sigma * math.sqrt(2.0 / runs)


def runs_needed(
    sigma: float, delta: float, alpha: float = ALPHA, target: float = POWER_TARGET
) -> int:
    """Runs per condition so that ``mde_run_noise(sigma, runs) <= delta`` (normal approximation)."""
    if delta <= 0:
        raise ValueError("delta must be positive")
    if sigma == 0:
        return 1
    return max(1, math.ceil(2.0 * ((z(1 - alpha / 2) + z(target)) * sigma / delta) ** 2))


def mdd_bootstrap_analytic(
    n: int, sd: float, rho: float, alpha: float = ALPHA, target: float = POWER_TARGET
) -> float:
    """Minimum detectable mean difference of a paired per-query metric (normal approximation)."""
    if not -1.0 <= rho <= 1.0 or n <= 0 or sd < 0:
        raise ValueError("invalid n, sd or rho")
    sd_diff = sd * math.sqrt(2.0 * (1.0 - rho))
    return (z(1 - alpha / 2) + z(target)) * sd_diff / math.sqrt(n)


def simulate_bootstrap_power(
    n: int,
    sd: float,
    rho: float,
    delta: float,
    reps: int,
    draws: int,
    seed: int,
    alpha: float = ALPHA,
) -> tuple[float, float]:
    """Power of the percentile paired bootstrap at true mean difference ``delta`` (simulation).

    Each replicate draws n paired normal scores, resamples queries ``draws`` times and rejects when
    the (alpha/2, 1 - alpha/2) percentile interval of the mean difference excludes zero.
    """
    rng = np.random.default_rng(seed)
    sd_diff = sd * math.sqrt(2.0 * (1.0 - rho))
    hits = 0
    for _ in range(reps):
        diff = rng.normal(delta, sd_diff, size=n)
        idx = rng.integers(0, n, size=(draws, n))
        means = diff[idx].mean(axis=1)
        lo, hi = np.quantile(means, [alpha / 2, 1 - alpha / 2])
        if lo > 0 or hi < 0:
            hits += 1
    p = hits / reps
    return p, math.sqrt(p * (1 - p) / reps)


def _t_crit(df: int, alpha: float, rng: np.random.Generator) -> float:
    """Two-sided critical value of Student's t, from a large simulated null sample (df < 30)."""
    sample = np.abs(rng.standard_t(df, size=2_000_000))
    return float(np.quantile(sample, 1 - alpha))


def mdd_seeds(
    k: int,
    rho: float | None,
    reps: int,
    seed: int,
    alpha: float = ALPHA,
    target: float = POWER_TARGET,
) -> float:
    """Minimum detectable difference of two arms with ``k`` seeds each, in units of the seed SD.

    ``rho is None``: unpaired two-sample equal-variance t-test, df = 2k - 2. Otherwise the arms
    share seeds and the paired t-test (df = k - 1) sees per-seed differences with standard
    deviation sqrt(2 (1 - rho)) times the seed SD. Found by bisection on a simulated power.
    """
    if k < 2:
        raise ValueError("need at least two seeds per arm")
    if rho is not None and not 0.0 <= rho < 1.0:
        raise ValueError("rho must be in [0, 1)")
    rng = np.random.default_rng(seed)
    df = 2 * k - 2 if rho is None else k - 1
    crit = _t_crit(df, alpha, rng)

    def power(delta: float) -> float:
        if rho is not None:
            diffs = rng.normal(delta, math.sqrt(2.0 * (1.0 - rho)), size=(reps, k))
            t = diffs.mean(axis=1) / (diffs.std(axis=1, ddof=1) / math.sqrt(k))
        else:
            a = rng.normal(0.0, 1.0, size=(reps, k))
            b = rng.normal(delta, 1.0, size=(reps, k))
            sp = np.sqrt((a.var(axis=1, ddof=1) + b.var(axis=1, ddof=1)) / 2.0)
            t = (b.mean(axis=1) - a.mean(axis=1)) / (sp * math.sqrt(2.0 / k))
        return float(np.mean(np.abs(t) > crit))

    lo, hi = 0.0, 30.0
    for _ in range(30):
        mid = (lo + hi) / 2.0
        if power(mid) >= target:
            hi = mid
        else:
            lo = mid
    return round((lo + hi) / 2.0, 2)


def power_grid(
    ns: Sequence[int], ds: Sequence[float], effects: Sequence[float], alpha: float = ALPHA
) -> list[dict[str, float]]:
    """Exact McNemar power for every (n, d, e); infeasible cells (e > d) are skipped."""
    rows: list[dict[str, float]] = []
    for n in ns:
        for d in ds:
            for e in effects:
                if e > d + 1e-12:
                    continue
                rows.append(
                    {"n": n, "discordance": d, "effect": e, "power": mcnemar_power(n, d, e, alpha)}
                )
    return rows


NS = (302, 432, 500)
DISCORDANCES = (0.10, 0.20, 0.30)
EFFECTS = (0.02, 0.04, 0.06, 0.08, 0.10)
BASELINES = (0.2, 0.3, 0.4, 0.5, 0.6)
SIGMAS_PTS = (2.0, 3.0, 4.0, 5.0)
DELTAS_PTS = (2.0, 4.0, 6.0, 8.0, 10.0)
RUNS = (1, 2, 3, 5, 10)
BOOT_NS = (432, 302)
BOOT_SDS = (0.2, 0.3, 0.4)
BOOT_RHOS = (0.5, 0.7, 0.9)
SEED_KS = (3, 5)
SEED_RHOS = (None, 0.5, 0.8)


def build_tables(
    seed: int, sim_reps: int, boot_reps: int, boot_draws: int
) -> dict[str, list[dict[str, object]]]:
    """Every table of the power analysis as lists of rows (CSV-ready), plus the validation rows.

    Deterministic for a given ``seed``. ``sim_reps`` is the Monte Carlo size for the McNemar and
    seed checks, ``boot_reps`` x ``boot_draws`` the size of the bootstrap check.
    """
    t: dict[str, list[dict[str, object]]] = {}
    t["mcnemar_power"] = [{**r, "n": int(r["n"])} for r in power_grid(NS, DISCORDANCES, EFFECTS)]
    t["mcnemar_mde"] = [
        {
            "n": n,
            "discordance": d,
            "mde_points": None if (m := mde_mcnemar(n, d)) is None else round(100 * m, 2),
        }
        for n in NS
        for d in DISCORDANCES
    ]
    t["mcnemar_feasibility"] = [
        {"baseline": b, "discordance": d, "effect": e, "feasible": feasible(b, d, e)}
        for b in BASELINES
        for d in DISCORDANCES
        for e in EFFECTS
    ]
    t["run_noise_mde"] = [
        {"sigma_points": s, "runs_per_condition": r, "mde_points": round(mde_run_noise(s, r), 2)}
        for s in SIGMAS_PTS
        for r in RUNS
    ]
    t["runs_needed"] = [
        {"sigma_points": s, "effect_points": dl, "runs_per_condition": runs_needed(s, dl)}
        for s in SIGMAS_PTS
        for dl in DELTAS_PTS
    ]
    t["bootstrap_mdd"] = [
        {
            "n": n,
            "sd": sd,
            "rho": rho,
            "mdd_ndcg_points": round(100 * mdd_bootstrap_analytic(n, sd, rho), 2),
        }
        for n in BOOT_NS
        for sd in BOOT_SDS
        for rho in BOOT_RHOS
    ]
    rows: list[dict[str, object]] = []
    for k in SEED_KS:
        for rho in SEED_RHOS:
            rows.append(
                {
                    "seeds_per_arm": k,
                    "design": "unpaired t" if rho is None else f"paired t, rho {rho}",
                    "mdd_in_seed_sd": mdd_seeds(k, rho, sim_reps * 5, seed),
                }
            )
    t["seed_mdd"] = rows
    val: list[dict[str, object]] = []
    for n, d, e in ((302, 0.2, 0.06), (432, 0.1, 0.04), (500, 0.3, 0.08), (432, 0.2, 0.04)):
        sim, se = simulate_mcnemar_power(n, d, e, sim_reps, seed)
        ex = mcnemar_power(n, d, e)
        val.append(
            {
                "check": "mcnemar exact vs simulation",
                "cell": f"n={n} d={d} e={e}",
                "closed_form": round(ex, 4),
                "simulated": round(sim, 4),
                "se": round(se, 4),
                "z": round((sim - ex) / se, 2) if se > 0 else 0.0,
            }
        )
    for n, sd, rho in ((432, 0.3, 0.7), (302, 0.4, 0.5), (432, 0.2, 0.9)):
        dl = mdd_bootstrap_analytic(n, sd, rho)
        sim, se = simulate_bootstrap_power(n, sd, rho, dl, boot_reps, boot_draws, seed)
        val.append(
            {
                "check": "bootstrap power at the analytic minimum (target 0.80)",
                "cell": f"n={n} sd={sd} rho={rho} delta={dl:.4f}",
                "closed_form": POWER_TARGET,
                "simulated": round(sim, 4),
                "se": round(se, 4),
                "z": round((sim - POWER_TARGET) / se, 2) if se > 0 else 0.0,
            }
        )
    t["validation"] = val
    return t


def bootstrap_means(
    values: npt.ArrayLike, *, draws: int = 2000, seed: int = 0
) -> npt.NDArray[np.float64]:
    """Means of ``draws`` resamples (with replacement) of ``values``."""
    v = np.asarray(values, dtype=np.float64)
    if v.size == 0:
        return np.full(draws, np.nan)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, v.size, size=(draws, v.size))
    return np.asarray(v[idx].mean(axis=1), dtype=np.float64)


def mean_ci(
    values: npt.ArrayLike, *, draws: int = 2000, seed: int = 0, level: float = 0.95
) -> tuple[float, float, float]:
    """``(mean, low, high)``: the sample mean and its percentile-bootstrap interval."""
    v = np.asarray(values, dtype=np.float64)
    if v.size == 0:
        return (math.nan, math.nan, math.nan)
    means = bootstrap_means(v, draws=draws, seed=seed)
    a = (1.0 - level) / 2.0
    lo, hi = np.quantile(means, [a, 1.0 - a])
    return (float(v.mean()), float(lo), float(hi))


def paired_diff_ci(
    a: npt.ArrayLike, b: npt.ArrayLike, *, draws: int = 2000, seed: int = 0, level: float = 0.95
) -> tuple[float, float, float]:
    """``(mean(a - b), low, high)`` with the same queries resampled for both conditions."""
    x = np.asarray(a, dtype=np.float64)
    y = np.asarray(b, dtype=np.float64)
    if x.shape != y.shape:
        raise ValueError(f"paired samples differ in length: {x.shape} vs {y.shape}")
    return mean_ci(x - y, draws=draws, seed=seed, level=level)


def clustered_mean_ci(
    values: npt.ArrayLike,
    repositories: Sequence[str],
    *,
    draws: int = 2000,
    seed: int = 0,
    level: float = 0.95,
) -> tuple[float, float, float]:
    """Query-weighted mean and whole-repository percentile bootstrap (D17).

    Draw R repositories with replacement from R unique names; each occurrence contributes all
    its queries. Recompute the query-weighted mean of each draw, including its random denominator.
    This is neither a mean of repository means nor a within-repository query bootstrap.
    """
    v = np.asarray(values, dtype=np.float64)
    if v.ndim != 1 or v.size == 0 or v.size != len(repositories):
        raise ValueError("need a nonempty vector and one repository per query")
    if not np.isfinite(v).all() or draws < 1 or not 0 < level < 1:
        raise ValueError("values must be finite, draws positive, level in (0, 1)")
    blocks = sorted(set(repositories))
    sums = np.asarray([v[np.asarray(repositories) == r].sum() for r in blocks])
    sizes = np.asarray([repositories.count(r) for r in blocks])
    rng = np.random.default_rng(seed)
    means = np.empty(draws)
    # Draw one replicate at a time: memory stays linear in query and repository counts.
    for i in range(draws):
        picks = rng.integers(0, len(blocks), size=len(blocks))
        means[i] = sums[picks].sum() / sizes[picks].sum()
    a = (1 - level) / 2
    lo, hi = np.quantile(means, [a, 1 - a])
    return float(v.mean()), float(lo), float(hi)


def clustered_paired_diff_ci(
    a: npt.ArrayLike,
    b: npt.ArrayLike,
    repositories: Sequence[str],
    *,
    draws: int = 2000,
    seed: int = 0,
    level: float = 0.95,
) -> tuple[float, float, float]:
    """Paired mean(a - b) and repository-clustered interval; caller aligns query identities."""
    x, y = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    if x.shape != y.shape:
        raise ValueError("paired samples must have identical shapes")
    return clustered_mean_ci(x - y, repositories, draws=draws, seed=seed, level=level)


class Boot:
    """Resample weights for a fixed set of queries; one set shared by every column."""

    def __init__(self, repos: list[str], seed: int, draws: int = 2000) -> None:
        q = len(repos)
        if not q or draws < 1:
            raise ValueError("need queries and positive bootstrap draws")
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
