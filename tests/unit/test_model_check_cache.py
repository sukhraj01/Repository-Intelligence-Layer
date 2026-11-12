"""D158: single provider / candidate by written key, measured-caching cost projection, the cache
probe and adjacent-repeat scheduling. Synthetic data and a scripted transport only; no network."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from ril.agent.providers.cache_probe import probe_items, run_probe
from ril.agent.providers.calllog import CallLog
from ril.agent.providers.driver import DriverConfig, LoggedReplies, drive, latest_rows
from ril.agent.providers.gemini import ApiKey, GeminiClient, GeminiConfig, cached_tokens_of
from ril.agent.providers.limiter import Limits, PersistentLimiter
from ril.agent.providers.model_check import (
    load_spec,
    project_study_cost,
    render_table,
    select_model,
    summarise,
    validate_limits,
)
from ril.agent.providers.pilot_run import RunConfig, load_items, plan_units, prepare_items
from ril.agent.providers.spend import GuardedClient, Price, SpendGuard
from tests.unit._providers_fakes import FakeClock, FakeTransport
from tests.unit.test_providers_pilot import GOOD, context_row
from tests.unit.test_rq3_driver import result


def limits_file(tmp_path: Path, **top: Any) -> Path:
    model = {
        "provider": "gemini",
        "tier": "Tier 1",
        "rpm": 1000,
        "tpm": 2_000_000,
        "rpd": 10_000,
        "input_per_m": 0.75,
        "output_per_m": 3.75,
        "cached_input_per_m": 0.075,
        "price_as_of": "2026-11-12",
        "price_source": "provider pricing page",
        "thinking": None,
        "caps_usd": [1, 3],
    }
    data: dict[str, Any] = {
        "as_of": "2026-11-12",
        "study_budget_usd": 45,
        "study_arm_runs": 12,
        "confirmatory_n": 327,
        "models": {"gemini-3.8-flash": model},
    }
    data.update(top)
    p = tmp_path / "limits.yaml"
    p.write_text(yaml.safe_dump(data))
    return p


# ---------------------------------------------------------------- single provider / candidate


def test_one_provider_and_one_candidate_need_both_written_keys(tmp_path: Path) -> None:
    problems = " | ".join(validate_limits(limits_file(tmp_path)))
    assert "fewer than two candidate models" in problems and "at least two providers" in problems
    only_candidate = validate_limits(limits_file(tmp_path, single_candidate_ok=True))
    assert any("at least two providers" in p for p in only_candidate)
    only_provider = validate_limits(limits_file(tmp_path, single_provider_ok=True))
    assert any("fewer than two candidate models" in p for p in only_provider)
    both = limits_file(tmp_path, single_provider_ok=True, single_candidate_ok=True)
    assert validate_limits(both) == []
    spec = load_spec(both)
    assert spec.single_provider and spec.single_candidate and spec.runs_per_arm == 3


def test_a_flag_must_be_literally_true(tmp_path: Path) -> None:
    p = limits_file(tmp_path, single_provider_ok="yes", single_candidate_ok=1)
    assert validate_limits(p)


def test_the_previous_generation_model_is_not_a_candidate(tmp_path: Path) -> None:
    data = yaml.safe_load(
        limits_file(tmp_path, single_provider_ok=True, single_candidate_ok=True).read_text()
    )
    data["models"]["gemini-3.6-flash"] = dict(data["models"]["gemini-3.8-flash"])
    p = tmp_path / "with36.yaml"
    p.write_text(yaml.safe_dump(data))
    assert any("gemini-3.6-flash: not a candidate" in x for x in validate_limits(p))


def test_the_cached_price_must_not_exceed_the_input_price(tmp_path: Path) -> None:
    data = yaml.safe_load(
        limits_file(tmp_path, single_provider_ok=True, single_candidate_ok=True).read_text()
    )
    data["models"]["gemini-3.8-flash"]["cached_input_per_m"] = 5.0
    p = tmp_path / "bad.yaml"
    p.write_text(yaml.safe_dump(data))
    assert any("cached_input_per_m" in x for x in validate_limits(p))


def test_arm_runs_must_be_a_multiple_of_runs_per_arm(tmp_path: Path) -> None:
    p = limits_file(
        tmp_path, single_provider_ok=True, single_candidate_ok=True, study_runs_per_arm=5
    )
    assert any("multiple" in x for x in validate_limits(p))


# ---------------------------------------------------------------- cost projection


def spec_and_model(tmp_path: Path) -> tuple[Any, Any]:
    spec = load_spec(limits_file(tmp_path, single_provider_ok=True, single_candidate_ok=True))
    return spec, spec.models["gemini-3.8-flash"]


def test_projection_prices_first_runs_uncached_and_repeats_at_the_measured_fraction(
    tmp_path: Path,
) -> None:
    spec, m = spec_and_model(tmp_path)
    inp, out, n = 5_000_000, 400_000, 50
    scale = 327 / 50
    first = (inp * 0.75 + out * 3.75) / 1e6 * scale
    uncached = project_study_cost(m.price, inp, out, n, spec, None)
    assert uncached == pytest.approx(12 * first)
    hit = 0.8
    repeat = ((inp * 0.2) * 0.75 + (inp * 0.8) * 0.075 + out * 3.75) / 1e6 * scale
    cached = project_study_cost(m.price, inp, out, n, spec, hit)
    assert cached == pytest.approx(4 * (first + 2 * repeat))
    assert cached < uncached
    assert project_study_cost(m.price, inp, out, n, spec, 0.0) == pytest.approx(uncached)


def test_no_cached_price_means_no_discount_even_with_a_probe(tmp_path: Path) -> None:
    spec, m = spec_and_model(tmp_path)
    plain = Price("m", 0.75, 3.75, True, "d")
    assert project_study_cost(plain, 10**6, 10**5, 50, spec, 0.9) == pytest.approx(
        project_study_cost(plain, 10**6, 10**5, 50, spec, None)
    )
    with pytest.raises(ValueError):
        project_study_cost(m.price, 10**6, 10**5, 50, spec, 1.5)


def rows(resolved: int, n: int = 50) -> list[dict[str, Any]]:
    return [
        {
            "instance_id": f"i{k}",
            "arm": "rrf",
            "run": 0,
            "outcome": "resolved" if k < resolved else "executed_unresolved",
            "resolved": k < resolved,
            "calls": 1,
            "input_tokens": 12_600,
            "output_tokens": 950,
            "thought_tokens": 0,
        }
        for k in range(n)
    ]


def test_summary_uses_the_probe_fraction_and_reports_both_projections(tmp_path: Path) -> None:
    spec, m = spec_and_model(tmp_path)
    plain = summarise("gemini-3.8-flash", rows(10), {"stopped": "complete"}, m, spec)
    probed = summarise(
        "gemini-3.8-flash", rows(10), {"stopped": "complete"}, m, spec, cache_hit_fraction=0.9
    )
    assert plain["study_usd"] == pytest.approx(plain["study_uncached_usd"])
    assert plain["cache_hit_fraction"] is None
    assert probed["study_usd"] < probed["study_uncached_usd"] == pytest.approx(plain["study_usd"])
    assert plain["study_usd"] > 45 > probed["study_usd"]  # the arithmetic of the brief


# ---------------------------------------------------------------- selection with one candidate


def test_single_candidate_is_selected_only_if_it_passes_both_filters(tmp_path: Path) -> None:
    spec, m = spec_and_model(tmp_path)
    ok = summarise("gemini-3.8-flash", rows(12), {}, m, spec, cache_hit_fraction=0.9)
    res = select_model([ok], spec.budget_usd, single_provider=True)
    assert res["status"] == "selected" and res["chosen"] == "gemini-3.8-flash"
    assert res["single_candidate"] and "single-provider limitation" in res["limitations"][0]
    assert any("gemini-3.5-flash-lite: not run, not available" in t for t in res["not_run"])
    low = summarise("gemini-3.8-flash", rows(5), {}, m, spec, cache_hit_fraction=0.9)  # 10% < 15%
    assert select_model([low], spec.budget_usd)["chosen"] is None
    dear = summarise("gemini-3.8-flash", rows(12), {}, m, spec)  # uncached: over 45
    res = select_model([dear], spec.budget_usd)
    assert res["status"] == "no_selection" and res["chosen"] is None
    assert "no candidate passes" in render_table(res)


# ---------------------------------------------------------------- cached tokens and the guard


def body(inp: int, out: int, cached: int | None, text: str = GOOD) -> str:
    usage: dict[str, int] = {"promptTokenCount": inp, "candidatesTokenCount": out}
    if cached is not None:
        usage["cachedContentTokenCount"] = cached
    return json.dumps(
        {
            "candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}],
            "usageMetadata": usage,
        }
    )


def test_cached_tokens_are_read_from_usage_and_priced_at_the_cached_rate() -> None:
    assert cached_tokens_of(body(1000, 10, 600)) == 600
    assert cached_tokens_of(body(1000, 10, None)) == 0 and cached_tokens_of("not json") == 0
    price = Price("m", 1.0, 10.0, True, "d", 0.1)
    assert price.cost(1000, 100, 600) == pytest.approx((400 * 1.0 + 600 * 0.1 + 100 * 10.0) / 1e6)
    assert price.cost(1000, 100) == pytest.approx((1000 + 1000) / 1e6)
    assert Price("m", 1.0, 10.0, True, "d").cost(1000, 100, 600) == pytest.approx(2000 / 1e6)


def client_for(tmp_path: Path, transport: FakeTransport) -> tuple[GeminiClient, PersistentLimiter]:
    clk = FakeClock(1_800_000_000.0)
    lim = PersistentLimiter(
        Limits("m", 1000, 10_000_000, 100_000, "x", margin=1.0), tmp_path / "lim.jsonl", clk
    )
    return GeminiClient(GeminiConfig(model="m"), ApiKey("k-secret"), lim, transport, clk), lim


def test_the_guard_counts_the_providers_reported_billable_tokens(tmp_path: Path) -> None:
    tr = FakeTransport([body(1000, 100, 0), body(1000, 100, 900)])
    client, _ = client_for(tmp_path, tr)
    price = Price("m", 1.0, 10.0, True, "d", 0.1)
    guard = SpendGuard(10.0, price, 4096)
    g = GuardedClient(client, guard)
    contents = [{"role": "user", "parts": [{"text": "x"}]}]
    g.generate(contents)
    first = guard.spent
    g.generate(contents)
    assert first == pytest.approx((1000 + 1000) / 1e6)
    assert guard.spent - first == pytest.approx((100 + 90 + 1000) / 1e6)  # a hit is not assumed


# ---------------------------------------------------------------- the probe


def prompt_items(n: int) -> list[dict[str, Any]]:
    return [{"instance_id": f"i{k:02d}", "arm": "rrf", "prompt": f"p{k}"} for k in range(n)]


def test_probe_sends_each_prompt_twice_in_a_row_and_measures_the_second_send(
    tmp_path: Path,
) -> None:
    def script(req: str) -> str:
        seen = script.seen  # type: ignore[attr-defined]
        again = req in seen
        seen.add(req)
        return body(2000, 50, 1600 if again else 0)

    script.seen = set()  # type: ignore[attr-defined]
    tr = FakeTransport(script)
    client, _ = client_for(tmp_path, tr)
    price = Price("m", 0.75, 3.75, True, "d", 0.075)
    res = run_probe(prompt_items(12), client, price, "m", n=10)
    sent = [r[2] for r in tr.requests]
    assert len(sent) == 20 and all(sent[2 * k] == sent[2 * k + 1] for k in range(10))
    assert len({sent[2 * k] for k in range(10)}) == 10
    assert res["usable"] and res["pairs"] == 10 and res["hit_fraction"] == pytest.approx(0.8)
    assert res["first_send_cached_tokens"] == 0 and res["requests_identical_within_pair"]
    assert [i["instance_id"] for i in probe_items(prompt_items(12))] == [
        f"i{k:02d}" for k in range(10)
    ]
    assert res["billed_cost_usd"] > 0 and "p0" not in json.dumps(res)


def test_probe_that_hits_the_spend_cap_is_not_usable(tmp_path: Path) -> None:
    tr = FakeTransport(lambda req: body(2000, 50, 0))
    client, _ = client_for(tmp_path, tr)
    price = Price("m", 0.75, 3.75, True, "d", 0.075)
    guarded = GuardedClient(client, SpendGuard(0.02, price, 4096))
    res = run_probe(prompt_items(10), guarded, price, "m")
    assert res["stopped"] == "spend_cap" and not res["usable"] and res["pairs"] < 10


# ---------------------------------------------------------------- adjacent repeats


def test_adjacent_order_is_instance_arm_run_with_the_same_unit_set() -> None:
    its = [{"instance_id": i, "arm": a} for i in ("b", "a") for a in ("rrf", "bm25")]
    run_major = plan_units(its, 3)
    adjacent = plan_units(its, 3, adjacent_repeats=True)
    assert sorted(u for u, _ in run_major) == sorted(u for u, _ in adjacent)
    assert [u for u, _ in adjacent][:6] == [
        ("a", "bm25", 0),
        ("a", "bm25", 1),
        ("a", "bm25", 2),
        ("a", "rrf", 0),
        ("a", "rrf", 1),
        ("a", "rrf", 2),
    ]
    assert [u for u, _ in run_major][:4] == [
        ("a", "bm25", 0),
        ("a", "rrf", 0),
        ("b", "bm25", 0),
        ("b", "rrf", 0),
    ]


def run_driver(tmp_path: Path, adjacent: bool) -> tuple[Path, list[str]]:
    work = tmp_path / ("adj" if adjacent else "maj")
    prepare_items(
        [context_row(f"i{k}", a) for k in range(2) for a in ("bm25", "rrf")], work / "prep"
    )
    its = load_items(work / "prep")
    tr = FakeTransport(lambda req: body(1000, 100, 0))
    client, lim = client_for(work, tr)
    cfg = RunConfig("m", 0, 0.0, runs=3, run_indices=(0, 1, 2))
    src = LoggedReplies(CallLog(work / "log"), cfg, client, lim.day_of)
    ok = result()
    dcfg = DriverConfig(model="m", run_indices=(0, 1, 2), adjacent_repeats=adjacent)
    s = drive(
        its,
        work / "out",
        src,
        lambda iid, diff: ok,
        lambda i: {"a/b.py": "x = 1\n"}.get,
        dcfg,
        Price("m", 1.0, 10.0, True, "d", 0.1),
    )
    assert s.written == 12 and s.stopped == "complete"
    return work, [r[2] for r in tr.requests]


TIMING = ("wall_s", "call_wall_s", "exec_seconds")


def test_adjacent_repeats_send_the_same_requests_in_the_stated_order_with_equal_rows(
    tmp_path: Path,
) -> None:
    major, req_major = run_driver(tmp_path, False)
    adj, req_adj = run_driver(tmp_path, True)
    assert sorted(req_major) == sorted(req_adj) and len(req_adj) == 12

    def sequence(root: Path) -> list[tuple[str, str, int]]:
        return [(r["instance_id"], r["arm"], r["run_index"]) for r in CallLog(root / "log").rows()]

    # run index innermost: the three runs of one prompt are consecutive requests
    assert sequence(adj) == [
        (i, a, k) for i in ("i0", "i1") for a in ("bm25", "rrf") for k in range(3)
    ]
    # the default order is run-major: instance and arm vary fastest
    assert sequence(major) == [
        (i, a, k) for k in range(3) for i in ("i0", "i1") for a in ("bm25", "rrf")
    ]

    def table(root: Path) -> dict[Any, str]:
        rows = latest_rows(root / "out" / "results.jsonl")
        return {
            k: json.dumps({a: b for a, b in v.items() if a not in TIMING}, sort_keys=True)
            for k, v in rows.items()
        }

    assert table(major) == table(adj) and len(table(adj)) == 12
    meta_m = json.loads((major / "out" / "meta.json").read_text())
    meta_a = json.loads((adj / "out" / "meta.json").read_text())
    assert (meta_m["schedule"], meta_a["schedule"]) == ("run_major", "adjacent_repeats")
    calls_a = {
        (r["prompt_sha256"], r["request_sha256"], r["run_index"])
        for r in CallLog(adj / "log").rows()
    }
    calls_m = {
        (r["prompt_sha256"], r["request_sha256"], r["run_index"])
        for r in CallLog(major / "log").rows()
    }
    assert calls_a == calls_m


# ---------------------------------------------------------------- the command line


def load_cli() -> Any:
    import importlib.util

    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(
        "rq3_driver_cli", root / "scripts" / "rq3_driver.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_select_command_reads_the_probe_and_a_single_candidate_file_validates(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    mod = load_cli()
    limits = limits_file(tmp_path, single_provider_ok=True, single_candidate_ok=True)
    assert mod.main(["model-check-limits", str(limits)]) == 0
    run = tmp_path / "runs" / "gemini-3.8-flash"
    run.mkdir(parents=True)
    (run / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows(12)))
    (run / "meta.json").write_text(json.dumps({"stopped": "complete", "thinking_config": None}))
    out = tmp_path / "choice.json"
    args = ["model-check-select", str(out), str(tmp_path / "runs"), "--limits", str(limits)]
    assert mod.main(args) == 3  # no probe: uncached projection, over the budget, nothing chosen
    assert json.loads(out.read_text())["status"] == "no_selection"
    (run / "cache_probe.json").write_text(json.dumps({"hit_fraction": 0.9}))
    assert mod.main(args) == 0
    got = json.loads(out.read_text())
    assert got["chosen"] == "gemini-3.8-flash" and got["limitations"]
    assert "cache hit 90%" in capsys.readouterr().out
