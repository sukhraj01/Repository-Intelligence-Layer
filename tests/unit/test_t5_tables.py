"""Tests for the matched-pool arms pilot tables: pooled subsample draws, the unique-example table
(D42), the stage-2 trigger read literally, the largest cells and the minimum detectable
difference."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any

import numpy as np

from ril.analysis import t2_tables as tt
from ril.analysis import t5_tables as t5
from ril.analysis.e3_tables import COLUMN

QUERIES = [(f"own__repo{r}-{i}", lv) for r in range(4) for i in range(10) for lv in ("L2", "L3")]
FIELDS = ["instance", "level", "repo", "role", "name"] + [f"{r}:{m}" for r, m in COLUMN]


def _write_run(
    root: Path,
    exp: str,
    seed: int,
    shift: float,
    rng: np.random.Generator,
    *,
    arm: str = "RAW",
    pool: int = 100,
    seen: int = 64,
    unique: int = 64,
) -> None:
    d = root / "rq2" / exp / f"2026-10-31_{exp[-4:]}{seed}"
    os.makedirs(d)
    variant = f"{exp}__{d.name}"
    with open(d / "query_rows.csv", "w", encoding="utf-8", newline="") as h:
        w = csv.DictWriter(h, fieldnames=FIELDS)
        w.writeheader()
        for i, (inst, lv) in enumerate(QUERIES):
            base = 0.2 + 0.01 * (i % 7)
            for name, v in (
                (f"dense:{variant}", base + shift + 0.002 * rng.standard_normal()),
                (f"rrf:{variant}", base + 0.05 + shift / 2),
            ):
                row = {"instance": inst, "level": lv, "repo": inst.split("-")[0], "role": "dev"}
                row["name"] = name
                row.update({f"{r}:{m}": round(v, 6) for r, m in COLUMN})
                w.writerow(row)
    rec = {
        "training": {
            "exp_id": exp,
            "seed": seed,
            "config_hash": f"{exp}{seed}" * 4,
            "arm": {"name": arm},
            "teacher_equals_base": False,
            "budget": {
                "optimizer_updates": 2,
                "batch_size": 32,
                "pool_examples": pool,
                "examples_seen": seen,
                "unique_examples_seen": unique,
                "effective_epochs": seen / pool,
                "gpu_hours_train_loop": 0.01,
            },
            "filter": {"examples_in": 120, "examples_out": pool, "examples_kept_share": 0.8},
            "loss_first": {"loss": 2.0},
            "loss_last": {"loss": 1.0},
        },
        "evaluation": {"variant": variant},
    }
    (d / "results.json").write_text(json.dumps(rec))


def _step0(path: Path) -> str:
    with open(path, "w", encoding="utf-8", newline="") as h:
        w = csv.DictWriter(h, fieldnames=FIELDS)
        w.writeheader()
        for i, (inst, lv) in enumerate(QUERIES):
            base = 0.2 + 0.01 * (i % 7)
            for kind, v in (("dense", base), ("rrf", base + 0.05)):
                row = {"instance": inst, "level": lv, "repo": inst.split("-")[0], "role": "dev"}
                row["name"] = f"{kind}:step0"
                row.update({f"{r}:{m}": round(v, 6) for r, m in COLUMN})
                w.writerow(row)
    return str(path)


def _build(root: Path, shifts: dict[str, float]) -> None:
    rng = np.random.default_rng(1)
    for s in (0, 1, 2):
        _write_run(root, "t5a_raw", s, shifts["raw"], rng)
        _write_run(root, "t5a_sub_d0", s, shifts["sub"], rng, arm="RAW_SUBSAMPLE", pool=90)
        _write_run(root, "t5a_sub_d1", s, shifts["sub"], rng, arm="RAW_SUBSAMPLE", pool=90)
        for c in ("filter_bm25", "filter_srs", "filter_cre", "weight_cre", "curr_cre"):
            _write_run(
                root, f"t5a_{c}", s, shifts.get(c, shifts["raw"]), rng, arm="FILTER", pool=100
            )


def test_pooled_draws_average_the_draws_per_seed(tmp_path: Path) -> None:
    rng = np.random.default_rng(0)
    for s in (0, 1):
        _write_run(tmp_path, "t5a_sub_d0", s, 0.00, rng)
        _write_run(tmp_path, "t5a_sub_d1", s, 0.04, rng)
    d0 = tt.load_condition(str(tmp_path), "t5a_sub_d0")
    d1 = tt.load_condition(str(tmp_path), "t5a_sub_d1")
    pooled = t5.pooled_draws([d0, d1])
    assert [r.seed for r in pooled] == [0, 1] and pooled[0].variant == t5.SUB
    q = QUERIES[0]
    key = "units_all_nomod:ndcg10"
    got = pooled[0].values[(q[0], q[1], f"dense:{t5.SUB}", key)]
    want = (
        d0[0].values[(q[0], q[1], f"dense:{d0[0].variant}", key)]
        + d1[0].values[(q[0], q[1], f"dense:{d1[0].variant}", key)]
    ) / 2
    assert abs(got - want) < 1e-9
    one = t5.pooled_draws([d0])
    assert (
        one[1].values[(q[0], q[1], f"dense:{t5.SUB}", key)]
        == d0[1].values[(q[0], q[1], f"dense:{d0[1].variant}", key)]
    )


def test_unique_rows_flag_repeats_and_shortfalls(tmp_path: Path) -> None:
    rng = np.random.default_rng(0)
    _write_run(tmp_path, "t5a_raw", 0, 0.0, rng, pool=100, seen=64, unique=64)
    _write_run(tmp_path, "t5a_filter_bm25", 0, 0.0, rng, pool=40, seen=64, unique=40)
    conds = {c: tt.load_condition(str(tmp_path), c) for c in ("t5a_raw", "t5a_filter_bm25")}
    rows = {r["condition"]: r for r in t5.unique_rows(conds)}
    assert rows["t5a_raw"]["repeats_examples"] is False
    assert rows["t5a_raw"]["below_common_unique_count"] is False
    assert rows["t5a_filter_bm25"]["repeats_examples"] is True
    assert rows["t5a_filter_bm25"]["below_common_unique_count"] is True
    assert rows["t5a_filter_bm25"]["pool_before_arm"] == 120


def test_matched_tables_null_world_does_not_trigger(tmp_path: Path) -> None:
    _build(tmp_path, {"raw": 0.10, "sub": 0.10})
    out = t5.matched_tables(
        str(tmp_path),
        list(
            (
                "t5a_raw",
                "t5a_filter_bm25",
                "t5a_filter_srs",
                "t5a_filter_cre",
                "t5a_weight_cre",
                "t5a_curr_cre",
            )
        ),
        ["t5a_sub_d0", "t5a_sub_d1"],
        _step0(tmp_path / "step0.csv"),
        str(tmp_path / "tables"),
    )
    assert out["runs"]["t5a_raw"] == [0, 1, 2]
    assert out["unique_flags"] == {"repeats": [], "below_common": []}
    trig = out["trigger"]
    assert len(trig["cells"]) == 10  # five cells against two references
    assert not trig["ii_raw_gap_above_1"]
    mdd = {r["level"]: r for r in out["minimum_detectable"]}
    assert mdd["L2"]["seed_df"] > 0 and mdd["L2"]["binding"] is not None
    for n in ("effects", "seeds", "unique"):
        assert (tmp_path / "tables" / f"t5a_{n}.csv").exists()


def test_planted_effect_fires_the_literal_trigger_and_picks_cells(tmp_path: Path) -> None:
    _build(
        tmp_path,
        {"raw": 0.10, "sub": 0.10, "filter_cre": 0.14, "curr_cre": 0.07, "filter_bm25": 0.101},
    )
    cells = [
        "t5a_raw",
        "t5a_filter_bm25",
        "t5a_filter_srs",
        "t5a_filter_cre",
        "t5a_weight_cre",
        "t5a_curr_cre",
    ]
    out = t5.matched_tables(
        str(tmp_path),
        cells,
        ["t5a_sub_d0"],
        _step0(tmp_path / "step0.csv"),
        str(tmp_path / "tables"),
    )
    trig = out["trigger"]
    assert trig["i_literal"] is True
    fired = {(h["condition"], h["reference"]) for h in trig["cells"] if h["literal_i"]}
    assert ("t5a_filter_cre", "t5a_raw") in fired and ("t5a_filter_cre", "t5a_sub") in fired
    assert ("t5a_curr_cre", "t5a_raw") in fired
    h = next(
        x
        for x in trig["cells"]
        if x["condition"] == "t5a_filter_cre" and x["reference"] == "t5a_raw"
    )
    assert h["L2"]["d"] > 3.5 and h["L3"]["d"] > 3.5 and h["same_sign"]
    assert [c["condition"] for c in out["largest_cells"]] == ["t5a_filter_cre", "t5a_curr_cre"]


def test_trigger_requires_same_sign_and_reads_the_gap() -> None:
    def eff(cond: str, level: str, d: float, lo: float, hi: float) -> dict[str, Any]:
        return {
            "condition": cond,
            "part": "mean",
            "ref": f"{t5.RAW}:mean",
            "level": level,
            "reading": tt.READINGS[0],
            "kind": "dense",
            "repos": 5 if level == "L2" else 2,
            "d": d,
            "d_c_lo": lo,
            "d_c_hi": hi,
            "d_q_lo": lo,
            "d_q_hi": hi,
        }

    effects = [
        eff("t5a_filter_bm25", "L2", 1.0, 0.5, 1.5),  # excludes 0, positive
        eff("t5a_filter_bm25", "L3", -0.2, -1.0, 0.6),  # includes 0, negative: signs differ
        eff("t5a_filter_srs", "L2", 1.0, 0.5, 1.5),
        eff("t5a_filter_srs", "L3", 0.3, -0.5, 1.1),  # same sign, one interval excludes 0
        eff("t5a_curr_cre", "L2", -1.0, -1.5, -0.5),
        eff("t5a_curr_cre", "L3", -1.0, -1.5, -0.5),  # both exclude 0, same direction
    ]
    spread = [
        {
            "condition": t5.RAW,
            "kind": "dense",
            "reading": tt.READINGS[0],
            "level": "L2",
            "range": 1.2,
            "per_seed": [29.0, 30.2],
            "sd": 0.85,
        },
        {
            "condition": t5.RAW,
            "kind": "dense",
            "reading": tt.READINGS[0],
            "level": "L3",
            "range": 0.4,
            "per_seed": [45.0, 45.4],
            "sd": 0.28,
        },
    ]
    trig = t5.stage2_trigger(effects, spread, references=(t5.RAW,))
    by = {h["condition"]: h for h in trig["cells"]}
    assert by["t5a_filter_bm25"]["literal_i"] is False
    assert by["t5a_filter_srs"]["literal_i"] is True and by["t5a_filter_srs"]["strict_i"] is False
    assert by["t5a_curr_cre"]["strict_i"] is True
    assert trig["i_literal"] and trig["i_strict"] and trig["ii_raw_gap_above_1"]


def test_minimum_detectable_scales_with_seed_sd() -> None:
    spread = [
        {
            "condition": c,
            "kind": "dense",
            "reading": tt.READINGS[0],
            "level": "L2",
            "range": 1.0,
            "per_seed": [1.0, 2.0, 3.0],
            "sd": 1.0,
        }
        for c in ("a", "b")
    ]
    out = t5.minimum_detectable(spread, [], seeds=3)
    l2 = next(r for r in out if r["level"] == "L2")
    assert abs(l2["pooled_seed_sd"] - 1.0) < 1e-9 and l2["seed_df"] == 4
    assert abs(l2["seed_mdd"] - round(t5.Z_POWER * (2 / 3) ** 0.5, 2)) < 1e-9
    l3 = next(r for r in out if r["level"] == "L3")
    assert l3["pooled_seed_sd"] is None and l3["binding"] is None
