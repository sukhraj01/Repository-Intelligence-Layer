"""The stage functions of ``ril.bench.fusion_measure`` on a synthetic snapshot."""

from __future__ import annotations

import numpy as np

from ril.bench import fusion_measure as fm
from ril.bench.latency_harness import LATENCY_STAGES, StageRegistry


def _stages(n: int = 60) -> fm.FusionStages:
    rng = np.random.default_rng(0)
    st = object.__new__(fm.FusionStages)
    st.n = n
    st.file_of_unit = np.repeat(np.arange(n // 3), 3).astype(np.int32)
    st.age_days = rng.uniform(0, 400, size=n)
    st.pool = [rng.normal(size=80).astype(np.float32)]
    st.cache = {}
    bm = rng.random(n)
    st.index = type("Idx", (), {"scores": lambda self, toks: bm})()  # type: ignore[assignment]
    return st


def test_resize_is_seeded_and_exact_length() -> None:
    pool = [np.arange(10, dtype=np.float32)]
    a = fm.resize_scores(pool, 25, np.random.default_rng(3))
    b = fm.resize_scores(pool, 25, np.random.default_rng(3))
    assert len(a) == 25 and np.array_equal(a, b)
    assert set(a) <= set(map(float, pool[0]))


def test_stage_outputs_have_the_documented_shape(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    st = _stages()
    monkeypatch.setattr(fm, "tokenize", lambda q: q.split())
    st.prepare(["a b", "c d"], seed=0)
    fused = st.rrf_fusion("a b")
    assert len(fused) == min(fm.TOP_K, st.n) and len(set(map(int, fused))) == len(fused)
    exp = st.same_file_expansion("a b")
    assert len(exp) == min(fm.CAP, st.n - fm.SEEDS) or len(exp) == fm.CAP
    assert not set(exp) & {int(u) for u in st.cache["a b"][3][: fm.SEEDS]}
    rec = st.recency_prior("a b")
    assert len(rec) == min(fm.TOP_K, st.n)


def test_new_stages_are_in_the_taxonomy() -> None:
    reg = StageRegistry()
    for name in ("rrf_fusion", "same_file_expansion", "recency_prior"):
        assert name in LATENCY_STAGES
        reg.register(name, lambda q: q)
