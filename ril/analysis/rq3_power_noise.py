"""Power of the primary RQ3 contrast with run-to-run noise. Implements ``docs/RQ3_PILOT.md`` (D113).

The placeholder table of ``rq3_power`` (McNemar, one pass, discordance assumed) stays beside this
one. Here the primary contrast is simulated as it will be analysed: ``n`` instances, ``k`` runs per
arm, the instance score the fraction of runs that resolve, the paired sign-flip permutation test on
the per-instance difference of scores (``rq3_results.sign_flip_p``'s statistic).

Model (every item is stated; which are measured and which are assumptions is in ``ASSUMPTIONS``):

* arm A resolves instance ``i`` with probability ``p_i ~ Beta(mu * kappa, (1 - mu) * kappa)``;
* arm B has ``logit p_i^B = logit p_i^A + gamma`` with ``gamma`` chosen so that the mean
  probability of B exceeds that of A by the effect ``delta`` exactly (in the large-sample sense);
* run 0 of an arm is a Bernoulli draw of its probability; each later run repeats the previous
  run's outcome with probability ``s`` (the agent returned the same reply) and is otherwise a fresh
  Bernoulli draw; ``s`` is the pilot's share of pairs with the same reply text;
* runs of the two arms are independent given ``p_i``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt

Arr = npt.NDArray[np.float64]

N_CONFIRMATORY = 327
SAME_REPLY = 0.635
"""Pilot: same first-reply text in 63.5% of run pairs (``rq3_pilot_run_to_run.csv``, all arms)."""
RATES: tuple[float, ...] = (0.10, 0.20, 0.30)
EFFECTS: tuple[float, ...] = (0.0, 0.02, 0.04, 0.06, 0.08, 0.10)
RUNS: tuple[int, ...] = (1, 2, 3)
KAPPAS: tuple[float, ...] = (1.0, 4.0)
ALPHA = 0.05
TARGET = 0.8

ASSUMPTIONS: dict[str, str] = {
    "overall resolved rate (10, 20, 30%)": "assumption: no resolved rate has been measured",
    "arm effect (0 to 10 points)": "assumption: the quantity the test is meant to detect",
    "heterogeneity kappa (1, 4)": "assumption: no pilot evidence; low kappa = instances mostly "
    "always solved or never solved, so the arms' outcomes are strongly correlated",
    "same reply in repeated runs (0.635)": "measured on the 100-instance pilot (Flash-Lite, "
    "BM25 and RRF), dev instances, a different model may differ",
    "same usability (97.5%)": "measured in the pilot; not modelled separately: an unusable reply "
    "is an unresolved outcome and is inside the resolve probability",
    "arms independent given the instance": "assumption",
}


def _sigmoid(x: Arr) -> Arr:
    out: Arr = 1.0 / (1.0 + np.exp(-x))
    return out


def _logit(p: Arr) -> Arr:
    q = np.clip(p, 1e-9, 1 - 1e-9)
    out: Arr = np.log(q / (1 - q))
    return out


def shift_for_effect(p: Arr, delta: float) -> float:
    """``gamma`` with ``mean(sigmoid(logit p + gamma)) - mean(p) = delta`` (bisection)."""
    if delta == 0.0:
        return 0.0
    base = float(p.mean())
    lo, hi = 0.0, 20.0
    target = base + delta
    if target >= 1.0:
        raise ValueError("effect too large for this rate")
    lp = _logit(p)
    for _ in range(80):
        mid = (lo + hi) / 2
        if float(_sigmoid(lp + mid).mean()) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def simulate_scores(
    rng: np.random.Generator,
    n: int,
    sims: int,
    k: int,
    mu: float,
    kappa: float,
    delta: float,
    same: float = SAME_REPLY,
    gamma_pool: int = 200_000,
) -> tuple[Arr, Arr]:
    """Instance scores of arm A and arm B, each of shape ``(sims, n)``."""
    pool = rng.beta(mu * kappa, (1 - mu) * kappa, size=gamma_pool)
    gamma = shift_for_effect(pool, delta)
    p_a = rng.beta(mu * kappa, (1 - mu) * kappa, size=(sims, n))
    p_b = _sigmoid(_logit(p_a) + gamma)

    def runs(p: Arr) -> Arr:
        out = (rng.random(p.shape) < p).astype(np.float64)
        total = out.copy()
        prev = out
        for _ in range(1, k):
            fresh = (rng.random(p.shape) < p).astype(np.float64)
            keep = rng.random(p.shape) < same
            prev = np.where(keep, prev, fresh)
            total += prev
        result: Arr = total / k
        return result

    return runs(p_a), runs(p_b)


def reject_rate(a: Arr, b: Arr, flips: Arr, alpha: float = ALPHA) -> float:
    """Share of simulated datasets whose paired sign-flip p-value is at most ``alpha``.

    ``flips`` is a ``(permutations, n)`` matrix of +-1 shared by all datasets (a fixed null
    reference set; the p-value of a dataset counts itself among the permutations).
    """
    d = b - a
    n = d.shape[1]
    observed = np.abs(d.mean(axis=1))
    null = np.abs(d @ flips.T) / n
    hits = (null >= observed[:, None] - 1e-12).sum(axis=1)
    p = (hits + 1) / (flips.shape[0] + 1)
    return float(np.mean(p <= alpha))


@dataclass(frozen=True)
class PowerCell:
    rate: float
    kappa: float
    runs: int
    effect: float
    power: float
    mc_se: float


def power_table(
    n: int = N_CONFIRMATORY,
    rates: Sequence[float] = RATES,
    effects: Sequence[float] = EFFECTS,
    runs: Sequence[int] = RUNS,
    kappas: Sequence[float] = KAPPAS,
    sims: int = 400,
    permutations: int = 2000,
    seed: int = 0,
    same: float = SAME_REPLY,
) -> list[PowerCell]:
    """Rejection rate at every (rate, kappa, k, effect); the effect-0 rows are the test's size."""
    rng = np.random.default_rng(seed)
    flips: Arr = (rng.integers(0, 2, size=(permutations, n)) * 2.0 - 1.0).astype(np.float64)
    cells: list[PowerCell] = []
    for mu in rates:
        for kappa in kappas:
            for k in runs:
                for delta in effects:
                    a, b = simulate_scores(rng, n, sims, k, mu, kappa, delta, same)
                    pw = reject_rate(a, b, flips)
                    cells.append(
                        PowerCell(mu, kappa, k, delta, pw, math.sqrt(pw * (1 - pw) / sims))
                    )
    return cells


def minimum_detectable(cells: Sequence[PowerCell], target: float = TARGET) -> list[dict[str, Any]]:
    """Smallest effect at power ``target`` by linear interpolation between grid points, per
    (rate, kappa, k); ``None`` if power stays below the target on the grid, the smallest grid
    effect if it is reached already there."""
    groups: dict[tuple[float, float, int], list[PowerCell]] = {}
    for c in cells:
        groups.setdefault((c.rate, c.kappa, c.runs), []).append(c)
    out: list[dict[str, Any]] = []
    for (rate, kappa, k), cs in sorted(groups.items()):
        cs = sorted((c for c in cs if c.effect > 0), key=lambda c: c.effect)
        mdd: float | None = None
        prev: PowerCell | None = None
        for c in cs:
            if c.power >= target:
                if prev is None or prev.power >= target:
                    mdd = c.effect
                else:
                    frac = (target - prev.power) / (c.power - prev.power)
                    mdd = prev.effect + frac * (c.effect - prev.effect)
                break
            prev = c
        out.append(
            {
                "rate": rate,
                "kappa": kappa,
                "runs": k,
                "mdd_points": None if mdd is None else round(100 * mdd, 2),
                "grid_max_points": round(100 * cs[-1].effect, 1),
            }
        )
    return out


def to_rows(cells: Sequence[PowerCell], n: int = N_CONFIRMATORY) -> list[dict[str, Any]]:
    return [
        {
            "n": n,
            "rate": c.rate,
            "kappa": c.kappa,
            "runs": c.runs,
            "effect_points": round(100 * c.effect, 1),
            "power": round(c.power, 3),
            "mc_se": round(c.mc_se, 3),
        }
        for c in cells
    ]
