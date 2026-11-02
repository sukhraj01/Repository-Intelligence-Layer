"""Scale cost of the mining run (stage M4): linear extrapolation from a measured pilot.

Implements ``docs/experiments/B.md`` E-MINE-PILOT question 5. Every output is a product of a
measured per-unit quantity and a target count; nothing is fitted. The constraints compared are
the ones that can bind: the REST and GraphQL hourly limits, the wall time of one process (the
walls of the job queue are applied by the caller), and the account's disk and file quota. The
binding constraint is the one with the largest ratio of required to available hours or bytes.

Kept compatible with Python 3.10 (the cluster's compute nodes).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

REST_PER_HOUR = 5000
GRAPHQL_POINTS_PER_HOUR = 5000
JOB_WALL_HOURS = 12.0


def extrapolate(
    measured: Mapping[str, float],
    *,
    repos: int,
    linked_prs: int,
    quota_bytes: float,
    quota_files: float,
) -> dict[str, Any]:
    """Cost of listing ``repos`` repositories and mining ``linked_prs`` linked pull requests.

    ``measured`` keys: ``merged_prs_per_repo``, ``graphql_cost_per_listing_page``,
    ``pr_per_listing_page``, ``listing_seconds_per_page``, ``rest_calls_per_attempted_pr``,
    ``graphql_cost_per_attempted_pr``, ``mining_seconds_per_attempted_pr``,
    ``mined_share`` (mined / attempted), ``bytes_per_mined_pr``, ``files_per_mined_pr``.
    """
    pages = repos * measured["merged_prs_per_repo"] / measured["pr_per_listing_page"]
    list_points = pages * measured["graphql_cost_per_listing_page"]
    list_seconds = pages * measured["listing_seconds_per_page"]
    rest = linked_prs * measured["rest_calls_per_attempted_pr"]
    mine_points = linked_prs * measured["graphql_cost_per_attempted_pr"]
    mine_seconds = linked_prs * measured["mining_seconds_per_attempted_pr"]
    mined = linked_prs * measured["mined_share"]
    disk = mined * measured["bytes_per_mined_pr"]
    files = mined * measured["files_per_mined_pr"]
    api_hours = max(rest / REST_PER_HOUR, (list_points + mine_points) / GRAPHQL_POINTS_PER_HOUR)
    wall_hours = (list_seconds + mine_seconds) / 3600
    ratios = {
        "api_limit": api_hours / max(wall_hours, 1e-9),
        "disk_quota": disk / quota_bytes,
        "file_quota": files / quota_files,
    }
    out: dict[str, Any] = {
        "repos": repos,
        "linked_prs": linked_prs,
        "listing_pages": round(pages),
        "graphql_points": round(list_points + mine_points),
        "rest_calls": round(rest),
        "api_hours_at_limit": round(api_hours, 2),
        "wall_hours_measured_rate": round(wall_hours, 2),
        "sessions_of_12h": math.ceil(wall_hours / JOB_WALL_HOURS),
        "mined_prs": round(mined),
        "disk_gb": round(disk / 1e9, 2),
        "files": round(files),
        "disk_share_of_quota": round(ratios["disk_quota"], 3),
        "files_share_of_quota": round(ratios["file_quota"], 3),
    }
    out["binding"] = _binding(wall_hours, api_hours, ratios)
    return out


def _binding(wall_hours: float, api_hours: float, ratios: Mapping[str, float]) -> str:
    """Name of the constraint that is exceeded most (or comes closest), with its reading."""
    if ratios["disk_quota"] >= 1 or ratios["file_quota"] >= 1:
        worst = max(("disk_quota", "file_quota"), key=lambda k: ratios[k])
        return f"{worst} (required {ratios[worst]:.2f} of the account quota)"
    if api_hours > wall_hours:
        return (
            f"api_limit ({api_hours:.1f} h at the hourly limit against {wall_hours:.1f} h measured)"
        )
    return f"wall_time ({wall_hours:.1f} h measured; the API limit needs {api_hours:.1f} h)"
