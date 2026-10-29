"""Tests for the RQ3 power table (docs/EXPERIMENTS.md E-POWER update)."""

from __future__ import annotations

import pytest

from ril.analysis import rq3_power
from ril.evaluation import power


def test_exact_cells_match_the_earlier_registry_values() -> None:
    rows = {(r.n, r.discordance): r for r in rq3_power.build_rows((302, 432), (0.10, 0.20, 0.30))}
    assert rows[(432, 0.20)].mde_exact == 6.25
    assert rows[(432, 0.10)].mde_exact == 4.5
    assert rows[(302, 0.30)].mde_exact == 9.25


def test_normal_form_is_close_to_exact_and_monotone() -> None:
    for d in rq3_power.DISCORDANCES:
        prev = 1.0
        for n in rq3_power.NS:
            nm = rq3_power.mde_normal(n, d)
            ex = power.mde_mcnemar(n, d)
            assert nm is not None and ex is not None
            assert nm < prev
            assert abs(nm - ex) < 0.012
            prev = nm


def test_power_at_normal_mde_is_near_target() -> None:
    nm = rq3_power.mde_normal(600, 0.2)
    assert nm is not None
    assert 0.75 < power.mcnemar_power(600, 0.2, nm) < 0.88


def test_n_required_grows_as_effect_shrinks() -> None:
    big = rq3_power.n_required(0.06, 0.15)
    small = rq3_power.n_required(0.03, 0.15)
    assert big is not None and small is not None and small > 3 * big
    assert power.mcnemar_power(small, 0.15, 0.03) >= power.POWER_TARGET


def test_discordance_from_counts_and_validation() -> None:
    assert rq3_power.discordance_from_counts(500, 129, 126, 94) == (35, 32, pytest.approx(0.134))
    with pytest.raises(ValueError):
        rq3_power.discordance_from_counts(500, 100, 100, 120)
    with pytest.raises(ValueError):
        rq3_power.n_required(0.3, 0.1)
    with pytest.raises(ValueError):
        rq3_power.mde_normal(0, 0.1)
