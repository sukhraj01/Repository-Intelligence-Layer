"""Scale extrapolation (E-MINE-PILOT, stage M4): arithmetic on a hand-built measurement."""

from __future__ import annotations

from ril.data_mining.scale import extrapolate

M = {
    "merged_prs_per_repo": 100.0,
    "pr_per_listing_page": 50.0,
    "graphql_cost_per_listing_page": 1.0,
    "listing_seconds_per_page": 3.0,
    "rest_calls_per_attempted_pr": 2.0,
    "graphql_cost_per_attempted_pr": 0.0,
    "mining_seconds_per_attempted_pr": 6.0,
    "mined_share": 0.5,
    "bytes_per_mined_pr": 1_000_000.0,
    "files_per_mined_pr": 4.0,
}


def test_extrapolation_is_the_product_of_measured_unit_and_target() -> None:
    out = extrapolate(M, repos=10, linked_prs=1000, quota_bytes=1e12, quota_files=1e9)
    assert out["listing_pages"] == 20 and out["graphql_points"] == 20
    assert out["rest_calls"] == 2000 and out["mined_prs"] == 500
    assert out["disk_gb"] == 0.5 and out["files"] == 2000
    assert out["wall_hours_measured_rate"] == round((20 * 3 + 1000 * 6) / 3600, 2)
    assert out["binding"].startswith("wall_time")


def test_quota_binds_when_exceeded_and_api_when_the_hourly_limit_is_slower() -> None:
    big = extrapolate(M, repos=10, linked_prs=100_000, quota_bytes=1e9, quota_files=1e9)
    assert big["binding"].startswith("disk_quota")
    fast = dict(M, mining_seconds_per_attempted_pr=0.1)
    out = extrapolate(fast, repos=10, linked_prs=100_000, quota_bytes=1e12, quota_files=1e9)
    assert out["binding"].startswith("api_limit") and out["api_hours_at_limit"] == 40.0


def test_scale_inputs_divide_measured_totals_by_the_units_they_were_measured_on() -> None:
    from ril.data_mining.report import scale_inputs

    summary = {
        "yield": {
            "merged_prs": 1000,
            "repositories_listed": 10,
            "prs_mined_attempted": 200,
            "prs_mined": 150,
        }
    }
    costs = {
        "api": {"calls_by_endpoint": {"graphql": 20, "repos/compare": 210}},
        "seconds": {"listing": 1.0, "mining": 2000.0},
        "disk": {"bytes_per_mined_pr": 1.5e6, "files_per_mined_pr": 4.0},
    }
    u = scale_inputs(summary, costs, listing_seconds=100.0)
    assert u["merged_prs_per_repo"] == 100.0 and u["listing_seconds_per_page"] == 5.0
    assert u["rest_calls_per_attempted_pr"] == 1.05 and u["mined_share"] == 0.75
    assert u["mining_seconds_per_attempted_pr"] == 10.0
    out = extrapolate(u, repos=20, linked_prs=2000, quota_bytes=1e12, quota_files=1e12)
    assert out["listing_pages"] == 40 and out["rest_calls"] == 2100
