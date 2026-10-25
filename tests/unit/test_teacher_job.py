"""Tests for the one-pass teacher job (K-ranks and mined candidates from the example cache) and the
feature table built from its rows."""

from __future__ import annotations

from pathlib import Path

import pytest

from ril.training import pool_ranks as pr
from ril.training.negatives import bm25_score_fn, mine, read_mined
from ril.training.pool_reader import load_feature_table, write_cache
from ril.training.train_jobs import feature_table_job, teacher_job
from tests.unit._training_fixtures import synthetic_examples

HELD_OUT = "data/held_out/held_out_repos.json"


def test_teacher_pass_equals_separate_ranks_and_mining(tmp_path: Path) -> None:
    exs = synthetic_examples(repos=2, prs=3)
    cache = str(tmp_path / "pool.jsonl.gz")
    write_cache(cache, exs)
    ranks, mined = str(tmp_path / "ranks.jsonl"), str(tmp_path / "mined.jsonl.gz")
    rec = teacher_job(cache, ranks, mined, teacher="bm25", keep=5)
    assert rec["examples"] == len(exs) and rec["scored_now"] == len(exs)
    rows = {r["dir"]: r for r in pr.read_jsonl(ranks)}
    got = read_mined(mined)
    for e in exs:
        s = bm25_score_fn(e, list(e.positive_texts) + list(e.candidate_texts))
        assert rows[e.instance_id]["ranks"] == pr.positive_ranks(e.ids, s, e.positive_ids)
        assert got[e.instance_id] == mine(e, "bm25", bm25_score_fn, 5)
    again = teacher_job(cache, ranks, mined, teacher="bm25", keep=5)  # resumable: nothing to do
    assert again["scored_now"] == 0 and len(pr.read_jsonl(ranks)) == len(exs)


def test_feature_table_needs_every_teacher(tmp_path: Path) -> None:
    exs = synthetic_examples(repos=2, prs=3)
    cache = str(tmp_path / "pool.jsonl.gz")
    write_cache(cache, exs)
    ranks = str(tmp_path / "ranks.jsonl")
    teacher_job(cache, ranks, str(tmp_path / "m.jsonl.gz"), teacher="bm25", keep=3)
    # a second "teacher" that covers only the first example
    first = pr.read_jsonl(ranks)[0]
    other = str(tmp_path / "ranks_other.jsonl")
    pr.append_jsonl(other, {**first, "teacher": "other"})
    out = str(tmp_path / "features.csv")
    rec = feature_table_job(
        [ranks, other],
        out,
        teachers=["bm25", "other"],
        held_out_path=HELD_OUT,
        rename_cache_path=None,
    )
    assert rec["directories_ranked"] == len(exs) and rec["directories_complete"] == 1
    table = load_feature_table(out)
    assert table.teachers == ("bm25", "other") and table.instances() == {first["dir"]}
    ex = next(e for e in exs if e.instance_id == first["dir"])
    assert table.covers(ex.instance_id, ex.positive_ids)
    for x in first["ranks"]:
        assert table.rank(ex.instance_id, x["positive"], "bm25") == x["rank"]
    rec_all = feature_table_job(
        [ranks], out, teachers=["bm25"], held_out_path=HELD_OUT, rename_cache_path=None
    )
    assert rec_all["directories_complete"] == len(exs)
    with pytest.raises(FileNotFoundError):
        feature_table_job(
            [ranks], out, teachers=["bm25"], held_out_path="nope.json", rename_cache_path=None
        )
