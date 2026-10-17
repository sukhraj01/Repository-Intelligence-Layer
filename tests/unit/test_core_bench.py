"""Folder loading and the two readings of the benchmark protocol (docs/06_core_bench.md)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ril.evaluation.core_bench import evaluate_folder, rank_positives, read_folder


def _write(
    folder: Path, corpus: list[tuple[str, str]], queries: list[dict], qrels: list[tuple[str, str]]
) -> None:
    folder.mkdir(parents=True)
    (folder / "corpus.jsonl").write_text(
        "\n".join(json.dumps({"_id": i, "text": t}) for i, t in corpus) + "\n", encoding="utf-8"
    )
    (folder / "queries.jsonl").write_text(
        "\n".join(json.dumps(q) for q in queries) + "\n", encoding="utf-8"
    )
    (folder / "qrels.jsonl").write_text(
        "\n".join(json.dumps({"query_id": q, "corpus_id": c, "score": 1}) for q, c in qrels) + "\n",
        encoding="utf-8",
    )


def test_queries_without_qrels_are_dropped_and_scores_of_zero_are_not_positives(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "f",
        [("c1", "alpha beta"), ("c2", "gamma")],
        [
            {"_id": "q1", "text": "alpha", "filtered_corpus_id": ["c1", "c2"]},
            {"_id": "q2", "text": "x"},
        ],
        [("q1", "c1")],
    )
    with open(tmp_path / "f" / "qrels.jsonl", "a", encoding="utf-8") as h:
        h.write(json.dumps({"query_id": "q1", "corpus_id": "c2", "score": 0}) + "\n")
    folder = read_folder(str(tmp_path / "f"))
    assert [q.query_id for q in folder.queries] == ["q1"] and folder.dropped_queries == 1
    assert folder.qrels == {"q1": {"c1"}}


def test_protocol_truncates_before_the_filter_but_filter_first_does_not() -> None:
    # scores: doc0 9, doc1 8, doc2 7, doc3 6, doc4 5; the query's candidates are docs 3 and 4
    scores = np.array([9.0, 8.0, 7.0, 6.0, 5.0])
    cand = np.array([3, 4], dtype=np.int64)
    r = rank_positives(scores, cand, [3, 4], prefilter_k=4)
    assert r[3]["protocol"] == 1 and r[3]["filter_first"] == 1
    assert r[4]["protocol"] is None and r[4]["filter_first"] == 2  # beyond the first 4 overall
    assert r[4]["folder_rank"] == 5


def test_ties_report_best_and_worst_rank_and_break_by_order() -> None:
    scores = np.array([1.0, 1.0, 1.0, 0.0])
    r = rank_positives(scores, None, [1], prefilter_k=10)[1]
    assert (r["filter_first"], r["lo"], r["hi"]) == (2, 1, 3)


def test_a_positive_outside_its_candidate_list_is_not_ranked() -> None:
    scores = np.array([3.0, 2.0, 1.0])
    r = rank_positives(scores, np.array([0, 1], dtype=np.int64), [2], prefilter_k=10)[2]
    assert r["in_candidates"] is False and r["filter_first"] is None and r["protocol"] is None


def test_evaluate_folder_ranks_the_matching_chunk_first(tmp_path: Path) -> None:
    corpus = [
        ("c1", "database connection pool timeout"),
        ("c2", "render html template"),
        ("c3", "log"),
    ]
    _write(
        tmp_path / "f",
        corpus,
        [
            {
                "_id": "q1",
                "text": "connection pool timeout error",
                "filtered_corpus_id": ["c1", "c2", "c3"],
            }
        ],
        [("q1", "c1")],
    )
    rec = evaluate_folder(read_folder(str(tmp_path / "f")))
    assert rec[0]["positives"]["c1"]["protocol"] == 1
    assert rec[0]["n_candidates"] == 3 and rec[0]["n_positives"] == 1
