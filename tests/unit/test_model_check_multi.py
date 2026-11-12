"""The D152 selection rule, the limits file and the aggregation command, on synthetic rows only."""

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from ril.agent.providers.model_check import (
    load_spec,
    power_context,
    provider_for,
    render_table,
    run_config_sha256,
    select_model,
    summarise,
    validate_limits,
    wilson,
)
from ril.agent.providers.spend import price_from_limits

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "configs" / "agent" / "model_check_limits.template.yaml"
CANDIDATES = tuple(yaml.safe_load(TEMPLATE.read_text())["models"])


def filled(tmp_path: Path, **over: Any) -> Path:
    data = yaml.safe_load(TEMPLATE.read_text())
    data["as_of"] = "2026-11-13"
    data["source"] = "provider consoles"
    prov = {"gemini-3.5-flash-lite": (0.1, 0.4), "gemini-3.8-flash": (0.3, 2.5)}
    for name, m in data["models"].items():
        inp, out = prov.get(name, (1.0, 5.0) if name == "second-provider-model-a" else (2.0, 10.0))
        if m["provider"] == "messages":
            m.update(
                api_url="https://api.example.invalid/v1/messages",
                key_variable="TEST_KEY",
                key_header="x-test-key",
            )
        m.update(
            tier="paid",
            rpm=100,
            tpm=1_000_000,
            rpd=10_000,
            input_per_m=inp,
            output_per_m=out,
            price_as_of="2026-11-13",
            price_source="provider pricing page",
        )
    data.update(over)
    p = tmp_path / "limits.yaml"
    p.write_text(yaml.safe_dump(data))
    return p


def rows(
    resolved: int, n: int = 50, unusable: int = 0, inp: int = 12_000, out: int = 900
) -> list[dict[str, Any]]:
    out_rows = []
    for k in range(n):
        if k < resolved:
            outcome = "resolved"
        elif k < resolved + unusable:
            outcome = "unusable"
        else:
            outcome = "executed_unresolved"
        out_rows.append(
            {
                "instance_id": f"i{k}",
                "arm": "rrf",
                "run": 0,
                "outcome": outcome,
                "resolved": outcome == "resolved",
                "calls": 1,
                "input_tokens": inp,
                "output_tokens": out,
                "thought_tokens": 0,
            }
        )
    return out_rows


def summ(tmp_path: Path, model: str, resolved: int, n: int = 50, **kw: Any) -> dict[str, Any]:
    spec = load_spec(filled(tmp_path))
    return summarise(
        model, rows(resolved, n, **kw), {"stopped": "complete"}, spec.models[model], spec
    )


# ---------------------------------------------------------------------------- limits file


def test_template_is_refused_until_filled(tmp_path: Path) -> None:
    problems = validate_limits(TEMPLATE)
    assert any("as_of is unset" in p for p in problems)
    assert sum("price_source is unset" in p for p in problems) == len(CANDIDATES)
    with pytest.raises(ValueError):
        load_spec(TEMPLATE)
    assert validate_limits(filled(tmp_path)) == []


def test_two_providers_connection_fields_and_ascending_caps_are_required(tmp_path: Path) -> None:
    data = yaml.safe_load(filled(tmp_path).read_text())
    data["models"]["second-provider-model-a"]["caps_usd"] = [5, 2]
    data["models"]["second-provider-model-b"]["api_url"] = "UNSET"
    p = tmp_path / "bad.yaml"
    p.write_text(yaml.safe_dump(data))
    problems = " | ".join(validate_limits(p))
    assert "second-provider-model-a: caps_usd" in problems
    assert "second-provider-model-b: api_url is unset" in problems
    one = {"models": {k: v for k, v in data["models"].items() if k.startswith("gemini")}}
    data.update(one)
    q = tmp_path / "one.yaml"
    q.write_text(yaml.safe_dump(data))
    assert "candidates must come from at least two providers" in " | ".join(validate_limits(q))


def test_budget_defaults_to_150_when_the_key_is_absent(tmp_path: Path) -> None:
    data = yaml.safe_load(filled(tmp_path).read_text())
    assert load_spec(filled(tmp_path)).budget_usd == 150.0  # the template's own value
    del data["study_budget_usd"]
    p = tmp_path / "nob.yaml"
    p.write_text(yaml.safe_dump(data))
    spec = load_spec(p)
    assert spec.budget_usd == 150.0 and spec.budget_defaulted and spec.arm_runs == 12


def test_price_comes_from_the_limits_entry_and_is_marked_by_its_source(tmp_path: Path) -> None:
    p = filled(tmp_path)
    price = price_from_limits(p, "second-provider-model-a")
    assert price is not None and (price.input_per_m, price.output_per_m, price.verified) == (
        1.0,
        5.0,
        True,
    )
    assert (
        price_from_limits(
            ROOT / "configs" / "agent" / "gemini_limits.yaml", "gemini-3.5-flash-lite"
        )
        is None
    )


def test_provider_choice_and_config_hash() -> None:
    assert provider_for("anything", {}) == "gemini"  # the pilot provider is the default
    assert provider_for("gemini-3.8-flash", {}) == "gemini"
    assert provider_for("anything", {"provider": "messages"}) == "messages"
    assert provider_for("messages-x", {"provider": "gemini"}, "messages") == "messages"
    with pytest.raises(ValueError):
        provider_for("m", {}, "other")
    a = {"model": "m", "thinking": None, "temperature": 0.0}
    assert run_config_sha256(a) == run_config_sha256(dict(reversed(list(a.items()))))
    assert run_config_sha256(a) != run_config_sha256({**a, "thinking": {"budget": 1}})


# ---------------------------------------------------------------------------- summary


def test_summary_counts_tokens_and_projects_cost(tmp_path: Path) -> None:
    s = summ(tmp_path, "second-provider-model-a", resolved=10, unusable=5)
    assert (s["n"], s["resolved"], s["unusable"], s["complete"]) == (50, 10, 5, True)
    assert s["input_tokens"] == 50 * 12_000 and s["output_tokens"] == 50 * 900
    slice_cost = (600_000 * 1.0 + 45_000 * 5.0) / 1e6
    assert s["slice_cost_usd"] == pytest.approx(slice_cost)
    assert s["arm_run_usd"] == pytest.approx(slice_cost / 50 * 327)
    assert s["study_usd"] == pytest.approx(s["arm_run_usd"] * 12)
    lo, hi = wilson(10, 50)
    assert lo < 0.2 < hi and (s["rate_lo"], s["rate_hi"]) == (lo, hi)


def test_a_partial_run_or_left_over_environment_errors_is_not_complete(tmp_path: Path) -> None:
    assert not summ(tmp_path, "gemini-3.8-flash", 5, n=40)["complete"]
    spec = load_spec(filled(tmp_path))
    r = rows(5)
    r[0] = {**r[0], "outcome": "exec_error:env", "resolved": False}
    s = summarise("gemini-3.8-flash", r, {}, spec.models["gemini-3.8-flash"], spec)
    assert s["exec_error_rows"] == 1 and s["n"] == 49 and not s["complete"]


# ---------------------------------------------------------------------------- the rule


def table(tmp_path: Path, resolved: dict[str, int], **kw: Any) -> list[dict[str, Any]]:
    return [summ(tmp_path, m, resolved[m], **kw) for m in CANDIDATES]


def test_highest_resolved_wins_when_clearly_ahead(tmp_path: Path) -> None:
    got = select_model(
        table(
            tmp_path,
            {
                "gemini-3.5-flash-lite": 8,
                "gemini-3.8-flash": 12,
                "second-provider-model-a": 14,
                "second-provider-model-b": 22,
            },
        ),
        150.0,
    )
    assert got["status"] == "selected" and got["chosen"] == "second-provider-model-b"
    assert [r["selected"] for r in got["candidates"]] == [False, False, False, True]


def test_a_near_tie_goes_to_the_cheaper_model(tmp_path: Path) -> None:
    # 20 and 18 are within 2 instances: the cheaper (lower projected study cost) is taken
    got = select_model(
        table(
            tmp_path,
            {
                "gemini-3.5-flash-lite": 5,
                "gemini-3.8-flash": 18,
                "second-provider-model-a": 19,
                "second-provider-model-b": 20,
            },
        ),
        150.0,
    )
    band = {r["model"] for r in got["candidates"] if r["in_tie_band"]}
    assert band == {"gemini-3.8-flash", "second-provider-model-a", "second-provider-model-b"}
    assert got["chosen"] == "gemini-3.8-flash"
    # three behind is outside the band
    got = select_model(
        table(
            tmp_path,
            {
                "gemini-3.5-flash-lite": 5,
                "gemini-3.8-flash": 17,
                "second-provider-model-a": 19,
                "second-provider-model-b": 20,
            },
        ),
        150.0,
    )
    assert {r["model"] for r in got["candidates"] if r["in_tie_band"]} == {
        "second-provider-model-a",
        "second-provider-model-b",
    }
    assert got["chosen"] == "second-provider-model-a"


def test_budget_discards_before_capability(tmp_path: Path) -> None:
    t = table(
        tmp_path,
        {
            "gemini-3.5-flash-lite": 8,
            "gemini-3.8-flash": 10,
            "second-provider-model-a": 14,
            "second-provider-model-b": 22,
        },
    )
    large = next(r for r in t if r["model"] == "second-provider-model-b")
    assert large["study_usd"] > 20
    got = select_model(t, large["study_usd"] - 0.01)
    assert next(r for r in got["candidates"] if r["model"] == "second-provider-model-b")[
        "over_budget"
    ]
    assert got["chosen"] == "second-provider-model-a"
    assert (
        select_model(t, large["study_usd"])["chosen"] == "second-provider-model-b"
    )  # equal to B passes


def test_floor_is_inclusive_at_15_percent_and_nothing_chosen_below(tmp_path: Path) -> None:
    low = {m: 7 for m in CANDIDATES}  # 14%
    got = select_model(table(tmp_path, low), 150.0)
    assert got["status"] == "no_selection" and got["chosen"] is None
    assert all(r["below_floor"] for r in got["candidates"])
    at = select_model(table(tmp_path, {**low, "second-provider-model-a": 8}), 150.0)  # exactly 16%
    assert at["chosen"] == "second-provider-model-a"


def test_no_choice_when_every_passing_model_is_over_budget(tmp_path: Path) -> None:
    got = select_model(table(tmp_path, {m: 20 for m in CANDIDATES}), 0.5)
    assert got["status"] == "no_selection"
    assert all(r["over_budget"] for r in got["candidates"])


def test_an_unfinished_candidate_blocks_the_comparison(tmp_path: Path) -> None:
    t = table(tmp_path, {m: 20 for m in CANDIDATES})
    t[1] = summ(tmp_path, "gemini-3.8-flash", 20, n=30)
    got = select_model(t, 150.0)
    assert got["status"] == "incomplete" and got["chosen"] is None
    assert "gemini-3.8-flash" in got["note"]


def test_ties_in_resolved_and_cost_break_by_name(tmp_path: Path) -> None:
    t = table(tmp_path, {m: 20 for m in CANDIDATES})
    for r in t:
        r["study_usd"] = 10.0
    assert select_model(t, 150.0)["chosen"] == "gemini-3.5-flash-lite"


def test_table_text_and_power_context(tmp_path: Path) -> None:
    got = select_model(table(tmp_path, {m: 20 for m in CANDIDATES}), 150.0)
    text = render_table(got)
    assert "SELECTED" in text and "tie band" in text and "chosen:" in text
    mdd = tmp_path / "mdd.csv"
    with mdd.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["n", "rate", "kappa", "runs", "mdd_points", "grid_max_points"])
        for rate in (0.1, 0.2, 0.3):
            for runs in (1, 3):
                w.writerow([327, rate, 1.0, runs, round(rate * 10 + runs, 2), 10.0])
    ctx = power_context(mdd, 0.4)
    assert ctx["nearest_grid_rate"] == 0.3 and ctx["outside_grid"]
    assert power_context(mdd, 0.18)["nearest_grid_rate"] == 0.2


# ---------------------------------------------------------------------------- the command


def load_cli() -> Any:
    spec = importlib.util.spec_from_file_location(
        "rq3_driver_cli", ROOT / "scripts" / "rq3_driver.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write_runs(base: Path, resolved: dict[str, int]) -> None:
    for m in CANDIDATES:
        d = base / m
        d.mkdir(parents=True)
        (d / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows(resolved[m])))
        (d / "meta.json").write_text(json.dumps({"stopped": "complete", "thinking_config": None}))


def test_select_command_on_stored_rows(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    mod = load_cli()
    limits = filled(tmp_path)
    assert mod.main(["model-check-limits", str(limits)]) == 0
    assert mod.main(["model-check-limits", str(TEMPLATE)]) == 2
    runs = tmp_path / "runs"
    write_runs(
        runs,
        {
            "gemini-3.5-flash-lite": 6,
            "gemini-3.8-flash": 10,
            "second-provider-model-a": 11,
            "second-provider-model-b": 19,
        },
    )
    out = tmp_path / "choice.json"
    code = mod.main(["model-check-select", str(out), str(runs), "--limits", str(limits)])
    assert code == 0
    got = json.loads(out.read_text())
    assert got["chosen"] == "second-provider-model-b" and got["status"] == "selected"
    assert got["budget_defaulted"] is False and got["study_arm_runs"] == 12
    assert got["power_context"]["nearest_grid_rate"] in (0.3, 0.2, 0.1)
    assert "SELECTED" in capsys.readouterr().out
    # a missing candidate is an error, an unfinished one gives status incomplete and a non-zero code
    (runs / "second-provider-model-a" / "results.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows(11, n=30))
    )
    assert mod.main(["model-check-select", str(out), str(runs), "--limits", str(limits)]) == 3
    assert json.loads(out.read_text())["status"] == "incomplete"
