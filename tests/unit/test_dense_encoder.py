"""Tests for the dense encoder wrapper and the flat exact index (provisional: ADR-006)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from ril.retrieval.dense_encoder import (
    ENCODERS,
    PROVISIONAL,
    DenseEncoder,
    EncoderSpec,
    FlatIndex,
    normalise_rows,
)


class FakeTokenizer:
    def __call__(self, texts: list[str], **kwargs: Any) -> dict[str, list[list[int]]]:
        return {"input_ids": [[0] + [1] * len(t.split()) + [2] for t in texts]}


class FakeBackend:
    """Deterministic bag-of-characters embedding; records what it was asked to encode."""

    def __init__(self) -> None:
        self.max_seq_length = 0
        self.tokenizer = FakeTokenizer()
        self.seen: list[str] = []

    def encode(self, sentences: list[str], **kwargs: Any) -> Any:
        self.seen += sentences
        out = np.zeros((len(sentences), 8), dtype=np.float32)
        for i, s in enumerate(sentences):
            for ch in s:
                out[i, ord(ch) % 8] += 1.0
        return out


def test_specs_are_provisional_and_query_side_only() -> None:
    assert PROVISIONAL == "provisional: ADR-006"
    qwen = ENCODERS["qwen3-embedding-0.6b"]
    assert qwen.query_text("bug").startswith("Instruct: ") and qwen.query_text("bug").endswith(
        "Query:bug"
    )
    cre = ENCODERS["coderankembed"]
    assert cre.trust_remote_code and cre.query_text("x").endswith(": x")
    assert cre.with_max_tokens(1024).max_tokens == 1024 and cre.max_tokens == 512


def test_spec_validation() -> None:
    with pytest.raises(ValueError):
        EncoderSpec("x", "m", "no placeholder")
    with pytest.raises(ValueError):
        EncoderSpec("x", "m", "{query}", max_tokens=2)


def test_encoder_applies_template_to_queries_only_and_sets_cut() -> None:
    backend = FakeBackend()
    enc = DenseEncoder(ENCODERS["coderankembed"].with_max_tokens(1024), backend)
    assert backend.max_seq_length == 1024
    docs = enc.encode_documents(["def f(): pass", "class A: pass"])
    q = enc.encode_query("crash in f")
    assert backend.seen[:2] == ["def f(): pass", "class A: pass"]
    assert backend.seen[2] == ENCODERS["coderankembed"].query_text("crash in f")
    assert docs.shape == (2, 8) and q.shape == (8,)
    assert np.allclose(np.linalg.norm(docs, axis=1), 1.0)
    assert enc.token_lengths(["a b c"]) == [5]


def test_encoder_is_deterministic() -> None:
    a = DenseEncoder(ENCODERS["coderankembed"], FakeBackend()).encode_documents(["x y", "z"])
    b = DenseEncoder(ENCODERS["coderankembed"], FakeBackend()).encode_documents(["x y", "z"])
    assert np.array_equal(a, b)


def test_normalise_rows_keeps_zero_rows() -> None:
    out = normalise_rows([[3.0, 4.0], [0.0, 0.0]])
    assert np.allclose(out[0], [0.6, 0.8]) and np.all(out[1] == 0)


def test_flat_index_matches_brute_force() -> None:
    rng = np.random.default_rng(0)
    mat = rng.normal(size=(500, 16))
    q = rng.normal(size=16)
    index = FlatIndex(mat)
    idx, sc = index.search(q, 20)
    ref = normalise_rows(mat) @ q.astype(np.float32)
    assert list(idx) == list(np.argsort(-ref, kind="stable")[:20])
    assert np.allclose(sc, ref[idx])
    assert index.size == 500 and index.dim == 16


def test_flat_index_ties_by_lower_index_and_k_bounds() -> None:
    mat = np.asarray([[1.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 0.0]])
    index = FlatIndex(mat)
    idx, _ = index.search([1.0, 0.0], 2)
    assert list(idx) == [0, 2]
    idx_all, _ = index.search([1.0, 0.0], 99)
    assert list(idx_all) == [0, 2, 3, 1]
    assert len(index.search([1.0, 0.0], 0)[0]) == 0
    with pytest.raises(ValueError):
        index.scores([1.0, 0.0, 0.0])
