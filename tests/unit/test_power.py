"""Tests for the power calculations (ril.evaluation.power)."""

from __future__ import annotations

import math

import pytest

from ril.evaluation import power as pw


def _brute_force_power(n: int, d: float, e: float) -> float:
    """Enumerate every (b, c) outcome of a multinomial and sum the probability of rejection."""
    p_second, p_first = pw.discordant_probs(d, e)
    p_none = 1.0 - d
    total = 0.0
    for b in range(n + 1):
        for c in range(n + 1 - b):
            prob = (
                math.exp(
                    math.lgamma(n + 1)
                    - math.lgamma(b + 1)
                    - math.lgamma(c + 1)
                    - math.lgamma(n - b - c + 1)
                )
                * (p_second**b)
                * (p_first**c)
                * (p_none ** (n - b - c))
            )
            if pw.exact_mcnemar_p(b, c) <= pw.ALPHA:
                total += prob
    return total


@pytest.mark.parametrize("n,d,e", [(20, 0.5, 0.3), (30, 0.4, 0.2), (40, 0.3, 0.3), (25, 0.6, 0.0)])
def test_exact_power_matches_enumeration(n: int, d: float, e: float) -> None:
    assert pw.mcnemar_power(n, d, e) == pytest.approx(_brute_force_power(n, d, e), abs=1e-9)


def test_p_value_known_values() -> None:
    assert pw.exact_mcnemar_p(0, 5) == pytest.approx(2 / 32)
    assert pw.exact_mcnemar_p(0, 6) == pytest.approx(2 / 64)
    assert pw.exact_mcnemar_p(3, 3) == 1.0
    assert pw.exact_mcnemar_p(0, 0) == 1.0
    with pytest.raises(ValueError):
        pw.exact_mcnemar_p(-1, 2)


def test_critical_value() -> None:
    assert pw.critical_value(5) == -1  # 2 * (1/32) = 0.0625 > 0.05
    assert pw.critical_value(6) == 0
    assert pw.critical_value(0) == -1
    assert pw.critical_value(100) > pw.critical_value(50) > 0


def test_power_at_zero_effect_is_at_most_alpha() -> None:
    assert pw.mcnemar_power(432, 0.2, 0.0) <= pw.ALPHA


def test_power_increases_with_effect_and_n() -> None:
    assert pw.mcnemar_power(432, 0.2, 0.08) > pw.mcnemar_power(432, 0.2, 0.04)
    assert pw.mcnemar_power(500, 0.2, 0.06) > pw.mcnemar_power(302, 0.2, 0.06)
    assert pw.mcnemar_power(432, 0.1, 0.06) > pw.mcnemar_power(432, 0.3, 0.06)


def test_power_symmetric_in_sign_of_effect() -> None:
    assert pw.mcnemar_power(302, 0.2, -0.06) == pytest.approx(pw.mcnemar_power(302, 0.2, 0.06))


def test_invalid_inputs() -> None:
    with pytest.raises(ValueError):
        pw.mcnemar_power(0, 0.2, 0.05)
    with pytest.raises(ValueError):
        pw.discordant_probs(0.05, 0.10)  # effect above discordance
    with pytest.raises(ValueError):
        pw.discordant_probs(1.2, 0.0)
    assert pw.mcnemar_power(100, 0.0, 0.0) == 0.0


def test_feasible_limits() -> None:
    assert pw.feasible(0.5, 0.2, 0.1)
    assert not pw.feasible(0.05, 0.4, 0.0)  # P(only first) = 0.2 > baseline 0.05
    assert not pw.feasible(0.95, 0.2, 0.1)  # second rate above 1
    assert not pw.feasible(0.5, 0.05, 0.1)


def test_mde_mcnemar_values_and_none() -> None:
    m = pw.mde_mcnemar(432, 0.2)
    assert m is not None and pw.mcnemar_power(432, 0.2, m) >= pw.POWER_TARGET
    assert pw.mcnemar_power(432, 0.2, m - 0.0025) < pw.POWER_TARGET or m <= 0.0025
    assert pw.mde_mcnemar(10, 0.2) is None  # ten instances cannot reach 80% power


def test_simulation_agrees_with_closed_form() -> None:
    sim, se = pw.simulate_mcnemar_power(302, 0.2, 0.06, 20000, 3)
    assert abs(sim - pw.mcnemar_power(302, 0.2, 0.06)) < 4 * se


def test_simulation_is_deterministic() -> None:
    assert pw.simulate_mcnemar_power(100, 0.3, 0.1, 500, 1) == pw.simulate_mcnemar_power(
        100, 0.3, 0.1, 500, 1
    )


def test_run_noise_formulas_round_trip() -> None:
    for sigma in (2.0, 5.0):
        for delta in (3.0, 8.0):
            r = pw.runs_needed(sigma, delta)
            assert pw.mde_run_noise(sigma, r) <= delta + 1e-9
            if r > 1:
                assert pw.mde_run_noise(sigma, r - 1) > delta
    assert pw.runs_needed(0.0, 1.0) == 1
    with pytest.raises(ValueError):
        pw.runs_needed(2.0, 0.0)
    with pytest.raises(ValueError):
        pw.mde_run_noise(2.0, 0)
    assert pw.mde_run_noise(2.0, 1) == pytest.approx(2.8016 * 2 * math.sqrt(2), rel=1e-3)


def test_bootstrap_analytic_scaling() -> None:
    base = pw.mdd_bootstrap_analytic(432, 0.3, 0.7)
    assert (
        pw.mdd_bootstrap_analytic(432, 0.3, 0.9) < base < pw.mdd_bootstrap_analytic(432, 0.3, 0.5)
    )
    assert pw.mdd_bootstrap_analytic(302, 0.3, 0.7) > base
    assert pw.mdd_bootstrap_analytic(432, 0.3, 1.0) == 0.0
    with pytest.raises(ValueError):
        pw.mdd_bootstrap_analytic(432, 0.3, 1.5)


def test_bootstrap_simulation_near_target() -> None:
    delta = pw.mdd_bootstrap_analytic(200, 0.3, 0.5)
    sim, se = pw.simulate_bootstrap_power(200, 0.3, 0.5, delta, reps=250, draws=400, seed=1)
    assert abs(sim - pw.POWER_TARGET) < 4 * se + 0.03
    null, _ = pw.simulate_bootstrap_power(200, 0.3, 0.5, 0.0, reps=250, draws=400, seed=1)
    assert null < 0.15


def test_seed_mdd_known_values_and_errors() -> None:
    assert pw.mdd_seeds(3, None, 40000, 0) == pytest.approx(3.07, abs=0.15)
    assert pw.mdd_seeds(5, None, 40000, 0) < pw.mdd_seeds(3, None, 40000, 0)
    assert pw.mdd_seeds(3, 0.8, 40000, 0) < pw.mdd_seeds(3, 0.0, 40000, 0)
    with pytest.raises(ValueError):
        pw.mdd_seeds(1, None, 100, 0)
    with pytest.raises(ValueError):
        pw.mdd_seeds(3, 1.0, 100, 0)


def test_power_grid_skips_infeasible_effects() -> None:
    rows = pw.power_grid((100,), (0.05,), (0.02, 0.10))
    assert [r["effect"] for r in rows] == [0.02]
