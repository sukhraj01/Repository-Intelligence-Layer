"""Result analysis on synthetic rows with known effects; size, coverage, power, cost."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pytest

from ril.agent.providers.spend import Price
from ril.analysis import rq3_cost, rq3_power_noise
from ril.analysis.rq3_results import (
    Plan,
    analyse,
    discordance,
    latest,
    outcome_group,
    paired_contrast,
    score_matrix,
    sign_flip_p,
    wilson,
)

CLASSES = ["resolved", "executed_unresolved", "apply_failed:no_match", "unusable"]


def row(iid: str, arm: str, run: int, outcome: str, tolerant: str | None = None) -> dict[str, Any]:
    tol = tolerant or outcome
    return {
        "instance_id": iid,
        "arm": arm,
        "run": run,
        "outcome": outcome,
        "outcome_tolerant": tol,
        "resolved": outcome == "resolved",
        "resolved_tolerant": tol == "resolved",
    }


def synthetic(n: int, p_a: float, p_b: float, k: int, seed: int) -> list[dict[str, Any]]:
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        for arm, p in (("A", p_a), ("B", p_b)):
            for r in range(k):
                ok = rng.random() < p
                rows.append(row(f"i{i}", arm, r, "resolved" if ok else CLASSES[1 + r % 3]))
    return rows


def test_wilson_and_outcome_group() -> None:
    assert wilson(0, 0)[0] != wilson(0, 0)[0]  # nan
    p, lo, hi = wilson(50, 100)
    assert (
        p == 0.5 and lo == pytest.approx(0.404, abs=0.002) and hi == pytest.approx(0.596, abs=0.002)
    )
    assert outcome_group("apply_failed:no_match") == "apply_failed"
    assert outcome_group("resolved") == "resolved"


def test_latest_row_replaces_an_exec_error() -> None:
    rows = [row("i", "A", 0, "exec_error:install"), row("i", "A", 0, "resolved")]
    assert [r["outcome"] for r in latest(rows)] == ["resolved"]


def test_score_is_the_fraction_of_runs_and_missing_runs_are_listed() -> None:
    rows = [
        row("i1", "A", 0, "resolved"),
        row("i1", "A", 1, "unusable"),
        row("i1", "B", 0, "resolved"),
    ]
    s = score_matrix(rows, ["i1", "i2"], ["A", "B"], [0, 1])
    assert s.values[0, 0] == 0.5 and s.values[0, 1] == 1.0
    assert math.isnan(s.values[1, 0])
    assert ("i1", "B", 1) in s.missing and ("i2", "A", 0) in s.missing


def test_known_effect_is_recovered_with_a_covering_interval() -> None:
    rows = synthetic(327, 0.20, 0.30, 2, seed=1)
    ids = [f"i{i}" for i in range(327)]
    repo = {i: "r" for i in ids}
    t = analyse(rows, ids, repo, Plan(("A", "B"), ("B", "A"), (), (0, 1)), 2000, 2000)
    primary = next(c for c in t["contrasts"] if c["role"] == "primary" and c["reading"] == "exact")
    assert primary["difference"] == pytest.approx(0.10, abs=0.05)
    assert primary["ci_low"] <= 0.10 <= primary["ci_high"] and primary["ci_low"] > 0
    assert primary["p_permutation"] < 0.05
    tol = next(c for c in t["contrasts"] if c["reading"] == "tolerant")
    assert tol["p_permutation"] is None
    assert t["exec_errors"] == [] and t["missing"] == []


def test_no_effect_rejects_at_the_nominal_rate_and_the_interval_covers() -> None:
    n, sims = 327, 300
    rng = np.random.default_rng(7)
    rejected = covered = 0
    for s in range(sims):
        a = (rng.random((n, 2)) < 0.25).mean(axis=1)
        b = (rng.random((n, 2)) < 0.25).mean(axis=1)
        res = paired_contrast(b, a, seed=s, resamples=400, permutations=400, test=True)
        rejected += res["p_permutation"] <= 0.05
        covered += res["ci_low"] <= 0.0 <= res["ci_high"]
    assert 0.02 <= rejected / sims <= 0.09
    assert 0.91 <= covered / sims <= 0.99


def test_interval_coverage_for_a_true_nonzero_difference() -> None:
    n, sims = 327, 200
    rng = np.random.default_rng(11)
    covered = 0
    for s in range(sims):
        a = (rng.random(n) < 0.30).astype(float)
        b = (rng.random(n) < 0.20).astype(float)
        res = paired_contrast(a, b, seed=s, resamples=400, test=False)
        covered += res["ci_low"] <= 0.10 <= res["ci_high"]
    assert 0.90 <= covered / sims <= 0.99


def test_sign_flip_p_is_one_for_a_zero_mean_and_small_for_a_shift() -> None:
    d = np.array([1.0, -1.0] * 50)
    assert sign_flip_p(d, 0, 500) == pytest.approx(1.0, abs=0.01)
    assert sign_flip_p(np.full(60, 0.1), 0, 500) < 0.01


def test_discordance_counts() -> None:
    a = np.array([1.0, 1.0, 0.0, 0.5, math.nan])
    b = np.array([1.0, 0.0, 1.0, 0.0, 1.0])
    d = discordance(a, b)
    assert (d["n_pairs"], d["any_both"], d["any_only_first"], d["any_only_second"]) == (4, 1, 2, 1)
    assert (d["all_both"], d["all_only_first"], d["all_neither"]) == (1, 1, 1)


def test_outcome_tables_split_by_arm_repository_and_reading() -> None:
    rows = [
        row("i1", "A", 0, "apply_failed:no_match", tolerant="resolved"),
        row("i1", "B", 0, "unusable"),
        row("i2", "A", 0, "resolved"),
        row("i2", "B", 0, "executed_unresolved"),
    ]
    repo = {"i1": "x/x", "i2": "y/y"}
    t = analyse(rows, ["i1", "i2"], repo, Plan(("A", "B"), ("A", "B"), (), (0,)), 200, 200)
    a_exact = next(r for r in t["outcomes"] if r["arm"] == "A" and r["reading"] == "exact")
    a_tol = next(r for r in t["outcomes"] if r["arm"] == "A" and r["reading"] == "tolerant")
    assert a_exact["apply_failed_n"] == 1 and a_tol["apply_failed_n"] == 0
    assert a_tol["resolved_n"] == 2
    assert {r["repository"] for r in t["outcomes_by_repository"]} == {"all", "x/x", "y/y"}
    assert t["apply_failure_classes"] == [{"arm": "A", "class": "apply_failed:no_match", "runs": 1}]


# ------------------------------------------------------------------ power with run noise


def test_shift_hits_the_requested_effect() -> None:
    rng = np.random.default_rng(0)
    p = rng.beta(0.8, 3.2, size=200_000)
    g = rq3_power_noise.shift_for_effect(p, 0.04)
    p2 = 1 / (1 + np.exp(-(np.log(p / (1 - p)) + g)))
    assert p2.mean() - p.mean() == pytest.approx(0.04, abs=1e-4)


def test_run_noise_model_has_the_stated_agreement() -> None:
    rng = np.random.default_rng(0)
    a, _ = rq3_power_noise.simulate_scores(rng, 4000, 1, 2, 0.5, 1e6, 0.0, same=0.635)
    # kappa huge: p is 0.5 for everyone; two runs agree with prob same + (1 - same) * 0.5
    both = a[0]
    agree = np.mean((both == 0.0) | (both == 1.0))
    assert agree == pytest.approx(0.635 + 0.365 * 0.5, abs=0.03)


def test_power_table_size_and_monotonicity() -> None:
    cells = rq3_power_noise.power_table(
        rates=(0.2,),
        kappas=(4.0,),
        runs=(1, 3),
        effects=(0.0, 0.04, 0.10),
        sims=200,
        permutations=500,
        seed=3,
    )
    by = {(c.runs, c.effect): c.power for c in cells}
    assert by[(1, 0.0)] <= 0.12 and by[(3, 0.0)] <= 0.12
    assert by[(1, 0.10)] > by[(1, 0.04)] and by[(3, 0.10)] >= by[(3, 0.04)]
    assert by[(3, 0.10)] >= by[(1, 0.10)] - 0.05
    mdd = rq3_power_noise.minimum_detectable(cells)
    assert all(m["mdd_points"] is None or 0 < m["mdd_points"] <= 10 for m in mdd)


# ------------------------------------------------------------------ cost


def test_cost_model_scales_with_units_and_marks_classes() -> None:
    tokens = rq3_cost.UnitTokens(calls=1.4, calls_hi=1.5, input_tokens=12_000, output_tokens=900)
    price = Price("m", 0.30, 2.50, False, "2026-11-08")
    one = rq3_cost.cost_of(1000, tokens, price)
    assert one["cost_usd"] == pytest.approx(
        (1000 * 12_000 * 0.30 + 1000 * 900 * 2.50) / 1e6, abs=0.01
    )
    high = rq3_cost.cost_of(1000, tokens, price, "high")
    assert high["cost_usd"] > one["cost_usd"] * 1.5
    rows = rq3_cost.cost_table(tokens, [price])
    grid = {(r["what"], r["scenario"]): r for r in rows}
    a = grid[("one arm-run, confirmatory", "central")]
    b = grid[("grid 3 arms x k=3", "central")]
    assert b["cost_usd"] == pytest.approx(9 * a["cost_usd"], rel=0.01)
    assert a["dollars_class"].startswith("estimated") and a["tokens_class"].startswith("measured")
    cap = rq3_cost.graded_check_cap(rows)
    assert cap["recommended_cap_usd"] >= cap["sum_high_usd"]
    with pytest.raises(ValueError):
        rq3_cost.cost_of(1, tokens, price, "nope")
