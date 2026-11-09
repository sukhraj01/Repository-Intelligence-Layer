"""The Student t distribution and the cluster-robust t interval (D136, DEV-040)."""

from __future__ import annotations

import numpy as np
import pytest

from ril.analysis import cluster_t as C


@pytest.mark.parametrize(
    ("p", "df", "want"),
    [
        (0.975, 1, 12.7062),
        (0.975, 2, 4.3027),
        (0.975, 7, 2.3646),
        (0.975, 11, 2.2010),
        (0.975, 19, 2.0930),
        (0.975, 30, 2.0423),
        (0.975, 1000, 1.9623),
        (0.995, 11, 3.1058),
        (0.99, 7, 2.9980),
        (0.9, 5, 1.4759),
    ],
)
def test_t_quantiles_match_tables(p: float, df: int, want: float) -> None:
    assert C.t_ppf(p, df) == pytest.approx(want, abs=5e-5)


def test_t_cdf_and_ppf_are_inverse_and_symmetric() -> None:
    for df in (1, 3, 7, 19):
        for x in (-4.0, -1.0, 0.0, 0.7, 3.2):
            assert C.t_ppf(C.t_cdf(x, df), df) == pytest.approx(x, abs=1e-8)
            assert C.t_cdf(x, df) + C.t_cdf(-x, df) == pytest.approx(1.0)
    assert C.t_cdf(2.0, 5) == pytest.approx(0.94903, abs=1e-5)


def test_bad_arguments_are_refused() -> None:
    with pytest.raises(ValueError):
        C.t_ppf(1.0, 5)
    with pytest.raises(ValueError):
        C.t_cdf(0.0, 0)
    with pytest.raises(ValueError):
        C.cluster_t(np.array([1.0]), ["a"])


def test_cluster_t_equals_the_textbook_t_when_every_cluster_is_one_value() -> None:
    # twelve singleton repositories: the linearised variance is the sample variance over n
    x = np.array([0.3, -0.1, 0.8, 0.2, 0.5, -0.4, 0.1, 0.6, 0.0, 0.9, 0.4, -0.2])
    r = C.cluster_t(x, [f"r{i}" for i in range(12)])
    assert r.kind == "repository-clustered" and r.df == 11
    assert r.se == pytest.approx(x.std(ddof=1) / np.sqrt(len(x)))
    lo, hi = r.interval(0.05)
    half = 2.2010 * x.std(ddof=1) / np.sqrt(len(x))
    assert (lo, hi) == pytest.approx((x.mean() - half, x.mean() + half), abs=1e-4)


def test_cluster_t_matches_a_hand_computed_ratio_estimator() -> None:
    # repositories of unequal size: the point estimate is the mean over queries
    x = np.array([1.0, 2.0, 3.0, 10.0, 12.0, 0.0, 1.0, 2.0, 3.0])
    g = ["a"] * 3 + ["b"] * 2 + ["c"] * 4
    r = C.cluster_t(x, g)
    m = x.mean()
    s = [(x[:3] - m).sum(), (x[3:5] - m).sum(), (x[5:] - m).sum()]
    want = np.sqrt(3 / 2 * sum(v * v for v in s)) / len(x)
    assert r.d == pytest.approx(m) and r.se == pytest.approx(want) and r.df == 2


def test_fewer_than_three_repositories_fall_back_to_queries() -> None:
    x = np.arange(10.0)
    r = C.cluster_t(x, ["a"] * 5 + ["b"] * 5)
    assert r.kind == "query-level" and r.df == 9 and r.clusters == 10


def test_zero_variance_is_a_point_interval_and_a_decided_p_value() -> None:
    same = C.cluster_t(np.full(6, 0.5), [f"r{i}" for i in range(6)])
    assert same.interval(0.05) == (0.5, 0.5) and same.p_value() == 0.0
    nil = C.cluster_t(np.zeros(6), [f"r{i}" for i in range(6)])
    assert nil.p_value() == 1.0


def test_p_value_agrees_with_the_interval() -> None:
    rng = np.random.default_rng(3)
    for _ in range(40):
        x = rng.normal(0.4, 1.0, 30)
        g = [f"r{i % 8}" for i in range(30)]
        r = C.cluster_t(x, g)
        lo, hi = r.interval(0.05)
        assert (r.p_value() < 0.05) == (lo > 0 or hi < 0)
