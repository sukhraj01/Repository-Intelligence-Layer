"""Run-to-run agreement of the graded untrained arm and the power simulation re-run with it.

Implements ``docs/RQ3_PILOT.md`` "Power with run-to-run noise" (D113) and entry
``E-RQ3-RUN-AGREEMENT``. Reads stored result rows only; no provider call.

The simulation of ``rq3_power_noise`` lets run ``j`` repeat run ``j - 1`` with probability ``s``
and otherwise draw afresh from the instance's resolve probability
``p_i ~ Beta(mu * kappa, (1 - mu) * kappa)``. For one instance the chain has second eigenvalue
``s``, so two runs ``L`` positions apart agree with probability ``s**L + (1 - s**L) * A`` where
``A = E[p**2 + (1 - p)**2] = 1 - 2 mu (1 - mu) kappa / (kappa + 1)``. ``calibrate_s`` inverts
that for the measured share of agreeing pairs.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ril.analysis import rq3_power_noise

PAIRS: tuple[tuple[int, int], ...] = ((0, 1), (0, 2), (1, 2))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def resolved_by_instance(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[int, bool]]:
    """``{instance_id: {run: resolved}}``; an unusable reply is an unresolved row."""
    out: dict[str, dict[int, bool]] = defaultdict(dict)
    for r in rows:
        out[str(r["instance_id"])][int(r["run"])] = bool(r["resolved"])
    return dict(out)


def agreement_summary(res: Mapping[str, Mapping[int, bool]]) -> dict[str, Any]:
    """Counts of instances resolved in 3, 1 to 2 and 0 repeats, and pairwise agreement."""
    ids = sorted(res)
    if any(len(res[i]) != 3 for i in ids):
        raise ValueError("every instance needs exactly three repeats")
    dist = Counter(sum(res[i].values()) for i in ids)
    pairs: dict[str, dict[str, float | int]] = {}
    agree_total = 0
    for a, b in PAIRS:
        agree = sum(res[i][a] == res[i][b] for i in ids)
        both = sum(res[i][a] and res[i][b] for i in ids)
        pa = sum(res[i][a] for i in ids) / len(ids)
        pb = sum(res[i][b] for i in ids) / len(ids)
        expected = pa * pb + (1 - pa) * (1 - pb)
        observed = agree / len(ids)
        kappa = (observed - expected) / (1 - expected) if expected < 1 else float("nan")
        pairs[f"{a}-{b}"] = {
            "agree": agree,
            "differ": len(ids) - agree,
            "resolved_in_both": both,
            "agreement": round(observed, 4),
            "cohen_kappa": round(kappa, 3),
        }
        agree_total += agree
    n = len(ids)
    return {
        "instances": n,
        "resolved_in_3": dist[3],
        "resolved_in_2": dist[2],
        "resolved_in_1": dist[1],
        "resolved_in_none": dist[0],
        "resolved_in_some": dist[1] + dist[2],
        "any_of_3": dist[1] + dist[2] + dist[3],
        "mean_resolved_rate": sum(sum(res[i].values()) for i in ids) / (3 * n),
        "pairs": pairs,
        "pooled_agreement": agree_total / (3 * n),
        "pooled_agreement_counts": [agree_total, 3 * n],
    }


def chance_agreement(mu: float, kappa: float) -> float:
    """``A``: agreement of two independent runs under ``p ~ Beta(mu kappa, (1 - mu) kappa)``."""
    return 1.0 - 2.0 * mu * (1.0 - mu) * kappa / (kappa + 1.0)


def implied_pooled_agreement(s: float, mu: float, kappa: float) -> float:
    """Model agreement averaged over the three pairs (two adjacent, one two apart)."""
    a = chance_agreement(mu, kappa)
    return (2 / 3) * (s + (1 - s) * a) + (1 / 3) * (s * s + (1 - s * s) * a)


def calibrate_s(target: float, mu: float, kappa: float) -> float | None:
    """The repeat probability ``s`` whose implied pooled agreement equals ``target``.

    ``None`` if even ``s = 0`` already agrees at least as much as ``target`` (then the
    heterogeneity alone explains the agreement) or if ``target`` exceeds 1.
    """
    if target > 1.0 or implied_pooled_agreement(0.0, mu, kappa) >= target:
        return None
    lo, hi = 0.0, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if implied_pooled_agreement(mid, mu, kappa) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def kappa_alone(target: float, mu: float) -> float:
    """The kappa at which ``s = 0`` already gives ``target`` (heterogeneity-only reading)."""
    x = (1.0 - target) / (2.0 * mu * (1.0 - mu))
    return x / (1.0 - x)


def settings_by_repeat(
    rows: Sequence[Mapping[str, Any]], calls: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Every recorded setting per repeat: which values occur, cache state, order, request hashes."""
    constant_fields = (
        "arm",
        "model",
        "temperature",
        "seed",
        "budget",
        "template_version",
        "first_stage",
        "date_pacific",
    )
    values: dict[str, dict[int, list[str]]] = {}
    for f in constant_fields:
        per: dict[int, set[str]] = defaultdict(set)
        for c in calls:
            per[int(c["run_index"])].add(str(c[f]))
        values[f] = {k: sorted(v) for k, v in sorted(per.items())}
    first_attempt: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    per_run: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for c in calls:
        per_run[int(c["run_index"])].append(c)
        if int(c["attempt"]) == 0:
            first_attempt[int(c["run_index"])].append(c)
    by_run: dict[str, dict[str, Any]] = {}
    for k in sorted(per_run):
        cs, a0 = per_run[k], first_attempt[k]
        by_run[str(k)] = {
            "calls": len(cs),
            "first_attempts": len(a0),
            "first_attempts_with_cached_tokens": sum(int(c["cached_tokens"]) > 0 for c in a0),
            "cached_share_of_prompt_tokens": round(
                sum(int(c["cached_tokens"]) for c in cs) / sum(int(c["input_tokens"]) for c in cs),
                3,
            ),
            "thought_tokens": sum(int(c["thought_tokens"]) for c in cs),
            "finish_reasons": dict(Counter(str(c["finish_reason"]) for c in cs)),
            "retries": sum(int(c["retries"]) for c in cs),
            "mean_latency_s": round(sum(float(c["latency_s"]) for c in cs) / len(cs), 1),
        }
    groups: list[tuple[str, list[int]]] = []
    for c in calls:
        if not groups or groups[-1][0] != c["instance_id"]:
            groups.append((str(c["instance_id"]), []))
        groups[-1][1].append(int(c["run_index"]))
    adjacent = all(sorted(set(g[1])) == [0, 1, 2] and g[1] == sorted(g[1]) for g in groups)
    h: dict[str, dict[str, int]] = {}
    for name in ("prompt_sha256", "request_sha256", "response_sha256"):
        by_inst: dict[str, dict[int, str]] = defaultdict(dict)
        for c in first_attempt_calls(calls):
            by_inst[str(c["instance_id"])][int(c["run_index"])] = str(c[name])
        h[name] = {
            f"{a}-{b}": sum(v[a] == v[b] for v in by_inst.values() if a in v and b in v)
            for a, b in PAIRS
        }
    return {
        "values_per_repeat": values,
        "per_repeat": by_run,
        "instances_in_call_log": len(groups),
        "repeats_adjacent_in_order_per_instance": adjacent,
        "first_attempt_equal_counts": h,
    }


def first_attempt_calls(calls: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [c for c in calls if int(c["attempt"]) == 0]


def power_rerun(
    scenarios: Sequence[tuple[str, float, Sequence[float]]],
    rates: Sequence[float] = (*rq3_power_noise.RATES, 0.40),
    n: int = rq3_power_noise.N_CONFIRMATORY,
    sims: int = 500,
    permutations: int = 2000,
    seed: int = 0,
) -> list[dict[str, Any]]:
    """Minimum detectable difference per (scenario, kappa, rate, runs).

    A scenario is ``(label, s, kappas)``: the repeat probability ``s`` used for those kappas.
    The same seed is used for every scenario; with ``s = 0.635`` and both kappas the first three
    rates reproduce the stored table cell for cell.
    """
    out: list[dict[str, Any]] = []
    for label, s, kappas in scenarios:
        cells = rq3_power_noise.power_table(
            n=n,
            rates=rates,
            kappas=kappas,
            sims=sims,
            permutations=permutations,
            seed=seed,
            same=s,
        )
        for m in rq3_power_noise.minimum_detectable(cells):
            out.append({"n": n, "scenario": label, "s": round(s, 4), **m})
    return out
