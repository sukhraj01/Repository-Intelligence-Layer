"""What the executable subset needs before RQ3 can run on it: labels, unit records, build cost.

Implements D106 (``docs/RQ3_PILOT.md``), part 4 of the brief: report, without choosing, how many
executable instances carry L2 and L3 labels and stored unit records, which repositories lack
records, and what building them would cost at the rates measured in the eight-repository build
(``results/tables/eval_repo_build_measured.csv``, E-EVAL-REPOS-BUILD).
"""

from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def coverage_rows(
    executable: Sequence[Mapping[str, Any]],
    l2_ids: Iterable[str],
    l3_ids: Iterable[str],
    unit_ids: Iterable[str],
    all_instances: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Per repository: instances, executable, and the executable ones with each resource."""
    l2, l3, units = set(l2_ids), set(l3_ids), set(unit_ids)
    members = {m["instance_id"] for m in executable}
    out: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "instances": 0,
            "executable": 0,
            "exec_with_l2": 0,
            "exec_with_l3": 0,
            "exec_with_units": 0,
            "exec_l2_and_units": 0,
            "exec_l3_and_units": 0,
        }
    )
    for inst in all_instances:
        iid, repo = inst["instance_id"], inst["repo"]
        row = out[repo]
        row["instances"] += 1
        if iid in members:
            row["executable"] += 1
            row["exec_with_l2"] += iid in l2
            row["exec_with_l3"] += iid in l3
            row["exec_with_units"] += iid in units
            row["exec_l2_and_units"] += iid in l2 and iid in units
            row["exec_l3_and_units"] += iid in l3 and iid in units
    return [{"repo": repo, **out[repo]} for repo in sorted(out)]


@dataclass(frozen=True)
class BuildRates:
    """Rates measured in the eight-repository build, per repository, as (low, median, high)."""

    seconds_per_snapshot_per_1k_units: tuple[float, float, float]
    distinct_text_share: tuple[float, float, float]
    texts_per_second_overall: float


def rates_from_measured(path: Path, overall_texts_per_second: float) -> BuildRates:
    """Rates from ``eval_repo_build_measured.csv`` (instance-cache pass; distinct texts / units)."""
    sec: list[float] = []
    share: list[float] = []
    with path.open() as src:
        for r in csv.DictReader(src):
            snaps = float(r["snapshots"])
            units = float(r["units_median_per_snapshot"])
            sec.append(float(r["e3_prepare_seconds_measured"]) / snaps / (units / 1000.0))
            share.append(float(r["distinct_unit_texts_full_measured"]) / (snaps * units))

    def lmh(xs: list[float]) -> tuple[float, float, float]:
        return min(xs), statistics.median(xs), max(xs)

    return BuildRates(lmh(sec), lmh(share), overall_texts_per_second)


def build_cost(
    snapshots: int, units_per_snapshot: float, rates: BuildRates
) -> dict[str, tuple[float, float, float]]:
    """Cost of unit records, instance caches and dense stores for one repository.

    ``cpu_hours`` from the instance-cache pass; ``gpu_hours`` from distinct texts at the overall
    measured encode rate, per checkpoint. Both scale with the unit count, which is an input.
    """
    cpu = tuple(
        snapshots * (units_per_snapshot / 1000.0) * s / 3600.0
        for s in rates.seconds_per_snapshot_per_1k_units
    )
    texts = tuple(snapshots * units_per_snapshot * x for x in rates.distinct_text_share)
    gpu = tuple(t / rates.texts_per_second_overall / 3600.0 for t in texts)
    return {
        "cpu_hours": (cpu[0], cpu[1], cpu[2]),
        "gpu_hours_per_checkpoint": (gpu[0], gpu[1], gpu[2]),
        "distinct_texts": (texts[0], texts[1], texts[2]),
    }
