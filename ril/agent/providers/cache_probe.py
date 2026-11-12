"""Cache probe: how much of a repeated prompt the provider serves from its cache (D158).

Implements ``docs/RQ3_PILOT.md`` ("Model check across providers", D158). For one candidate, a few
held-out instances are each sent twice back to back with an identical request (the request of a
unit's first call in the graded runs). The provider's reported cached-token count of the second
call, over its prompt tokens, is the *measured* hit fraction that the whole-study cost projection
uses; it is never assumed. Every call goes through the spend guard, so the probe is bound by the
same cap and authorisation as the check, and its billed cost is recorded.

No prompt text is written: rows hold hashes and token counts only.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol

from ril.agent.providers.gemini import CallResult
from ril.agent.providers.spend import Price, SpendCapReached

PROBE_N = 10
PROBE_VERSION = "cache-probe/v1"


class Generator(Protocol):
    def generate(
        self, contents: Sequence[Mapping[str, Any]], *, wait_for_daily: bool = False
    ) -> CallResult: ...


def probe_items(items: Sequence[Mapping[str, Any]], n: int = PROBE_N) -> list[Mapping[str, Any]]:
    """The first ``n`` items in the fixed (instance, arm) order (deterministic, no sampling)."""
    ordered = sorted(items, key=lambda r: (r["instance_id"], r["arm"]))
    return ordered[:n]


def run_probe(
    items: Sequence[Mapping[str, Any]],
    client: Generator,
    price: Price,
    model: str,
    n: int = PROBE_N,
) -> dict[str, Any]:
    """Send each probe item twice in a row; return the per-call rows and the hit fraction.

    ``hit_fraction`` = cached tokens of the second calls / prompt tokens of the second calls (token
    weighted). A run that stops on the spend cap or has fewer than ``n`` complete pairs reports it
    in ``stopped`` / ``pairs`` and is not usable for a projection (``usable`` is false)."""
    rows: list[dict[str, Any]] = []
    stopped = "complete"
    pairs = 0
    for item in probe_items(items, n):
        contents = [{"role": "user", "parts": [{"text": str(item["prompt"])}]}]
        pair: list[CallResult] = []
        try:
            for _ in range(2):
                pair.append(client.generate(contents))
        except SpendCapReached:
            stopped = "spend_cap"
        for k, res in enumerate(pair):
            rows.append(
                {
                    "instance_id": item["instance_id"],
                    "arm": item["arm"],
                    "send": k + 1,
                    "input_tokens": res.input_tokens,
                    "cached_tokens": res.cached_tokens,
                    "output_tokens": res.output_tokens,
                    "thought_tokens": res.thought_tokens,
                    "cost_usd": round(
                        price.cost(res.input_tokens, res.output_tokens, res.cached_tokens), 6
                    ),
                    "error": res.error or "",
                    "request_sha256": res.request_sha256,
                }
            )
        if len(pair) == 2 and not any(r.error for r in pair):
            pairs += 1
        if stopped != "complete":
            break
    return summarise_probe(rows, pairs, n, stopped, model, price)


def summarise_probe(
    rows: Sequence[Mapping[str, Any]],
    pairs: int,
    n: int,
    stopped: str,
    model: str,
    price: Price,
) -> dict[str, Any]:
    first = [r for r in rows if r["send"] == 1 and not r["error"]]
    second = [r for r in rows if r["send"] == 2 and not r["error"]]
    in2 = sum(int(r["input_tokens"]) for r in second)
    hit = sum(int(r["cached_tokens"]) for r in second) / in2 if in2 else 0.0
    sent = {(r["instance_id"], r["arm"], r["send"]): r["request_sha256"] for r in rows}
    same = all(sent.get((i, a, 2), h) == h for (i, a, s), h in sent.items() if s == 1)
    return {
        "probe": PROBE_VERSION,
        "model": model,
        "pairs": pairs,
        "pairs_planned": n,
        "stopped": stopped,
        "usable": stopped == "complete" and pairs == n and in2 > 0,
        "hit_fraction": hit,
        "first_send_cached_tokens": sum(int(r["cached_tokens"]) for r in first),
        "first_send_input_tokens": sum(int(r["input_tokens"]) for r in first),
        "second_send_input_tokens": in2,
        "second_send_cached_tokens": sum(int(r["cached_tokens"]) for r in second),
        "billed_cost_usd": round(sum(float(r["cost_usd"]) for r in rows), 6),
        "price_cached_per_m": price.cached_input_per_m,
        "requests_identical_within_pair": same,
        "rows": list(rows),
    }


def write_probe(path: str | Path, result: Mapping[str, Any]) -> None:
    Path(path).write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8")
