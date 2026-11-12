"""The model check across providers: limits file, per-candidate summary, and the rule of D155.

Implements ``docs/RQ3_PILOT.md`` ("Model check across providers", D155). The rule is code so that it
is fixed before any result exists, and it is applied mechanically to the finished runs:

1. a candidate that has not finished all instances of the slice is not compared (the table is
   reported and names what to finish);
2. discard a candidate whose projected whole-study cost exceeds the study budget ``B``;
3. discard a candidate below ``FLOOR`` resolved on the slice (exact reading);
4. of the rest take the highest resolved count; candidates within ``TIE_INSTANCES`` instances of it
   are indistinguishable and the cheaper (projected whole-study cost) of them is taken, ties by
   name;
5. if nothing passes 2 and 3, nothing is chosen.

The projected whole-study cost is the measured tokens per instance (input, and output including
thinking tokens, over every call and follow-up) times the confirmatory N, priced from the limits
file, times the number of arm-runs of the analysis plan. ``model_choice.choose`` (D112, cheapest
first) is superseded for this selection and kept only for the record.
"""

from __future__ import annotations

import csv
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ril.agent.providers.messages_api import CONNECTION_FIELDS
from ril.agent.providers.model_choice import FLOOR
from ril.agent.providers.spend import Price

PROVIDERS = ("gemini", "messages")
"""``gemini``: the generateContent API; ``messages``: a messages-style API (``messages_api.py``)
whose endpoint and header names are configuration in the limits entry."""
TIE_INSTANCES = 2
DEFAULT_BUDGET_USD = 150.0
DEFAULT_ARM_RUNS = 12
CONFIRMATORY_N = 327
SLICE_N = 50
UNSET = "UNSET"


def limits_entry(path: str | Path, model: str) -> dict[str, Any]:
    """The raw entry of ``model`` in a limits file (empty if the file has none)."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    entry = (data.get("models") or {}).get(model) or {}
    return dict(entry)


def provider_for(model: str, entry: Mapping[str, Any], explicit: str | None = None) -> str:
    """The provider of a run: the command-line choice, else the limits entry, else ``gemini``
    (the provider of the pilot)."""
    name = explicit or entry.get("provider") or "gemini"
    if name not in PROVIDERS:
        raise ValueError(f"unknown provider {name!r}; one of {', '.join(PROVIDERS)}")
    return str(name)


def run_config_sha256(config: Mapping[str, Any]) -> str:
    """Hash of the run configuration that D155 pins (provider, model, temperature, thinking,
    output allowance, follow-up rule, template version); recorded in ``meta.json``."""
    import hashlib
    import json

    text = json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------- limits file


@dataclass(frozen=True)
class CheckModel:
    """One candidate as the limits file describes it."""

    model: str
    provider: str
    tier: str
    rpm: int
    tpm: int
    rpd: int
    price: Price
    price_source: str
    thinking: Mapping[str, Any] | None
    caps_usd: tuple[float, ...]


@dataclass(frozen=True)
class CheckSpec:
    models: Mapping[str, CheckModel]
    budget_usd: float
    budget_defaulted: bool
    arm_runs: int
    confirmatory_n: int
    as_of: str


def validate_limits(path: str | Path) -> list[str]:
    """Problems that make the file unusable for the check (empty list = usable). Reads no key.

    The candidates are the models of the file (D155 fixes the list in the decision; the lead's
    local file carries the exact model strings): at least two models, from at least two
    providers, none with an unset value."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    problems: list[str] = []
    if str(data.get("as_of", UNSET)) == UNSET:
        problems.append("as_of is unset")
    models = data.get("models") or {}
    if len(models) < 2:
        problems.append("fewer than two candidate models")
    if len({(m or {}).get("provider") for m in models.values()}) < 2:
        problems.append("candidates must come from at least two providers")
    for name, m in models.items():
        m = m or {}
        if m.get("provider") not in PROVIDERS:
            problems.append(f"{name}: provider must be one of {', '.join(PROVIDERS)}")
        if m.get("provider") == "messages":
            for key in CONNECTION_FIELDS:
                if str(m.get(key, UNSET)).strip() in ("", UNSET):
                    problems.append(f"{name}: {key} is unset")
        for key in ("rpm", "tpm", "rpd"):
            if not isinstance(m.get(key), int) or m[key] <= 0:
                problems.append(f"{name}: {key} must be a positive integer")
        for key in ("input_per_m", "output_per_m"):
            v = m.get(key)
            if not isinstance(v, int | float) or isinstance(v, bool) or v <= 0:
                problems.append(f"{name}: {key} must be a positive number (USD per million tokens)")
        for key in ("price_as_of", "price_source", "tier"):
            if str(m.get(key, UNSET)).strip() in ("", UNSET):
                problems.append(f"{name}: {key} is unset")
        caps = m.get("caps_usd")
        if (
            not isinstance(caps, list)
            or not caps
            or any(not isinstance(c, int | float) or c <= 0 for c in caps)
            or list(caps) != sorted(caps)
        ):
            problems.append(
                f"{name}: caps_usd must be a non-empty ascending list of positive numbers"
            )
    for key in ("study_budget_usd", "study_arm_runs"):
        if key in data and (not isinstance(data[key], int | float) or data[key] <= 0):
            problems.append(f"{key} must be positive")
    return problems


def load_spec(path: str | Path) -> CheckSpec:
    """The limits file as a spec; ``ValueError`` lists every problem (``validate_limits``)."""
    problems = validate_limits(path)
    if problems:
        raise ValueError("limits file not usable: " + "; ".join(problems))
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    models: dict[str, CheckModel] = {}
    for name, m in data["models"].items():
        models[name] = CheckModel(
            model=name,
            provider=str(m["provider"]),
            tier=str(m["tier"]),
            rpm=int(m["rpm"]),
            tpm=int(m["tpm"]),
            rpd=int(m["rpd"]),
            price=Price(
                name, float(m["input_per_m"]), float(m["output_per_m"]), True, str(m["price_as_of"])
            ),
            price_source=str(m["price_source"]),
            thinking=dict(m["thinking"]) if m.get("thinking") else None,
            caps_usd=tuple(float(c) for c in m["caps_usd"]),
        )
    return CheckSpec(
        models=models,
        budget_usd=float(data.get("study_budget_usd", DEFAULT_BUDGET_USD)),
        budget_defaulted="study_budget_usd" not in data,
        arm_runs=int(data.get("study_arm_runs", DEFAULT_ARM_RUNS)),
        confirmatory_n=int(data.get("confirmatory_n", CONFIRMATORY_N)),
        as_of=str(data["as_of"]),
    )


# ---------------------------------------------------------------------------- summary of one run


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval of a proportion (95% by default)."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def summarise(
    model: str,
    rows: Sequence[Mapping[str, Any]],
    meta: Mapping[str, Any],
    check: CheckModel,
    spec: CheckSpec,
    expected_n: int = SLICE_N,
) -> dict[str, Any]:
    """Counts, tokens, realised cost and the projections of one candidate from its result rows."""
    final = [r for r in rows if not str(r["outcome"]).startswith("exec_error")]
    n = len(final)
    resolved = sum(1 for r in final if r["resolved"])
    inp = sum(int(r["input_tokens"]) for r in final)
    out = sum(int(r["output_tokens"]) for r in final)
    thought = sum(int(r["thought_tokens"]) for r in final)
    price = check.price
    per_arm_run_slice = price.cost(inp, out)
    per_instance = per_arm_run_slice / n if n else 0.0
    arm_run = per_instance * spec.confirmatory_n
    lo, hi = wilson(resolved, n)
    return {
        "model": model,
        "provider": check.provider,
        "n": n,
        "expected_n": expected_n,
        "complete": n == expected_n and len(rows) == n,
        "exec_error_rows": len(rows) - n,
        "resolved": resolved,
        "rate": resolved / n if n else 0.0,
        "rate_lo": lo,
        "rate_hi": hi,
        "unusable": sum(1 for r in final if r["outcome"] == "unusable"),
        "apply_failed": sum(1 for r in final if str(r["outcome"]).startswith("apply_failed")),
        "executed_unresolved": sum(1 for r in final if r["outcome"] == "executed_unresolved"),
        "calls": sum(int(r["calls"]) for r in final),
        "input_tokens": inp,
        "output_tokens": out,
        "thought_tokens": thought,
        "slice_cost_usd": per_arm_run_slice,
        "arm_run_usd": arm_run,
        "study_usd": arm_run * spec.arm_runs,
        "stopped": str(meta.get("stopped", "")),
        "thinking_config": meta.get("thinking_config"),
        "config_sha256": meta.get("config_sha256"),
        "price_as_of": price.as_of,
    }


# ---------------------------------------------------------------------------- the rule


def select_model(
    summaries: Sequence[Mapping[str, Any]],
    budget_usd: float,
    floor: float = FLOOR,
    tie_instances: int = TIE_INSTANCES,
) -> dict[str, Any]:
    """Apply the rule of D155 to candidate summaries; return the decision and the table."""
    if not summaries:
        raise ValueError("no candidates")
    rows = [dict(s) for s in summaries]
    for r in rows:
        r["over_budget"] = r["study_usd"] > budget_usd
        r["below_floor"] = r["rate"] < floor
        r["passes"] = bool(r["complete"]) and not r["over_budget"] and not r["below_floor"]
        r["in_tie_band"] = False
        r["selected"] = False
    unfinished = [r["model"] for r in rows if not r["complete"]]
    base: dict[str, Any] = {
        "rule": "D155",
        "floor": floor,
        "budget_usd": budget_usd,
        "tie_instances": tie_instances,
        "candidates": rows,
    }
    if unfinished:
        return {
            **base,
            "status": "incomplete",
            "chosen": None,
            "note": "not compared: unfinished candidates " + ", ".join(sorted(unfinished)),
        }
    passing = [r for r in rows if r["passes"]]
    if not passing:
        return {
            **base,
            "status": "no_selection",
            "chosen": None,
            "note": "no candidate passes both the budget and the floor; the table is reported "
            "and nothing is chosen",
        }
    top = max(r["resolved"] for r in passing)
    band = [r for r in passing if r["resolved"] >= top - tie_instances]
    for r in band:
        r["in_tie_band"] = True
    pick = min(band, key=lambda r: (r["study_usd"], r["model"]))
    pick["selected"] = True
    return {
        **base,
        "status": "selected",
        "chosen": pick["model"],
        "note": f"{len(band)} candidate(s) within {tie_instances} instances of the top "
        f"({top} resolved); the cheaper was taken"
        if len(band) > 1
        else "the highest resolved count among the candidates that pass",
        "rate": pick["rate"],
        "n": pick["n"],
        "study_usd": pick["study_usd"],
    }


# ---------------------------------------------------------------------------- reporting


def power_context(csv_path: str | Path, rate: float, n: int = CONFIRMATORY_N) -> dict[str, Any]:
    """Minimum detectable differences of the stored power table at the grid rate nearest ``rate``.

    The grid (rates 0.1, 0.2, 0.3) holds assumptions, not measurements; a rate outside the grid
    is reported as such and the nearest grid rate is used."""
    with Path(csv_path).open(newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if int(r["n"]) == n and r["mdd_points"]]
    rates = sorted({float(r["rate"]) for r in rows})
    near = min(rates, key=lambda g: (abs(g - rate), g))
    return {
        "rate": rate,
        "nearest_grid_rate": near,
        "outside_grid": rate < rates[0] or rate > rates[-1],
        "mdd_points": [
            {
                "kappa": float(r["kappa"]),
                "runs": int(r["runs"]),
                "mdd_points": float(r["mdd_points"]),
            }
            for r in rows
            if float(r["rate"]) == near
        ],
    }


def render_table(result: Mapping[str, Any]) -> str:
    """The check table as plain text (resolved with interval, unusable, cost, projection, flags)."""
    head = (
        f"{'model':<24}{'resolved':>10}{'rate [95% Wilson]':>24}{'unusable':>10}{'arm-run $':>11}"
        f"{'study $':>10}  flags"
    )
    lines = [head, "-" * len(head)]
    for r in result["candidates"]:
        flags = []
        if not r["complete"]:
            flags.append(f"INCOMPLETE n={r['n']}/{r['expected_n']}")
        if r["exec_error_rows"]:
            flags.append(f"exec_error_rows={r['exec_error_rows']}")
        if r["over_budget"]:
            flags.append("over budget")
        if r["below_floor"]:
            flags.append("below floor")
        if r["in_tie_band"]:
            flags.append("tie band")
        if r["selected"]:
            flags.append("SELECTED")
        if r["stopped"] and r["stopped"] != "complete":
            flags.append(f"stopped:{r['stopped']}")
        interval = f"{r['rate']:.1%} [{r['rate_lo']:.1%}, {r['rate_hi']:.1%}]"
        lines.append(
            f"{r['model']:<24}{r['resolved']:>5}/{r['n']:<4}{interval:>24}"
            f"{r['unusable']:>5}/{r['n']:<4}{r['arm_run_usd']:>11.2f}{r['study_usd']:>10.2f}  "
            + ", ".join(flags)
        )
    lines.append(
        f"budget B = {result['budget_usd']:.2f} USD, floor {result['floor']:.0%}, tie band "
        f"{result['tie_instances']} instances; status: {result['status']}; "
        f"chosen: {result['chosen']}; {result['note']}"
    )
    return "\n".join(lines)
