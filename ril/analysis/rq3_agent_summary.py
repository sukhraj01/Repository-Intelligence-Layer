"""Per-arm summary of the graded RQ3 runs: counts, truncation, cache share, cost, repeat spread.

Reads stored result and call files only (no call, no cluster). Every input file is listed with
its SHA-256 so each figure traces to a file. Implements ``docs/RQ3_PILOT.md`` (analysis plan,
D113, D121, D167); the contrasts themselves come from ``ril.analysis.rq3_results``.
"""

from __future__ import annotations

import hashlib
import json
import statistics
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _jsonl(path: str | Path) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def arm_summary(
    arm: str, results_path: str | Path, calls_path: str | Path, runs: Sequence[int]
) -> dict[str, Any]:
    """Counts, truncation, cache share, cost and the spread over repeats of one arm."""
    rows = _jsonl(results_path)
    calls = _jsonl(calls_path)
    by_run = {k: [r for r in rows if int(r["run"]) == k] for k in runs}
    fractions = [sum(1 for r in v if r["resolved"]) / len(v) for v in by_run.values()]
    finish = Counter(str(c["finish_reason"]) for c in calls)
    inp = sum(int(c["input_tokens"]) for c in calls)
    cached = sum(int(c.get("cached_tokens", 0)) for c in calls)
    later = [c for c in calls if int(c["run_index"]) != min(runs)]
    later_in = sum(int(c["input_tokens"]) for c in later)
    later_cached = sum(int(c.get("cached_tokens", 0)) for c in later)
    return {
        "arm": arm,
        "rows": len(rows),
        "resolved": sum(1 for r in rows if r["resolved"]),
        "unusable": sum(1 for r in rows if r["outcome"] == "unusable"),
        "unusable_share": sum(1 for r in rows if r["outcome"] == "unusable") / len(rows),
        "apply_failed": sum(1 for r in rows if str(r["outcome"]).startswith("apply_failed")),
        "resolved_fraction_by_repeat": fractions,
        "repeat_sd_points": 100 * statistics.stdev(fractions) if len(fractions) > 1 else None,
        "calls": len(calls),
        "follow_up_calls": sum(1 for c in calls if int(c["attempt"]) > 0),
        "calls_at_output_limit": finish.get("MAX_TOKENS", 0),
        "truncation_share": finish.get("MAX_TOKENS", 0) / len(calls),
        "finish_reasons": dict(sorted(finish.items())),
        "cache_share_all": cached / inp if inp else None,
        "cache_share_repeats_after_first": later_cached / later_in if later_in else None,
        "cost_usd": round(sum(float(r["cost_usd"]) for r in rows), 4),
    }


def build(
    arms: Mapping[str, tuple[str, str]],
    runs: Sequence[int],
    extra_inputs: Mapping[str, str],
) -> dict[str, Any]:
    """Summary of every arm plus the SHA-256 of every input file."""
    inputs: dict[str, str] = {}
    for name, (results, calls) in arms.items():
        inputs[f"{name}:results"] = sha256_file(results)
        inputs[f"{name}:calls"] = sha256_file(calls)
    for label, path in extra_inputs.items():
        inputs[label] = sha256_file(path)
    return {
        "version": "rq3-agent-summary/v1",
        "arms": [arm_summary(n, r, c, runs) for n, (r, c) in arms.items()],
        "input_sha256": inputs,
        "total_cost_usd": round(
            sum(arm_summary(n, r, c, runs)["cost_usd"] for n, (r, c) in arms.items()), 4
        ),
    }
