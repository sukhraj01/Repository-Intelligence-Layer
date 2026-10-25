"""Tests for the training pool reader: selection, streaming, feature table, cache."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from ril.config.paths import repo_root
from ril.training import pool_ranks as pr
from ril.training.pool_rank_jobs import POOL_PREFIX
from ril.training.pool_reader import (
    PoolExample,
    ReaderStats,
    load_feature_table,
    read_cache,
    read_pool,
    select_instances,
    write_cache,
)
from tests.unit._training_fixtures import fake_archive, synthetic_examples, write_feature_table


def test_stream_round_trips_examples_from_a_fake_archive() -> None:
    exs = synthetic_examples(repos=2, prs=3)
    listing, fetch = fake_archive(exs)
    members = {k: dict(v) for k, v in pr.group_members(listing["members"], POOL_PREFIX).items()}
    names = select_instances(members, is_held_out=lambda r: False)
    got = {e.instance_id: e for e in read_pool("u", members, names, fetch=fetch, ahead=2)}
    assert set(got) == {e.instance_id for e in exs}
    for e in exs:
        g = got[e.instance_id]
        assert g.repo == e.repo and g.pr == e.pr and g.query == e.query
        assert set(g.positive_ids) == set(e.positive_ids)
        assert set(g.candidate_ids) == set(e.candidate_ids)
        # the stored id line is stripped (text form 'code')
        assert dict(zip(g.positive_ids, g.positive_texts, strict=True)) == dict(
            zip(e.positive_ids, e.positive_texts, strict=True)
        )


def test_selection_drops_held_out_and_uncovered_and_counts(tmp_path: Path) -> None:
    exs = synthetic_examples(repos=3, prs=2)
    table_path = str(tmp_path / "t.csv")
    write_feature_table(table_path, [e for e in exs if e.instance_id != "own__repo1-100"])
    table = load_feature_table(table_path)
    st = ReaderStats()
    names = select_instances(
        [e.instance_id for e in exs], is_held_out=lambda r: r == "own/repo0", table=table, stats=st
    )
    assert st.listed == 6 and st.held_out_dropped == 2 and st.not_in_table_dropped == 1
    assert st.selected == 3 and "own__repo1-101" in names and "own__repo0-100" not in names
    with pytest.raises(ValueError):
        select_instances(["no-pr-number"], is_held_out=lambda r: False)


def test_reader_skips_instances_whose_positives_lack_rows(tmp_path: Path) -> None:
    exs = synthetic_examples(repos=1, prs=2)
    other = synthetic_examples(repos=1, prs=2, seed=9)  # same instance ids, other positives
    table_path = str(tmp_path / "t.csv")
    write_feature_table(table_path, [exs[0], other[1]])
    table = load_feature_table(table_path)
    listing, fetch = fake_archive(exs)
    members = {k: dict(v) for k, v in pr.group_members(listing["members"], POOL_PREFIX).items()}
    st = ReaderStats()
    got = list(read_pool("u", members, sorted(members), fetch=fetch, table=table, stats=st))
    assert [g.instance_id for g in got] == [exs[0].instance_id]
    assert st.positives_not_in_table == 1 and st.yielded == 1


def test_feature_table_key_and_id_forms_agree(tmp_path: Path) -> None:
    exs = synthetic_examples(repos=1, prs=3)
    a, b = str(tmp_path / "a.csv"), str(tmp_path / "b.csv")
    write_feature_table(a, exs, ("bm25", "x"))
    write_feature_table(b, exs, ("bm25", "x"), ids=True)
    ta, tb = load_feature_table(a), load_feature_table(b)
    assert ta.teachers == ("bm25", "x") == tb.teachers
    for e in exs:
        for p in e.positive_ids:
            assert ta.rank(e.instance_id, p, "bm25") == tb.rank(e.instance_id, p, "bm25") >= 1
    assert ta.rank("nope", "x", "bm25") is None


def test_tracked_x3_feature_table_loads() -> None:
    path = os.path.join(repo_root(), "results", "tables", "x3_pool_ranks_features.csv")
    t = load_feature_table(path)
    assert len(t.instances()) == 160 and len(t.ranks) == 1522
    assert {"swerankembed-small", "coderankembed", "bm25"} <= set(t.teachers)


def test_cache_round_trip_and_example_checks(tmp_path: Path) -> None:
    exs = synthetic_examples(repos=1, prs=2)
    p = str(tmp_path / "c" / "pool.jsonl.gz")
    assert write_cache(p, exs) == 2
    assert read_cache(p) == exs
    e = exs[0]
    with pytest.raises(ValueError):
        PoolExample(e.instance_id, e.repo, e.pr, e.query, (), (), (), ())
    with pytest.raises(ValueError):
        PoolExample(e.instance_id, e.repo, e.pr, e.query, ("a",), ("t",), ("a",), ("t",))
