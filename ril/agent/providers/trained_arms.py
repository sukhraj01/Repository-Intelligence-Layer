"""Arm list, prompts and analysis plan of the trained arms of RQ3.

Implements ``docs/RQ3_PILOT.md`` ("Trained arms", D113, D121). The driver and the analysis are
keyed by an arm name; a trained arm is one more name (``tr_<run id>``, see
``ril.evaluation.rq3_trained``), with its own contexts directory and its own prepared directory
(the driver's ``run`` takes one prepared directory per arm), so nothing in the driver changes.

Two things are fixed here, both ``provisional`` until the lead rules on them (recorded as open
lines of ``E-RQ3-TRAINED-ARMS``):

* **one arm per retained model**, so every (cell, seed) is its own arm; seeds are never averaged
  into one arm silently;
* **the contrasts of D113 carried to the trained arms**: the primary contrast stays one named
  pair, RAW (at the primary seed) against the untrained encoder (the arm ``dense`` of
  E-RQ3-CONTEXTS), with the paired bootstrap and sign-flip of ``ril.analysis.rq3_results``; every
  other pair (the other seeds of RAW against the untrained encoder, FILTER-BM25 against the
  untrained encoder and against RAW of the same seed, the remaining cells against RAW of the same
  seed) is an estimate with an interval and no test. The primary seed is the smallest seed for
  which a RAW model is retained, a rule fixed here and written into the plan.

Prompts are built by the untrained path (``rows_from_records`` and ``prepare_screened``,
pseudonymised before the screen, D120); :func:`prepare_trained` only wraps those two calls.
"""

from __future__ import annotations

import json
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ril.analysis.rq3_results import Plan

UNTRAINED_ARM = "dense"
"""The untrained encoder alone (arm of E-RQ3-CONTEXTS), the baseline of the primary contrast."""
RAW_CELL = "mined_raw"
FILTER_CELL = "mined_filter_bm25"
PLAN_VERSION = "rq3-trained-plan/v1"


@dataclass(frozen=True)
class TrainedArm:
    """A trained arm as the plan sees it (no paths, no hashes beyond the model's)."""

    arm: str
    run_id: str
    cell: str
    seed: int
    model_sha256: str = ""


def arms_from_records(records: Sequence[Mapping[str, Any]]) -> list[TrainedArm]:
    """Arms from the model records written by the encode stage (``model.json`` of each model)."""
    out = [
        TrainedArm(
            str(r["arm"]),
            str(r["run_id"]),
            str(r["cell"]),
            int(r["seed"]),
            str(r.get("model_sha256", "")),
        )
        for r in records
    ]
    names = [a.arm for a in out]
    if len(set(names)) != len(names):
        raise ValueError("two models give the same arm name")
    return sorted(out, key=lambda a: (a.seed, a.cell, a.run_id))


def primary_seed(arms: Sequence[TrainedArm]) -> int | None:
    """Smallest seed with a RAW model, or ``None`` if there is no RAW model."""
    seeds = sorted(a.seed for a in arms if a.cell == RAW_CELL)
    return seeds[0] if seeds else None


def build_plan(
    arms: Sequence[TrainedArm],
    runs: Sequence[int],
    *,
    untrained: str = UNTRAINED_ARM,
    seed: int = 0,
) -> dict[str, Any]:
    """The analysis plan of the trained arms (arm list, primary pair, estimates) as a record.

    ``arms`` in the plan: the untrained arm first, then the trained arms in (seed, cell) order.
    Without a RAW model there is no primary contrast, and the plan refuses (D113's primary pair
    is RAW against the untrained encoder).
    """
    ps = primary_seed(arms)
    if ps is None:
        raise ValueError("no RAW model among the trained arms: the primary pair cannot be formed")
    raw = {a.seed: a for a in arms if a.cell == RAW_CELL}
    filt = {a.seed: a for a in arms if a.cell == FILTER_CELL}
    primary = (raw[ps].arm, untrained)
    estimates: list[tuple[str, str]] = []
    for s in sorted(raw):
        if (raw[s].arm, untrained) != primary:
            estimates.append((raw[s].arm, untrained))
    for s in sorted(filt):
        estimates.append((filt[s].arm, untrained))
        if s in raw:
            estimates.append((filt[s].arm, raw[s].arm))
    for a in arms:
        if a.cell in (RAW_CELL, FILTER_CELL):
            continue
        estimates.append((a.arm, untrained))
        if a.seed in raw:
            estimates.append((a.arm, raw[a.seed].arm))
    unique: list[tuple[str, str]] = []
    for pair in estimates:
        if pair != primary and pair not in unique:
            unique.append(pair)
    return {
        "version": PLAN_VERSION,
        "provisional": "D113, D121 for trained arms; primary seed = smallest RAW seed",
        "arms": [untrained, *[a.arm for a in arms]],
        "primary": list(primary),
        "estimates": [list(p) for p in unique],
        "runs": [int(r) for r in runs],
        "seed": int(seed),
        "primary_seed": ps,
        "models": [
            {
                "arm": a.arm,
                "run_id": a.run_id,
                "cell": a.cell,
                "seed": a.seed,
                "sha256": a.model_sha256,
            }
            for a in arms
        ],
    }


def plan_from_record(record: Mapping[str, Any]) -> Plan:
    """The ``rq3_results.Plan`` of a plan record (what ``analyse`` takes)."""
    return Plan(
        arms=tuple(str(a) for a in record["arms"]),
        primary=(str(record["primary"][0]), str(record["primary"][1])),
        estimates=tuple((str(a), str(b)) for a, b in record["estimates"]),
        runs=tuple(int(r) for r in record["runs"]),
        seed=int(record["seed"]),
    )


def read_plan(path: str) -> Plan:
    """Read a plan file written by ``scripts/rq3_trained_arm.py analysis-plan``."""
    return plan_from_record(json.loads(Path(path).read_text(encoding="utf-8")))


def prepare_trained(
    ctx_dir: str,
    arm: str,
    issues: Mapping[str, str],
    budget: int,
    out_dir: str,
    *,
    instance_ids: Collection[str] | None = None,
    allowed_email_digests: Collection[str] = (),
    forbidden_emails: Sequence[str] = (),
) -> dict[str, Any]:
    """Prompts of one trained arm: the untrained path (rows, pseudonymise, screen, write).

    Returns ``{written, rejected, skipped}``. The writing is ``prepare_screened`` unchanged, so a
    prompt differs from the untrained arm's only where the retrieved context differs.
    """
    from ril.agent.providers.rq3_prompts import prepare_screened, rows_from_records

    rows, skipped = rows_from_records(ctx_dir, issues, budget, [arm], instance_ids)
    n, rejected = prepare_screened(rows, out_dir, allowed_email_digests, forbidden_emails)
    return {"written": n, "rejected": rejected, "skipped": skipped}
