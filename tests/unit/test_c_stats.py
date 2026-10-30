"""Shared statistics preserve the published power calculations and table bootstrap behavior."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pytest

from ril.analysis.e3_tables import Boot as OldBoot
from ril.evaluation import power, stats
from ril.evaluation.metrics import mean_ci

ROOT = Path(__file__).resolve().parents[2]


def test_published_2026_10_18_power_cells_are_unchanged() -> None:
    with (ROOT / "results/tables/x_power_mcnemar_mde.csv").open() as handle:
        for row in csv.DictReader(handle):
            effect = stats.mde_mcnemar(int(row["n"]), float(row["discordance"]))
            assert effect is not None
            assert round(100 * effect, 2) == float(row["mde_points"])
    with (ROOT / "results/tables/x_power_mcnemar_power.csv").open() as handle:
        for row in csv.DictReader(handle):
            assert stats.mcnemar_power(
                int(row["n"]), float(row["discordance"]), float(row["effect"])
            ) == pytest.approx(float(row["power"]), abs=1e-12)
    assert power.exact_mcnemar_p is stats.exact_mcnemar_p
    assert mean_ci is stats.mean_ci


def test_shared_bootstrap_matches_existing_table_builder_exactly() -> None:
    repos = ["a", "a", "b", "c", "c", "c"]
    values = np.arange(12, dtype=float).reshape(6, 2)
    old, shared = OldBoot(repos, seed=7, draws=100), stats.Boot(repos, seed=7, draws=100)
    for average in ("micro", "macro_repo", "cluster"):
        for a, b in zip(
            old.summarize(values, average), shared.summarize(values, average), strict=True
        ):
            np.testing.assert_array_equal(a, b)


def test_cluster_mean_is_query_weighted_with_random_denominators() -> None:
    result = stats.clustered_mean_ci([0, 0, 0, 1], ["a", "a", "a", "b"], draws=2000)
    assert result == (0.25, 0.0, 1.0)
    assert (
        stats.clustered_paired_diff_ci([0, 0, 0, 1], [0, 0, 0, 0], ["a", "a", "a", "b"], draws=2000)
        == result
    )
    assert stats.clustered_paired_diff_ci([0.3, 0.4], [0.3, 0.4], ["a", "b"]) == (0, 0, 0)


@pytest.mark.parametrize("values,repos", [([], []), ([1, 2], ["a"]), ([float("nan")], ["a"])])
def test_bad_cluster_samples_fail(values: list[float], repos: list[str]) -> None:
    with pytest.raises(ValueError):
        stats.clustered_mean_ci(values, repos)


def test_mde_accepts_measured_off_grid_discordance_and_checks_edges() -> None:
    for d in (7 / 51, 1 / 1001, 0.1333):
        effect = stats.mde_mcnemar(432, d)
        assert effect is None or 0 < effect <= d
    assert stats.mde_mcnemar(432, 0) is None
    for args in ((0, 0.2), (432, float("nan")), (432, 1.1)):
        with pytest.raises(ValueError):
            stats.mde_mcnemar(*args)
    with pytest.raises(ValueError):
        stats.mde_mcnemar(432, 0.2, step=0)
    with pytest.raises(ValueError):
        stats.exact_mcnemar_p(1.5, 3)
    with pytest.raises(ValueError):
        stats.discordant_probs(0.2, float("nan"))
