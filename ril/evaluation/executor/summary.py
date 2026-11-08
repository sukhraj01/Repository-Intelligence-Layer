"""How the executable subset differs from the 500, and what a run costs.

Implements D106 (``docs/RQ3_PILOT.md``): the report states the subset's size, repositories and
difference from the 500 (repository, L2/L3 label availability, the dataset's difficulty field),
because a result on the subset does not carry to the excluded instances. Cost is reported as
p50 / p95 / p99 (nearest rank), never a mean.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from ril.evaluation.executor.spec import InstanceSpec


def percentile(values: Sequence[float], q: float) -> float:
    """Nearest-rank percentile (``q`` in 0..100) of a non-empty sample."""
    xs = sorted(values)
    rank = max(1, math.ceil(q / 100.0 * len(xs)))
    return xs[rank - 1]


def p50_p95_p99(values: Sequence[float]) -> dict[str, float]:
    return {f"p{q}": round(percentile(values, q), 1) for q in (50, 95, 99)}


def distribution_shift(
    specs: Sequence[InstanceSpec],
    members: Iterable[Mapping[str, Any]],
    l2_ids: Iterable[str],
    l3_ids: Iterable[str],
) -> list[dict[str, Any]]:
    """Rows (dimension, value, n_all, share_all, n_exec, share_exec): the 500 against the subset."""
    ids = {m["instance_id"] for m in members}
    l2, l3 = set(l2_ids), set(l3_ids)
    dims: dict[str, dict[str, tuple[int, int]]] = {}

    def add(dim: str, value: str, in_exec: bool) -> None:
        a, b = dims.setdefault(dim, {}).get(value, (0, 0))
        dims[dim][value] = (a + 1, b + (1 if in_exec else 0))

    for s in specs:
        e = s.instance_id in ids
        add("repository", s.repo, e)
        add("difficulty", s.difficulty or "unrecorded", e)
        add("has_L2_labels", "yes" if s.instance_id in l2 else "no", e)
        add("has_L3_labels", "yes" if s.instance_id in l3 else "no", e)
    n_all, n_exec = len(specs), len(ids)
    rows = []
    for dim, values in dims.items():
        for value in sorted(values):
            a, b = values[value]
            rows.append(
                {
                    "dimension": dim,
                    "value": value,
                    "n_all": a,
                    "share_all": round(a / n_all, 4),
                    "n_exec": b,
                    "share_exec": round(b / n_exec, 4) if n_exec else 0.0,
                }
            )
    return rows


def cost_summary(rows: Sequence[Mapping[str, Any]], member_ids: Iterable[str]) -> dict[str, Any]:
    """Seconds per instance and run for the subset members, cold (run 1) and warm (run 2)."""
    keep = set(member_ids)
    by_run: dict[int, list[float]] = {}
    peaks: list[float] = []
    by_phase: Counter[str] = Counter()
    for r in rows:
        if r["instance_id"] not in keep:
            continue
        by_run.setdefault(int(r["run"]), []).append(float(r["seconds"]["total"]))
        peaks.append(float(r["peak_rss_mb"]))
        for k, v in r["seconds"].items():
            if k != "total":
                by_phase[k] += v
    out: dict[str, Any] = {
        "instances": len(keep),
        "peak_rss_mb": p50_p95_p99(peaks) if peaks else {},
    }
    for run, xs in sorted(by_run.items()):
        out[f"run_{run}_seconds"] = {**p50_p95_p99(xs), "sum_hours": round(sum(xs) / 3600, 2)}
    out["seconds_by_phase_all_runs"] = {k: round(v) for k, v in by_phase.most_common()}
    return out
