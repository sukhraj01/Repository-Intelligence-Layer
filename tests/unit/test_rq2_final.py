"""Tests of the RQ2 final analysis (``ril.analysis.rq2_final``).

Synthetic rows with a known effect only; nothing here is a result. Simulation sizes and tolerances
are stated at each test and in ``docs/experiments/B.md`` E-RQ2-ANALYSIS.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from ril.analysis import rq2_final as R
from ril.evaluation.stats import Boot
from tests.unit._rq2_final_fixtures import run_table, synthetic_rows

FILTER = "mined_filter_bm25"
SPEC = R.ContrastSpec(f"{FILTER} - mined_raw", FILTER, "mined_raw", "confirmatory", "confirmatory")


def _analyse(rows: list[dict[str, Any]], **kw: Any) -> dict[str, Any]:
    kw.setdefault("source_kind", "synthetic")
    kw.setdefault("draws", 400)
    return R.analyse(rows, run_table(rows), **kw)


def _confirmatory(summary: dict[str, Any]) -> list[dict[str, Any]]:
    return [c for c in summary["contrasts"] if c["family"] == "confirmatory" and c["primary"]]


# ------------------------------------------------------------------------------------- Holm


def holm_reference(p: list[float]) -> list[float]:
    """Holm by its definition (Holm 1979), written differently from ``holm_adjust``.

    Hypothesis i is rejected at level a when, for every j up to i in the ascending order,
    p_(j) <= a / (m - j + 1); the adjusted p-value is the smallest such a, found by bisection.
    """
    m = len(p)
    order = sorted(range(m), key=lambda i: p[i])

    def rejected(a: float) -> set[int]:
        out: set[int] = set()
        for rank, i in enumerate(order):
            if p[i] <= a / (m - rank):
                out.add(i)
            else:
                break
        return out

    adj = []
    for i in range(m):
        lo, hi = 0.0, 1.0
        if i not in rejected(1.0):
            adj.append(1.0)
            continue
        for _ in range(60):
            mid = (lo + hi) / 2
            if i in rejected(mid):
                hi = mid
            else:
                lo = mid
        adj.append(hi)
    return adj


def test_holm_hand_computed() -> None:
    # sorted 0.005, 0.01, 0.03, 0.04 -> x4, x3, x2, x1 = 0.02, 0.03, 0.06, 0.04 -> running max
    # 0.02, 0.03, 0.06, 0.06; same as p.adjust(c(0.01, 0.04, 0.03, 0.005), "holm") in R
    got = R.holm_adjust([0.01, 0.04, 0.03, 0.005])
    assert got == pytest.approx([0.03, 0.06, 0.06, 0.02])


def test_holm_caps_at_one_and_keeps_ties_ordered() -> None:
    assert R.holm_adjust([0.5, 0.5, 0.9]) == pytest.approx([1.0, 1.0, 1.0])
    assert R.holm_adjust([0.01, 0.01]) == pytest.approx([0.02, 0.02])
    assert R.holm_adjust([0.2]) == [0.2]


def test_holm_against_independent_reference() -> None:
    # no statsmodels in the environment: a transparent reference (the definition, by bisection)
    rng = random.Random(7)
    for _ in range(200):
        m = rng.randint(1, 8)
        p = [round(rng.random() ** 2, 4) for _ in range(m)]
        assert R.holm_adjust(p) == pytest.approx(holm_reference(p), abs=1e-9)


def test_holm_rejection_equals_interval_excludes_zero() -> None:
    # the reported Holm interval and the decision are the same statement, on every simulated family
    for i in range(60):
        rows = synthetic_rows(effects={FILTER: 1.0 if i % 2 else 0.0}, seed=i, repos=8)
        s = _analyse(rows)
        for c in _confirmatory(s):
            lo, hi = c["holm"]["ci"]
            assert c["holm"]["rejected"] == (lo > 0 or hi < 0)


def test_holm_interval_is_wider_than_uncorrected_after_step_one() -> None:
    rows = synthetic_rows(effects={FILTER: 2.0}, seed=3)
    s = _analyse(rows)
    for c in _confirmatory(s):
        lo_h, hi_h = c["holm"]["ci"]
        lo_u, hi_u = c["ci_uncorrected"]
        assert lo_h <= lo_u + 1e-9 and hi_h >= hi_u - 1e-9
        assert c["holm"]["m"] == 4


# --------------------------------------------------------------------------- classification


@pytest.mark.parametrize(
    ("d", "lo", "hi", "word"),
    [
        (2.0, 0.5, 3.5, "reported-effect"),
        (1.5, 0.1, 2.9, "reported-effect"),  # exactly delta counts
        (1.4, 0.2, 2.6, "estimate-with-bounds"),  # excludes zero but below delta
        (0.2, -0.8, 1.2, "estimate-with-bounds"),  # bounded below delta
        (-2.0, -3.0, -1.0, "estimate-with-bounds"),  # harmful, flagged beside
        (1.0, -0.5, 2.5, "inconclusive"),  # cannot exclude zero or delta
        (3.0, 0.0, 6.0, "inconclusive"),  # lower end at zero does not exclude it
        (0.0, -1.0, 1.5, "inconclusive"),  # upper end equal to delta
    ],
)
def test_classify_boundaries(d: float, lo: float, hi: float, word: str) -> None:
    assert R.classify(d, lo, hi) == word


# ------------------------------------------------------------------------------ estimates


def test_known_effects_recovered_and_classified() -> None:
    # a true effect of exactly delta is reported about half the time by construction, so only the
    # estimate is checked there; 0 is never reported and 3 points always is
    for effect in (0.0, 1.5, 3.0):
        rows = synthetic_rows(effects={FILTER: effect}, seed=11, tau=0.5)
        for x in _confirmatory(_analyse(rows)):
            if x["contrast"] != SPEC.name:
                continue
            assert x["d"] == pytest.approx(effect, abs=0.8)
            if effect == 0.0:
                assert x["class"] != "reported-effect"
            if effect == 3.0:
                assert x["class"] == "reported-effect"


def test_interval_kind_follows_the_repository_count() -> None:
    many = _analyse(synthetic_rows(effects={FILTER: 1.0}, seed=1, repos=12))
    two = _analyse(synthetic_rows(effects={FILTER: 1.0}, seed=1, repos=2, per_repo=60))
    assert {c["interval"] for c in _confirmatory(many)} == {"repository-clustered"}
    assert {c["interval"] for c in _confirmatory(two)} == {"query-level"}
    assert all(c["ci_cluster"] is None for c in _confirmatory(two))
    assert all(c["ci_cluster"] is not None for c in _confirmatory(many))


def test_clustered_interval_is_wider_when_the_effect_varies_by_repository() -> None:
    rows = synthetic_rows(effects={FILTER: 2.0}, seed=5, repos=12, tau=2.0)
    c = _confirmatory(_analyse(rows, draws=1000))[0]
    w_q = c["ci_query"][1] - c["ci_query"][0]
    w_c = c["ci_cluster"][1] - c["ci_cluster"][0]
    assert w_c > 1.5 * w_q


def test_per_seed_and_pooled_differences() -> None:
    rows = synthetic_rows(effects={FILTER: 2.0}, seed=2, seeds=3)
    c = _confirmatory(_analyse(rows))[0]
    assert [s["seed"] for s in c["per_seed"]] == [100.0, 101.0, 102.0]
    assert np.mean([s["d"] for s in c["per_seed"]]) == pytest.approx(c["d"], abs=1e-5)
    assert c["seed_sd_of_difference"] is not None


def test_both_metrics_reported_and_only_primary_gets_holm() -> None:
    s = _analyse(synthetic_rows(effects={FILTER: 2.0}, seed=2))
    cs = [c for c in s["contrasts"] if c["contrast"] == SPEC.name]
    assert {(c["level"], c["metric"], c["primary"]) for c in cs} == {
        ("L2", "ndcg10", True),
        ("L2", "recall100", False),
        ("L3", "ndcg10", False),
        ("L3", "recall100", True),
    }
    assert all((c["holm"] is not None) == c["primary"] for c in cs)


def test_matches_the_existing_clustered_bootstrap() -> None:
    # the interval is the stored D17 bootstrap (whole repositories, shared draws), not a new one
    rows = synthetic_rows(effects={FILTER: 1.5}, seed=9, repos=6)
    panel = R.build_panels(rows)[("dev", "L2")]
    d = 100 * (panel.cells[FILTER].pooled("ndcg10") - panel.cells["mined_raw"].pooled("ndcg10"))
    boot = Boot(panel.repos, 0, 400)
    lo, hi = np.quantile(boot.cluster @ d, [0.025, 0.975])
    e = R.estimate(panel, SPEC, "ndcg10", boot)
    assert e is not None
    assert e.ci == pytest.approx((lo, hi))
    assert e.d == pytest.approx(d.mean())


# ---------------------------------------------------------------------------- invariances


def test_row_order_and_run_ids_do_not_matter() -> None:
    rows = synthetic_rows(effects={FILTER: 2.0}, seed=4, repos=6)
    shuffled = list(rows)
    random.Random(1).shuffle(shuffled)
    a, b = _analyse(rows), _analyse(shuffled)
    assert a["analysis_hash"] == b["analysis_hash"]
    renamed = [{**r, "run_id": "x" + r["run_id"]} for r in rows]
    assert _analyse(renamed)["contrasts"] == a["contrasts"]


def test_consistent_seed_relabelling_changes_nothing_but_the_labels() -> None:
    rows = synthetic_rows(effects={FILTER: 2.0}, seed=4, repos=6)
    relabel = {100: 7, 101: 3, 102: 55}
    other = [{**r, "seed": relabel[r["seed"]]} for r in rows]
    a, b = _analyse(rows), _analyse(other)
    for x, y in zip(a["contrasts"], b["contrasts"], strict=True):
        assert x["d"] == y["d"]
        assert x["ci_uncorrected"] == y["ci_uncorrected"]
        assert x["holm"] == y["holm"]
        assert sorted(s["d"] for s in x["per_seed"]) == pytest.approx(
            sorted(s["d"] for s in y["per_seed"])
        )


def test_pooled_result_does_not_depend_on_which_seed_pairs_with_which() -> None:
    rows = synthetic_rows(effects={FILTER: 2.0}, seed=4, repos=6)
    swap = {100: 101, 101: 102, 102: 100}
    other = [{**r, "seed": swap[r["seed"]]} if r["cell"] == FILTER else r for r in rows]
    a, b = _analyse(rows), _analyse(other)
    for x, y in zip(a["contrasts"], b["contrasts"], strict=True):
        assert x["d"] == pytest.approx(y["d"])
        assert x["ci_uncorrected"] == pytest.approx(y["ci_uncorrected"])


# ------------------------------------------------------------------------- input checks


def test_bad_rows_are_refused_not_dropped() -> None:
    rows = synthetic_rows(effects={FILTER: 1.0}, seed=1, repos=3, per_repo=4)
    with pytest.raises(ValueError, match="duplicate"):
        R.build_panels([*rows, rows[0]])
    with pytest.raises(ValueError, match="not a fraction"):
        R.build_panels([{**rows[0], "ndcg10": 1.5}, *rows[1:]])
    with pytest.raises(ValueError, match="not a fraction"):
        R.build_panels([{**rows[0], "recall100": float("nan")}, *rows[1:]])
    gap = [r for r in rows if not (r["cell"] == FILTER and r["query_id"].endswith("q000"))]
    with pytest.raises(ValueError, match="different queries"):
        R.build_panels(gap)
    assert R.build_panels(gap, intersect=True)[("dev", "L2")].queries_dropped > 0
    two_repos = [{**rows[0], "repo": "other/repo"}, *rows[1:]]
    with pytest.raises(ValueError, match="two repositories"):
        R.build_panels(two_repos)
    ragged = [
        r
        for r in rows
        if not (
            r["cell"] == FILTER
            and r["seed"] == 101
            and r["level"] == "L2"
            and r["query_id"].endswith("q001")
        )
    ]
    with pytest.raises(ValueError, match="seeds cover different queries"):
        R.build_panels(ragged)


def test_unknown_source_kind_is_refused() -> None:
    rows = synthetic_rows(effects={}, seed=1, repos=3, per_repo=3)
    with pytest.raises(ValueError, match="source_kind"):
        R.analyse(rows, run_table(rows), source_kind="headline")


# ----------------------------------------------------------------------------- sealed order


def _final_rows() -> list[dict[str, Any]]:
    return synthetic_rows(effects={FILTER: 3.0}, seed=8, eval_set="exec377", repos=8)


def test_final_sets_refuse_without_a_dev_analysis_id() -> None:
    rows = _final_rows()
    with pytest.raises(R.SealedOrderError):
        _analyse(rows)
    with pytest.raises(R.SealedOrderError):
        _analyse(rows, dev_analysis_id="dev analysis")
    for sealed in R.SEALED_SETS:
        with pytest.raises(R.SealedOrderError):
            _analyse([{**r, "eval_set": sealed} for r in rows])


def test_dev_rows_need_no_id_and_the_id_is_recorded() -> None:
    dev = _analyse(synthetic_rows(effects={}, seed=1, repos=3, per_repo=3))
    assert dev["dev_analysis_entry"] is None
    s = _analyse(_final_rows(), dev_analysis_id="E-RQ2-DEV-ANALYSIS")
    assert s["dev_analysis_entry"] == "E-RQ2-DEV-ANALYSIS"


def test_the_id_must_be_a_registry_row_when_the_docs_are_given(tmp_path: Path) -> None:
    (tmp_path / "docs" / "experiments").mkdir(parents=True)
    (tmp_path / "docs" / "EXPERIMENTS.md").write_text("| E-OTHER | x |\n", encoding="utf-8")
    (tmp_path / "docs" / "experiments" / "B.md").write_text(
        "| E-RQ2-DEV-ANALYSIS | RQ2 |\n", encoding="utf-8"
    )
    assert R.require_dev_analysis("E-RQ2-DEV-ANALYSIS", tmp_path) == "E-RQ2-DEV-ANALYSIS"
    with pytest.raises(R.SealedOrderError, match="registry"):
        R.require_dev_analysis("E-NOT-THERE", tmp_path)


def test_the_loader_refuses_a_sealed_set_too(tmp_path: Path) -> None:
    rows = _final_rows()
    path = tmp_path / "rows.csv"
    cols = R.ROW_COLUMNS
    path.write_text(
        ",".join(cols)
        + "\n"
        + "\n".join(",".join("" if r[c] is None else str(r[c]) for c in cols) for r in rows)
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(R.SealedOrderError):
        R.read_rows(path)
    assert len(R.read_rows(path, dev_analysis_id="E-RQ2-DEV-ANALYSIS")) == len(rows)


# ------------------------------------------------------------------------- claims, fallback


def _claims(
    effect_l2: float, effect_l3: float, dev_effect: float = 3.0, *, levels=("L2", "L3")
) -> dict[str, Any]:
    final = synthetic_rows(
        effects={FILTER: effect_l2}, seed=21, eval_set="exec377", repos=10, levels=("L2",)
    )
    final += synthetic_rows(
        effects={FILTER: effect_l3}, seed=22, eval_set="exec377", repos=10, levels=("L3",)
    )
    final = [r for r in final if r["level"] in levels]
    dev = synthetic_rows(effects={FILTER: dev_effect}, seed=23, eval_set="dev", repos=5)
    return _analyse(final + dev, dev_analysis_id="E-RQ2-DEV-ANALYSIS")


def _claim(summary: dict[str, Any], contrast: str = SPEC.name) -> dict[str, Any]:
    return next(c for c in summary["claims"] if c["contrast"] == contrast)


def test_positive_needs_both_levels_dev_sign_and_gives_the_rq3_contrast() -> None:
    s = _claims(4.0, 4.0)
    assert _claim(s)["claim"] == "positive"
    assert s["fallback"]["separates"] is True
    assert "against" in s["fallback"]["rq3_primary_contrast"]
    assert "untrained" not in s["fallback"]["rq3_primary_contrast"]


def test_one_level_is_level_specific_and_triggers_the_fallback() -> None:
    s = _claims(4.0, 0.0)
    assert _claim(s)["claim"] == "level-specific"
    assert s["fallback"]["separates"] is False
    assert "untrained encoder" in s["fallback"]["rq3_primary_contrast"]
    assert s["fallback"]["fallback_declared"] is True


def test_dev_sign_disagreement_withholds_the_positive() -> None:
    s = _claims(4.0, 4.0, dev_effect=-3.0)
    c = _claim(s)
    assert c["claim"] == "inconclusive"
    assert any("dev" in r for r in c["reasons"])
    assert s["fallback"]["separates"] is False


def test_a_null_gives_bounds_or_inconclusive_never_positive() -> None:
    c = _claim(_claims(0.0, 0.0, dev_effect=0.0))
    assert c["claim"] in ("estimate-with-bounds", "inconclusive")
    assert c["claim"] != "positive"


def test_a_set_with_one_level_cannot_be_positive() -> None:
    s = _claims(4.0, 4.0, levels=("L2",))
    assert _claim(s)["claim"] == "level-specific"
    assert s["fallback"]["separates"] is False and s["fallback"]["sets_considered"] == []


def test_leave_largest_repository_out_is_reported_for_final_sets() -> None:
    s = _claims(4.0, 4.0)
    final = [c for c in s["contrasts"] if c["eval_set"] == "exec377" and c["primary"]]
    assert all(c["leave_largest_repo_out"] is not None for c in final)
    assert all(c["leave_largest_repo_out"]["repos"] == 9 for c in final)
    dev = [c for c in s["contrasts"] if c["eval_set"] == "dev" and c["primary"]]
    assert all(c["leave_largest_repo_out"] is None for c in dev)


def test_leave_out_sign_change_makes_l3_inconclusive() -> None:
    # one repository carries the whole L3 effect; without it the estimate changes sign
    rows = synthetic_rows(effects={FILTER: 0.0}, seed=31, eval_set="exec377", repos=6, per_repo=20)
    bump = [
        {**r, "ndcg10": min(1.0, r["ndcg10"] + 0.3), "recall100": min(1.0, r["recall100"] + 0.3)}
        if r["cell"] == FILTER and r["repo"] == "org/repo00"
        else r
        for r in rows
    ]
    dev = synthetic_rows(effects={FILTER: 3.0}, seed=32, eval_set="dev", repos=5)
    s = _analyse(bump + dev, dev_analysis_id="E-RQ2-DEV-ANALYSIS")
    lo3 = next(
        c
        for c in s["contrasts"]
        if c["eval_set"] == "exec377"
        and c["level"] == "L3"
        and c["primary"]
        and c["contrast"] == SPEC.name
    )
    assert lo3["leave_largest_repo_out"]["left_out"] == "org/repo00"
    assert lo3["leave_largest_repo_out"]["d"] < lo3["d"]
    assert _claim(s)["claim"] != "positive"


# -------------------------------------------------------------------------- dose-response


def _two_rates(gain_low: float, gain_high: float) -> list[dict[str, Any]]:
    cells = ("r20_raw", "r20_filter", "r40_raw", "r40_filter")
    rows = synthetic_rows(
        effects={"r20_filter": gain_low, "r40_filter": gain_high},
        seed=41,
        repos=10,
        cells=cells,
        levels=("L2", "L3"),
    )
    return rows


def test_dose_response_rise_needs_the_difference_of_gains_to_clear_zero() -> None:
    rates = {
        0.2: {"raw": "r20_raw", "filter": "r20_filter"},
        0.4: {"raw": "r40_raw", "filter": "r40_filter"},
    }
    panels = R.build_panels(_two_rates(1.0, 5.0))
    rises = [r for r in R.dose_response(panels, rates, draws=600) if r.get("kind") == "rise"]
    assert all(r["rises_with_r"] is True for r in rises)
    flat = R.build_panels(_two_rates(2.0, 2.0))
    rises = [r for r in R.dose_response(flat, rates, draws=600) if r.get("kind") == "rise"]
    assert all(r["rises_with_r"] is False for r in rises)


def test_dose_response_with_one_rate_is_not_evaluable() -> None:
    rows = synthetic_rows(
        effects={"inj_oracle": 3.0, "inj_filter_bm25": 1.5},
        seed=2,
        repos=8,
        cells=("inj_raw", "inj_oracle", "inj_filter_bm25"),
    )
    panels = R.build_panels(rows)
    rates = {0.4: {"raw": "inj_raw", "oracle": "inj_oracle", "filter_bm25": "inj_filter_bm25"}}
    out = R.dose_response(panels, rates, draws=300)
    rise = [r for r in out if r.get("kind") == "rise"]
    assert rise and all(r["rises_with_r"] is None for r in rise)
    share = next(
        r for r in out if r.get("method") == "filter_bm25" and r["level"] == "L2" and "gain" in r
    )
    assert share["share_of_oracle"] == pytest.approx(
        share["gain"]
        / next(
            r["gain"]
            for r in out
            if r.get("method") == "oracle" and r["level"] == "L2" and "gain" in r
        )
    )


def test_calibration_sanity_without_a_clean_cell_is_not_evaluable() -> None:
    rows = synthetic_rows(
        effects={"inj_oracle": 3.0}, seed=2, repos=8, cells=("inj_raw", "inj_oracle")
    )
    panels = R.build_panels(rows)
    out = R.calibration_sanity(panels, raw="inj_raw", oracle="inj_oracle", clean=None, draws=300)
    assert all(r["informative"] is None and "no clean cell" in r["note"] for r in out)
    assert all(r["oracle_recovers"] for r in out)


def test_calibration_sanity_with_a_clean_cell() -> None:
    rows = synthetic_rows(
        effects={"inj_oracle": 3.0, "clean": 4.0},
        seed=2,
        repos=8,
        cells=("inj_raw", "inj_oracle", "clean"),
    )
    out = R.calibration_sanity(
        R.build_panels(rows), raw="inj_raw", oracle="inj_oracle", clean="clean", draws=300
    )
    assert all(r["raw_degrades"] and r["informative"] for r in out)


# ------------------------------------------------------------------------- diagnostics


def test_distinct_directory_diagnostics_flag_repeats_and_shortfall() -> None:
    runs = [
        {
            "run_id": f"{c}{s}",
            "cell": c,
            "seed": s,
            "config_hash": "h",
            "optimizer_updates": 100,
            "examples_seen": 3200,
            "distinct_directories_seen": d,
            "pool_examples": 5000,
        }
        for c, d in (("mined_raw", 3000), ("mined_filter_bm25", 700), ("inj_raw", 3200))
        for s in (100, 101)
    ]
    diag = R.diagnostics(runs)
    assert diag["mined_filter_bm25"]["repeats_examples"] is True
    assert diag["mined_filter_bm25"]["below_common_distinct"] is True
    assert diag["mined_raw"]["below_common_distinct"] is False
    assert diag["inj_raw"]["below_common_distinct"] is False  # another family: not compared
    assert diag["mined_raw"]["config_hashes"] == {"100": "h", "101": "h"}


def test_diagnostics_are_carried_into_every_contrast_and_cell() -> None:
    rows = synthetic_rows(effects={FILTER: 1.0}, seed=2, repos=4)
    s = _analyse(rows)
    assert all(c["distinct_directories_arm"] == [3200] * 3 for c in s["contrasts"])
    assert set(s["diagnostics"]) == {"mined_raw", "mined_sub", FILTER}


# --------------------------------------------------------------------------- the plan


def test_contrast_cells_exist_in_the_launch_plan() -> None:
    from ril.training import rq2_plan

    ids = {c.cell_id for c in rq2_plan.CELLS}
    status = {c.cell_id: c.status for c in rq2_plan.CELLS}
    for spec in R.FINAL_CONTRASTS:
        assert spec.arm in ids and spec.reference in ids
        assert (spec.status == "confirmatory") == (status[spec.arm] == "confirmatory")
    conf = [s for s in R.FINAL_CONTRASTS if s.family == R.CONFIRMATORY]
    assert [(s.arm, s.reference) for s in conf] == [
        ("mined_filter_bm25", "mined_raw"),
        ("mined_filter_bm25", "mined_sub"),
    ]
    assert R.DELTA == 1.5 and R.ALPHA == 0.05 and R.DRAWS == 2000 and R.BOOT_SEED == 0


# --------------------------------------------------------------------------- simulation

SIM_SMOKE = 60


def _coverage(
    effect: float, tau: float, seeds: int, n: int, repos: int = 12, draws: int = 400
) -> tuple[float, float]:
    hit = hit_q = 0
    for i in range(n):
        rows = synthetic_rows(
            effects={FILTER: effect},
            seed=1000 + i,
            repos=repos,
            tau=tau,
            seeds=seeds,
            levels=("L2",),
        )
        panel = R.build_panels(rows)[("dev", "L2")]
        e = R.estimate(panel, SPEC, "ndcg10", Boot(panel.repos, 0, draws))
        assert e is not None
        hit += e.ci[0] <= effect <= e.ci[1]
        hit_q += e.ci_query[0] <= effect <= e.ci_query[1]
    return hit / n, hit_q / n


def _fwer(tau: float, n: int, draws: int = 400) -> tuple[float, float]:
    any_rej = any_eff = 0
    for i in range(n):
        rows = synthetic_rows(effects={FILTER: 0.0}, seed=5000 + i, tau=tau, seeds=3)
        conf = _confirmatory(_analyse(rows, draws=draws))
        assert len(conf) == 4  # two contrasts at two levels
        any_rej += any(c["holm"]["rejected"] for c in conf)
        any_eff += any(c["class"] == "reported-effect" for c in conf)
    return any_rej / n, any_eff / n


def test_simulation_smoke_runs_and_is_roughly_calibrated() -> None:
    cov, _ = _coverage(1.5, 1.0, 3, SIM_SMOKE)
    assert cov >= 0.80  # 60 simulations: standard error 0.03, this only catches gross errors
    rej, eff = _fwer(1.0, SIM_SMOKE)
    assert rej <= 0.15 and eff <= rej


@pytest.mark.slow
@pytest.mark.parametrize("seeds", [2, 3])
@pytest.mark.parametrize("effect", [0.0, 1.5, 3.0])
@pytest.mark.parametrize("tau", [0.0, 1.5])
def test_coverage_of_the_clustered_interval(effect: float, tau: float, seeds: int) -> None:
    # 1,000 simulations, 12 repositories of 25 queries, 500 draws. Monte Carlo standard error 0.7
    # points. Tolerance: coverage in [0.89, 0.97]; the percentile bootstrap over 12 whole
    # repositories is known to sit a little under 0.95, and the measured values are in the entry.
    cov, _ = _coverage(effect, tau, seeds, 1000, draws=500)
    assert 0.89 <= cov <= 0.97, cov


@pytest.mark.slow
def test_coverage_of_the_query_level_interval_with_two_repositories() -> None:
    # dev L3 has two repositories: the interval is query-level and, with no repository term in the
    # effect, should be near nominal: 1,000 simulations, tolerance [0.93, 0.97]
    hit = 0
    for i in range(1000):
        rows = synthetic_rows(
            effects={FILTER: 1.5}, seed=2000 + i, repos=2, per_repo=80, levels=("L2",)
        )
        panel = R.build_panels(rows)[("dev", "L2")]
        e = R.estimate(panel, SPEC, "ndcg10", Boot(panel.repos, 0, 500))
        assert e is not None and e.interval_kind == "query-level"
        hit += e.ci[0] <= 1.5 <= e.ci[1]
    assert 0.93 <= hit / 1000 <= 0.97


_NOMINAL_REASON = (
    "measured: the repository-clustered percentile interval of D17 does not hold the family-wise "
    "error rate of Holm at 8 to 12 repositories (1,000 simulations: 0.16 and 0.10 at 12 "
    "repositories, 0.22 and 0.15 at 8); the entry E-RQ2-ANALYSIS lists the options for the lead. "
    "strict: this test starts passing the day the interval rule changes, which must be a decision"
)


@pytest.mark.slow
@pytest.mark.xfail(strict=True, reason=_NOMINAL_REASON)
@pytest.mark.parametrize("tau", [0.0, 1.5])
def test_false_positive_rate_after_holm_is_nominal_with_twelve_repositories(tau: float) -> None:
    # 1,000 simulations of the four confirmatory contrasts under no effect: the chance that Holm
    # rejects any of them (family-wise) should not exceed the nominal 5% by more than 2 points
    # (Monte Carlo standard error 0.7). It does, so the assertion is expected to fail.
    rej, _ = _fwer(tau, 1000, draws=500)
    assert rej <= 0.07, rej


@pytest.mark.slow
@pytest.mark.parametrize("tau", [0.0, 1.5])
def test_family_wise_error_rate_of_the_current_rule_is_pinned(tau: float) -> None:
    # characterisation of the rule as protocol-fixed (D17, D72): 1,000 simulations, 12 repositories,
    # three seeds, 500 draws. Measured 0.16 (tau 0) and 0.10 (tau 1.5); the band keeps a change of
    # rule a conscious one. A reported effect (a rejection of at least delta) never occurs here
    # because the paired difference is estimated far more tightly than delta.
    rej, eff = _fwer(tau, 1000, draws=500)
    assert 0.07 <= rej <= 0.25, rej
    assert eff <= 0.02


@pytest.mark.slow
def test_false_reported_effects_stay_rare_in_a_wide_stress_case() -> None:
    # stress case: tau 3 points gives a standard error of the pooled difference of 0.92 (minimum
    # detectable difference 2.6 points, wider than the design's 1.3 to 1.5 at 12 repositories,
    # which tau 1.5 matches). 12 repositories, 1,000 simulations: measured 0.032; tolerance 0.07.
    # The delta guard, not Holm, is what keeps this rate low.
    _, eff = _fwer(3.0, 1000, draws=500)
    assert eff <= 0.07, eff
