"""Analysis of the no-retrieval floor arm (RQ3, E-RQ3-FLOOR, D169). Exploratory, descriptive.

The floor arm has one repeat. Contrasts are another arm minus the floor, by the registered method
(paired difference of the per-instance mean resolved fraction, paired bootstrap interval, sign-flip
permutation p), unadjusted and with no decision: in the arm's own repeats (3 for the untrained arm,
2 for the oracle) and at matched k (the other arm restricted to the floor's repeat 0). Reads stored
rows only; reuses the helpers of ``ril.analysis.rq3_oracle``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ril.analysis.rq3_oracle import Table, _contrast, arm_scores
from ril.analysis.rq3_results import Rows

FLOOR = "floor"


def floor_contrasts(
    rows: Rows,
    instances: Sequence[str],
    arms: Mapping[str, Sequence[int]],
    *,
    seed: int = 0,
    resamples: int = 10_000,
) -> Table:
    """``other minus floor`` for every arm in ``arms`` except the floor, both readings.

    The floor must be in ``arms``; its repeats define the matched-k form. Differences are in
    resolved-fraction units (multiply by 100 for points).
    """
    floor_runs = tuple(arms[FLOOR])
    out: Table = []
    for reading in ("exact", "tolerant"):
        f = arm_scores(rows, instances, FLOOR, floor_runs, reading)
        for other, runs in arms.items():
            if other == FLOOR:
                continue
            own = arm_scores(rows, instances, other, runs, reading)
            out.append(
                _contrast(
                    own,
                    f,
                    other,
                    FLOOR,
                    f"own k ({len(runs)} vs {len(floor_runs)})",
                    reading,
                    seed + 100,
                    resamples,
                )
            )
            if tuple(runs) != floor_runs:
                matched = arm_scores(rows, instances, other, floor_runs, reading)
                out.append(
                    _contrast(
                        matched,
                        f,
                        other,
                        FLOOR,
                        f"matched k ({len(floor_runs)} vs {len(floor_runs)})",
                        reading,
                        seed + 100,
                        resamples,
                    )
                )
    return out


def mdd_for(mdd: Sequence[Mapping[str, Any]], rate: float, runs: Sequence[int]) -> Table:
    """Stored minimum detectable differences at ``rate`` for the given repeat counts, as stored."""
    keep = {int(k) for k in runs}
    return [dict(r) for r in mdd if abs(float(r["rate"]) - rate) < 1e-9 and int(r["runs"]) in keep]
