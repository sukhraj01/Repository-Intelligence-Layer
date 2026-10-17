"""Unit tests for the latency harness (specs/latency_harness.md acceptance criteria)."""

from __future__ import annotations

import csv
import sys
import types
from pathlib import Path

import pytest

from ril.bench import latency_harness as lh
from ril.bench.stub_stages import build_stub_registry

THRESHOLD = lh.RegressionThreshold(rel_threshold=0.5, abs_floor_ms=0.5)


def _config(**over: object) -> lh.BenchConfig:
    base: dict[str, object] = {
        "seed": 0,
        "query_set": "synthetic-v1",
        "warmup_n": 2,
        "repeats": 2,
        "throughput_repeats": 1,
        "regression": THRESHOLD,
    }
    base.update(over)
    return lh.BenchConfig(**base)  # type: ignore[arg-type]


def _row(stage: str = "bm25", p50: float = 1.0, p95: float = 2.0, **over: object) -> lh.Row:
    row: lh.Row = {c: "x" for c in lh.LATENCY_COLUMNS}
    row.update(
        cpu_model="cpu",
        cpu_cores=8,
        ram_gb=8.0,
        gpu_name="none",
        query_set_id="q1",
        cache_state="warm",
        stage=stage,
        p50_ms=p50,
        p95_ms=p95,
        p99_ms=p95,
        n=10,
        commit="abc",
    )
    row.update(over)  # type: ignore[arg-type]
    return row


def _as_history(rows: list[lh.Row]) -> list[dict[str, str]]:
    return [{k: str(v) for k, v in r.items()} for r in rows]


def test_percentile_nearest_rank_from_raw_samples() -> None:
    samples = [float(i) for i in range(1, 101)]
    assert lh.percentile(samples, 50) == 50.0
    assert lh.percentile(samples, 95) == 95.0
    assert lh.percentile(samples, 99) == 99.0
    # order independent, and the tail is an observed value, not an average
    assert lh.percentile(list(reversed(samples)), 99) == 99.0
    assert lh.percentile([1.0, 1.0, 1.0, 1000.0], 99) == 1000.0


def test_percentile_rejects_empty_and_bad_p() -> None:
    with pytest.raises(ValueError):
        lh.percentile([], 50)
    with pytest.raises(ValueError):
        lh.percentile([1.0], 0)


def test_warmup_calls_are_discarded_and_counted() -> None:
    calls: list[str] = []
    stage = lh.LatencyStage("bm25", calls.append)
    queries = ["a", "b", "c"]
    samples = lh.measure_warm(stage, queries, warmup_n=2, repeats=2)
    assert len(calls) == 6  # every call is made ...
    assert len(samples) == 4  # ... the first 2 are not sampled


def test_warmup_must_leave_samples() -> None:
    stage = lh.LatencyStage("bm25", lambda q: None)
    with pytest.raises(ValueError):
        lh.measure_warm(stage, ["a"], warmup_n=1, repeats=1)


def test_cold_resets_before_every_call() -> None:
    events: list[str] = []
    stage = lh.LatencyStage("bm25", lambda q: events.append("call"), lambda: events.append("reset"))
    lh.measure_cold(stage, ["a", "b"])
    assert events == ["reset", "call", "reset", "call"]


def test_cuda_synchronize_brackets_each_timed_call(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    fake = types.SimpleNamespace(synchronize=lambda: events.append("sync"))
    monkeypatch.setattr(lh, "_cuda_module", lambda: fake)
    lh.time_call_ms(lambda q: events.append("work"), "q")
    assert events == ["sync", "work", "sync"]


def test_cpu_only_box_runs_without_torch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "torch", None)  # import raises ImportError
    assert lh._cuda_module() is None
    assert lh.time_call_ms(lambda q: None, "q") >= 0.0
    assert lh._gpu_info()[0] == "none"


def test_registry_rejects_unknown_stage_names() -> None:
    registry = lh.StageRegistry()
    with pytest.raises(ValueError):
        registry.register("bm_25", lambda q: None)
    with pytest.raises(ValueError):
        registry.register_throughput("bm25", lambda: 1)


def test_graph_stage_names_registered_in_taxonomy() -> None:
    for name in ("graph_expand_1hop", "graph_expand_2hop"):
        assert name in lh.LATENCY_STAGES
    for name in ("parse", "graph_build"):
        assert name in lh.THROUGHPUT_STAGES


def test_query_set_is_versioned_and_nonempty() -> None:
    assert len(lh.load_query_set("synthetic-v1")) == 32
    with pytest.raises(FileNotFoundError):
        lh.load_query_set("no-such-set")


def test_run_produces_contract_rows_cold_and_warm() -> None:
    registry = build_stub_registry(0)
    queries = lh.load_query_set("synthetic-v1")[:6]
    env = lh.capture_environment("hash")
    rows = lh.run_latency(registry, _config(), queries, env)
    assert {r["cache_state"] for r in rows} == {"cold", "warm"}
    assert {r["stage"] for r in rows} == set(lh.LATENCY_STAGES)
    for r in rows:
        assert set(r) >= set(lh.LATENCY_COLUMNS)
        assert 0 < float(r["p50_ms"]) <= float(r["p95_ms"]) <= float(r["p99_ms"])
        assert r["warmup_n"] == (0 if r["cache_state"] == "cold" else 2)
    warm = next(r for r in rows if r["stage"] == "bm25" and r["cache_state"] == "warm")
    assert warm["n"] == 6 * 2 - 2
    tput = lh.run_throughput(registry, _config(), env)
    assert {r["stage"] for r in tput} == set(lh.THROUGHPUT_STAGES)
    assert all(int(r["units"]) > 0 and float(r["units_per_s"]) > 0 for r in tput)


def test_hardware_spec_captured() -> None:
    env = lh.capture_environment("h")
    assert env["cpu_model"] and int(env["cpu_cores"]) >= 1 and float(env["ram_gb"]) > 0
    assert env["gpu_name"] and env["python"].startswith("3.")  # type: ignore[union-attr]
    assert set(env) == set(lh.ENV_COLUMNS)


def test_append_only_two_runs_two_rows_and_old_rows_untouched(tmp_path: Path) -> None:
    path = tmp_path / "latency_log.csv"
    lh.append_rows(path, lh.LATENCY_COLUMNS, [_row("bm25"), _row("assemble")])
    first = path.read_bytes()
    lh.append_rows(path, lh.LATENCY_COLUMNS, [_row("bm25"), _row("assemble")])
    assert path.read_bytes().startswith(first)  # prefix byte-identical: nothing rewritten
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 4 and sum(r["stage"] == "bm25" for r in rows) == 2


def test_append_refuses_header_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "latency_log.csv"
    path.write_text("a,b\n1,2\n")
    with pytest.raises(ValueError):
        lh.append_rows(path, lh.LATENCY_COLUMNS, [_row()])
    assert path.read_text() == "a,b\n1,2\n"


def test_regression_fails_on_synthetic_slowdown() -> None:
    history = _as_history([_row(p50=10.0, p95=12.0)])
    found, compared = lh.find_regressions([_row(p50=30.0, p95=40.0)], history, THRESHOLD)
    assert compared == 1
    assert {r.metric for r in found} == {"p50_ms", "p95_ms"}
    assert found[0].previous_commit == "abc"


def test_regression_passes_on_noise() -> None:
    history = _as_history([_row(p50=10.0, p95=12.0)])
    found, _ = lh.find_regressions([_row(p50=11.0, p95=13.5)], history, THRESHOLD)
    assert found == []


def test_regression_ignores_subfloor_jump_on_tiny_stage() -> None:
    history = _as_history([_row(p50=0.01, p95=0.02)])
    found, _ = lh.find_regressions([_row(p50=0.1, p95=0.2)], history, THRESHOLD)
    assert found == []  # 10x, but 0.09 ms: below the absolute floor


def test_regression_without_comparable_row_passes() -> None:
    history = _as_history(
        [_row(p50=1.0), _row(p50=1.0, cpu_model="other"), _row(cache_state="cold")]
    )
    new = [_row(p50=100.0, p95=100.0, query_set_id="q2")]
    assert lh.find_regressions(new, history, THRESHOLD) == ([], 0)


def test_regression_uses_most_recent_comparable_row() -> None:
    history = _as_history([_row(p50=1.0, p95=1.0), _row(p50=50.0, p95=60.0, commit="new")])
    found, compared = lh.find_regressions([_row(p50=55.0, p95=65.0)], history, THRESHOLD)
    assert compared == 1 and found == []


def test_config_loader_rejects_unknown_key_and_bad_values(tmp_path: Path) -> None:
    good = lh.load_bench_config(lh.default_config_path())
    assert good.regression.rel_threshold > 0
    bad = tmp_path / "c.yaml"
    bad.write_text(
        "seed: 0\nquery_set: s\nwarmup_n: -1\nrepeats: 1\nthroughput_repeats: 1\n"
        "regression: {rel_threshold: 0.5, abs_floor_ms: 0.5}\n"
    )
    with pytest.raises(ValueError):
        lh.load_bench_config(bad)
    bad.write_text(
        "seed: 0\nquery_set: s\nwarmup_n: 1\nrepeats: 1\nthroughput_repeats: 1\nextra: 1\n"
        "regression: {rel_threshold: 0.5, abs_floor_ms: 0.5}\n"
    )
    with pytest.raises(TypeError):
        lh.load_bench_config(bad)


def test_cli_check_appends_then_second_run_compares(tmp_path: Path) -> None:
    args = ["check", "--log-dir", str(tmp_path)]
    assert lh.main(args) == 0
    n1 = len((tmp_path / "latency_log.csv").read_text().splitlines())
    assert n1 == 1 + 2 * len(lh.LATENCY_STAGES)
    assert lh.main(["run", "--log-dir", str(tmp_path)]) == 0
    assert len((tmp_path / "latency_log.csv").read_text().splitlines()) == 1 + 2 * (n1 - 1)
    assert (tmp_path / "throughput_log.csv").exists()
