"""The curve rule of E-PILOT-CURVE on constructed curves (no data from any run)."""

from __future__ import annotations

import numpy as np

from ril.analysis.t3_tables import PRIMARY_READING, all_tables

STEPS = (0, 100, 300, 1000, 2000, 3000)


def _runs(level_gain: dict[int, float], gap: float = 0.0, noise: float = 0.02):
    """Two seeds, 60 queries in 4 repositories; the gain (fraction) at each step is the same for
    every query up to small noise; seed 1 is shifted by ``gap`` after step 0."""
    rng = np.random.default_rng(0)
    key = f"{PRIMARY_READING}:ndcg10"
    key3 = f"{PRIMARY_READING}:recall100"
    base = rng.uniform(0.2, 0.5, size=60)
    runs: dict = {}
    for seed in (0, 1):
        runs[seed] = {}
        for n in STEPS:
            q: dict = {}
            for i in range(60):
                g = level_gain.get(n, 0.0) + (gap if (seed == 1 and n > 0) else 0.0)
                v = float(np.clip(base[i] + g + rng.normal(0, noise), 0, 1))
                for lv, k in (("L2", key), ("L3", key3)):
                    q[(f"inst{i}", lv, "dense")] = {**q.get((f"inst{i}", lv, "dense"), {}), k: v}
                    q[(f"inst{i}", lv, "rrf")] = {**q.get((f"inst{i}", lv, "rrf"), {}), k: v}
                    q[(f"inst{i}", lv, "_repo")] = {f"repo_r{i % 4}": 0.0}
            runs[seed][n] = q
    return runs


def test_saturating_curve_has_its_knee_at_the_plateau() -> None:
    runs = _runs({100: 0.10, 300: 0.14, 1000: 0.14, 2000: 0.14, 3000: 0.14})
    _, d = all_tables(runs, draws=400)
    assert not d["no_movement"] and not d["beyond_2000"]
    assert d["knee"] == 300 and d["n_for_next_pilot"] == 300


def test_still_rising_curve_is_capped_at_2000() -> None:
    runs = _runs({100: 0.05, 300: 0.10, 1000: 0.15, 2000: 0.20, 3000: 0.25})
    _, d = all_tables(runs, draws=400)
    assert d["beyond_2000"] and d["n_for_next_pilot"] == 2000


def test_flat_curve_is_no_movement() -> None:
    runs = _runs({})
    _, d = all_tables(runs, draws=400)
    assert d["no_movement"] and d["n_for_next_pilot"] is None
