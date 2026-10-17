"""Recency prior from ``last_modified`` (pilot E5, exploratory).

Implements the leakage-safe prior of decision D8: ``last_modified`` is the time of the last commit
that touched a unit's file, restricted to commits at or before the snapshot commit (or ``""``).
The age of a unit is the snapshot commit's time minus that time; the prior is
``exp(-age / tau)`` and 0 for a unit without a history. A unit whose ``last_modified`` is later
than the snapshot is a leak and raises, because the history traversal can never produce one.

The prior is added to the retrieval score after dividing the score by the best score of the
query, so that the weight ``lam`` is on a fixed scale (``score / max + lam * prior``).

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import datetime, timezone

import numpy as np
import numpy.typing as npt

Floats = npt.NDArray[np.float64]
SECONDS_PER_DAY = 86400.0


def parse_utc(stamp: str) -> float:
    """Epoch seconds of a D8 timestamp ``YYYY-MM-DDTHH:MM:SSZ``."""
    parsed = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")
    return parsed.replace(tzinfo=timezone.utc).timestamp()  # noqa: UP017


def ages_in_days(last_modified: Sequence[str], snapshot_time: float) -> Floats:
    """Age in days of each unit at the snapshot; ``inf`` when ``last_modified`` is empty."""
    out = np.full(len(last_modified), np.inf, dtype=np.float64)
    for i, stamp in enumerate(last_modified):
        if not stamp:
            continue
        age = snapshot_time - parse_utc(stamp)
        if age < 0:
            raise ValueError(f"last_modified {stamp} is after the snapshot: history leak")
        out[i] = age / SECONDS_PER_DAY
    return out


def recency_prior(age_days: Floats, tau_days: float) -> Floats:
    """``exp(-age / tau)``; 0 where the age is unknown (``inf``)."""
    if tau_days <= 0 or math.isnan(tau_days):
        raise ValueError("tau must be positive")
    with np.errstate(over="ignore"):
        out: Floats = np.exp(-age_days / tau_days)
    return out


def blend(scores: Floats, prior: Floats, lam: float) -> Floats:
    """``scores / max(scores) + lam * prior``; a query with no positive score keeps the prior."""
    top = float(scores.max()) if len(scores) else 0.0
    base: Floats = scores / top if top > 0 else np.zeros_like(scores)
    out: Floats = base + lam * prior
    return out
