"""Tests for the X2 dense pipeline pieces that run without a model."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np

from ril.bench.dense_measure import build_issue_like_queries, scale_matrix
from ril.evaluation.x2_dense import (
    VectorStore,
    append_store,
    encode_store,
    rank_among,
    read_store,
    text_hash,
)
from ril.retrieval.dense_encoder import ENCODERS, DenseEncoder
from tests.unit.test_dense_encoder import FakeBackend


def test_store_dedupes_and_round_trips(tmp_path: Path) -> None:
    path = str(tmp_path / "s" / "a.jsonl")
    seen: set[str] = set()
    assert append_store(path, ["x", "y", "x"], seen) == 2
    assert append_store(path, ["y", "z"], seen) == 1
    got = read_store([path])
    assert set(got.values()) == {"x", "y", "z"} and got[text_hash("z")] == "z"


def test_encode_store_resumes_and_merges(tmp_path: Path) -> None:
    src = str(tmp_path / "t.jsonl")
    append_store(src, [f"text number {i}" * (i % 5 + 1) for i in range(23)], set())
    enc = DenseEncoder(ENCODERS["coderankembed"].with_max_tokens(8), FakeBackend())
    out = str(tmp_path / "enc")
    res = encode_store(enc, [src], "units__r", out, batch_size=4, piece=10)
    assert res["texts"] == 23 and res["encoded_now"] == 23 and res["cut_at_max_tokens"] > 0
    again = encode_store(enc, [src], "units__r", out, batch_size=4, piece=10)
    assert again["reused"]
    # a lost merged file is rebuilt from the pieces without encoding anything again
    os.remove(os.path.join(out, "units__r.npz"))
    third = encode_store(enc, [src], "units__r", out, batch_size=4, piece=10)
    assert third["encoded_now"] == 0
    vs = VectorStore([os.path.join(out, "units__r.npz")])
    texts = read_store([src])
    h = sorted(texts)[3]
    direct = enc.encode_documents([texts[h]])[0]
    assert np.allclose(vs.matrix([h])[0], direct, atol=1e-3)


def test_rank_among_candidates_ties_by_index() -> None:
    scores = np.asarray([0.1, 0.9, 0.5, 0.9, 0.3])
    cand = np.asarray([0, 1, 3, 4])
    assert list(rank_among(scores, cand)) == [4, 1, 2, 3]


def test_issue_like_queries_follow_counts_and_seed() -> None:
    idents: list[Any] = ["make_response", "SessionInterface", "open_resource"]
    a = build_issue_like_queries(idents, [5, 7], 10, seed=3)
    b = build_issue_like_queries(idents, [5, 7], 10, seed=3)
    assert a == b and all(len(q.split()) in (5, 7) for q in a)


def test_scale_matrix_rows_and_seed() -> None:
    v = np.eye(4, dtype=np.float32)
    assert scale_matrix(v, 4, 0).shape == (4, 4)
    m1, m2 = scale_matrix(v, 10, 1), scale_matrix(v, 10, 1)
    assert m1.shape == (10, 4) and np.array_equal(m1, m2)
