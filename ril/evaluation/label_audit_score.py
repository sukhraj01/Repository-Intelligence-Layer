"""Scorer of the pull-request label sheets: agreement, noise rates, findability, missing positives.

Implements ``docs/RQ2_PROTOCOL.md`` section 7 and ``docs/LABEL_AUDIT.md``. Input: the filled sheets
of the readers and the key file (stratum, K-rank cell, population size of each stratum). Every
number is *measured on a sample* of the stated n; a reader's verdict is a judgement, not ground
truth, and nothing here is a statement about the full mined set beyond the sample's strata.

Handling of uncertain answers (stated in the instructions page and used everywhere below):

* ``cannot tell`` is an answer. A pair with one reader and ``cannot tell`` is *unresolved*.
* A pair read by both readers is resolved only if they gave the same answer; two different
  answers (including ``cannot tell`` against a verdict) make it *disputed*, which is unresolved
  as well. Nobody adjudicates here.
* Every rate is reported in three readings: ``excluded`` (unresolved pairs left out of the
  denominator), ``lower`` (unresolved pairs stay in the denominator and count as *not* the event)
  and ``upper`` (they stay and count as the event). The truth of the sample lies between the last
  two if the readers' uncertainty is the only source of doubt.

Overall rates weight the two strata by their population sizes (the sample takes equal numbers from
each); the unweighted pooled share is printed beside it and labelled so. Intervals: Wilson for
shares within one stratum or pooled, a seeded stratified bootstrap for the weighted combinations.
Pairs of one pull request are not independent; the number of pull requests is reported. Kept
compatible with Python 3.10.
"""

from __future__ import annotations

import csv
import math
import random
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ril.evaluation.label_audit import (
    CANNOT_TELL,
    MISSING_ANSWERS,
    NO,
    NOT_RELEVANT,
    RELEVANT,
    STRATA,
    STRATUM_DROPPED,
    STRATUM_KEPT,
    VERDICTS,
    YES,
)
from ril.evaluation.spot_check import cohen_kappa

Z95 = 1.959964
DISPUTED = "disputed"
READINGS: tuple[str, ...] = ("excluded", "lower", "upper")
EVIDENCE = (
    "measured on a sample of readers' judgements (not ground truth); n stated beside each number"
)


class SheetError(ValueError):
    """A filled sheet that cannot be scored as it stands (never repaired silently)."""


@dataclass(frozen=True)
class KeyRow:
    pair_id: str
    stratum: str
    directory: str
    in_overlap: bool
    population: int
    dense_kept: bool | None


@dataclass
class Answers:
    """One reader's answers: pair id -> (verdict, issue_function_not_edited), blanks left out."""

    reader: str
    verdict: dict[str, str]
    missing: dict[str, str]
    reasons: dict[str, str]


def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float] | None:
    """Wilson score interval of a share ``k`` of ``n``; ``None`` for ``n == 0``."""
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, centre - half), min(1.0, centre + half)


def _norm(value: str) -> str:
    return " ".join(value.strip().lower().replace("_", " ").replace("-", " ").split())


def read_key(path: str) -> dict[str, KeyRow]:
    with open(path, encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    out: dict[str, KeyRow] = {}
    for r in rows:
        if r["stratum"] not in STRATA:
            raise SheetError(f"key: unknown stratum {r['stratum']!r}")
        dense = r.get("dense_kept_k20", "")
        out[r["pair_id"]] = KeyRow(
            r["pair_id"],
            r["stratum"],
            r["directory"],
            r["in_overlap"] == "1",
            int(r["stratum_population"]),
            None if dense == "" else dense == "1",
        )
    return out


def read_sheet(path: str, known: Mapping[str, Any]) -> Answers:
    """Answers of one filled sheet. Unknown values and unknown pair ids raise ``SheetError``."""
    with open(path, encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for col in ("pair_id", "verdict", "issue_function_not_edited"):
        if rows and col not in rows[0]:
            raise SheetError(f"{path}: column {col!r} is missing")
    readers = {r.get("reader_id", "").strip() for r in rows} - {""}
    if len(readers) > 1:
        raise SheetError(f"{path}: several reader ids {sorted(readers)}")
    ans = Answers(next(iter(readers), path), {}, {}, {})
    problems: list[str] = []
    for r in rows:
        pid = r["pair_id"].strip()
        if pid not in known:
            problems.append(f"{pid}: not a pair of this sample")
            continue
        if pid in ans.verdict or pid in ans.missing:
            problems.append(f"{pid}: appears twice")
            continue
        v, m = _norm(r["verdict"]), _norm(r["issue_function_not_edited"])
        if v and v not in VERDICTS:
            problems.append(f"{pid}: verdict {r['verdict']!r} is not one of {VERDICTS}")
        elif v:
            ans.verdict[pid] = v
        if m and m not in MISSING_ANSWERS:
            problems.append(
                f"{pid}: second answer {r['issue_function_not_edited']!r} "
                f"is not one of {MISSING_ANSWERS}"
            )
        elif m:
            ans.missing[pid] = m
        if r.get("reason", "").strip():
            ans.reasons[pid] = r["reason"].strip()
    if problems:
        raise SheetError(f"{path}: {len(problems)} problem(s), first: {problems[0]}")
    return ans


def combine(answers: Sequence[Answers], field: str) -> dict[str, str]:
    """One resolved answer per pair: the single answer, the agreed one, or ``disputed``."""
    seen: dict[str, list[str]] = {}
    for a in answers:
        for pid, v in getattr(a, field).items():
            seen.setdefault(pid, []).append(v)
    return {pid: vs[0] if len(set(vs)) == 1 else DISPUTED for pid, vs in seen.items()}


# --------------------------------------------------------------------------- agreement


def agreement(
    a: Answers, b: Answers, field: str, key: Mapping[str, KeyRow], *, seed: int, draws: int
) -> dict[str, Any]:
    """Percent agreement and Cohen's kappa (bootstrap interval) over pairs both readers answered."""
    va, vb = getattr(a, field), getattr(b, field)
    ids = sorted(set(va) & set(vb))
    out: dict[str, Any] = {
        "evidence": EVIDENCE,
        "readers": [a.reader, b.reader],
        "n_overlap_in_key": sum(1 for k in key.values() if k.in_overlap),
        "n_both_answered": len(ids),
    }
    if not ids:
        return out
    x, y = [va[i] for i in ids], [vb[i] for i in ids]
    agree = sum(1 for p, q in zip(x, y, strict=True) if p == q)
    out["agreement"] = agree / len(ids)
    out["agreement_wilson95"] = wilson(agree, len(ids))
    out["kappa"] = cohen_kappa(x, y)
    rng = random.Random(f"label-audit-score/{seed}/kappa/{field}")
    stats = []
    for _ in range(draws):
        idx = [rng.randrange(len(ids)) for _ in ids]
        stats.append(cohen_kappa([x[i] for i in idx], [y[i] for i in idx]))
    out["kappa_bootstrap95"] = _percentile(stats, 0.025, 0.975)
    out["kappa_bootstrap_draws"] = draws
    labels = sorted(set(x) | set(y))
    out["confusion_first_by_second"] = {
        p: {q: sum(1 for s, t in zip(x, y, strict=True) if s == p and t == q) for q in labels}
        for p in labels
    }
    out["disagreements"] = [
        {"pair_id": i, "first": p, "second": q} for i, p, q in zip(ids, x, y, strict=True) if p != q
    ]
    if field == "verdict":
        both = [(p, q) for p, q in zip(x, y, strict=True) if CANNOT_TELL not in (p, q)]
        out["two_way_without_cannot_tell"] = {
            "n": len(both),
            "agreement": (sum(1 for p, q in both if p == q) / len(both)) if both else None,
            "kappa": cohen_kappa([p for p, _ in both], [q for _, q in both]) if both else None,
        }
    return out


def _percentile(values: Sequence[float], lo: float, hi: float) -> tuple[float, float] | None:
    if not values:
        return None
    s = sorted(values)
    return s[int(lo * (len(s) - 1))], s[int(math.ceil(hi * (len(s) - 1)))]


# --------------------------------------------------------------------------- rates


def _outcomes(
    final: Mapping[str, str], key: Mapping[str, KeyRow], event: str, other: str, reading: str
) -> dict[str, list[int]]:
    """Per stratum, the 0/1 outcome of each resolved or unresolved pair under ``reading``."""
    out: dict[str, list[int]] = {s: [] for s in STRATA}
    for pid in sorted(final):
        v = final[pid]
        if v == event:
            o = 1
        elif v == other:
            o = 0
        elif reading == "excluded":
            continue
        else:
            o = 1 if reading == "upper" else 0
        out[key[pid].stratum].append(o)
    return out


def _weighted(p: Mapping[str, float | None], pop: Mapping[str, int]) -> float | None:
    if any(p[s] is None for s in STRATA):
        return None
    total = sum(pop.values())
    return sum(pop[s] / total * float(p[s] or 0.0) for s in STRATA)


def _combos(
    outcomes: Mapping[str, Sequence[int]], pop: Mapping[str, int]
) -> dict[str, float | None]:
    p = {s: (sum(v) / len(v) if v else None) for s, v in outcomes.items()}
    overall = _weighted(p, pop)
    dropped_noisy = pop[STRATUM_DROPPED] * (p[STRATUM_DROPPED] or 0.0)
    kept_noisy = pop[STRATUM_KEPT] * (p[STRATUM_KEPT] or 0.0)
    both = p[STRATUM_DROPPED] is not None and p[STRATUM_KEPT] is not None
    findable = (
        dropped_noisy / (dropped_noisy + kept_noisy)
        if both and (dropped_noisy + kept_noisy) > 0
        else None
    )
    p_dropped = p[STRATUM_DROPPED]
    lift = p_dropped / overall if overall and p_dropped is not None else None
    return {"overall_weighted": overall, "noisy_dropped_share": findable, "lift": lift}


def rate_table(
    final: Mapping[str, str],
    key: Mapping[str, KeyRow],
    event: str,
    other: str,
    *,
    population: Mapping[str, int],
    seed: int,
    draws: int,
) -> dict[str, Any]:
    """Share of ``event`` among answered pairs: per stratum, pooled, weighted, three readings."""
    unresolved = Counter(key[p].stratum for p, v in final.items() if v not in (event, other))
    out: dict[str, Any] = {
        "evidence": EVIDENCE,
        "event": event,
        "n_answered_by_stratum": dict(Counter(key[p].stratum for p in final)),
        "n_unresolved_by_stratum": {s: unresolved.get(s, 0) for s in STRATA},
        "n_pull_requests": len({key[p].directory for p in final}),
        "population_by_stratum": dict(population),
        "readings": {},
    }
    for reading in READINGS:
        oc = _outcomes(final, key, event, other, reading)
        by_stratum = {
            s: {
                "n": len(v),
                "events": sum(v),
                "share": (sum(v) / len(v)) if v else None,
                "wilson95": wilson(sum(v), len(v)),
            }
            for s, v in oc.items()
        }
        allv = [o for v in oc.values() for o in v]
        point = _combos(oc, population)
        rng = random.Random(f"label-audit-score/{seed}/{event}/{reading}")
        boots: dict[str, list[float]] = {k: [] for k in point}
        for _ in range(draws):
            resampled = {
                s: [v[rng.randrange(len(v))] for _ in v] if v else [] for s, v in oc.items()
            }
            for k, val in _combos(resampled, population).items():
                if val is not None:
                    boots[k].append(val)
        out["readings"][reading] = {
            "by_stratum": by_stratum,
            "pooled_unweighted": {
                "n": len(allv),
                "events": sum(allv),
                "share": (sum(allv) / len(allv)) if allv else None,
                "wilson95": wilson(sum(allv), len(allv)),
                "note": "equal numbers per stratum, not the pool share; see population_weighted",
            },
            "population_weighted": {
                k: {"value": point[k], "bootstrap95": _percentile(boots[k], 0.025, 0.975)}
                for k in point
            },
            "bootstrap_draws": draws,
        }
    return out


def dense_descriptive(final: Mapping[str, str], key: Mapping[str, KeyRow]) -> dict[str, Any]:
    """Counts of wrong positives by the dense K = 20 cell, for pairs that have a dense rank.

    Descriptive only: the sample was not stratified by this cell and covers a minority of pairs.
    """
    cells: dict[str, Counter[str]] = {"dense_kept": Counter(), "dense_dropped": Counter()}
    for pid, v in final.items():
        d = key[pid].dense_kept
        if d is None:
            continue
        cells["dense_kept" if d else "dense_dropped"][v] += 1
    return {
        "evidence": EVIDENCE + "; descriptive, unweighted",
        "cells": {k: dict(v) for k, v in cells.items()},
    }


def score(
    key: Mapping[str, KeyRow], sheets: Sequence[Answers], *, seed: int = 0, draws: int = 2000
) -> dict[str, Any]:
    """The full report as a JSON-ready dict."""
    population: dict[str, int] = {}
    for k in key.values():
        population[k.stratum] = k.population
    for s in STRATA:
        population.setdefault(s, 0)
    verdict = combine(sheets, "verdict")
    missing = combine(sheets, "missing")
    report: dict[str, Any] = {
        "readers": [a.reader for a in sheets],
        "n_pairs_in_key": len(key),
        "n_with_verdict": len(verdict),
        "n_without_verdict": len(key) - len(verdict),
        "verdict_counts": dict(Counter(verdict.values())),
        "rules": {
            "unresolved": "cannot tell, or two readers who gave different answers (disputed)",
            "readings": {
                "excluded": "unresolved pairs left out of the denominator",
                "lower": "unresolved pairs stay in the denominator and are not the event",
                "upper": "unresolved pairs stay in the denominator and are the event",
            },
        },
    }
    if len(sheets) == 2:
        report["agreement_verdict"] = agreement(
            sheets[0], sheets[1], "verdict", key, seed=seed, draws=draws
        )
        report["agreement_issue_function_not_edited"] = agreement(
            sheets[0], sheets[1], "missing", key, seed=seed, draws=draws
        )
    report["wrong_positive"] = rate_table(
        verdict, key, NOT_RELEVANT, RELEVANT, population=population, seed=seed, draws=draws
    )
    report["missing_positive"] = rate_table(
        missing, key, YES, NO, population=population, seed=seed, draws=draws
    )
    report["dense_cells"] = dense_descriptive(verdict, key)
    return report


def format_text(report: Mapping[str, Any]) -> str:
    """A short readable summary of the headline numbers (the JSON has the rest)."""

    def pct(x: float | None) -> str:
        return "n/a" if x is None else f"{100 * x:.1f}%"

    def ci(x: Sequence[float] | None) -> str:
        return "" if x is None else f" [{100 * x[0]:.1f}, {100 * x[1]:.1f}]"

    def cell(r: Mapping[str, Any], stratum: str) -> str:
        c = r["by_stratum"][stratum]
        return f"{pct(c['share'])}{ci(c['wilson95'])} (n = {c['n']})"

    lines = [
        f"readers: {report['readers']}; pairs with a verdict: "
        f"{report['n_with_verdict']} of {report['n_pairs_in_key']}"
    ]
    ag = report.get("agreement_verdict")
    if ag and ag.get("n_both_answered"):
        k = ag["kappa_bootstrap95"]
        lines.append(
            f"agreement (verdict): {pct(ag['agreement'])} of n = {ag['n_both_answered']}; "
            f"kappa {ag['kappa']:.2f}" + (f" [{k[0]:.2f}, {k[1]:.2f}]" if k else "")
        )
    for name, label in (
        ("wrong_positive", "wrong positives"),
        ("missing_positive", "pairs with an unedited function the issue is about"),
    ):
        for reading in READINGS:
            r = report[name]["readings"][reading]
            w = r["population_weighted"]["overall_weighted"]
            lines.append(
                f"{label} [{reading}]: weighted {pct(w['value'])}{ci(w['bootstrap95'])}; "
                f"kept {cell(r, STRATUM_KEPT)}; dropped {cell(r, STRATUM_DROPPED)}"
            )
            if name == "wrong_positive":
                f = r["population_weighted"]["noisy_dropped_share"]
                lines.append(
                    f"    precision of the K = 20 drops: {cell(r, STRATUM_DROPPED)}; "
                    f"share of noisy pairs dropped: {pct(f['value'])}{ci(f['bootstrap95'])}"
                )
    lines.append("evidence class of every number: " + EVIDENCE)
    return "\n".join(lines)
