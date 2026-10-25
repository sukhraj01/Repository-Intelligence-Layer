"""Tests for the smoke-pilot tables: per-query rows of the evaluation hook, paired contrasts of
conditions over seeds, seed spread, budget rows and teacher shares."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import numpy as np

from ril.analysis import t2_tables as tt
from ril.analysis.e3_tables import COLUMN, EvalTable
from ril.evaluation.checkpoint_eval import query_rows

QUERIES = [(f"own__repo{r}-{i}", lv) for r in range(3) for i in range(8) for lv in ("L2", "L3")]


def _write_run(root: Path, exp: str, seed: int, shift: float, rng: np.random.Generator) -> None:
    d = root / "rq2" / exp / f"2026-10-25_{exp[-4:]}{seed}"
    os.makedirs(d)
    variant = f"{exp}__{d.name}"
    cols = list(COLUMN)
    with open(d / "query_rows.csv", "w", encoding="utf-8", newline="") as h:
        w = csv.DictWriter(
            h,
            fieldnames=["instance", "level", "repo", "role", "name"]
            + [f"{r}:{m}" for r, m in cols],
        )
        w.writeheader()
        for i, (inst, lv) in enumerate(QUERIES):
            base = 0.2 + 0.01 * (i % 7)
            for name, v in (
                (f"dense:{tt.BASE}", base),
                (f"rrf:{tt.BASE}", base + 0.05),
                ("bm25", base - 0.02),
                (f"dense:{variant}", base + shift + 0.002 * rng.standard_normal()),
                (f"rrf:{variant}", base + 0.05 + shift / 2),
            ):
                row = {
                    "instance": inst,
                    "level": lv,
                    "repo": inst.split("-")[0],
                    "role": "dev",
                    "name": name,
                }
                row.update({f"{r}:{m}": round(v, 6) for r, m in cols})
                w.writerow(row)
    rec = {
        "training": {
            "exp_id": exp,
            "seed": seed,
            "config_hash": f"{exp}{seed}" * 4,
            "arm": {"name": "RAW"},
            "teacher_equals_base": False,
            "budget": {
                "optimizer_updates": 10,
                "batch_size": 4,
                "pool_examples": 40,
                "unique_examples_seen": 40,
                "effective_epochs": 1.0,
                "gpu_hours_train_loop": 0.01,
            },
            "filter": {"examples_kept_share": 1.0},
            "loss_first": {"loss": 2.0},
            "loss_last": {"loss": 1.0},
        },
        "evaluation": {"variant": variant},
    }
    (d / "results.json").write_text(json.dumps(rec))


def test_contrast_recovers_a_planted_effect(tmp_path: Path) -> None:
    rng = np.random.default_rng(0)
    for s in (0, 1):
        _write_run(tmp_path, "t2_raw", s, 0.01, rng)
        _write_run(tmp_path, "t2_filt", s, 0.04, rng)
    spec = {"name": "k", "reference": "t2_raw", "conditions": ["t2_raw", "t2_filt"]}
    out = tt.pilot_tables(str(tmp_path), spec, str(tmp_path / "tables"))
    assert out["runs"] == {"t2_raw": [0, 1], "t2_filt": [0, 1]}
    with open(tmp_path / "tables" / "t2_k_effects.csv", encoding="utf-8") as h:
        rows = list(csv.DictReader(h))
    dense_l2 = [
        r
        for r in rows
        if r["kind"] == "dense" and r["level"] == "L2" and r["reading"] == "units_all_nomod"
    ]
    by = {r["name"]: r for r in dense_l2}
    assert abs(float(by["t2_filt:mean"]["d"]) - 3.0) < 0.2  # planted +3 points over RAW
    assert abs(float(by["t2_raw:mean"]["d"]) - 1.0) < 0.2  # RAW against the base encoder
    assert by["t2_filt:s1"]["ref"] == "t2_raw:s1" and by["t2_raw:s1"]["ref"] == "t2_raw:s0"
    assert float(by["t2_filt:mean"]["d_q_lo"]) <= 3.0 <= float(by["t2_filt:mean"]["d_q_hi"]) + 0.2
    with open(tmp_path / "tables" / "t2_k_runs.csv", encoding="utf-8") as h:
        assert len(list(csv.DictReader(h))) == 4


def test_seed_spread_and_query_rows() -> None:
    keys = [f"dense|{tt.BASE}", "dense|v"]
    rows = [{"instance": f"i{j}", "level": "L2", "repo": "a/b", "role": "dev"} for j in range(3)]
    metrics = np.full((3, 2, len(COLUMN)), np.nan)
    metrics[:, 0, :] = 0.5
    metrics[:2, 1, :] = 0.25
    tab = EvalTable(
        keys, {k: i for i, k in enumerate(keys)}, rows, metrics, [], np.zeros((3, 0, 1))
    )
    out = query_rows(tab, [("dense:v", "dense|v", None)], ["dev"])
    assert len(out) == 3 and out[0]["units_all_nomod:ndcg10"] == 0.25
    assert out[2]["units_all_nomod:ndcg10"] == ""  # no gold under that reading
    assert query_rows(tab, [("dense:v", "dense|v", None)], ["test"]) == []


def test_teacher_rows_shares_and_agreement(tmp_path: Path) -> None:
    from ril.training import pool_ranks as pr

    p = str(tmp_path / "r.jsonl")
    for i in range(6):
        for t, mult in (("a", 1), ("b", 3)):
            pr.append_jsonl(
                p,
                {
                    "dir": f"own__repo-{i}",
                    "teacher": t,
                    "functions": 50,
                    "ranks": [
                        {
                            "positive": f"f{j}",
                            "rank": (1 + i + j) * mult,
                            "rank_all": (1 + i + j) * mult,
                            "ties": 0,
                        }
                        for j in range(2)
                    ],
                },
            )
    shares, agree = tt.teacher_rows([p], ["a", "b"], [5], 200, 0)
    by = {(s["teacher"], s["k"]): s for s in shares}
    assert by[("a", 5)]["positives"] == 12
    assert by[("a+b", 5)]["positives_inside_share"] <= by[("b", 5)]["positives_inside_share"]
    assert any(r["measure"] == "spearman_rank" and r["value"] == 1.0 for r in agree)
