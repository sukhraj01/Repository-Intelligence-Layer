"""Unit tests: the dense-score stage with a stand-in encoder (the real model is not loaded)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

from ril.evaluation.e6_dense import (
    EmbeddingStore,
    dense_instance,
    encode_missing,
    text_hash,
)


class FakeModel:
    """Hashes characters into an 8-dimensional unit vector; counts what it encodes."""

    def __init__(self) -> None:
        self.encoded: list[str] = []
        self.tokenizer = lambda docs, add_special_tokens=True: {
            "input_ids": [list(range(len(d) // 4 + 1)) for d in docs]
        }

    def encode(self, docs: list[str], **_: Any) -> np.ndarray[Any, Any]:
        out = np.zeros((len(docs), 8))
        for i, d in enumerate(docs):
            self.encoded.append(d)
            for j, ch in enumerate(d):
                out[i, (ord(ch) + j) % 8] += 1.0
            out[i] /= max(np.linalg.norm(out[i]), 1e-9)
        return out


def test_store_encodes_each_distinct_text_once_and_roundtrips(tmp_path: Path) -> None:
    model = FakeModel()
    store = EmbeddingStore(str(tmp_path / "s.npz"))
    assert encode_missing(model, store, ["alpha", "beta", "alpha"]) == 2
    assert encode_missing(model, store, ["beta", "gamma"]) == 1
    assert sorted(model.encoded) == ["alpha", "beta", "gamma"]
    store.save()
    again = EmbeddingStore(str(tmp_path / "s.npz"))
    assert set(again.vectors) == {text_hash(t) for t in ("alpha", "beta", "gamma")}
    assert np.allclose(again.vectors[text_hash("beta")], store.vectors[text_hash("beta")])
    assert encode_missing(model, again, ["alpha"]) == 0


def test_truncation_flag_follows_the_token_count(tmp_path: Path) -> None:
    model = FakeModel()
    store = EmbeddingStore(str(tmp_path / "s.npz"))
    encode_missing(model, store, ["x" * 10, "y" * 4000])
    assert not store.truncated[text_hash("x" * 10)]
    assert store.truncated[text_hash("y" * 4000)]


def test_dense_instance_scores_follow_unit_order_and_check_the_unit_count(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "a.py").write_text(
        "def one():\n    return 1\n\n\ndef two():\n    return 2\n"
    )
    model = FakeModel()
    store = EmbeddingStore(str(tmp_path / "s.npz"))
    arrays, meta = dense_instance(str(tmp_path), "acme/mini", {"L2": "return one"}, 4, model, store)
    assert arrays["dense_L2"].shape == (4,) and arrays["dense_L2"].dtype == np.float32
    assert meta["units"] == 4 and meta["new_texts_encoded"] >= 1
    with pytest.raises(RuntimeError, match="unit count"):
        dense_instance(str(tmp_path), "acme/mini", {"L2": "q"}, 99, model, store)
