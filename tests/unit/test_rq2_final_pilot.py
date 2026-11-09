"""The final analysis reproduces the stored pilot summaries (exploratory data, never a headline).

Each test rebuilds a summary the entries report from the stored per-query rows and compares it with
the stored table to the table's own rounding (two decimals, so an absolute tolerance of 0.006). The
pilots' bootstrap is the module's: whole repositories, shared draws, seed 0, 2,000 draws, queries
ordered by instance id. Skipped when the stored run files are not in the checkout.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import pytest

from ril.analysis import rq2_final as R
from ril.analysis import rq2_final_pilot as P

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
TOL = 0.006

NOISE = {
    "inj_raw": "n1_r40_raw",
    "inj_oracle": "n1_r40_oracle",
    "inj_sub": "n1_r40_sub",
    "inj_filter_bm25": "n1_r40_filter_bm25",
    "inj_filter_srs": "n1_r40_filter_srs",
    "inj_weight": "n1_r40_weight_srs",
}
MINED = {
    "mined_raw": "mp_raw",
    "mined_sub": "mp_sub",
    "mined_filter_bm25": "mp_filter_bm25",
}


def _need(*rels: str) -> None:
    missing = [r for r in rels if not (ROOT / r).exists()]
    if missing:
        pytest.skip(f"stored pilot files not present: {missing}")


def _table(rel: str) -> list[dict[str, str]]:
    with open(ROOT / rel, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _row(rows: list[dict[str, str]], **eq: str) -> dict[str, str]:
    hit = [r for r in rows if all(r[k] == v for k, v in eq.items())]
    assert len(hit) == 1, (eq, len(hit))
    return hit[0]


def _summary(cells: dict[str, str], **kw: Any) -> dict[str, Any]:
    rows, runs = P.pilot_inputs(str(RESULTS), cells)
    return R.analyse(rows, runs, source_kind="pilot", intersect=True, **kw)


def _compare(
    summary: dict[str, Any],
    table: list[dict[str, str]],
    arm: str,
    ref: str,
    stored: str,
    stored_ref: str,
    label: str | None = None,
) -> int:
    n = 0
    for level in R.LEVELS:
        c = next(
            x
            for x in summary["contrasts"]
            if x["arm"] == arm and x["reference"] == ref and x["level"] == level and x["primary"]
        )
        eq = {
            "name": f"{stored}:mean",
            "ref": f"{stored_ref}:mean",
            "level": level,
            "kind": "dense",
            "reading": "units_all_nomod",
            "part": "mean",
        }
        if label is not None:
            eq["label"] = label
        r = _row(table, **eq)
        assert c["d"] == pytest.approx(float(r["d"]), abs=TOL)
        assert c["ci_query"] == pytest.approx((float(r["d_q_lo"]), float(r["d_q_hi"])), abs=TOL)
        assert c["queries"] == int(r["queries"]) and c["repos"] == int(r["repos"])
        if c["interval"] == "repository-clustered":
            assert c["ci_cluster"] == pytest.approx(
                (float(r["d_c_lo"]), float(r["d_c_hi"])), abs=TOL
            )
            assert c["ci_boot_uncorrected"] == pytest.approx(c["ci_cluster"])
        else:
            assert c["ci_boot_uncorrected"] == pytest.approx(c["ci_query"])
        # the decision interval (D136) is a different, t-based one around the same estimate
        lo, hi = c["ci_uncorrected"]
        assert lo < c["d"] < hi
        n += 1
    return n


def test_noise_pilot_r40_effects_against_raw_reproduce() -> None:
    # E-PILOT-NOISE, rate 0.4, three seeds: gains over RAW with their intervals (L2 clustered over
    # five repositories, L3 query-level over two). Intervals equal the stored ones to rounding.
    _need("results/tables/n1/n1_effects.csv", "results/rq2/n1_r40_raw")
    table = _table("results/tables/n1/n1_effects.csv")
    s = _summary(NOISE)
    n = 0
    for arm, stored in NOISE.items():
        if arm == "inj_raw":
            continue
        n += (
            _compare(s, table, arm, "inj_raw", stored, "n1_r40_raw", "E-PILOT-NOISE r=0.4")
            if arm != "inj_sub"
            else 0
        )
    assert n == 8  # oracle, FILTER-BM25, FILTER-SweRankEmbed-Small, WEIGHT at two levels
    c = next(
        x
        for x in s["contrasts"]
        if x["arm"] == "inj_filter_bm25"
        and x["reference"] == "inj_raw"
        and x["level"] == "L2"
        and x["primary"]
    )
    assert round(c["d"], 2) == 1.82  # the number the entry and the state file quote


def test_noise_pilot_against_the_subsample_reproduces() -> None:
    _need("results/tables/n1/n1_effects.csv", "results/rq2/n1_r40_raw")
    table = _table("results/tables/n1/n1_effects.csv")
    s = _summary(NOISE)
    n = _compare(
        s,
        table,
        "inj_filter_bm25",
        "inj_sub",
        "n1_r40_filter_bm25",
        "n1_r40_sub",
        "E-PILOT-NOISE r=0.4",
    )
    n += _compare(
        s,
        table,
        "inj_filter_srs",
        "inj_sub",
        "n1_r40_filter_srs",
        "n1_r40_sub",
        "E-PILOT-NOISE r=0.4",
    )
    assert n == 4


def test_mined_pilot_effects_reproduce() -> None:
    # E-MINED-PILOT: FILTER-BM25 and the size-matched subsample against RAW on the mined set
    _need("results/tables/mp/mp_effects.csv", "results/rq2/mp_raw")
    table = _table("results/tables/mp/mp_effects.csv")
    extra = R.ContrastSpec(
        "mined_sub - mined_raw", "mined_sub", "mined_raw", "pilot", "exploratory"
    )
    s = _summary(MINED, contrasts=[*R.FINAL_CONTRASTS, extra])
    n = _compare(s, table, "mined_filter_bm25", "mined_raw", "mp_filter_bm25", "mp_raw")
    n += _compare(s, table, "mined_sub", "mined_raw", "mp_sub", "mp_raw")
    assert n == 4


def test_seed_spread_and_distinct_examples_reproduce() -> None:
    _need(
        "results/tables/n1/n1_seeds.csv",
        "results/tables/n1/n1_unique.csv",
        "results/rq2/n1_r40_raw",
    )
    s = _summary(NOISE)
    seeds = _table("results/tables/n1/n1_seeds.csv")
    for arm, stored in NOISE.items():
        for level in R.LEVELS:
            cell = next(
                c for c in s["cells"] if c["cell"] == arm and c["level"] == level and c["primary"]
            )
            r = _row(seeds, condition=stored, kind="dense", level=level, reading="units_all_nomod")
            stored_means = [float(x) for x in r["per_seed"].strip("[]").split(",")]
            assert cell["per_seed"] == pytest.approx(stored_means, abs=TOL)
            assert cell["seed_sd"] == pytest.approx(float(r["sd"]), abs=TOL)
    unique = _table("results/tables/n1/n1_unique.csv")
    for arm, stored in NOISE.items():
        for u in (x for x in unique if x["condition"] == stored):
            assert s["diagnostics"][arm]["distinct_directories_seen"][
                s["diagnostics"][arm]["seeds"].index(int(u["seed"]))
            ] == int(u["unique_examples_seen"])
        assert s["diagnostics"][arm]["repeats_examples"] == any(
            x["repeats_examples"] == "True" for x in unique if x["condition"] == stored
        )


def test_dose_response_reproduces_the_stored_gains_and_oracle_shares() -> None:
    # rule 2 on the two noise rates: gains over RAW per rate, share of the oracle recovery (the
    # entry's D58 figures 0.68 at L2 and 0.40 at L3 for FILTER-BM25 at r = 0.4), and the rise test
    _need("results/tables/n1/n1_effects.csv", "results/rq2/n1_r20_raw", "results/rq2/n1_r40_raw")
    cells = {
        f"r{r}_{m}": f"n1_r{r}_{c}"
        for r in (20, 40)
        for m, c in (("raw", "raw"), ("oracle", "oracle"), ("filter", "filter_bm25"))
    }
    rows, runs = P.pilot_inputs(str(RESULTS), cells)
    panels = R.build_panels(rows, intersect=True)
    rates = {
        0.2: {"raw": "r20_raw", "oracle": "r20_oracle", "filter": "r20_filter"},
        0.4: {"raw": "r40_raw", "oracle": "r40_oracle", "filter": "r40_filter"},
    }
    out = R.dose_response(panels, rates)
    table = _table("results/tables/n1/n1_effects.csv")
    for rate, stored_rate in ((0.2, "r=0.2"), (0.4, "r=0.4")):
        pct = int(rate * 100)
        for level in R.LEVELS:
            got = next(
                x
                for x in out
                if x.get("rate") == rate
                and x["method"] == "filter"
                and x["level"] == level
                and "gain" in x
            )
            r = _row(
                table,
                label=f"E-PILOT-NOISE {stored_rate}",
                name=f"n1_r{pct}_filter_bm25:mean",
                ref=f"n1_r{pct}_raw:mean",
                level=level,
                kind="dense",
                reading="units_all_nomod",
                part="mean",
            )
            assert got["gain"] == pytest.approx(float(r["d"]), abs=TOL)
            oracle = _row(
                table,
                label=f"E-PILOT-NOISE {stored_rate}",
                name=f"n1_r{pct}_oracle:mean",
                ref=f"n1_r{pct}_raw:mean",
                level=level,
                kind="dense",
                reading="units_all_nomod",
                part="mean",
            )
            assert got["share_of_oracle"] == pytest.approx(
                float(r["d"]) / float(oracle["d"]), abs=0.01
            )
    share = {
        x["level"]: x["share_of_oracle"]
        for x in out
        if x.get("rate") == 0.4 and x["method"] == "filter" and "gain" in x
    }
    assert round(share["L2"], 2) == 0.68 and round(share["L3"], 2) == 0.40
    rise = [x for x in out if x.get("kind") == "rise" and x["method"] == "filter"]
    assert {x["level"] for x in rise} == {"L2", "L3"}
    assert all(x["rate_high"] == 0.4 and x["rate_low"] == 0.2 for x in rise)


def test_learning_curve_step_reproduces() -> None:
    # E-PILOT-CURVE: change from step 0 to step 100, mean of two seeds, and each seed's change
    _need("results/tables/t3_curve/t3_curve_rows.csv", "results/rq2/t3_curve_raw")
    rows, _ = P.curve_inputs(str(RESULTS))
    spec = R.ContrastSpec("curve_100 - curve_0", "curve_100", "curve_0", "curve", "exploratory")
    s = R.analyse(rows, [], source_kind="pilot", contrasts=[spec], intersect=True)
    table = _table("results/tables/t3_curve/t3_curve_rows.csv")
    for level in R.LEVELS:
        c = next(x for x in s["contrasts"] if x["level"] == level and x["primary"])
        m = _row(
            table,
            part="M",
            step="100",
            seed="mean",
            level=level,
            kind="dense",
            reading="units_all_nomod",
        )
        assert c["d"] == pytest.approx(float(m["value"]), abs=0.0006)
        assert c["ci_query"] == pytest.approx((float(m["q_lo"]), float(m["q_hi"])), abs=0.0006)
        if level == "L2":
            assert c["ci_cluster"] == pytest.approx(
                (float(m["c_lo"]), float(m["c_hi"])), abs=0.0006
            )
        else:
            assert (
                c["ci_cluster"] is None
            )  # two repositories: the clustered interval is not estimable
        for seed in (0, 1):
            d = _row(
                table,
                part="delta",
                step="100",
                seed=str(seed),
                level=level,
                kind="dense",
                reading="units_all_nomod",
            )
            got = next(x["d"] for x in c["per_seed"] if x["seed"] == seed)
            assert got == pytest.approx(float(d["value"]), abs=0.0006)


def test_pilot_summary_is_labelled_and_cannot_reach_a_headline_table(tmp_path: Path) -> None:
    from ril.analysis import rq2_final_tables as T

    _need("results/rq2/mp_raw")
    s = _summary(MINED)
    assert s["source_kind"] == "pilot"
    (tmp_path / "results" / "rq2_final" / "analysis").mkdir(parents=True)
    R.write_summary(s, tmp_path / T.SUMMARY_REL)
    with pytest.raises(ValueError, match="cannot enter a headline table"):
        T.build_tables(tmp_path)
