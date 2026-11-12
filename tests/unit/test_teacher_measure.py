"""Teacher-cost measurement: counts, sampling, projection and the D125 rule (no torch)."""

from __future__ import annotations

import numpy as np
import pytest

from ril.training import teacher_measure as tm
from tests.unit._training_fixtures import synthetic_examples


class _Enc:
    def __init__(self) -> None:
        self.docs = 0

    def encode_query(self, q: str) -> list[float]:
        return [1.0, 0.0]

    def encode_documents(self, texts: list[str], batch_size: int) -> np.ndarray:
        self.docs += len(texts)
        return np.array([[float(len(t) % 3), 1.0] for t in texts])


def test_count_store_dedups_per_repository() -> None:
    exs = synthetic_examples(repos=2, prs=3)
    c = tm.count_store(exs)
    assert c.directories == len(exs) and c.repositories == 2
    assert c.distinct_texts <= c.function_rows


def test_sample_is_seeded_and_bounded() -> None:
    exs = synthetic_examples(repos=2, prs=3)
    a = tm.sample_examples(exs, 4, seed=1)
    assert [e.instance_id for e in a] == [e.instance_id for e in tm.sample_examples(exs, 4, seed=1)]
    assert len({e.instance_id for e in a}) == 4
    with pytest.raises(ValueError):
        tm.sample_examples(exs, len(exs) + 1, seed=0)


def test_projection_and_rule() -> None:
    s = tm.StoreCounts(100, 10, 100, 1000, 500)
    f = tm.StoreCounts(1000, 50, 1000, 20000, 10000)
    out = tm.project(110.0, s, f, query_seconds=10.0)
    assert out["dedup_gpu_hours"] == pytest.approx((100.0 / 500 * 10000 + 0.1 * 1000) / 3600)
    assert out["per_directory_gpu_hours"] == pytest.approx(1.1 * 1000 / 3600)
    assert tm.rule(6.0) and not tm.rule(6.01)


def test_measure_encodes_sample_once_per_distinct_text() -> None:
    exs = synthetic_examples(repos=2, prs=3)
    sample = tm.sample_examples(exs, 3, seed=0)
    enc = _Enc()
    out = tm.measure(exs, sample, enc, batch_size=8, warmup_texts=2)
    assert out["cache_misses"] + out["cache_hits"] == out["sample"]["function_rows"]
    assert out["projection"]["dedup_gpu_hours"] >= 0
