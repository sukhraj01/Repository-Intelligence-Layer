"""Tests for the stored-output analysis: variance components recovered from simulated data, the
minimum detectable difference, slices, winners and oracles, concentration, and the readers on a
small synthetic results tree."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np

from ril.analysis import stored_analysis as sa
from ril.analysis import stored_rows as sr
from ril.analysis import stored_stats as ss


def _simulate(
    rng: np.random.Generator,
    repos: int,
    per_repo: int,
    seeds: int,
    s_repo: float,
    s_q: float,
    s_sq: float,
) -> tuple[ss.FloatArray, ss.IntArray]:
    code = np.repeat(np.arange(repos), per_repo)
    a = rng.normal(0, s_repo, repos)[code]
    b = rng.normal(0, s_q, len(code))
    e = rng.normal(0, s_sq, (seeds, len(code)))
    return a + b + e, code.astype(np.int64)


def test_components_recover_simulated_variances() -> None:
    rng = np.random.default_rng(0)
    est = [ss.components(*_simulate(rng, 40, 25, 3, 0.3, 0.2, 0.1)) for _ in range(20)]
    for key, truth in (("s2_repo", 0.09), ("s2_query", 0.04), ("s2_seedquery", 0.01)):
        assert abs(float(np.mean([e[key] for e in est])) - truth) < 0.2 * truth + 0.005, key
    assert float(np.mean([e["s2_seed"] for e in est])) < 0.002  # no seed main effect simulated


def test_seed_main_effect_is_found() -> None:
    rng = np.random.default_rng(1)
    y, code = _simulate(rng, 5, 200, 4, 0.0, 0.1, 0.05)
    y = y + np.array([0.0, 0.2, -0.2, 0.1])[:, None]
    c = ss.components(y, code)
    assert c["s2_seed"] > 0.01
    assert c["seed_var_direct"] >= c["s2_seed"]


def test_negative_estimate_is_floored_and_flagged() -> None:
    y = np.zeros((2, 6))
    y[0], y[1] = [0, 1, 0, 1, 0, 1], [1, 0, 1, 0, 1, 0]  # seeds disagree, query means equal
    c = ss.components(y, np.array([0, 0, 0, 1, 1, 1]))
    assert c["s2_query"] == 0.0 and "s2_query<0" in c["flags"]


def test_minimum_detectable_shrinks_with_seeds_but_not_to_zero() -> None:
    c = {
        "n": 100,
        "repos": 4,
        "s2_repo": 0.01,
        "s2_query": 0.02,
        "s2_seedquery": 0.04,
        "s2_seed": 0.004,
    }
    m2, m3, m100 = (ss.minimum_detectable(c, k) for k in (2, 3, 100))
    assert m2 > m3 > m100 > 0
    floor = ss.Z_POWER * math.sqrt(0.01 / 4 + 0.02 / 100)
    assert m100 > floor
    assert ss.minimum_detectable(c, 2, with_repo=False) < m2


def test_old_style_seed_bound_matches_formula() -> None:
    sd, mdd = ss.old_style_seed_mdd([0.25, 0.25], 3)
    assert sd == 0.5
    assert abs(mdd - ss.Z_POWER * 0.5 * math.sqrt(2 / 3)) < 1e-12


def test_quartile_bins_merge_equal_cuts_and_cover_everything() -> None:
    v = np.array([1.0] * 6 + [2.0, 3.0, 9.0, 20.0])
    bins = ss.quartile_bins(v)
    assert sum(int(m.sum()) for _, m in bins) == len(v)
    assert len(bins) < 4 or len({lab for lab, _ in bins}) == len(bins)


def test_slice_gain_overall_and_repository_cluster_interval() -> None:
    rng = np.random.default_rng(2)
    repo = np.repeat(np.arange(6), 20).astype(np.int64)
    gain = 0.1 + rng.normal(0, 0.05, 120)
    masks = {"low": np.arange(120) < 40, "none": np.zeros(120, dtype=bool)}
    rows = ss.slice_gain(gain, repo, masks, 300, 0)
    names = [r["slice"] for r in rows]
    assert names == ["all", "low"]  # empty slice dropped
    allrow = rows[0]
    assert allrow["lo"] < allrow["mean_gain"] < allrow["hi"]
    assert (
        abs(allrow["share_positive"] + allrow["share_negative"] + allrow["share_zero"] - 1) < 1e-9
    )


def test_complementarity_winners_ties_and_oracle() -> None:
    arms = {
        "RAW": np.array([0.5, 0.5, 0.0, 0.2]),
        "A": np.array([0.7, 0.5, 0.0, 0.1]),
        "B": np.array([0.4, 0.9, 0.0, 0.1]),
    }
    r = ss.complementarity(arms, "RAW", [0.0, 0.15, 0.3])
    assert r["wins"] == {"RAW": 1, "A": 1, "B": 1} and r["ties"] == 1
    assert r["oracle_mean"] == np.mean([0.7, 0.9, 0.0, 0.2])
    assert r["share_best_other_beats_ref"] == {"0": 0.5, "0.15": 0.5, "0.3": 0.25}
    assert r["oracle_minus_reference"] > 0


def test_oracle_of_identical_arms_equals_reference() -> None:
    v = np.random.default_rng(3).random(30)
    r = ss.complementarity({"RAW": v, "X": v.copy()}, "RAW", [0.0])
    assert r["oracle_minus_reference"] == 0.0 and r["ties"] == 30
    assert r["share_best_other_beats_ref"] == {"0": 0.0}


def test_concentration_shares() -> None:
    loss = np.array([0.5, 0.3, 0.1, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    c = ss.concentration(loss, [0.1, 0.2])
    assert abs(c["share_total_0.1"] - 0.5) < 1e-12 and abs(c["share_total_0.2"] - 0.8) < 1e-12
    flat = ss.concentration(np.full(10, 0.1), [0.1])
    assert abs(flat["share_total_0.1"] - 0.1) < 1e-12
    assert math.isnan(ss.concentration(np.zeros(5), [0.2])["share_total_0.2"])


def test_bootstrap_is_seeded() -> None:
    repo = np.repeat(np.arange(5), 10).astype(np.int64)
    v = np.random.default_rng(4).random(50)
    f = lambda idx: float(v[idx].mean())  # noqa: E731
    assert ss.bootstrap(repo, f, 200, 7) == ss.bootstrap(repo, f, 200, 7)
    assert ss.bootstrap(repo, f, 200, 7, clustered=False) != ss.bootstrap(repo, f, 200, 7)


FIELDS = ["instance", "level", "repo", "role", "name"] + [
    f"units_all_nomod:{m}" for m in ("ndcg10", "recall100")
]


def _tree(root: Path) -> Path:
    """Two cells with two seeds each, two repositories, one query with an empty metric."""
    rng = np.random.default_rng(5)
    for cell, shift in (("c_raw", 0.0), ("c_arm", 0.05)):
        for seed in (0, 1):
            d = root / cell / f"2026-01-01_{seed}"
            d.mkdir(parents=True)
            (d / "config.yaml").write_text(f"exp_id: {cell}\nseed: {seed}\n")
            with open(d / "query_rows.csv", "w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=FIELDS)
                w.writeheader()
                for r in range(2):
                    for i in range(6):
                        for lv in ("L2", "L3"):
                            base = 0.3 + 0.1 * r
                            v = float(np.clip(base + shift + rng.normal(0, 0.05), 0, 1))
                            row = {
                                "instance": f"o__r{r}-{i}",
                                "level": lv,
                                "repo": f"o/r{r}",
                                "role": "dev",
                                "name": "dense:x",
                                "units_all_nomod:ndcg10": v,
                                "units_all_nomod:recall100": v,
                            }
                            if (r, i, lv) == (0, 0, "L3"):
                                row["units_all_nomod:recall100"] = ""
                            w.writerow(row)
                            w.writerow({**row, "name": "bm25"})
    return root


def test_readers_align_runs_and_skip_undefined_metrics(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    runs = sr.discover(str(root), ["c_raw", "c_arm", "missing"])
    assert [r.seed for r in runs["c_raw"]] == [0, 1] and runs["missing"] == []
    panel = sr.build_panel({k: v for k, v in runs.items() if v})
    assert len(panel.keys) == 23  # 24 queries, one with an empty L3 metric
    assert panel.values["c_raw"].shape == (2, 23)
    assert panel.values["c_arm"].mean() > panel.values["c_raw"].mean()
    assert set(panel.repos) == {"o/r0", "o/r1"}


def test_gold_info_counts_units_without_module_ids(tmp_path: Path) -> None:
    pos = [
        {"level": "L2", "kind": "method", "units_all": ["a.py::C.m", "a.py::C", "a.py::<module>"]},
        {"level": "L2", "kind": "module_residual", "units_all": ["a.py::<module>"]},
        {"level": "L3", "kind": "function", "units_all": ["b.py::f"]},
    ]
    (tmp_path / "o__r-1.json").write_text(json.dumps({"positives": pos}))
    info = sr.gold_info(str(tmp_path), [("L2", "o__r-1"), ("L3", "o__r-1")])
    assert info[("L2", "o__r-1")] == {"n_pos": 2, "kinds": {"method"}}
    assert info[("L3", "o__r-1")] == {"n_pos": 1, "kinds": {"function"}}


def test_slice_labels_cover_kinds_and_mix() -> None:
    keys = [("L2", f"i{i}") for i in range(4)]
    info = {
        keys[0]: {"n_pos": 1, "kinds": {"function"}},
        keys[1]: {"n_pos": 2, "kinds": {"function", "method"}},
        keys[2]: {"n_pos": 3, "kinds": {"class"}},
        keys[3]: {"n_pos": 9, "kinds": {"method"}},
    }
    fam = sa.slice_labels(keys, ["a", "a", "b", "b"], info)
    assert fam["kind"]["function"].tolist() == [True, True, False, False]
    assert fam["kind_mix"]["mixed_kinds"].tolist() == [False, True, False, False]
    assert sum(int(m.sum()) for m in fam["n_positives"].values()) == 4


def test_run_all_is_deterministic_on_a_tree(tmp_path: Path) -> None:
    root = _tree(tmp_path / "rq2")
    runs = sr.discover(str(root), ["c_raw", "c_arm"])
    panel = sr.build_panel(runs)
    repo = ss.repo_index(panel.repos)
    d = panel.values["c_arm"] - panel.values["c_raw"]
    a = ss.components(d, repo)
    b = ss.components(d, repo)
    assert a == b
    assert ss.minimum_detectable(ss.mean_components([a]), 2) > 0
