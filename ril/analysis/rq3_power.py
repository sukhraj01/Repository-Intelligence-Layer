"""Power table for the planned RQ3 paired comparison of resolved rate (exact and normal forms).

Implements the RQ3 power question of ``docs/EXPERIMENTS.md`` (E-POWER, update of 2026-10-29) and
the sample-size note of ADR-007. Numbers only: nothing here chooses a sample size, a number of
runs or whether RQ3 is a test or an interval estimate.

Model: n instances, two retrievers behind one fixed agent, one pass each; ``d`` is the share of
instances on which exactly one of the two passes resolves (discordance) and ``e`` the difference in
resolved rate. The test is the exact McNemar test (:mod:`ril.evaluation.power`); the normal form
is the usual large-sample approximation, shown beside it so the gap is visible. Run-to-run noise
of the agent is not in this model (it only raises ``d``).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import NormalDist

from ril.evaluation import power

NS: tuple[int, ...] = (302, 432, 600, 900)
DISCORDANCES: tuple[float, ...] = (0.10, 0.15, 0.20, 0.30)


@dataclass(frozen=True)
class PowerRow:
    """One cell of the table: minimum detectable effect in percentage points, two forms."""

    n: int
    discordance: float
    mde_exact: float | None
    mde_normal: float | None


def mde_normal(
    n: int, d: float, alpha: float = power.ALPHA, target: float = power.POWER_TARGET
) -> float | None:
    """Minimum detectable effect (as a fraction) from the normal approximation.

    The statistic is (b - c) / n with b, c the two discordant counts. Under the null its variance
    is d / n; under an effect ``e`` it is (d - e^2) / n. The effect solves
    ``e * sqrt(n) = z_{1-alpha/2} * sqrt(d) + z_{target} * sqrt(d - e^2)``, found by fixed-point
    iteration. ``None`` if no ``e <= d`` satisfies it.
    """
    if n <= 0 or not 0.0 < d <= 1.0:
        raise ValueError("n must be positive and d in (0, 1]")
    nd = NormalDist()
    za = nd.inv_cdf(1.0 - alpha / 2.0)
    zb = nd.inv_cdf(target)
    e = (za + zb) * math.sqrt(d / n)
    for _ in range(200):
        if e > d:
            return None
        nxt = (za * math.sqrt(d) + zb * math.sqrt(max(d - e * e, 0.0))) / math.sqrt(n)
        if abs(nxt - e) < 1e-12:
            e = nxt
            break
        e = nxt
    return e if e <= d else None


def build_rows(
    ns: Sequence[int] = NS, discordances: Sequence[float] = DISCORDANCES
) -> list[PowerRow]:
    """All (n, discordance) cells with both minimum detectable effects in points."""
    rows: list[PowerRow] = []
    for n in ns:
        for d in discordances:
            ex = power.mde_mcnemar(n, d)
            nm = mde_normal(n, d)
            rows.append(
                PowerRow(
                    n,
                    d,
                    None if ex is None else round(100.0 * ex, 2),
                    None if nm is None else round(100.0 * nm, 2),
                )
            )
    return rows


def n_required(effect: float, d: float, n_max: int = 20000) -> int | None:
    """Smallest n (step 10) whose exact power at (d, effect) stays at 0.8 for every larger step.

    Doubling search then a scan; ``None`` if not reached by ``n_max``. ``effect`` is a fraction.
    """
    if effect > d:
        raise ValueError("effect cannot exceed discordance")
    n = 10
    while n <= n_max and power.mcnemar_power(n, d, effect) < power.POWER_TARGET:
        n += 10 if n < 1000 else 50
    if n > n_max:
        return None
    # the exact test saws; require the next few steps to stay above the target
    while any(power.mcnemar_power(n + k, d, effect) < power.POWER_TARGET for k in range(1, 40)):
        n += 10
        if n > n_max:
            return None
    return n


def discordance_from_counts(
    n: int, resolved_a: int, resolved_b: int, both: int
) -> tuple[int, int, float]:
    """(only-A, only-B, discordance) from per-condition resolved counts and the joint count."""
    if min(n, resolved_a, resolved_b, both) < 0 or both > min(resolved_a, resolved_b):
        raise ValueError("inconsistent counts")
    only_a = resolved_a - both
    only_b = resolved_b - both
    if only_a + only_b + both > n:
        raise ValueError("counts exceed n")
    return only_a, only_b, (only_a + only_b) / n


def to_csv(rows: Sequence[PowerRow]) -> str:
    """CSV text of the table (header included)."""
    out = ["n,discordance,mde_exact_points,mde_normal_points"]
    for r in rows:
        ex = "" if r.mde_exact is None else r.mde_exact
        nm = "" if r.mde_normal is None else r.mde_normal
        out.append(f"{r.n},{r.discordance},{ex},{nm}")
    return "\n".join(out) + "\n"
