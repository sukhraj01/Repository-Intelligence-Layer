"""Retrieval-versus-reasoning breakdown of the graded agent runs and their cost (E-RQ3-BREAKDOWN).

Exploratory and descriptive; reads stored rows only and calls no model. For every graded run of the
four registered arms (E-RQ3-AGENT) on the 327 confirmatory instances, the instance is put in one of
three classes by the arm's own context: every file the gold patch modifies is in the context
(``all``), some but not all are (``some``), or none is (``none``). Files the gold patch creates
cannot be in a context and are left out of the gold set (one instance has one).

* A failed run whose class is ``none`` is a retrieval failure: the model never saw a file it had to
  change. A failed run of class ``all`` is a reasoning or editing failure: every file was there.
* The resolved-rate gain of a trained arm over the untrained arm that its retrieval alone explains
  is the change in the number of instances in each class times the untrained arm's resolved
  fraction in that class, summed and divided by the 327 (reasoned arithmetic on measured parts):
  the gain the trained arm would show if it converted each class exactly as the untrained arm.

Cost per attempt is the sum of prompt and output tokens (output includes thinking) and of the
realised cost over the arm's graded runs, one run being one repeat of one instance with its
follow-up calls. Kept compatible with Python 3.10.
"""

from __future__ import annotations

import os
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from ril.assembly.tokens import ApproxTokenizer

Record = dict[str, Any]
CLASSES = ("all", "some", "none")
OUTCOMES = ("resolved", "executed_unresolved", "apply_failed", "unusable", "exec_error")


def gold_class(gold_modified: Iterable[str], context_files: Iterable[str]) -> str:
    """``all``, ``some`` or ``none`` of the gold patch's modified files in the context."""
    gold, ctx = set(gold_modified), set(context_files)
    if gold and gold <= ctx:
        return "all"
    return "some" if gold & ctx else "none"


def outcome_of(row: Record) -> str:
    """Outcome bucket of one graded run (the exact patch reading, as registered)."""
    if row["resolved"]:
        return "resolved"
    kind = str(row.get("outcome", "")).split(":", 1)[0]
    return kind if kind in OUTCOMES else "other"


def breakdown(
    rows: Sequence[Record],
    instances: Sequence[str],
    gold: Mapping[str, Sequence[str]],
    context_files: Mapping[str, Sequence[str]],
) -> Record:
    """Instances and runs per gold class, with outcomes, for one arm on ``instances``."""
    cls = {i: gold_class(gold[i], context_files.get(i, ())) for i in instances}
    wanted = set(instances)
    runs: dict[str, Counter[str]] = {c: Counter() for c in CLASSES}
    for r in rows:
        if r["instance_id"] in wanted:
            runs[cls[r["instance_id"]]][outcome_of(r)] += 1
    per_class: dict[str, Record] = {}
    for c in CLASSES:
        n = sum(runs[c].values())
        per_class[c] = {
            "instances": sum(1 for v in cls.values() if v == c),
            "runs": n,
            "resolved": runs[c]["resolved"],
            "resolved_share": runs[c]["resolved"] / n if n else None,
            "outcomes": dict(sorted(runs[c].items())),
        }
    failed = {c: per_class[c]["runs"] - per_class[c]["resolved"] for c in CLASSES}
    total_failed = sum(failed.values())
    return {
        "instances": len(instances),
        "runs": sum(per_class[c]["runs"] for c in CLASSES),
        "classes": per_class,
        "failed_runs": total_failed,
        "failed_share_all_gold_present": failed["all"] / total_failed if total_failed else None,
        "failed_share_no_gold_present": failed["none"] / total_failed if total_failed else None,
    }


def expected_retrieval_gain(arm: Record, baseline: Record) -> Record:
    """Resolved-rate gain explained by the arm's class mix at the baseline's per-class rates."""
    shift = {
        c: arm["classes"][c]["instances"] - baseline["classes"][c]["instances"] for c in CLASSES
    }
    rates = {c: baseline["classes"][c]["resolved_share"] or 0.0 for c in CLASSES}
    gain = sum(shift[c] * rates[c] for c in CLASSES) / baseline["instances"]
    return {
        "instance_shift": shift,
        "baseline_resolved_share": rates,
        "explained_gain_points": 100 * gain,
    }


def attempt_cost(rows: Sequence[Record], instances: Sequence[str]) -> Record:
    """Tokens and USD per graded run (one repeat of one instance, follow-ups included).

    Prompt tokens are split into cached and uncached; thought tokens are the ones the provider
    logged separately (as logged, they may or may not be inside ``output_tokens``).
    """
    wanted = set(instances)
    sel = [r for r in rows if r["instance_id"] in wanted]
    prompt = sum(int(r["input_tokens"]) for r in sel)
    output = sum(int(r["output_tokens"]) for r in sel)
    cached = sum(int(r.get("cached_tokens") or 0) for r in sel)
    thought = sum(int(r.get("thought_tokens") or 0) for r in sel)
    usd = sum(float(r["cost_usd"]) for r in sel)
    n = len(sel)
    return {
        "runs": n,
        "calls": sum(int(r["calls"]) for r in sel),
        "prompt_tokens": prompt,
        "cached_prompt_tokens": cached,
        "uncached_prompt_tokens": prompt - cached,
        "output_tokens": output,
        "thought_tokens": thought,
        "cached_share": cached / prompt if prompt else None,
        "tokens_per_run": (prompt + output) / n if n else None,
        "usd": usd,
        "usd_per_run": usd / n if n else None,
    }


def gap_closed(context: float, floor: float, oracle: float) -> float:
    """Share of the floor-to-oracle distance that a context arm covers."""
    return (context - floor) / (oracle - floor)


def python_tokens(root: str) -> Record:
    """Python files and approximate tokens (the assembly's counter) of a checkout, no ``.git``."""
    tok = ApproxTokenizer()
    files = tokens = 0
    for d, dirs, names in os.walk(root):
        dirs[:] = sorted(x for x in dirs if x != ".git")
        for name in sorted(names):
            if name.endswith(".py"):
                with open(os.path.join(d, name), encoding="utf-8", errors="replace") as handle:
                    tokens += tok.count(handle.read())
                files += 1
    return {"python_files": files, "approx_tokens": tokens}
