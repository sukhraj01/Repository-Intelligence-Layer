"""Cost model of the RQ3 runs. Implements ``docs/RQ3_PILOT.md`` (D112, D114).

Tokens per unit and calls per unit are *measured* in the pilot (``rq3_pilot_cost.csv``: 400 units,
565 calls, 100 dev instances, BM25 and RRF, Flash-Lite, no thought tokens billed). Prices are
*estimated*: dated list prices from ``configs/agent/prices.yaml``, marked unverified until the
project owner confirms them in the provider console. A stronger model may reason longer and bill
thought tokens that the pilot model did not produce, so a second scenario multiplies the output
tokens (the ``thought_multiplier``, an assumption) and uses the upper end of the measured interval
of calls per unit.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ril.agent.providers.spend import Price

CONFIRMATORY_N = 327
HELDOUT_N = 50
THOUGHT_MULTIPLIER = 3.0


@dataclass(frozen=True)
class UnitTokens:
    """Measured per-unit usage of the pilot (a unit is one instance, one arm, one run)."""

    calls: float
    calls_hi: float
    input_tokens: float
    output_tokens: float


def unit_tokens_from_pilot(row: Mapping[str, str]) -> UnitTokens:
    """From the ``all`` row of ``rq3_pilot_cost.csv``."""
    return UnitTokens(
        calls=float(row["calls_per_unit"]),
        calls_hi=float(row["calls_per_unit_hi"]),
        input_tokens=float(row["input_tokens_per_unit_mean"]),
        output_tokens=float(row["output_tokens_per_unit_mean"]),
    )


def cost_of(
    units: float, tokens: UnitTokens, price: Price, scenario: str = "central"
) -> dict[str, Any]:
    """Calls, tokens and dollars of ``units`` units under a scenario (``central`` or ``high``)."""
    if scenario == "central":
        scale, out_mult = 1.0, 1.0
    elif scenario == "high":
        scale, out_mult = tokens.calls_hi / tokens.calls, THOUGHT_MULTIPLIER
    else:
        raise ValueError(f"unknown scenario {scenario!r}")
    inp = units * tokens.input_tokens * scale
    out = units * tokens.output_tokens * scale * out_mult
    return {
        "calls": round(units * tokens.calls * scale, 1),
        "input_tokens": round(inp),
        "output_tokens": round(out),
        "cost_usd": round(price.cost(round(inp), round(out)), 2),
    }


def cost_table(
    tokens: UnitTokens,
    prices: Sequence[Price],
    n: int = CONFIRMATORY_N,
    n_heldout: int = HELDOUT_N,
) -> list[dict[str, Any]]:
    """Rows: one arm-run of ``n`` and of ``n_heldout``, and the grids of D113, per price and
    scenario. Token figures are measured (pilot); dollar figures are estimated."""
    shapes: list[tuple[str, int, int]] = [
        ("one arm-run, confirmatory", n, 1),
        ("one arm-run, held-out slice", n_heldout, 1),
        ("grid 3 arms x k=2", n, 3 * 2),
        ("grid 3 arms x k=3", n, 3 * 3),
        ("grid 4 arms x k=2", n, 4 * 2),
        ("grid 4 arms x k=3", n, 4 * 3),
    ]
    rows: list[dict[str, Any]] = []
    for price in prices:
        for scenario in ("central", "high"):
            for label, inst, arm_runs in shapes:
                rows.append(
                    {
                        "model": price.model,
                        "price_input_per_m": price.input_per_m,
                        "price_output_per_m": price.output_per_m,
                        "price_as_of": price.as_of,
                        "price_verified": price.verified,
                        "scenario": scenario,
                        "what": label,
                        "instances": inst,
                        "arm_runs": arm_runs,
                        **cost_of(inst * arm_runs, tokens, price, scenario),
                        "tokens_class": "measured (pilot, Flash-Lite)",
                        "dollars_class": "estimated (price unverified)"
                        if not price.verified
                        else "estimated (price verified)",
                    }
                )
    return rows


def graded_check_cap(rows: Sequence[Mapping[str, Any]], margin: float = 1.25) -> dict[str, Any]:
    """Cap recommended for the graded model check: the sum over candidates of the ``high`` scenario
    cost of one arm-run on the held-out slice, times ``margin``, rounded up to a whole dollar."""
    import math

    held = [
        r for r in rows if r["what"] == "one arm-run, held-out slice" and r["scenario"] == "high"
    ]
    total = sum(float(r["cost_usd"]) for r in held)
    return {
        "candidates": [r["model"] for r in held],
        "sum_high_usd": round(total, 2),
        "margin": margin,
        "recommended_cap_usd": max(1, math.ceil(total * margin)),
    }
