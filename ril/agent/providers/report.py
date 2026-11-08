# ruff: noqa: E501  (markdown table rows are one line each)
"""Tables from the per-call log. Implements ``docs/RQ3_PILOT.md`` ("Outputs").

Latency is reported as p50, p95 and p99 (never the mean); token and call counts as mean, median and
maximum per unit. The resolved rate appears only when a grades file is supplied.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from statistics import mean, median
from typing import Any

from ril.agent.providers.calllog import CallLog, Row, Unit


def quantile(values: Sequence[float], q: float) -> float:
    """Nearest-rank quantile (no interpolation); NaN for an empty sample."""
    if not values:
        return math.nan
    s = sorted(values)
    return s[min(len(s) - 1, max(0, math.ceil(q * len(s)) - 1))]


def _share(num: int, den: int) -> float:
    return num / den if den else math.nan


def summarise(log: CallLog, grades: Mapping[Unit, bool] | None = None) -> dict[str, Any]:
    units = log.by_unit()
    rows: list[Row] = [r for rs in units.values() for r in rs]
    replies = [r for r in rows if r["kind"] == "reply"]
    finals = {u: next((r for r in rs if r["final"]), None) for u, rs in units.items()}
    done = {u: f for u, f in finals.items() if f is not None}
    arms = sorted({u[1] for u in units})
    out: dict[str, Any] = {
        "calls": len(rows),
        "reply_calls": len(replies),
        "units_started": len(units),
        "units_final": len(done),
        "models": sorted({str(r["model"]) for r in rows}),
        "dates_pacific": sorted({str(r["date_pacific"]) for r in rows}),
        "http_429": sum(int(r["n_429"]) for r in rows),
        "http_5xx": sum(int(r["n_5xx"]) for r in rows),
        "retries": sum(int(r["retries"]) for r in rows),
        "provider_failures": sum(1 for r in rows if r["kind"] == "failed"),
        "latency_s": {
            f"p{p}": quantile([float(r["latency_s"]) for r in replies], p / 100)
            for p in (50, 95, 99)
        },
        "per_arm": {},
    }
    for arm in arms:
        a_units = {u: rs for u, rs in units.items() if u[1] == arm}
        a_done = {u: f for u, f in done.items() if u[1] == arm and f is not None}
        calls_per = [
            sum(1 for r in rs if r["kind"] == "reply") for u, rs in a_units.items() if u in a_done
        ]
        in_tok = [
            sum(int(r["input_tokens"]) for r in rs) for u, rs in a_units.items() if u in a_done
        ]
        out_tok = [
            sum(int(r["output_tokens"]) for r in rs) for u, rs in a_units.items() if u in a_done
        ]
        first_bad = sum(
            1 for u in a_done if a_units[u][0]["kind"] == "reply" and not a_units[u][0]["patch_ok"]
        )
        final_bad = sum(1 for f in a_done.values() if f is not None and not f["patch_ok"])
        entry: dict[str, Any] = {
            "units_final": len(a_done),
            "calls_per_unit": {
                "mean": mean(calls_per) if calls_per else math.nan,
                "median": median(calls_per) if calls_per else math.nan,
                "max": max(calls_per, default=0),
            },
            "input_tokens_per_unit": {
                "mean": mean(in_tok) if in_tok else math.nan,
                "median": median(in_tok) if in_tok else math.nan,
                "max": max(in_tok, default=0),
            },
            "output_tokens_per_unit": {
                "mean": mean(out_tok) if out_tok else math.nan,
                "median": median(out_tok) if out_tok else math.nan,
                "max": max(out_tok, default=0),
            },
            "malformed_first_reply_rate": _share(first_bad, len(a_done)),
            "unusable_after_reasks_rate": _share(final_bad, len(a_done)),
        }
        if grades is not None:
            g = [grades[u] for u in a_done if u in grades]
            entry["resolved"] = {"n": len(g), "rate": _share(sum(g), len(g))}
        out["per_arm"][arm] = entry
    out["run_to_run"] = _agreement(done)
    out["token_ratio"] = token_ratio(log, rows)
    return out


def token_ratio(log: CallLog, rows: Sequence[Row]) -> dict[str, Any]:
    """Approximate count of the first message over the model's input tokens (first attempts).

    The assembly budget is in approximate tokens (``approx-words-v1``); this is the realised
    conversion to the model's own count, to be read before a budget is stated in model tokens.
    """
    import json

    from ril.assembly.tokens import ApproxTokenizer

    tok = ApproxTokenizer()
    ratios: list[float] = []
    for r in rows:
        if r["kind"] != "reply" or int(r["attempt"]) != 0 or int(r["input_tokens"]) <= 0:
            continue
        contents = json.loads(log.load("prompts", r["prompt_sha256"]))
        ratios.append(tok.count(contents[0]["parts"][0]["text"]) / int(r["input_tokens"]))
    return {
        "n": len(ratios),
        "approx_per_model_token": {f"p{p}": quantile(ratios, p / 100) for p in (5, 50, 95)},
    }


def _agreement(done: Mapping[Unit, Row | None]) -> dict[str, Any]:
    """Pairs of final rows of the same (instance, arm) from different runs (first two runs)."""
    by_pair: dict[tuple[str, str], dict[int, Row]] = {}
    for (iid, arm, k), f in done.items():
        if f is not None:
            by_pair.setdefault((iid, arm), {})[k] = f
    pairs = [(v[min(v)], v[sorted(v)[1]]) for v in by_pair.values() if len(v) >= 2]
    both_ok = [(a, b) for a, b in pairs if a["patch_ok"] and b["patch_ok"]]
    return {
        "pairs": len(pairs),
        "same_reply_text": _share(
            sum(1 for a, b in pairs if a["response_sha256"] == b["response_sha256"]), len(pairs)
        ),
        "both_usable": _share(len(both_ok), len(pairs)),
        "same_patch_given_both_usable": _share(
            sum(1 for a, b in both_ok if a["edits_sha256"] == b["edits_sha256"]), len(both_ok)
        ),
        "same_usability": _share(
            sum(1 for a, b in pairs if a["patch_ok"] == b["patch_ok"]), len(pairs)
        ),
    }


def to_markdown(summary: Mapping[str, Any]) -> str:
    """A short markdown rendering of ``summarise``."""

    def f(x: float) -> str:
        return (
            "n/a"
            if isinstance(x, float) and math.isnan(x)
            else (f"{x:.2f}" if isinstance(x, float) else str(x))
        )

    lat = summary["latency_s"]
    lines = [
        f"models: {', '.join(summary['models'])}; dates (Pacific): {', '.join(summary['dates_pacific'])}",
        f"calls {summary['calls']} (replies {summary['reply_calls']}), units final {summary['units_final']} of {summary['units_started']} started; "
        f"429 {summary['http_429']}, 5xx {summary['http_5xx']}, retries {summary['retries']}, provider failures {summary['provider_failures']}",
        f"latency per call (s): p50 {f(lat['p50'])}, p95 {f(lat['p95'])}, p99 {f(lat['p99'])}",
        "",
        "| arm | units | calls/unit mean (max) | input tok/unit mean | output tok/unit mean | malformed 1st reply | unusable after re-asks |"
        + (" resolved |" if any("resolved" in e for e in summary["per_arm"].values()) else ""),
        "|---|---|---|---|---|---|---|"
        + ("---|" if any("resolved" in e for e in summary["per_arm"].values()) else ""),
    ]
    for arm, e in summary["per_arm"].items():
        res = f" {f(e['resolved']['rate'])} (n={e['resolved']['n']}) |" if "resolved" in e else ""
        lines.append(
            f"| {arm} | {e['units_final']} | {f(e['calls_per_unit']['mean'])} ({e['calls_per_unit']['max']}) | {f(e['input_tokens_per_unit']['mean'])} | "
            f"{f(e['output_tokens_per_unit']['mean'])} | {f(e['malformed_first_reply_rate'])} | {f(e['unusable_after_reasks_rate'])} |"
            + res
        )
    tr = summary["token_ratio"]["approx_per_model_token"]
    lines += [
        "",
        f"approximate tokens per model token on the first message (n {summary['token_ratio']['n']}): "
        f"p5 {f(tr['p5'])}, p50 {f(tr['p50'])}, p95 {f(tr['p95'])}",
    ]
    r = summary["run_to_run"]
    lines += [
        "",
        f"run-to-run (pairs {r['pairs']}): same reply text {f(r['same_reply_text'])}; both usable {f(r['both_usable'])}; "
        f"same patch given both usable {f(r['same_patch_given_both_usable'])}; same usability {f(r['same_usability'])}",
    ]
    return "\n".join(lines) + "\n"
