"""Tables of the noise dose-response pilot (E-PILOT-NOISE; exploratory, not an RQ table).

Builds on ``ril.analysis.t2_tables`` and ``ril.analysis.t5_tables`` (percentage points, paired
queries, bootstrap draws shared by the columns of a table; L2 intervals clustered over the
repositories, L3 intervals over queries). What is new here is the pre-registered reading of D47,
evaluated literally from the effect rows and written out:

* (i) noise sanity: RAW at rate r against RAW on the clean pool (the E-PILOT-ARMS2 RAW cells,
  reused as the r = 0 anchor), both levels;
* (ii) ORACLE-CLEAN against RAW at r, and the share of RAW's loss it recovers;
* (iii) each method against RAW at r: "works" when the interval excludes 0 in the positive direction
  at both levels; its difference as a fraction of ORACLE-CLEAN's;
* (iv) FILTER against the size-matched subsample (RAW on as many random pairs as ORACLE-CLEAN has).

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import math
import os
from collections.abc import Mapping, Sequence
from typing import Any

from ril.analysis import t2_tables as tt
from ril.analysis import t4_tables as t4
from ril.analysis.t5_tables import Z_POWER, _effect, unique_rows
from ril.analysis.x2_tables import write_csv

Record = dict[str, Any]
N1_TABLES_VERSION = "n1-tables/v1"
CELLS = ("raw", "filter_bm25", "filter_srs", "weight_srs", "oracle", "sub")
METHODS = ("filter_bm25", "filter_srs", "weight_srs")
ANCHOR = "t5a_raw"
"""The r = 0 anchor: the E-PILOT-ARMS2 RAW cells, reused (not rerun)."""


def cond(prefix: str, rate: int, cell: str) -> str:
    """Condition name of a cell at noise rate ``rate`` percent (``n1_r40_oracle``)."""
    return f"{prefix}_r{rate}_{cell}"


def interval(e: Mapping[str, Any]) -> tuple[float, float, str]:
    """The interval a row is judged by: clustered over repositories from three up, else queries."""
    if int(e["repos"]) >= 3:
        return float(e["d_c_lo"]), float(e["d_c_hi"]), "repository-clustered"
    return float(e["d_q_lo"]), float(e["d_q_hi"]), "query-level"


def _level(effects: Sequence[Record], c: str, ref: str, level: str) -> Record | None:
    e = _effect(effects, c, ref, level, tt.READINGS[0])
    if e is None:
        return None
    lo, hi, kind = interval(e)
    return {
        "d": float(e["d"]),
        "lo": lo,
        "hi": hi,
        "interval": kind,
        "positive": lo > 0,
        "negative": hi < 0,
    }


def _ratio(num: Record | None, den: Record | None, negate_den: bool = False) -> float | None:
    """``num.d / den.d`` (``den`` negated for a loss); None unless the denominator is positive."""
    if num is None or den is None:
        return None
    d = -den["d"] if negate_den else den["d"]
    return float(num["d"]) / d if d > 0 else None


def rate_effects(
    conds: Mapping[str, Sequence[tt.Run]], refs: Sequence[str], seed: int, label: str
) -> tuple[list[Record], list[Record]]:
    """Effect rows against each reference (dense and RRF, both readings) and the seed spread."""
    effects: list[Record] = []
    spread: list[Record] = []
    labels = {"pilot": "n1", "evaluation": "evaluation", "label": label}
    for ref in refs:
        if not conds.get(ref):
            continue
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
    for kind in ("dense", "rrf"):
        for level in ("L2", "L3"):
            for reading in tt.READINGS:
                spread += tt.seed_spread(conds, kind=kind, level=level, reading=reading)
    return effects, spread


def reading_d47(
    effects: Sequence[Record],
    prefix: str,
    rates: Sequence[int],
    anchor: str = ANCHOR,
    methods: Sequence[str] = METHODS,
) -> Record:
    """The pre-registered reading, per rate; every statement carries its numbers."""
    out: dict[str, Any] = {"reading": tt.READINGS[0], "rates": {}}
    for rate in rates:
        raw, orc, sub = (cond(prefix, rate, c) for c in ("raw", "oracle", "sub"))
        r: Record = {}
        # (i) RAW degrades against the clean anchor
        deg = {lv: _level(effects, raw, anchor, lv) for lv in ("L2", "L3")}
        r["i_raw_vs_clean"] = deg
        r["i_degrades"] = all(v is not None and v["negative"] for v in deg.values())
        # (ii) ORACLE-CLEAN against RAW, as a share of the loss
        rec = {lv: _level(effects, orc, raw, lv) for lv in ("L2", "L3")}
        r["ii_oracle_vs_raw"] = rec
        r["ii_oracle_recovers"] = all(v is not None and v["positive"] for v in rec.values())
        r["ii_share_of_loss_recovered"] = {
            lv: _ratio(rec[lv], deg[lv], negate_den=True) for lv in ("L2", "L3")
        }
        # (iii) methods against RAW, as a share of the oracle's recovery; (iv) against the subsample
        per_method: dict[str, Record] = {}
        for m in methods:
            c = cond(prefix, rate, m)
            vs_raw = {lv: _level(effects, c, raw, lv) for lv in ("L2", "L3")}
            vs_sub = {lv: _level(effects, c, sub, lv) for lv in ("L2", "L3")}
            share = {lv: _ratio(vs_raw[lv], rec[lv]) for lv in ("L2", "L3")}
            per_method[m] = {
                "vs_raw": vs_raw,
                "vs_subsample": vs_sub,
                "share_of_oracle_recovery": share,
                "works": all(v is not None and v["positive"] for v in vs_raw.values()),
                "beats_subsample": all(v is not None and v["positive"] for v in vs_sub.values()),
            }
        r["iii_methods"] = per_method
        r["subsample_vs_raw"] = {lv: _level(effects, sub, raw, lv) for lv in ("L2", "L3")}
        out["rates"][str(rate)] = r
    return out


def minimum_detectable(
    spread: Sequence[Record],
    effects: Sequence[Record],
    prefix: str,
    rate: int,
    seeds: int = 2,
    cells: Sequence[str] = CELLS,
    methods: Sequence[str] = METHODS,
) -> list[Record]:
    """Smallest difference between two cells detectable at 5% and 80% power, from observed variance.

    As ``t5_tables.minimum_detectable``: the larger of the seed-noise bound (pooled SD of the
    rate's cells' per-seed means) and the query-sampling bound (mean half-width of the methods'
    intervals against RAW at the rate). Cells of the rate only (the anchor has two seeds).
    """
    reading = tt.READINGS[0]
    raw = cond(prefix, rate, "raw")
    mine = {cond(prefix, rate, c) for c in cells}
    out: list[Record] = []
    for level in ("L2", "L3"):
        ss, df = 0.0, 0
        for s in spread:
            if (
                s["condition"] in mine
                and s["level"] == level
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
        for m in methods:
            e = _effect(effects, cond(prefix, rate, m), raw, level, reading)
            if e is not None:
                lo, hi, _ = interval(e)
                halves.append((hi - lo) / 2)
        q_half = sum(halves) / len(halves) if halves else float("nan")
        seed_mdd = Z_POWER * sd * math.sqrt(2 / seeds) if df else float("nan")
        query_mdd = Z_POWER / 1.959964 * q_half if halves else float("nan")
        both = [x for x in (seed_mdd, query_mdd) if x == x]
        out.append(
            {
                "rate": rate / 100,
                "level": level,
                "seeds": seeds,
                "pooled_seed_sd": round(sd, 3) if df else None,
                "seed_df": df,
                "seed_mdd": round(seed_mdd, 2) if df else None,
                "query_mdd": round(query_mdd, 2) if halves else None,
                "binding": round(max(both), 2) if both else None,
            }
        )
    return out


def noise_tables(
    results_root: str,
    prefix: str,
    rates: Sequence[int],
    step0_rows: str,
    out_dir: str,
    seed: int = 0,
    anchor: str = ANCHOR,
    cells: Sequence[str] = CELLS,
    methods: Sequence[str] = METHODS,
    stem_name: str = "n1",
    label: str = "E-PILOT-NOISE",
) -> Record:
    """All tables of the pilot; returns the log record (the D47 reading, unique-example table).

    ``cells`` and ``methods`` select the cells a run set contains (E-PILOT-NOISE-SIB drops WEIGHT);
    ``stem_name`` names the output tables; ``label`` is written into the effect rows.
    """
    anchor_runs = tt.load_condition(results_root, anchor)
    effects: list[Record] = []
    spread: list[Record] = []
    unique: list[Record] = []
    mdd: list[Record] = []
    runs_seen: dict[str, list[int]] = {anchor: [r.seed for r in anchor_runs]}
    for rate in rates:
        conds: dict[str, list[tt.Run]] = {anchor: anchor_runs}
        for cell in cells:
            name = cond(prefix, rate, cell)
            conds[name] = tt.load_condition(results_root, name)
            runs_seen[name] = [r.seed for r in conds[name]]
        for runs in conds.values():
            t4.attach_base(runs, step0_rows)
        raw, sub = cond(prefix, rate, "raw"), cond(prefix, rate, "sub")
        e, s = rate_effects(
            {k: v for k, v in conds.items() if v},
            [anchor, raw, sub],
            seed,
            f"{label} r={rate / 100:g}",
        )
        effects += e
        spread += [x for x in s if x["condition"] != anchor or rate == rates[0]]
        mdd += minimum_detectable(s, e, prefix, rate, cells=cells, methods=methods)
        unique += unique_rows({k: v for k, v in conds.items() if v})
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.join(out_dir, stem_name)
    write_csv(f"{stem}_effects.csv", effects)
    write_csv(f"{stem}_seeds.csv", spread)
    write_csv(f"{stem}_unique.csv", unique)
    return {
        "version": N1_TABLES_VERSION,
        "runs": runs_seen,
        "reading": reading_d47(effects, prefix, rates, anchor, methods),
        "minimum_detectable": mdd,
        "tables": [f"{stem}_{n}.csv" for n in ("effects", "seeds", "unique")],
        "cells": list(cells),
    }
