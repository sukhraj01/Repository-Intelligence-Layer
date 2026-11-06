"""Patch format, prompt determinism, prepare, run with resume and re-asks, report."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ril.agent.providers.calllog import CallLog, sha256_text
from ril.agent.providers.gemini import ApiKey, GeminiClient, GeminiConfig
from ril.agent.providers.limiter import Limits, PersistentLimiter
from ril.agent.providers.patch_format import build_prompt, parse_edits
from ril.agent.providers.pilot_run import (
    RunConfig,
    load_items,
    plan_units,
    prepare_items,
    run_units,
)
from ril.agent.providers.report import quantile, summarise, to_markdown
from tests.unit._providers_fakes import FakeClock, FakeTransport, http, ok_body

GOOD = "FILE: a/b.py\n<<<<<<< SEARCH\nx = 1\n=======\nx = 2\n>>>>>>> REPLACE\n"


def context_row(
    iid: str, arm: str, context: str = "### a/b.py:1-2 function f (rank 1)\nx = 1\n"
) -> dict[str, Any]:
    return {
        "instance_id": iid,
        "arm": arm,
        "issue": "x is wrong",
        "context": context,
        "context_sha256": sha256_text(context),
        "files": ["a/b.py"],
        "budget": 8000,
        "tokenizer": "approx-words-v1",
    }


def test_parse_accepts_fenced_replies_and_rejects_format_faults() -> None:
    edits, err = parse_edits("```\n" + GOOD + "```", {"a/b.py"})
    assert err is None and edits[0].path == "a/b.py" and edits[0].new == "x = 2"
    assert parse_edits("I would change x.", {"a/b.py"})[1] == "no_edit_block"
    assert parse_edits(GOOD.replace(">>>>>>> REPLACE", ""), {"a/b.py"})[1] == "unterminated_block"
    assert parse_edits(GOOD.replace("x = 1", ""), {"a/b.py"})[1] == "empty_search"
    assert parse_edits(GOOD.replace("a/b.py", "../b.py"), None)[1] == "bad_path"
    assert parse_edits(GOOD, {"other.py"})[1] == "path_not_in_context"


def test_prompt_bytes_depend_only_on_the_inputs() -> None:
    assert build_prompt("issue", "ctx") == build_prompt("issue", "ctx")
    assert build_prompt("issue ", "ctx") == build_prompt(
        " issue", "ctx"
    )  # issue whitespace trimmed
    assert build_prompt("issue", "ctx") != build_prompt("issue", "ctx2")


def test_prepare_checks_the_context_hash_and_is_deterministic(tmp_path: Path) -> None:
    rows = [context_row("i2", "rrf"), context_row("i1", "bm25"), context_row("i1", "rrf")]
    assert prepare_items(rows, tmp_path / "p1") == 3
    prepare_items(list(reversed(rows)), tmp_path / "p2")
    assert (tmp_path / "p1" / "items.jsonl").read_bytes() == (
        tmp_path / "p2" / "items.jsonl"
    ).read_bytes()
    # identical contexts give identical prompt files for the two arms of one instance
    items = load_items(tmp_path / "p1")
    assert items[0]["prompt_sha256"] == items[1]["prompt_sha256"]
    bad = context_row("i3", "bm25")
    bad["context_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        prepare_items([bad], tmp_path / "p3")
    with pytest.raises(ValueError):
        prepare_items([rows[0], rows[0]], tmp_path / "p4")


def harness(
    tmp_path: Path, script: list[Any], rpd: int = 1000
) -> tuple[Any, CallLog, PersistentLimiter, FakeTransport]:
    clk = FakeClock(1_800_000_000.0)
    lim = PersistentLimiter(
        Limits("m", 1000, 10_000_000, rpd, "x", margin=1.0), tmp_path / "lim.jsonl", clk
    )
    tr = FakeTransport(list(script))
    client = GeminiClient(GeminiConfig(model="m"), ApiKey("k-secret"), lim, tr, clk)
    return client, CallLog(tmp_path / "log"), lim, tr


def items_for(
    tmp_path: Path, n: int = 1, arms: tuple[str, ...] = ("bm25", "rrf")
) -> list[dict[str, Any]]:
    prepare_items([context_row(f"i{k}", a) for k in range(n) for a in arms], tmp_path / "prep")
    return load_items(tmp_path / "prep")


def test_run_reasks_on_a_malformed_reply_and_stops_after_two(tmp_path: Path) -> None:
    items = items_for(tmp_path, arms=("bm25",))
    client, log, lim, tr = harness(
        tmp_path, [ok_body("no idea"), ok_body("still none"), ok_body("nope")]
    )
    s = run_units(items, log, client, RunConfig("m", 0, 0.0, runs=1), lim.day_of)
    assert (s.calls, s.units_finished, s.stopped) == (3, 1, "complete")
    rows = list(log.rows())
    assert [r["attempt"] for r in rows] == [0, 1, 2] and [r["final"] for r in rows] == [
        False,
        False,
        True,
    ]
    assert rows[-1]["patch_ok"] is False and rows[0]["format_error"] == "no_edit_block"
    import json

    third = json.loads(tr.requests[2][2])["contents"]  # user, model, user, model, user
    assert [c["role"] for c in third] == ["user", "model", "user", "model", "user"]


def test_run_stops_at_the_daily_cap_and_resumes_without_repeating(tmp_path: Path) -> None:
    items = items_for(tmp_path, n=2)  # 2 instances x 2 arms x 2 runs = 8 units
    client, log, lim, tr = harness(tmp_path, [ok_body(GOOD)] * 20, rpd=5)
    s = run_units(items, log, client, RunConfig("m", 0, 0.0), lim.day_of)
    assert (s.stopped, s.calls, s.units_finished) == ("daily_cap", 5, 5) and s.resume_at is not None
    # next day: a fresh limiter and client on the same files; finished units are not resent
    clk2 = FakeClock(s.resume_at + 1)
    lim2 = PersistentLimiter(
        Limits("m", 1000, 10_000_000, 5, "x", margin=1.0), tmp_path / "lim.jsonl", clk2
    )
    client2 = GeminiClient(
        GeminiConfig(model="m"), ApiKey("k-secret"), lim2, FakeTransport([ok_body(GOOD)] * 20), clk2
    )
    s2 = run_units(items, CallLog(tmp_path / "log"), client2, RunConfig("m", 0, 0.0), lim2.day_of)
    assert (s2.calls, s2.units_skipped, s2.stopped) == (3, 5, "complete")
    keys = [(r["instance_id"], r["arm"], r["run_index"]) for r in CallLog(tmp_path / "log").rows()]
    assert len(keys) == len(set(keys)) == 8


def test_resume_after_a_reask_continues_the_conversation(tmp_path: Path) -> None:
    items = items_for(tmp_path, arms=("bm25",))
    client, log, lim, _ = harness(tmp_path, [ok_body("bad")], rpd=1)
    run_units(
        items, log, client, RunConfig("m", 0, 0.0, runs=1), lim.day_of
    )  # cap after the first reply
    client2, log2, lim2, tr2 = harness(tmp_path, [ok_body(GOOD)])
    lim2._entries.clear()  # new day
    run_units(items, log2, client2, RunConfig("m", 0, 0.0, runs=1), lim2.day_of)
    import json

    sent = json.loads(tr2.requests[0][2])["contents"]
    assert [c["role"] for c in sent] == ["user", "model", "user"] and sent[1]["parts"][0][
        "text"
    ] == "bad"
    assert [r["attempt"] for r in log2.rows()] == [0, 1] and list(log2.rows())[-1][
        "patch_ok"
    ] is True


def test_provider_failure_stops_the_run_and_is_logged_as_failed(tmp_path: Path) -> None:
    items = items_for(tmp_path, arms=("bm25",))
    client, log, lim, _ = harness(tmp_path, [http(503)] * 10)
    s = run_units(items, log, client, RunConfig("m", 0, 0.0, runs=1), lim.day_of)
    assert s.stopped == "provider_unavailable"
    rows = list(log.rows())
    assert rows[-1]["kind"] == "failed" and rows[-1]["final"] is False and rows[-1]["n_5xx"] == 6


def test_max_calls_bounds_a_smoke_run(tmp_path: Path) -> None:
    items = items_for(tmp_path, n=3)
    client, log, lim, tr = harness(tmp_path, [ok_body(GOOD)] * 20)
    s = run_units(items, log, client, RunConfig("m", 0, 0.0, max_calls=3), lim.day_of)
    assert (s.stopped, s.calls, len(tr.requests)) == ("max_calls", 3, 3)


def test_plan_order_is_run_then_instance_then_arm(tmp_path: Path) -> None:
    order = [u for u, _ in plan_units(items_for(tmp_path, n=2), 2)]
    assert order[:4] == [("i0", "bm25", 0), ("i0", "rrf", 0), ("i1", "bm25", 0), ("i1", "rrf", 0)]
    assert order[4][2] == 1


def test_report_tables_and_agreement(tmp_path: Path) -> None:
    items = items_for(tmp_path, n=2, arms=("bm25",))
    other = GOOD.replace("x = 2", "x = 3")
    client, log, lim, _ = harness(
        tmp_path,
        [
            ok_body(GOOD),
            ok_body("bad"),
            ok_body(GOOD),
            ok_body(GOOD),
            ok_body(other),
            ok_body(GOOD),
        ],
    )
    run_units(items, log, client, RunConfig("m", 7, 0.0), lim.day_of)
    s = summarise(log, {("i0", "bm25", 0): True, ("i0", "bm25", 1): False})
    arm = s["per_arm"]["bm25"]
    assert s["calls"] == 5 and s["units_final"] == 4 and s["models"] == ["m"]
    assert arm["calls_per_unit"]["max"] == 2 and arm["malformed_first_reply_rate"] == 0.25
    assert arm["resolved"] == {"n": 2, "rate": 0.5}
    r = s["run_to_run"]
    assert (
        r["pairs"] == 2 and r["same_reply_text"] == 0.5 and r["same_patch_given_both_usable"] == 0.5
    )
    assert (
        "p95" in to_markdown(s)
        and "mean" not in to_markdown(s).split("latency per call")[1].split("\n")[0]
    )
    assert s["token_ratio"]["n"] == 4 and s["token_ratio"]["approx_per_model_token"]["p50"] > 0
    assert "approximate tokens per model token" in to_markdown(s)
    assert quantile([1, 2, 3, 4], 0.5) == 2 and quantile([], 0.5) != quantile([], 0.5)


def test_context_rows_use_the_shared_assembly_and_hash_the_text() -> None:
    from ril.agent.providers.contexts import context_rows
    from ril.assembly.assemble import Candidate, UnitText
    from ril.assembly.config import AssemblyConfig
    from ril.assembly.tokens import ApproxTokenizer

    units = [
        UnitText("a.py::f", "a.py", 1, 2, "function", "f", "def f():\n    return 1"),
        UnitText("b.py::g", "b.py", 3, 4, "function", "g", "def g():\n    return 2"),
    ]
    ranked = {
        "bm25": [Candidate("a.py::f", 2.0), Candidate("b.py::g", 1.0)],
        "rrf": [Candidate("b.py::g", 0.5), Candidate("a.py::f", 0.4)],
    }
    rows = context_rows("i1", "issue", units, ranked, AssemblyConfig(budget=500), ApproxTokenizer())
    assert [r["arm"] for r in rows] == ["bm25", "rrf"]
    assert all(sha256_text(r["context"]) == r["context_sha256"] for r in rows)
    # blocks are ordered by file and line, so one included set reads the same in both arms
    # (the rank in each block header differs, so the hashes differ)
    assert rows[0]["files"] == rows[1]["files"] == ["a.py", "b.py"]
    assert rows[0]["context_sha256"] != rows[1]["context_sha256"]
    again = context_rows(
        "i1", "issue", units, ranked, AssemblyConfig(budget=500), ApproxTokenizer()
    )
    assert [r["context"] for r in rows] == [r["context"] for r in again]
