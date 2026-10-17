"""Same seed gives identical stub workload outputs; only wall-clock may vary."""

from __future__ import annotations

from ril.bench.latency_harness import load_query_set
from ril.bench.stub_stages import build_stub_registry


def test_stub_outputs_identical_for_same_seed() -> None:
    queries = load_query_set("synthetic-v1")[:5]
    a, b = build_stub_registry(3), build_stub_registry(3)
    for name, stage in a.latency.items():
        for q in queries:
            out_a, out_b = stage.fn(q), b.latency[name].fn(q)
            assert repr(out_a) == repr(out_b), name
    for name, tstage in a.throughput.items():
        assert tstage.fn() == b.throughput[name].fn()


def test_stub_outputs_differ_across_seeds() -> None:
    q = load_query_set("synthetic-v1")[0]
    assert repr(build_stub_registry(1).latency["dense_search"].fn(q)) != repr(
        build_stub_registry(2).latency["dense_search"].fn(q)
    )
