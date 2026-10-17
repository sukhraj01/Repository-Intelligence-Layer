"""Unit tests: bootstrap weights, paired comparison, selection, fitted weights, held-out merging."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pytest

from ril.analysis.e3_tables import (
    Boot,
    EvalTable,
    add_heldout_keys,
    compare,
    graph_cells,
    select_setting,
)
from ril.analysis.fitted_weights import fit_from_precision, fit_from_reach, scale_to_gamma


def make_table() -> EvalTable:
    keys = [
        "bm25",
        "list|all|C3|g0.5|h2",
        "list|rand_whole|all|C3|h2",
        "list|rand_files|all|C3|h2",
        "list|all|C3|w:loro_a__x|h2",
        "list|all|C3|w:loro_b__y|h2",
    ]
    rows = []
    for i in range(6):
        rows.append(
            {
                "instance": f"i{i}",
                "level": "L2",
                "repo": "a/x" if i < 3 else "b/y",
                "role": "dev",
                "dataset": "d",
                "folder": "f",
                "units": 10,
                "gold_units": 1,
            }
        )
    m = np.zeros((6, len(keys), 6))
    m[:, 0, :] = 0.2
    m[:, 1, :] = 0.5  # graph run beats BM25 by 30 points
    m[:, 2, :] = 0.45
    m[:, 3, :] = 0.3
    m[:, 4, :] = 0.6
    m[:, 5, :] = 0.7
    aux_keys = ["E|invoke|C3|g0.5|h1", "E|contain|C3|g0.5|h1"]
    aux = np.zeros((6, 2, 4))
    aux[:, 0, :] = [10, 2, 2, 1]
    aux[:, 1, :] = [20, 1, 1, 0]
    return EvalTable(keys, {k: i for i, k in enumerate(keys)}, rows, m, aux_keys, aux)


def test_bootstrap_point_estimates_and_intervals() -> None:
    boot = Boot(["a"] * 4 + ["b"] * 2, seed=0, draws=500)
    d = np.array([[1.0], [1.0], [1.0], [1.0], [4.0], [4.0]])
    mean, lo, hi = boot.summarize(d, "micro")
    assert mean[0] == pytest.approx(2.0)
    mean2, lo2, hi2 = boot.summarize(d, "macro")
    assert mean2[0] == pytest.approx(2.5)  # mean of the repository means 1 and 4
    assert lo[0] <= mean[0] <= hi[0]
    const = np.ones((6, 1))
    m3, l3, h3 = boot.summarize(const, "micro")
    assert l3[0] == pytest.approx(1.0) and h3[0] == pytest.approx(1.0)


def test_compare_reports_paired_differences_against_all_comparators() -> None:
    tab = make_table()
    cells = [c for c in graph_cells(tab) if c.labels["weights"] == ""]
    assert len(cells) == 1 and set(cells[0].controls) == {"rand_whole", "rand_files"}
    rows = compare(tab, tab.mask(role="dev"), "dev_all", "L2", cells, seed=0)
    r = next(
        x
        for x in rows
        if x["average"] == "micro" and x["metric"] == "ndcg10" and x["gold_reading"] == "units"
    )
    assert r["d_bm25"] == pytest.approx(30.0)
    assert r["d_rand_whole"] == pytest.approx(5.0)
    assert r["d_rand_files"] == pytest.approx(20.0)
    assert r["bm25"] == pytest.approx(20.0) and r["value"] == pytest.approx(50.0)
    assert r["queries"] == 6 and r["repos"] == 2
    assert r["d_bm25_lo"] == pytest.approx(30.0) and r["d_bm25_hi"] == pytest.approx(30.0)


def test_heldout_merge_takes_each_repository_from_its_own_fit() -> None:
    tab = make_table()
    added = add_heldout_keys(tab)
    assert added == ["list|all|C3|w:loro|h2"]
    col = tab.metrics[:, tab.index[added[0]], 0]
    assert list(col) == [0.6, 0.6, 0.6, 0.7, 0.7, 0.7]


def test_select_setting_uses_l2_ndcg_and_l3_recall_of_the_stated_cell() -> None:
    def row(level: str, metric: str, c: int, d: float) -> dict[str, object]:
        return {
            "subset": "core",
            "variant": "list",
            "gold_reading": "units",
            "average": "micro",
            "level": level,
            "metric": metric,
            "C": c,
            "gamma": 0.5,
            "hops": 1,
            "d_bm25": d,
        }

    rows = [
        row("L2", "ndcg10", 1, 1.0),
        row("L3", "recall100", 1, 1.0),
        row("L2", "ndcg10", 3, 3.0),
        row("L3", "recall100", 3, -1.0),
        row("L2", "ndcg10", 5, 0.0),
        row("L3", "recall100", 5, 4.0),
        row("L2", "recall100", 5, 99.0),  # ignored metric
    ]
    best = select_setting(rows, "core", "list")  # type: ignore[arg-type]
    assert best is not None and best["C"] == 5 and best["score"] == 2.0 and best["cells"] == 3
    assert select_setting(rows, "all", "list") is None  # type: ignore[arg-type]


def test_fitted_weights_from_reach_table_and_precision(tmp_path: Path) -> None:
    path = tmp_path / "reach.csv"
    cols = ["analysis", "group", "subset", "hop", "control", "obs_share", "difference"]
    stats = {
        "contain": (0.4, -0.01),
        "import": (0.1, 0.0),
        "invoke_both": (0.2, 0.1),
        "inherit": (0.04, 0.04),
        "tests": (0.0, 0.0),
        "configures": (0.0, 0.0),
        "co_change_n3": (0.03, 0.005),
    }
    with open(path, "w", newline="") as h:
        w = csv.DictWriter(h, fieldnames=cols)
        w.writeheader()
        for sub, (obs, diff) in stats.items():
            w.writerow(
                dict(
                    analysis="primary",
                    group="all_python",
                    subset=sub,
                    hop="le2",
                    control="same_files",
                    obs_share=obs,
                    difference=diff,
                )
            )
    reach = fit_from_reach(str(path))
    assert reach["contain"] == 0.5 and reach["invoke"] == 0.25 and reach["tests"] == 0.0
    excess = fit_from_reach(str(path), statistic="excess")
    assert excess["invoke"] == 0.5 and excess["contain"] == 0.0  # negative excess counts as 0
    with pytest.raises(ValueError):
        fit_from_reach(str(path), statistic="nope")
    assert scale_to_gamma({"a": 0.0}, 0.5) == {"a": 0.0}
    tab = make_table()
    mask = np.ones(6, dtype=bool)
    prec = fit_from_precision(tab, mask, families=("invoke", "contain"), seeds=3, gamma=0.5, hops=1)
    assert prec["invoke"] == 0.5 and prec["contain"] == pytest.approx(0.5 * 0.05 / 0.2)
