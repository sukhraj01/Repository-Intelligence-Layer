"""Retrieval-versus-reasoning breakdown of graded RQ3 attempts (E-RQ3-FAILURE-BREAKDOWN, D173).

Implements ``docs/experiments/B.md`` E-RQ3-FAILURE-BREAKDOWN. Exploratory and descriptive: reads
stored result rows and stored context manifests only; no model call. The definitions (outcome
classes, gold status at file and unit level, the paired counts, the consistency check, the
efficiency numbers, the gap-closed ratio and the django split) are written in the entry and are not
chosen after the results.

The unit of analysis for intervals is the instance, as in ``ril.analysis.rq3_results``.
"""

from __future__ import annotations

import math
from collections.abc import Collection, Mapping, Sequence
from typing import Any

import numpy as np
import numpy.typing as npt

from ril.analysis.rq3_results import (
    Rows,
    latest,
    paired_contrast,
    percentile_interval,
    score_matrix,
)

Arr = npt.NDArray[np.float64]
Table = list[dict[str, Any]]

CLASSES = ("resolved", "no_usable_edit", "edits_failed_to_apply", "tests_failed", "exec_error")
UNRESOLVED = CLASSES[1:]
STATUSES = ("all", "some", "none", "na")
RESAMPLES = 10_000


def outcome_class(outcome: str) -> str:
    """Map a stored outcome to the entry's class (``unusable`` is no usable edit set)."""
    head = outcome.split(":", 1)[0]
    return {
        "resolved": "resolved",
        "unusable": "no_usable_edit",
        "apply_failed": "edits_failed_to_apply",
        "executed_unresolved": "tests_failed",
    }.get(head, "exec_error")


def status_of(n_gold: int, n_in: int) -> str:
    """``all`` / ``some`` / ``none`` of the gold present; ``na`` when there is no gold."""
    if n_gold <= 0:
        return "na"
    if n_in >= n_gold:
        return "all"
    return "none" if n_in == 0 else "some"


def presence(
    entries: Sequence[Mapping[str, Any]],
    gold_files: Collection[str],
    gold_units: Collection[str],
) -> dict[str, int]:
    """Counts of gold files and units among the entries of one context manifest.

    A gold file is present when at least one included unit lies in it; a gold unit when it is an
    entry (cut by the unit cap or not).
    """
    files = {str(e["file"]) for e in entries}
    units = {str(e["unit_id"]) for e in entries}
    gf, gu = set(gold_files), set(gold_units)
    return {
        "n_gold_files": len(gf),
        "files_in": len(gf & files),
        "n_gold_units": len(gu),
        "units_in": len(gu & units),
    }


def attempts(
    rows: Rows,
    arm: str,
    instances: Collection[str],
    pres: Mapping[str, Mapping[str, Any]] | None,
) -> Table:
    """One row per graded attempt of ``arm`` with outcome class and gold status.

    ``pres[instance]`` holds ``n_gold_files``, ``files_in``, ``n_gold_files_py``,
    ``files_in_py``, ``n_gold_units``, ``units_in``; ``None`` (the floor arm) leaves every status
    ``na_no_context``.
    """
    keep = set(instances)
    out: Table = []
    for r in latest(rows):
        iid = str(r["instance_id"])
        if str(r["arm"]) != arm or iid not in keep:
            continue
        row: dict[str, Any] = {
            "arm": arm,
            "instance_id": iid,
            "run": int(r["run"]),
            "outcome": str(r["outcome"]),
            "outcome_class": outcome_class(str(r["outcome"])),
            "resolved": int(bool(r["resolved"])),
        }
        if pres is None:
            row.update(
                file_status="no_context", file_status_py="no_context", unit_status="no_context"
            )
        else:
            p = pres[iid]
            row["file_status"] = status_of(int(p["n_gold_files"]), int(p["files_in"]))
            row["file_status_py"] = status_of(int(p["n_gold_files_py"]), int(p["files_in_py"]))
            row["unit_status"] = status_of(int(p["n_gold_units"]), int(p["units_in"]))
        out.append(row)
    return out


def _by_instance(att: Table, level: str) -> tuple[list[str], Arr, Arr, list[str]]:
    """Instances, attempts per instance, resolved per instance, status per instance."""
    ids = sorted({a["instance_id"] for a in att})
    n = np.zeros(len(ids))
    k = np.zeros(len(ids))
    st = ["na"] * len(ids)
    pos = {i: j for j, i in enumerate(ids)}
    for a in att:
        j = pos[a["instance_id"]]
        n[j] += 1
        k[j] += a["resolved"]
        st[j] = a[level]
    return ids, n, k, st


def failure_split(att: Table, level: str) -> Table:
    """Table a: unresolved attempts of one arm by outcome class and gold status."""
    unresolved = [a for a in att if a["outcome_class"] != "resolved"]
    out: Table = []
    total = len(unresolved)
    for cls in UNRESOLVED:
        sel = [a for a in unresolved if a["outcome_class"] == cls]
        row: dict[str, Any] = {"outcome_class": cls, "n": len(sel)}
        for s in STATUSES:
            row[s] = sum(1 for a in sel if a[level] == s)
        out.append(row)
    all_row: dict[str, Any] = {"outcome_class": "all_unresolved", "n": total}
    for s in STATUSES:
        all_row[s] = sum(1 for a in unresolved if a[level] == s)
    all_row["share_all_gold"] = all_row["all"] / total if total else math.nan
    out.append(all_row)
    return out


def conditional_rates(att: Table, level: str, seed: int, resamples: int = RESAMPLES) -> Table:
    """Table b: resolved attempts over attempts by gold status, interval by instance bootstrap.

    Descriptive only: easy-to-retrieve gold may also be easy to repair.
    """
    ids, n, k, st = _by_instance(att, level)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(ids), size=(resamples, len(ids)))
    stat = np.array(st)
    out: Table = []
    for s in STATUSES:
        mask = stat == s
        row: dict[str, Any] = {
            "status": s,
            "instances": int(mask.sum()),
            "attempts": int(n[mask].sum()),
            "resolved": int(k[mask].sum()),
            "rate": float(k[mask].sum() / n[mask].sum()) if n[mask].sum() else math.nan,
        }
        num = (k * mask)[idx].sum(axis=1)
        den = (n * mask)[idx].sum(axis=1)
        ok = den > 0
        if ok.any() and mask.any():
            lo, hi = percentile_interval(num[ok] / den[ok])
            row["ci_low"], row["ci_high"] = lo, hi
        out.append(row)
    return out


def _flag(att: Table, level: str, kind: str) -> dict[str, int | None]:
    """Per instance: 1 if the gold is present (``all``: status all; ``any``: not none), 0 if not,
    ``None`` when the instance has no gold at this level."""
    out: dict[str, int | None] = {}
    for a in att:
        s = a[level]
        out[a["instance_id"]] = (
            None if s == "na" else int(s == "all" if kind == "all" else s != "none")
        )
    return out


def paired_counts(base: Table, arm: Table, level: str, kind: str) -> dict[str, Any]:
    """Table c row: instances gaining, losing and keeping presence against the untrained arm.

    ``kept_present`` and ``kept_absent`` are the two ways of keeping; ``net`` = gains - losses.
    Instances without gold at this level are counted apart.
    """
    fb, fa = _flag(base, level, kind), _flag(arm, level, kind)
    gain = loss = kept_p = kept_a = na = 0
    for iid, b in fb.items():
        a = fa.get(iid)
        if b is None or a is None:
            na += 1
        elif a and not b:
            gain += 1
        elif b and not a:
            loss += 1
        elif a:
            kept_p += 1
        else:
            kept_a += 1
    return {
        "level": level,
        "view": kind,
        "gains": gain,
        "losses": loss,
        "kept_present": kept_p,
        "kept_absent": kept_a,
        "no_gold": na,
        "net": gain - loss,
        "gross_moved": gain + loss,
        "present_base": kept_p + loss,
        "present_arm": kept_p + gain,
    }


def consistency_check(
    base: Table,
    arm: Table,
    scores_base: Mapping[str, float],
    scores_arm: Mapping[str, float],
    level: str,
    seed: int,
    resamples: int = RESAMPLES,
) -> dict[str, Any]:
    """Table d: the all-gold net change times the conditional effect, beside the measured contrast.

    A consistency check, not an explanation proven. Form (i) uses ``r_all - r_notall`` of the
    untrained arm, form (ii) the literal ``r_all``; both in points of the resolved fraction over the
    instances with gold at this level. The bootstrap redraws instances and recomputes the net, the
    rates and the measured paired difference together.
    """
    ids = sorted(i for i, f in _flag(base, level, "all").items() if f is not None)
    fb, fa = _flag(base, level, "all"), _flag(arm, level, "all")
    present_b = np.array([fb[i] for i in ids], dtype=float)
    present_a = np.array([fa[i] for i in ids], dtype=float)
    sb = np.array([scores_base[i] for i in ids])
    sa = np.array([scores_arm[i] for i in ids])
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(ids), size=(resamples, len(ids)))

    def stats(ix: npt.NDArray[np.int64]) -> tuple[Any, Any, Any, int]:
        pb, pa, b = present_b[ix], present_a[ix], sb[ix]
        net = (pa - pb).sum(axis=-1)
        r_all = (b * pb).sum(axis=-1) / np.maximum(pb.sum(axis=-1), 1)
        r_not = (b * (1 - pb)).sum(axis=-1) / np.maximum((1 - pb).sum(axis=-1), 1)
        n = pb.shape[-1]
        return net, r_all, r_not, n

    net, r_all, r_not, n = stats(idx)
    f1 = net * (r_all - r_not) / n
    f2 = net * r_all / n
    net0, r_all0, r_not0, n0 = stats(np.arange(len(ids)))
    out: dict[str, Any] = {
        "level": level,
        "instances_with_gold": len(ids),
        "net_all_gold": int(net0),
        "r_all_untrained": float(r_all0),
        "r_not_all_untrained": float(r_not0),
        "predicted_effect_difference_points": float(net0 * (r_all0 - r_not0) / n0 * 100),
        "predicted_effect_literal_points": float(net0 * r_all0 / n0 * 100),
        "measured_difference_points_on_these": float((sa - sb).mean() * 100),
    }
    for name, v in (("difference", f1), ("literal", f2)):
        lo, hi = percentile_interval(v)
        out[f"predicted_{name}_ci_low_points"] = lo * 100
        out[f"predicted_{name}_ci_high_points"] = hi * 100
    return out


def efficiency(
    rows: Rows, arm: str, instances: Collection[str], seed: int = 0, resamples: int = RESAMPLES
) -> dict[str, Any]:
    """Per-arm tokens, calls and cost from the result rows (sums over the calls of an attempt).

    Per-attempt means come with a percentile bootstrap interval over instances (the mean of each
    instance's attempts is resampled), for the cost, the uncached prompt, the output tokens and the
    calls.
    """
    keep = set(instances)
    sel = [r for r in latest(rows) if str(r["arm"]) == arm and str(r["instance_id"]) in keep]
    n = len(sel)

    def total(key: str) -> float:
        return float(sum(float(r.get(key) or 0) for r in sel))

    inp, cached = total("input_tokens"), total("cached_tokens")
    ids = sorted({str(r["instance_id"]) for r in sel})
    pos = {i: j for j, i in enumerate(ids)}

    def per_instance(fn: Any) -> Arr:
        acc = np.zeros(len(ids))
        cnt = np.zeros(len(ids))
        for r in sel:
            j = pos[str(r["instance_id"])]
            acc[j] += fn(r)
            cnt[j] += 1
        return acc / cnt

    out: dict[str, Any] = {
        "arm": arm,
        "attempts": n,
        "instances": len(ids),
        "prompt_tokens_per_attempt": inp / n,
        "cached_prompt_tokens_per_attempt": cached / n,
        "uncached_prompt_tokens_per_attempt": (inp - cached) / n,
        "cached_share": cached / inp if inp else math.nan,
        "output_tokens_per_attempt": total("output_tokens") / n,
        "thought_tokens_per_attempt": total("thought_tokens") / n,
        "calls_per_attempt": total("calls") / n,
        "cost_usd_per_attempt": total("cost_usd") / n,
        "cost_usd_total": total("cost_usd"),
        "prompt_tokens_total": inp,
        "output_tokens_total": total("output_tokens"),
    }
    series = {
        "cost_usd": lambda r: float(r.get("cost_usd") or 0),
        "uncached_prompt_tokens": lambda r: (
            float(r.get("input_tokens") or 0) - float(r.get("cached_tokens") or 0)
        ),
        "output_tokens": lambda r: float(r.get("output_tokens") or 0),
        "calls": lambda r: float(r.get("calls") or 0),
    }
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(ids), size=(resamples, len(ids)))
    for name, fn in series.items():
        lo, hi = percentile_interval(per_instance(fn)[idx].mean(axis=1))
        out[f"{name}_per_attempt_ci_low"] = lo
        out[f"{name}_per_attempt_ci_high"] = hi
    return out


def gap_closed(u: Arr, f: Arr, o: Arr, seed: int, resamples: int = RESAMPLES) -> dict[str, Any]:
    """(untrained - floor) / (oracle - floor) over paired instances, with a paired bootstrap.

    ``u``, ``f``, ``o`` are per-instance scores on the same instances. The ratio is unstable when
    the denominator interval is wide, so the denominator and numerator are reported with theirs.
    Resamples whose denominator is not positive have no ratio; they are left out of the ratio
    interval and counted in ``ratio_resamples_with_denominator_le_zero``.
    """
    n = len(u)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(resamples, n))
    num = (u[idx] - f[idx]).mean(axis=1)
    den = (o[idx] - f[idx]).mean(axis=1)
    ok = den > 0
    ratio = num[ok] / den[ok]
    lo, hi = percentile_interval(ratio) if ok.any() else (math.nan, math.nan)
    nlo, nhi = percentile_interval(num)
    dlo, dhi = percentile_interval(den)
    return {
        "instances": n,
        "untrained": float(u.mean()),
        "floor": float(f.mean()),
        "oracle": float(o.mean()),
        "numerator_points": float((u - f).mean() * 100),
        "numerator_ci_low": nlo * 100,
        "numerator_ci_high": nhi * 100,
        "denominator_points": float((o - f).mean() * 100),
        "denominator_ci_low": dlo * 100,
        "denominator_ci_high": dhi * 100,
        "ratio": float((u - f).mean() / (o - f).mean()),
        "ratio_ci_low": lo,
        "ratio_ci_high": hi,
        "ratio_resamples_with_denominator_le_zero": int((den <= 0).sum()),
    }


def repository_split(
    rows: Rows,
    instances: Sequence[str],
    repo_of: Mapping[str, str],
    base_arm: str,
    arms: Sequence[str],
    runs: Sequence[int],
    seed: int,
    repo: str = "django/django",
    resamples: int = RESAMPLES,
) -> Table:
    """Each arm minus the base arm on ``repo`` and on all other repositories (registered form)."""
    names = [base_arm, *arms]
    sc = score_matrix(rows, instances, names, runs, "exact")
    isin = np.array([repo_of[i] == repo for i in instances])
    out: Table = []
    for label, mask in ((repo, isin), (f"not {repo}", ~isin)):
        for j, arm in enumerate(arms, start=1):
            res = paired_contrast(
                sc.values[mask, j], sc.values[mask, 0], seed, resamples, 0, test=False
            )
            out.append(
                {"slice": label, "arm": arm, "base": base_arm, "instances": int(mask.sum())} | res
            )
    return out
