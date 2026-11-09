"""Cluster-robust t interval of a mean over queries, clustered over repositories.

Implements the decision interval of ``docs/RQ2_PROTOCOL.md`` section 11 (D135, DEV-040): the point
estimate is the mean over queries; the variance is the one-way cluster-robust (linearisation)
estimate over repositories, ``G / (G - 1) * sum_g (sum_{i in g} (x_i - mean))^2 / N^2``; the
interval is ``mean +- t_{1 - alpha / 2, G - 1} * se``. With fewer than ``MIN_CLUSTERS``
repositories every query is its own cluster (``G = N``), the query-level reading of section 4.

No scipy in the environment: the Student t distribution is the regularised incomplete beta function
(continued fraction, Lentz) with a bisection inverse, checked against tabulated quantiles in
``tests/unit/test_cluster_t.py``. Numbers only, nothing here chooses a design.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

MIN_CLUSTERS = 3
"""Repository-clustered from three repositories up, query-level below (section 4)."""

Arr = npt.NDArray[np.float64]


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction of the incomplete beta function (modified Lentz)."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 400):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta function ``I_x(a, b)`` for ``0 <= x <= 1``."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_front = (
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(log_front) * _betacf(a, b, x) / a
    return 1.0 - math.exp(log_front) * _betacf(b, a, 1.0 - x) / b


def t_cdf(x: float, df: float) -> float:
    """P(T <= x) for Student's t with ``df`` degrees of freedom."""
    if df <= 0:
        raise ValueError("degrees of freedom must be positive")
    tail = 0.5 * betainc(df / 2.0, 0.5, df / (df + x * x))
    return 1.0 - tail if x > 0 else tail


def t_ppf(p: float, df: float) -> float:
    """The ``p`` quantile of Student's t with ``df`` degrees of freedom (bisection, 1e-12)."""
    if not 0.0 < p < 1.0:
        raise ValueError("p must be in (0, 1)")
    if p == 0.5:
        return 0.0
    if p < 0.5:
        return -t_ppf(1.0 - p, df)
    lo, hi = 0.0, 1.0
    while t_cdf(hi, df) < p:
        hi *= 2.0
        if hi > 1e12:
            raise ValueError("quantile out of range")
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if t_cdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-12 * max(1.0, hi):
            break
    return 0.5 * (lo + hi)


@dataclass(frozen=True)
class ClusterT:
    """Mean, cluster-robust standard error, degrees of freedom and clusters of one contrast."""

    d: float
    se: float
    df: int
    clusters: int
    kind: str
    """``repository-clustered`` or ``query-level``."""

    def p_value(self) -> float:
        """Two-sided p-value of ``d = 0``. A zero standard error gives 1 (d = 0) or 0."""
        if self.se <= 0.0:
            return 1.0 if self.d == 0.0 else 0.0
        return float(min(1.0, 2.0 * (1.0 - t_cdf(abs(self.d) / self.se, self.df))))

    def interval(self, alpha: float) -> tuple[float, float]:
        """Two-sided interval at level ``1 - alpha``."""
        if self.se <= 0.0:
            return self.d, self.d
        half = t_ppf(1.0 - alpha / 2.0, self.df) * self.se
        return self.d - half, self.d + half


def cluster_t(values: Arr, groups: Sequence[str]) -> ClusterT:
    """The cluster-robust t summary of the mean of ``values`` clustered by ``groups``.

    Fewer than ``MIN_CLUSTERS`` distinct groups: each value is its own cluster. Needs two values.
    """
    x = np.asarray(values, dtype=np.float64)
    n = int(x.size)
    if n < 2 or n != len(groups):
        raise ValueError("need at least two values and one group label per value")
    names = sorted(set(groups))
    clustered = len(names) >= MIN_CLUSTERS
    mean = float(x.mean())
    resid = x - mean
    if clustered:
        index = {g: i for i, g in enumerate(names)}
        sums = np.zeros(len(names))
        np.add.at(sums, [index[g] for g in groups], resid)
        g_count = len(names)
    else:
        sums = resid
        g_count = n
    var = g_count / (g_count - 1.0) * float(np.sum(sums**2)) / (n * n)
    return ClusterT(
        mean,
        math.sqrt(max(var, 0.0)),
        g_count - 1,
        g_count,
        "repository-clustered" if clustered else "query-level",
    )
