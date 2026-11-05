"""Gate N0 arithmetic: separation of injected from clean pairs by a teacher's K-rank."""

from __future__ import annotations

import numpy as np

from ril.analysis import n0_tables as n0
from ril.training import pool_ranks as pr
from tests.unit._training_fixtures import synthetic_examples


def _oracle_scores(examples):  # type: ignore[no-untyped-def]
    """Scores that rank every true positive first: a perfect teacher."""
    store = {}
    for e in examples:
        s = np.zeros(len(e.ids))
        s[: len(e.positive_ids)] = 1.0 + np.arange(len(e.positive_ids))
        store[e.instance_id] = s
    return store


def test_a_perfect_teacher_separates_injected_pairs() -> None:
    ex = synthetic_examples(repos=10, prs=40)
    r = n0.separation(ex, _oracle_scores(ex), "oracle", 0.4, 0, k=1)
    assert r["auc_pair"] == 1.0 and not r["gate_fails"]
    assert r["clean_pairs_dropped"] == 0.0 and r["injected_pairs_dropped"] == 1.0


def test_a_random_teacher_fails_the_gate() -> None:
    ex = synthetic_examples(repos=20, prs=100)
    rng = np.random.default_rng(1)
    store = {e.instance_id: rng.random(len(e.ids)) for e in ex}
    r = n0.separation(ex, store, "random", 0.4, 0, k=5)
    assert 0.4 < r["auc_pair"] < 0.6 and r["gate_fails"]


def test_reproduction_matches_the_published_rank_definition() -> None:
    from ril.training.pool_reader import FeatureTable

    ex = synthetic_examples(repos=2, prs=5)
    rng = np.random.default_rng(2)
    store = {e.instance_id: rng.random(len(e.ids)) for e in ex}
    table = FeatureTable(teachers=("t",))
    for e in ex:
        for row in pr.positive_ranks(e.ids, store[e.instance_id], e.positive_ids):
            table.ranks[(e.instance_id, pr.positive_key(str(row["positive"])))] = {"t": row["rank"]}
    r = n0.reproduction(ex, store, table, "t")
    assert r["identical_share"] == 1.0 and r["positives_compared"] > 0
