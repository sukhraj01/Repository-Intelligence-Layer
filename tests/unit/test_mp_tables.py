"""Plumbing test of the mined-set pilot tables (E-MINED-PILOT), on stored Wave 6 runs as stand-ins.

The three mined cells are linked to three stored cells of the matched-pool arms pilot, so the
numbers mean nothing here; the test checks that the tables are built, deterministic and carry the
rows the entry reads.
"""

from __future__ import annotations

import csv
import glob
import os

from ril.analysis import mp_tables as mp

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "results", "rq2")
STAND_IN = {
    mp.MINED_RAW: "t5a_raw",
    mp.MINED_FILTER: "t5a_filter_bm25",
    mp.MINED_SUB: "t5a_sub_d0",
    mp.POOL_RAW: "t5a_raw",
}
STEP0 = sorted(glob.glob(os.path.join(ROOT, "t3_curve_raw", "*", "step_00000", "query_rows.csv")))


def test_tables_are_built_with_the_rows_the_entry_reads(tmp_path) -> None:
    assert STEP0, "the stored learning-curve rows are tracked in results/rq2"
    root = tmp_path / "res"
    (root / "rq2").mkdir(parents=True)
    for cell, src in STAND_IN.items():
        os.symlink(os.path.abspath(os.path.join(ROOT, src)), root / "rq2" / cell)
    out = str(tmp_path / "out")
    effects, spread, uniq = mp.effect_tables(str(root), STEP0[0], out)
    assert {r["condition"] for r in uniq} == set(STAND_IN)
    names = {(r["reference"], r["name"]) for r in effects}
    assert (mp.POOL_RAW, f"{mp.MINED_RAW}:mean") in names
    assert (mp.MINED_RAW, f"{mp.MINED_FILTER}:mean") in names
    assert (mp.MINED_SUB, f"{mp.MINED_FILTER}:mean") in names
    assert spread and os.path.exists(os.path.join(out, "mp_effects.csv"))
    rows = mp.minimum_detectable_rows(str(root / "rq2"), out, draws=25)
    assert {(r["level"], r["variant"]) for r in rows} == {
        (lv, v) for lv in ("L2", "L3") for v in ("with_repo_term", "query_level")
    }
    assert all(r["mdd_points"] > 0 for r in rows)
    again = mp.minimum_detectable_rows(str(root / "rq2"), out, draws=25)
    assert again == rows
    with open(os.path.join(out, "mp_mdd.csv"), encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == len(rows)
