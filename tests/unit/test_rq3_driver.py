"""Driver: outcome classes, both readings, env retry, resume, logged and live replies, spend cap."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ril.agent.providers.calllog import CallLog
from ril.agent.providers.driver import (
    DriverConfig,
    LoggedReplies,
    StoredReplies,
    drive,
    final_keys,
    latest_rows,
    run_with_retry,
)
from ril.agent.providers.gemini import ApiKey, GeminiClient, GeminiConfig
from ril.agent.providers.limiter import Limits, PersistentLimiter
from ril.agent.providers.pilot_run import RunConfig, load_items, prepare_items
from ril.agent.providers.spend import GuardedClient, Price, SpendGuard
from ril.evaluation.executor.runner import ExecResult
from tests.unit._providers_fakes import FakeClock, FakeTransport, ok_body
from tests.unit.test_providers_pilot import GOOD, context_row

FILE = "a/b.py"
TEXT = "x = 1\ny = 2\nx = 1  \n"  # "x = 1" occurs twice (second with trailing blanks)


def reply(old: str, new: str, path: str = FILE) -> str:
    return f"FILE: {path}\n<<<<<<< SEARCH\n{old}\n=======\n{new}\n>>>>>>> REPLACE\n"


def reader_for(iid: str) -> Any:
    return {FILE: TEXT, "a/c.py": "def f():\n    return 1\n"}.get


def result(**kw: Any) -> ExecResult:
    base: dict[str, Any] = {
        "instance_id": "i",
        "built": True,
        "patch_applied": True,
        "tests_ran": True,
        "f2p_total": 1,
        "f2p_passed": 1,
        "p2p_total": 2,
        "p2p_passed": 2,
        "seconds": {"total": 3.0},
    }
    base.update(kw)
    return ExecResult(**base)


class Exec:
    def __init__(self, *outcomes: ExecResult) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[str] = []

    def __call__(self, iid: str, diff: str) -> ExecResult:
        self.calls.append(diff)
        return self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]


def items(*arms: str) -> list[dict[str, Any]]:
    return [
        {"instance_id": "i1", "arm": a, "paths": None, "repo": "r/r", "template_version": "t"}
        for a in arms
    ]


def run_stored(
    tmp_path: Path, replies: dict[str, str], executor: Any, **kw: Any
) -> dict[str, dict[str, Any]]:
    its = items(*replies)
    source = StoredReplies({("i1", a, 0): t for a, t in replies.items()})
    cfg = DriverConfig(model="m", mode="replay", env_backoff_s=0.0, **kw)
    drive(its, tmp_path / "out", source, executor, reader_for, cfg, sleep=lambda s: None)
    return {u[1]: r for u, r in latest_rows(tmp_path / "out" / "results.jsonl").items()}


def test_outcome_classes(tmp_path: Path) -> None:
    def by_diff(iid: str, diff: str) -> ExecResult:
        return result() if "+y = 3" in diff else result(f2p_passed=0)

    rows = run_stored(
        tmp_path,
        {
            "ok": reply("y = 2", "y = 3"),
            "unusable": "I would change y.",
            "nomatch": reply("z = 9", "z = 1"),
            "multi": reply("x = 1", "x = 0"),
            "wrongfile": reply("x", "y", "a/zzz.py"),
            "noop": reply("y = 2", "y = 2"),
            "fails": reply("y = 2", "y = 4"),
        },
        by_diff,
    )
    got = {k: v["outcome"] for k, v in rows.items()}
    assert got == {
        "ok": "resolved",
        "unusable": "unusable",
        "nomatch": "apply_failed:no_match",
        "multi": "apply_failed:multiple_matches",
        "wrongfile": "apply_failed:file_missing",
        "noop": "executed_unresolved",
        "fails": "executed_unresolved",
    }
    assert rows["noop"]["empty_diff"] and not rows["unusable"]["usable"]
    assert rows["ok"]["resolved"] and not rows["fails"]["resolved"]
    assert rows["fails"]["f2p"] == [0, 1]


def test_exact_failure_with_tolerant_success_is_a_sensitivity_only(tmp_path: Path) -> None:
    # the SEARCH text differs from the file only in trailing whitespace of its first line
    ex = Exec(result())
    rows = run_stored(tmp_path, {"a": reply("y = 2  \nx = 1", "y = 5\nx = 1")}, ex)
    r = rows["a"]
    assert r["outcome"] == "apply_failed:no_match"
    assert r["outcome_tolerant"] == "resolved" and r["resolved_tolerant"] and not r["resolved"]
    assert len(ex.calls) == 1


def test_identical_diffs_are_executed_once(tmp_path: Path) -> None:
    ex = Exec(result())
    rows = run_stored(tmp_path, {"a": reply("y = 2", "y = 3")}, ex)
    assert len(ex.calls) == 1 and rows["a"]["outcome_tolerant"] == rows["a"]["outcome"]


def test_classify_environment_and_patch_faults(tmp_path: Path) -> None:
    ex = Exec(
        result(built=False, patch_applied=False, tests_ran=False, failure_stage="install"),
        result(tests_ran=False, failure_stage="no_test_output"),
        result(patch_applied=False, tests_ran=False, failure_stage="patch_apply_failed"),
    )
    rows = run_stored(
        tmp_path,
        {
            "env": reply("y = 2", "y = 3"),
            "broken": reply("y = 2", "y = 4"),
            "gitapply": reply("y = 2", "y = 5"),
        },
        ex,
    )
    got = {k: v["outcome"] for k, v in rows.items()}
    assert sorted(got.values()) == sorted(
        ["exec_error:install", "executed_unresolved", "apply_failed:git_apply"]
    )


def test_name_resolution_failure_is_retried_but_a_test_failure_is_not() -> None:
    outage = result(
        built=False,
        patch_applied=False,
        tests_ran=False,
        failure_stage="build_env",
        failure_detail="error: Temporary failure in name resolution",
    )
    slept: list[float] = []
    ex = Exec(outage, outage, result())
    res, trail = run_with_retry(ex, "i", "d", 3, 10.0, slept.append)
    assert res.resolved and len(ex.calls) == 3 and slept == [10.0, 20.0]
    assert [t["attempt"] for t in trail] == [0, 1]
    failing = result(f2p_passed=0, failure_detail="Temporary failure in name resolution")
    ex2 = Exec(failing)
    res2, trail2 = run_with_retry(ex2, "i", "d", 3, 10.0, slept.append)
    assert len(ex2.calls) == 1 and trail2 == [] and not res2.resolved
    ex3 = Exec(outage)
    res3, trail3 = run_with_retry(ex3, "i", "d", 2, 0.0, lambda s: None)
    assert len(ex3.calls) == 3 and len(trail3) == 2 and not res3.built


def test_exec_error_rows_are_not_final_and_a_restart_reruns_them(tmp_path: Path) -> None:
    ex = Exec(result(built=False, patch_applied=False, tests_ran=False, failure_stage="install"))
    run_stored(tmp_path, {"a": reply("y = 2", "y = 3")}, ex)
    path = tmp_path / "out" / "results.jsonl"
    assert final_keys(path) == set()
    ex2 = Exec(result())
    run_stored(tmp_path, {"a": reply("y = 2", "y = 3")}, ex2)
    assert final_keys(path) == {("i1", "a", 0)}
    assert len(path.read_text().splitlines()) == 2
    ex3 = Exec(result())
    run_stored(tmp_path, {"a": reply("y = 2", "y = 3")}, ex3)  # finished: nothing is repeated
    assert ex3.calls == [] and len(path.read_text().splitlines()) == 2


def test_replay_expected_class_is_compared(tmp_path: Path) -> None:
    its = [{**items("a")[0], "expected": "apply_failed:no_match"}]
    src = StoredReplies({("i1", "a", 0): reply("zzz", "q")})
    drive(its, tmp_path / "o", src, Exec(result()), reader_for, DriverConfig(model="m"))
    row = latest_rows(tmp_path / "o" / "results.jsonl")[("i1", "a", 0)]
    assert row["match"] is True


def test_threaded_run_writes_every_row_once(tmp_path: Path) -> None:
    its = [
        {"instance_id": f"i{k}", "arm": "a", "paths": None, "template_version": "t"}
        for k in range(12)
    ]
    src = StoredReplies({(f"i{k}", "a", 0): reply("y = 2", "y = 3") for k in range(12)})
    s = drive(its, tmp_path / "o", src, Exec(result()), reader_for, DriverConfig("m", workers=4))
    assert s.written == 12
    assert len(final_keys(tmp_path / "o" / "results.jsonl")) == 12


# ------------------------------------------------------------------ logged and live replies


def harness(tmp_path: Path, script: list[Any], rpd: int = 1000) -> tuple[Any, CallLog, Any]:
    clk = FakeClock(1_800_000_000.0)
    lim = PersistentLimiter(
        Limits("m", 1000, 10_000_000, rpd, "x", margin=1.0), tmp_path / "lim.jsonl", clk
    )
    tr = FakeTransport(list(script))
    client = GeminiClient(GeminiConfig(model="m"), ApiKey("k-secret"), lim, tr, clk)
    return client, CallLog(tmp_path / "log"), lim


def prepared(tmp_path: Path, n: int = 2) -> list[dict[str, Any]]:
    prepare_items(
        [context_row(f"i{k}", a) for k in range(n) for a in ("bm25", "rrf")], tmp_path / "prep"
    )
    return load_items(tmp_path / "prep")


def test_live_run_then_grade_from_the_log_only(tmp_path: Path) -> None:
    its = prepared(tmp_path, 1)
    client, calllog, lim = harness(tmp_path, [ok_body(GOOD, 1000, 200)] * 4)
    price = Price("m", 1.0, 10.0, False, "d")
    cfg = RunConfig("m", 0, 0.0, runs=1)
    src = LoggedReplies(calllog, cfg, client, lim.day_of)
    ex = Exec(result())
    out = tmp_path / "out"
    dcfg = DriverConfig(model="m", runs=1)
    s = drive(its, out, src, ex, lambda i: {"a/b.py": "x = 1\n"}.get, dcfg, price)
    assert s.written == 2 and s.stopped == "complete"
    rows = latest_rows(out / "results.jsonl")
    r = rows[("i0", "bm25", 0)]
    assert r["resolved"] and r["calls"] == 1 and r["input_tokens"] == 1000
    assert r["cost_usd"] == pytest.approx((1000 * 1.0 + 200 * 10.0) / 1e6)
    # grade again from the log with no client: nothing is sent, finished rows are not repeated
    n_calls = len(list(calllog.rows()))
    src2 = LoggedReplies(CallLog(tmp_path / "log"), cfg)
    s2 = drive(its, out, src2, ex, lambda i: {"a/b.py": "x = 1\n"}.get, dcfg, price)
    assert s2.written == 0 and s2.skipped == 2 and len(list(calllog.rows())) == n_calls


def test_unfinished_units_are_skipped_without_a_client(tmp_path: Path) -> None:
    its = prepared(tmp_path, 1)
    src = LoggedReplies(CallLog(tmp_path / "log"), RunConfig("m", 0, 0.0, runs=1))
    s = drive(its, tmp_path / "out", src, Exec(result()), reader_for, DriverConfig(model="m"))
    assert s.written == 0 and s.not_available == 2


def test_spend_guard_stops_before_the_call_that_would_pass_the_cap(tmp_path: Path) -> None:
    its = prepared(tmp_path, 3)
    client, calllog, lim = harness(tmp_path, [ok_body(GOOD, 5000, 100)] * 20)
    price = Price("m", 1.0, 1.0, False, "d")
    guard = SpendGuard(cap_usd=0.0125, price=price, max_output_tokens=4096)
    cfg = RunConfig("m", 0, 0.0, runs=1)
    src = LoggedReplies(calllog, cfg, GuardedClient(client, guard), lim.day_of)
    s = drive(its, tmp_path / "out", src, Exec(result()), reader_for, DriverConfig("m"), price)
    assert s.stopped == "spend_cap" and guard.refused == 1
    assert guard.spent <= guard.cap_usd and guard.calls == len(list(calllog.rows()))
    # a restart counts the cost already logged before sending anything
    g2 = SpendGuard(cap_usd=0.0125, price=price, max_output_tokens=4096)
    g2.add_logged(calllog.rows())
    assert g2.spent == pytest.approx(guard.spent)


def test_guard_refuses_a_missing_or_nonpositive_cap() -> None:
    price = Price("m", 1.0, 1.0, False, "d")
    for bad in (0.0, -1.0, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            SpendGuard(cap_usd=bad, price=price, max_output_tokens=10)


def test_results_file_rows_are_valid_json_lines(tmp_path: Path) -> None:
    run_stored(tmp_path, {"a": reply("y = 2", "y = 3")}, Exec(result()))
    for line in (tmp_path / "out" / "results.jsonl").read_text().splitlines():
        assert json.loads(line)["driver"].startswith("rq3-driver/")
