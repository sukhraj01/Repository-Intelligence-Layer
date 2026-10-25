"""The whole training path on a CPU tiny model: pool archive -> reader -> filter by the held-out
list and the feature table -> mining -> arm hooks -> training with checkpoints -> resumption ->
result directory -> evaluation hook on X2-shaped development inputs.

Synthetic data only; the tiny model is a plumbing check, not a retriever (no number here is a
result).
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import torch

from ril.evaluation.checkpoint_eval import eval_checkpoint
from ril.training import pool_ranks as pr
from ril.training.encoders import TinyEncoder, load_trained
from ril.training.negatives import bm25_score_fn, mine_all
from ril.training.pool_rank_jobs import POOL_PREFIX
from ril.training.pool_reader import (
    ReaderStats,
    load_feature_table,
    read_pool,
    select_instances,
)
from ril.training.supervision import TableKRank
from ril.training.training import merge_results, train
from tests.unit._training_fixtures import (
    fake_archive,
    synthetic_examples,
    train_config,
    write_feature_table,
    x2_inputs,
)


def _pool(tmp: Path) -> tuple[list, dict]:  # type: ignore[type-arg]
    exs = synthetic_examples(repos=4, prs=5)
    listing, fetch = fake_archive(exs)
    table_path = str(tmp / "features.csv")
    write_feature_table(table_path, exs, ("bm25",))
    table = load_feature_table(table_path)
    members = {k: dict(v) for k, v in pr.group_members(listing["members"], POOL_PREFIX).items()}
    st = ReaderStats()
    names = select_instances(members, is_held_out=lambda r: r == "own/repo3", table=table, stats=st)
    got = list(read_pool("mem://pool", members, names, fetch=fetch, table=table, stats=st))
    assert st.held_out_dropped == 5 and st.yielded == 15 and len(got) == 15
    return got, {"bm25": TableKRank(table, "bm25")}


def test_tiny_model_end_to_end_with_resume_and_evaluation(tmp_path: Path) -> None:
    exs, signals = _pool(tmp_path)
    mined = mine_all(exs, "bm25", bm25_score_fn, keep=8)
    cfg = train_config(
        exp_id="t1_e2e",
        negatives={"name": "teacher_top_m", "m": 6},
        arm={"name": "FILTER", "filter": {"teacher": "bm25", "k": 20, "level": "positive"}},
        budget={"updates": 12},
        checkpoint={"every": 4, "keep": 2},
    )
    common = dict(
        results_root=str(tmp_path / "results"), date="2026-10-25", signals=signals, mined=mined
    )
    # uninterrupted reference run
    ref = train(cfg, exs, work_root=str(tmp_path / "w_ref"), **common)  # type: ignore[arg-type]
    assert ref["finished"] and ref["budget"]["optimizer_updates"] == 12
    # interrupted after 6 updates (checkpoint at 4), then resumed
    part = train(cfg, exs, work_root=str(tmp_path / "w"), stop_after=6, **common)  # type: ignore[arg-type]
    assert not part["finished"] and part["updates_this_process"] == 6
    done = train(cfg, exs, work_root=str(tmp_path / "w"), **common)  # type: ignore[arg-type]
    assert done["finished"] and done["updates_this_process"] == 8  # resumed from update 4
    assert done["plan_sha256"] == ref["plan_sha256"]
    a = torch.load(Path(ref["final_model"]) / "tiny.pt", weights_only=True)
    b = torch.load(Path(done["final_model"]) / "tiny.pt", weights_only=True)
    assert all(torch.equal(a[k], b[k]) for k in a)
    # budget table and result directory
    bud = done["budget"]
    assert bud["unique_examples_seen"] <= bud["pool_examples"] <= 15
    assert bud["effective_epochs"] == bud["examples_seen"] / bud["pool_examples"]
    assert bud["gpu_hours_train_loop"] == 0.0 and done["filter"]["examples_in"] == 15
    rdir = Path(done["result_dir"])
    assert rdir.parent.name == "t1_e2e" and rdir.parent.parent.name == "rq2"
    assert rdir.name.startswith("2026-10-25_") and len(rdir.name) == len("2026-10-25_") + 8
    for f in ("config.yaml", "results.json", "hardware.json"):
        assert (rdir / f).exists()
    assert os.path.exists(tmp_path / "results" / "logs" / f"t1_e2e_{rdir.name}.json")
    assert done["loss_last"]["loss"] < done["loss_first"]["loss"]

    # evaluation hook: the untrained model as baseline, then the checkpoint paired against it
    x2 = x2_inputs(str(tmp_path / "x2"))
    work = str(tmp_path / "evalwork")
    common_eval = dict(
        e1_config=x2["e1"],
        prep_dir=x2["prep"],
        cache_dir=x2["cache"],
        data_root=x2["data_root"],
        work_dir=work,
    )
    base = TinyEncoder(512, 16, 64, seed=cfg["seed"])
    eval_checkpoint(
        base,
        {
            "variant": "tiny_base",
            "roles": ["dev"],
            "rrf_k": 60,
            "batch_size": 8,
            "chunks": True,
            "seed": 0,
        },
        result_dir=str(tmp_path / "base_res"),
        **common_eval,
    )  # type: ignore[arg-type]
    trained = load_trained(done["final_model"], device="cpu")
    ev = eval_checkpoint(
        trained,
        {
            "variant": "t1_e2e",
            "roles": ["dev"],
            "rrf_k": 60,
            "batch_size": 8,
            "chunks": True,
            "seed": 0,
            "baselines": ["tiny_base"],
        },
        result_dir=str(rdir),
        baseline_enc_dirs={"tiny_base": os.path.join(work, "enc", "tiny_base")},
        **common_eval,  # type: ignore[arg-type]
    )
    merge_results(str(rdir), "evaluation", ev)
    assert ev["unit_queries"] == 4 and ev["chunk_queries"] == 4
    with open(rdir / "unit_rows.csv", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    names = {r["name"] for r in rows}
    assert {"bm25", "dense:tiny_base", "dense:t1_e2e", "rrf:t1_e2e"} <= names
    paired = [r for r in rows if r["name"] == "dense:t1_e2e"]
    assert paired and all(r["ref"] == "dense:tiny_base" and r["d"] != "" for r in paired)
    # the synthetic chunks are the units, so both levels must give the same dense value
    with open(rdir / "chunk_rows.csv", encoding="utf-8") as handle:
        crows = list(csv.DictReader(handle))
    for metric in ("ndcg10", "recall100"):
        u = next(r for r in paired if r["metric"] == metric and r["reading"] == "units_all")
        c = next(r for r in crows if r["name"] == "dense:t1_e2e" and r["metric"] == metric)
        assert u["value"] == c["value"]
    with open(rdir / "results.json", encoding="utf-8") as handle:
        res = json.load(handle)
    assert set(res) == {"training", "evaluation"} and res["evaluation"]["headline"]
