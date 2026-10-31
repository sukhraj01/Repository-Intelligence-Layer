"""Tables of the matched-pool arms pilot, stage 1 (E-PILOT-ARMS2; exploratory, not an RQ table).

Builds on ``ril.analysis.t2_tables`` and ``ril.analysis.t4_tables`` (percentage points, paired
queries, 2,000 bootstrap draws shared by the columns of a table, seeds averaged for the cell effect
and shown beside it; the untrained encoder's per-query values come from the learning curve's step-0
rows). What is new here:

* two reference conditions, RAW on the full pool and the size-matched random subset of RAW (D43):
  every other cell is contrasted with both. The subsample condition is the mean, per seed, of the
  draws that were run (``pooled_draws``); a single draw is a pooled condition of one.
* the unique-example table of D42 (``unique_rows``): per run, the pool the cell drew from, the
  examples seen, the unique examples seen, the effective epochs, and a flag for every cell that
  repeated an example or saw fewer unique examples than the cell with the most (never silent).
* the stage-2 trigger of the brief, evaluated literally and written out (``stage2_trigger``).
* the minimum detectable difference at a given number of seeds from the observed variance
  (``minimum_detectable``), for the case that the trigger does not fire.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import math
import os
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from ril.analysis import t2_tables as tt
from ril.analysis import t4_tables as t4
from ril.analysis.x2_tables import write_csv

Record = dict[str, Any]
T5_TABLES_VERSION = "t5-tables/v1"
RAW = "t5a_raw"
SUB = "t5a_sub"
ARM_CELLS = (
    "t5a_filter_bm25",
    "t5a_filter_srs",
    "t5a_filter_cre",
    "t5a_weight_cre",
    "t5a_curr_cre",
)
Z_POWER = 1.959964 + 0.841621
"""z(0.975) + z(0.80): two-sided 5% test with 80% power."""


def pooled_draws(draws: Sequence[Sequence[tt.Run]], name: str = SUB) -> list[tt.Run]:
    """One run per seed whose per-query values are the mean over the draws available for the seed.

    The pooled run carries a variant name of its own (``name``) so its columns can be addressed like
    any run's; its record and hash are those of the seed's first draw (the draws' hashes are in the
    per-run table).
    """
    by_seed: dict[int, list[tt.Run]] = {}
    for runs in draws:
        for r in runs:
            by_seed.setdefault(r.seed, []).append(r)
    out: list[tt.Run] = []
    for seed, rs in sorted(by_seed.items()):
        vals: dict[tuple[str, str, str, str], float] = {}
        keys: dict[tuple[str, str, str, str], list[float]] = {}
        for r in rs:
            for (inst, lv, col, k), v in r.values.items():
                kind = col.split(":", 1)[0]
                if col == f"{kind}:{r.variant}":
                    keys.setdefault((inst, lv, f"{kind}:{name}", k), []).append(v)
                else:
                    vals.setdefault((inst, lv, col, k), v)  # baseline columns: identical
        for key, xs in keys.items():
            vals[key] = float(np.mean(xs))
        first = rs[0]
        out.append(
            tt.Run(
                exp_id=name,
                seed=seed,
                config_hash=first.config_hash,
                result_dir=first.result_dir,
                variant=name,
                values=vals,
                repo_of=dict(first.repo_of),
                record=first.record,
            )
        )
    return out


def unique_rows(draws_and_cells: Mapping[str, Sequence[tt.Run]]) -> list[Record]:
    """D42 table: one row per run, with the repeat flags (computed over all rows given)."""
    rows: list[Record] = []
    for cond, cell_runs in draws_and_cells.items():
        for run in cell_runs:
            tr = run.record["training"]
            b = tr["budget"]
            f = tr.get("filter", {})
            rows.append(
                {
                    "condition": cond,
                    "seed": run.seed,
                    "config_hash": run.config_hash[:12],
                    "arm": tr["arm"]["name"],
                    "teacher_equals_base": tr.get("teacher_equals_base"),
                    "pool_before_arm": f.get("examples_in"),
                    "pool_examples": b.get("pool_examples"),
                    "optimizer_updates": b.get("optimizer_updates"),
                    "examples_seen": b.get("examples_seen"),
                    "unique_examples_seen": b.get("unique_examples_seen"),
                    "effective_epochs": round(float(b.get("effective_epochs", 0.0)), 3),
                    "positives_seen": b.get("positives_seen"),
                    "negative_shortfall_visits": b.get("negative_shortfall_visits"),
                    "gpu_hours_train_loop": round(float(b.get("gpu_hours_train_loop", 0.0)), 4),
                }
            )
    if rows:
        top = max(int(r["unique_examples_seen"] or 0) for r in rows)
        for r in rows:
            seen, uniq = int(r["examples_seen"] or 0), int(r["unique_examples_seen"] or 0)
            r["repeats_examples"] = seen > uniq
            r["below_common_unique_count"] = uniq < top
    return rows


def _effect(
    rows: Sequence[Record], cond: str, ref: str, level: str, reading: str, kind: str = "dense"
) -> Record | None:
    for r in rows:
        if (
            r.get("condition") == cond
            and r.get("part") == "mean"
            and r.get("ref") == f"{ref}:mean"
            and r.get("level") == level
            and r.get("reading") == reading
            and r.get("kind") == kind
        ):
            return r
    return None


def _excludes(lo: float, hi: float) -> bool:
    return lo > 0 or hi < 0


def stage2_trigger(
    effects: Sequence[Record],
    spread: Sequence[Record],
    cells: Sequence[str] = ARM_CELLS,
    references: Sequence[str] = (RAW, SUB),
) -> Record:
    """The T5b rule of the brief, dense column, primary gold reading.

    (i) a cell's paired difference to RAW or to the size-matched subsample has an interval excluding
    0 at L3 (query level) or at L2 (repository-clustered), the point differences at the two levels
    having the SAME sign. Read literally: ``literal_i`` needs one level's interval to exclude 0 and
    the two levels to agree in sign; ``strict_i`` (reported beside it, not used) needs both
    intervals to exclude 0 in the same direction. (ii) the RAW seed gap above 1.0 point at either
    level. The L2 interval is the clustered one when the level has three repositories or more.
    """
    reading = tt.READINGS[0]
    hits: list[Record] = []
    for ref in references:
        for cond in cells:
            lv: dict[str, Record] = {}
            for level in ("L2", "L3"):
                e = _effect(effects, cond, ref, level, reading)
                if e is None:
                    continue
                clustered = int(e["repos"]) >= 3
                lo, hi = (e["d_c_lo"], e["d_c_hi"]) if clustered else (e["d_q_lo"], e["d_q_hi"])
                lv[level] = {
                    "d": e["d"],
                    "lo": lo,
                    "hi": hi,
                    "interval": "repository-clustered" if clustered else "query-level",
                    "excludes_zero": _excludes(lo, hi),
                    "sign": int(math.copysign(1, e["d"])) if e["d"] else 0,
                }
            if set(lv) != {"L2", "L3"}:
                continue
            same = lv["L2"]["sign"] == lv["L3"]["sign"] != 0
            hits.append(
                {
                    "condition": cond,
                    "reference": ref,
                    "L2": lv["L2"],
                    "L3": lv["L3"],
                    "same_sign": same,
                    "literal_i": same and (lv["L2"]["excludes_zero"] or lv["L3"]["excludes_zero"]),
                    "strict_i": same and lv["L2"]["excludes_zero"] and lv["L3"]["excludes_zero"],
                }
            )
    gaps = [
        {"level": s["level"], "range": s["range"], "per_seed": s["per_seed"]}
        for s in spread
        if s["condition"] == RAW and s["kind"] == "dense" and s["reading"] == reading
    ]
    return {
        "reading": reading,
        "cells": hits,
        "raw_seed_gap": gaps,
        "i_literal": any(h["literal_i"] for h in hits),
        "i_strict": any(h["strict_i"] for h in hits),
        "ii_raw_gap_above_1": any(g["range"] is not None and g["range"] > 1.0 for g in gaps),
    }


def largest_cells(
    effects: Sequence[Record], n: int = 2, cells: Sequence[str] = ARM_CELLS
) -> list[Record]:
    """The ``n`` cells with the largest absolute difference (max over the levels and the two
    references), primary reading, dense column: the stage-2 cells if (i) fires."""
    reading = tt.READINGS[0]
    score: dict[str, float] = {}
    for cond in cells:
        best = 0.0
        for ref in (RAW, SUB):
            for level in ("L2", "L3"):
                e = _effect(effects, cond, ref, level, reading)
                if e is not None:
                    best = max(best, abs(float(e["d"])))
        score[cond] = best
    ranked = sorted(score.items(), key=lambda kv: (-kv[1], kv[0]))
    return [{"condition": c, "max_abs_d": round(v, 2)} for c, v in ranked[:n]]


def minimum_detectable(
    spread: Sequence[Record],
    effects: Sequence[Record],
    seeds: int = 3,
    cells: Sequence[str] = ARM_CELLS,
) -> list[Record]:
    """Smallest difference between two cells detectable at 5% (two-sided) and 80% power.

    Two sources, per level, primary reading, dense column. Seed noise: the pooled SD of the cells'
    per-seed means (cells with at least two seeds, weighted by their degrees of freedom), and the
    difference of two cell means over ``seeds`` seeds, ``(z_a + z_b) * SD * sqrt(2 / seeds)``. Query
    sampling: ``(z_a + z_b) / 1.96`` times the mean half-width of the cells' paired-difference
    intervals against RAW (clustered at L2, query-level at L3). The larger one binds.
    """
    reading = tt.READINGS[0]
    out: list[Record] = []
    for level in ("L2", "L3"):
        ss, df = 0.0, 0
        for s in spread:
            if (
                s["level"] == level
                and s["kind"] == "dense"
                and s["reading"] == reading
                and s["sd"] is not None
                and len(s["per_seed"]) > 1
            ):
                k = len(s["per_seed"])
                ss += (k - 1) * float(s["sd"]) ** 2
                df += k - 1
        sd = math.sqrt(ss / df) if df else float("nan")
        halves = []
        for cond in cells:
            e = _effect(effects, cond, RAW, level, reading)
            if e is None:
                continue
            clustered = int(e["repos"]) >= 3
            lo, hi = (e["d_c_lo"], e["d_c_hi"]) if clustered else (e["d_q_lo"], e["d_q_hi"])
            halves.append((hi - lo) / 2)
        q_half = float(np.mean(halves)) if halves else float("nan")
        seed_mdd = Z_POWER * sd * math.sqrt(2 / seeds) if df else float("nan")
        query_mdd = Z_POWER / 1.959964 * q_half if halves else float("nan")
        out.append(
            {
                "level": level,
                "seeds": seeds,
                "pooled_seed_sd": round(sd, 3) if df else None,
                "seed_df": df,
                "seed_mdd": round(seed_mdd, 2) if df else None,
                "mean_interval_half_width": round(q_half, 2) if halves else None,
                "query_mdd": round(query_mdd, 2) if halves else None,
                "binding": round(max(x for x in (seed_mdd, query_mdd) if x == x), 2)
                if (df or halves)
                else None,
            }
        )
    return out


def matched_tables(
    results_root: str,
    cells: Sequence[str],
    draws: Sequence[str],
    step0_rows: str,
    out_dir: str,
    seed: int = 0,
    seeds_for_mdd: int = 3,
) -> Record:
    """All stage-1 tables; returns the log record (trigger, largest cells, minimum detectable)."""
    conds: dict[str, list[tt.Run]] = {c: tt.load_condition(results_root, c) for c in cells}
    draw_runs = {d: tt.load_condition(results_root, d) for d in draws}
    conds[SUB] = pooled_draws([r for r in draw_runs.values() if r], SUB)
    for runs in [*conds.values(), *draw_runs.values()]:
        t4.attach_base(runs, step0_rows)
    labels = {"pilot": "t5a", "evaluation": "evaluation", "label": "E-PILOT-ARMS2 stage 1"}
    effects: list[Record] = []
    spread: list[Record] = []
    for ref in (RAW, SUB):
        if not conds.get(ref):
            continue
        for kind in ("dense", "rrf"):
            for level in ("L2", "L3"):
                for reading in tt.READINGS:
                    rows = tt.contrast_rows(
                        conds,
                        ref,
                        kind=kind,
                        level=level,
                        reading=reading,
                        seed=seed,
                        labels={**labels, "reference": ref},
                    )
                    effects += rows
    for kind in ("dense", "rrf"):
        for level in ("L2", "L3"):
            for reading in tt.READINGS:
                spread += tt.seed_spread(conds, kind=kind, level=level, reading=reading)
    runs_for_unique = {**{c: conds[c] for c in cells}, **{d: draw_runs[d] for d in draws}}
    uniq = unique_rows(runs_for_unique)
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.join(out_dir, "t5a")
    write_csv(f"{stem}_effects.csv", effects)
    write_csv(f"{stem}_seeds.csv", spread)
    write_csv(f"{stem}_unique.csv", uniq)
    trig = stage2_trigger(effects, spread)
    return {
        "version": T5_TABLES_VERSION,
        "runs": {c: [r.seed for r in rs] for c, rs in runs_for_unique.items()},
        "unique_flags": {
            "repeats": sorted({str(r["condition"]) for r in uniq if r["repeats_examples"]}),
            "below_common": sorted(
                {str(r["condition"]) for r in uniq if r["below_common_unique_count"]}
            ),
        },
        "trigger": trig,
        "largest_cells": largest_cells(effects),
        "minimum_detectable": minimum_detectable(spread, effects, seeds_for_mdd),
        "tables": [f"{stem}_{n}.csv" for n in ("effects", "seeds", "unique")],
    }


def persistence_tables(
    results_root: str,
    cells: Sequence[str],
    raw: str,
    sub: str,
    step0_rows: str,
    out_dir: str,
    seed: int = 0,
) -> Record:
    """Stage 2 (1,000 updates): the cells against RAW and the size-matched subsample.

    ``cells`` lists exp_ids (RAW and the subsample included); with the seeds that were run (stage
    2 is partial by budget), the rows are descriptive: intervals carry query sampling only.
    """
    conds = {c: tt.load_condition(results_root, c) for c in cells}
    for runs in conds.values():
        t4.attach_base(runs, step0_rows)
    labels = {"pilot": "t5b", "evaluation": "evaluation", "label": "E-PILOT-ARMS2 stage 2"}
    effects: list[Record] = []
    for ref in (raw, sub):
        for kind in ("dense", "rrf"):
            for level in ("L2", "L3"):
                for reading in tt.READINGS:
                    effects += tt.contrast_rows(
                        conds,
                        ref,
                        kind=kind,
                        level=level,
                        reading=reading,
                        seed=seed,
                        labels={**labels, "reference": ref},
                    )
    uniq = unique_rows(conds)
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.join(out_dir, "t5b")
    write_csv(f"{stem}_effects.csv", effects)
    write_csv(f"{stem}_unique.csv", uniq)
    return {
        "version": T5_TABLES_VERSION,
        "runs": {c: [r.seed for r in rs] for c, rs in conds.items()},
        "tables": [f"{stem}_effects.csv", f"{stem}_unique.csv"],
    }
