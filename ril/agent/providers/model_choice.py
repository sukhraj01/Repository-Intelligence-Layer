"""The model-choice rule of D112, as code so that it is fixed before any result exists.

Candidates are the cheapest model that can plausibly work and the next one or two stronger models
on the same API. Each runs one arm (RRF, 8,000 tokens) once on the held-out slice, with the same
prompt, follow-up policy and thinking configuration. The cheapest candidate whose resolved rate on
the slice (exact reading) is at least ``FLOOR`` is chosen; if none reaches the floor the strongest
candidate is taken and the floor is reported as not met. No other selection on resolved results is
allowed. "Cheapest" is the realised cost of the check run; "strongest" is the highest list price
for output tokens.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

FLOOR = 0.15
"""Resolved rate at which a discordance of 10% or more between arms is attainable at N = 327."""


def choose(candidates: Sequence[Mapping[str, Any]], floor: float = FLOOR) -> dict[str, Any]:
    """Apply the rule. Each candidate has ``model``, ``resolved`` (count), ``n`` (instances graded),
    ``cost_usd`` (realised) and ``output_price`` (list price per million output tokens)."""
    if not candidates:
        raise ValueError("no candidates")
    rated = [{**c, "rate": (c["resolved"] / c["n"]) if c["n"] else 0.0} for c in candidates]
    passing = sorted(
        (c for c in rated if c["rate"] >= floor), key=lambda c: (c["cost_usd"], c["model"])
    )
    if passing:
        pick = passing[0]
        met = True
    else:
        pick = max(rated, key=lambda c: (c["output_price"], c["model"]))
        met = False
    return {
        "chosen": pick["model"],
        "floor": floor,
        "floor_met": met,
        "rate": pick["rate"],
        "n": pick["n"],
        "note": ""
        if met
        else "no candidate reached the floor: the strongest is taken and the resolved-rate "
        "contrast is reported as low-power; the retrieval-side readings carry the weight",
        "candidates": [
            {"model": c["model"], "rate": c["rate"], "cost_usd": c["cost_usd"], "n": c["n"]}
            for c in rated
        ],
    }
