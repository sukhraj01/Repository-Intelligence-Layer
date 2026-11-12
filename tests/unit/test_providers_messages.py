"""Messages-style adapter on a scripted transport (no network).

Request shape, usage, retries, hard stop on a missing balance, secrecy of the key, and the same
record shape as the Gemini adapter."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ril.agent.providers.calllog import CallLog
from ril.agent.providers.gemini import (
    ApiKey,
    ApiKeyError,
    GeminiClient,
    GeminiConfig,
    InsufficientBalance,
    ProviderError,
    TransportError,
    load_api_key,
)
from ril.agent.providers.limiter import Limits, PersistentLimiter
from ril.agent.providers.messages_api import (
    MessagesClient,
    MessagesConfig,
    connection_from_entry,
    is_balance_error,
    parse_response,
    request_body,
    to_messages,
)
from ril.agent.providers.pilot_run import RunConfig, run_units
from ril.agent.providers.spend import GuardedClient, Price, SpendGuard
from tests.unit._providers_fakes import FakeClock, FakeTransport, http, ok_body

SECRET = "sk-TEST-SECRET-0123456789"
URL = "https://api.example.invalid/v1/messages"
CONN = {"api_url": URL, "key_header": "x-test-key", "extra_headers": {"x-test-version": "1"}}
CONTENTS = [{"role": "user", "parts": [{"text": "hello"}]}]
GOOD = "FILE: a/b.py\n<<<<<<< SEARCH\nx = 1\n=======\nx = 2\n>>>>>>> REPLACE\n"


def msg_body(text: str, inp: int = 100, out: int = 20, stop: str = "end_turn", **usage: int) -> str:
    return json.dumps(
        {
            "type": "message",
            "content": [{"type": "text", "text": text}],
            "stop_reason": stop,
            "usage": {"input_tokens": inp, "output_tokens": out, **usage},
        }
    )


def make(
    tmp_path: Path, script: list[Any], max_retries: int = 5, **cfg: Any
) -> tuple[MessagesClient, FakeTransport, FakeClock]:
    clk = FakeClock(1_800_000_000.0)
    lim = PersistentLimiter(
        Limits("m", 1000, 10_000_000, 10_000, "x", margin=1.0), tmp_path / "lim.jsonl", clk
    )
    tr = FakeTransport(list(script))
    client = MessagesClient(
        MessagesConfig(model="m", max_retries=max_retries, **CONN, **cfg),
        ApiKey(SECRET),
        lim,
        tr,
        clk,
    )
    return client, tr, clk


def test_success_sends_messages_and_the_key_only_in_a_header(tmp_path: Path) -> None:
    client, tr, _ = make(tmp_path, [msg_body("hi", 120, 7)])
    r = client.generate(CONTENTS)
    assert (r.text, r.finish_reason, r.input_tokens, r.output_tokens, r.thought_tokens) == (
        "hi",
        "end_turn",
        120,
        7,
        0,
    )
    assert (r.status, r.retries, r.error) == (200, 0, None)
    url, headers, body = tr.requests[0]
    assert url == URL
    assert SECRET not in url and SECRET not in body
    assert headers["x-test-key"] == SECRET and headers["x-test-version"] == "1"
    sent = json.loads(body)
    assert sent == {
        "model": "m",
        "max_tokens": 4096,
        "temperature": 0.0,
        "messages": [{"role": "user", "content": "hello"}],
    }


def test_thinking_is_sent_only_when_set_and_followups_map_to_assistant_turns() -> None:
    base = request_body(MessagesConfig(model="m", **CONN), [])
    assert "thinking" not in base
    pinned = request_body(
        MessagesConfig(
            model="m", **CONN, thinking_config={"type": "enabled", "budget_tokens": 1024}
        ),
        [],
    )
    assert pinned["thinking"] == {"type": "enabled", "budget_tokens": 1024}
    turns = [
        {"role": "user", "parts": [{"text": "a"}]},
        {"role": "model", "parts": [{"text": "b"}, {"text": "c"}]},
        {"role": "user", "parts": [{"text": "d"}]},
    ]
    assert to_messages(turns) == [
        {"role": "user", "content": "a"},
        {"role": "assistant", "content": "bc"},
        {"role": "user", "content": "d"},
    ]


def test_usage_includes_cache_tokens_and_reports_thinking_only_when_given() -> None:
    text, stop, inp, out, thought, err = parse_response(
        msg_body("t", 10, 5, cache_creation_input_tokens=3, cache_read_input_tokens=2)
    )
    assert (text, stop, inp, out, thought, err) == ("t", "end_turn", 15, 5, 0, None)
    assert parse_response(msg_body("t", 10, 50, thinking_tokens=40))[4] == 40
    thinking_block = json.dumps(
        {
            "content": [{"type": "thinking", "thinking": "hmm"}, {"type": "text", "text": "ok"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 1, "output_tokens": 2},
        }
    )
    assert parse_response(thinking_block)[0] == "ok"  # thinking blocks never reach the reply


def test_refusal_empty_and_malformed_replies() -> None:
    refusal = json.dumps(
        {"content": [], "stop_reason": "refusal", "usage": {"input_tokens": 4, "output_tokens": 0}}
    )
    assert parse_response(refusal)[5] == "blocked"
    empty = json.dumps(
        {"content": [], "stop_reason": "end_turn", "usage": {"input_tokens": 4, "output_tokens": 0}}
    )
    assert parse_response(empty)[5] == "malformed_response"
    assert parse_response("not json")[5] == "malformed_response"


def test_retries_429_5xx_and_network_faults_with_backoff(tmp_path: Path) -> None:
    client, tr, clk = make(
        tmp_path,
        [
            http(429, headers={"Retry-After": "7"}),
            http(529),
            TransportError("Timeout"),
            msg_body("ok"),
        ],
    )
    r = client.generate(CONTENTS)
    assert (r.text, r.retries, r.n_429, r.n_5xx, r.status) == ("ok", 3, 1, 1, 200)
    assert len(tr.requests) == 4 and clk.slept[0] >= 7.0


def test_retries_exhausted_is_reported_not_raised(tmp_path: Path) -> None:
    client, _, _ = make(tmp_path, [http(500)] * 3, max_retries=2)
    r = client.generate(CONTENTS)
    assert r.error == "retries_exhausted" and r.status == 500 and r.retries == 2


def test_other_client_errors_raise_and_are_not_retried(tmp_path: Path) -> None:
    client, tr, _ = make(tmp_path, [http(401, '{"error":{"message":"invalid key"}}')])
    with pytest.raises(ProviderError) as exc:
        client.generate(CONTENTS)
    assert exc.value.status == 401 and not isinstance(exc.value, InsufficientBalance)
    assert len(tr.requests) == 1


@pytest.mark.parametrize(
    "status,body",
    [
        (402, "{}"),
        (400, '{"error":{"message":"Your credit balance is too low to access the API."}}'),
    ],
)
def test_missing_balance_is_a_hard_stop_never_retried(
    tmp_path: Path, status: int, body: str
) -> None:
    client, tr, _ = make(tmp_path, [http(status, body)])
    with pytest.raises(InsufficientBalance):
        client.generate(CONTENTS)
    assert len(tr.requests) == 1
    assert is_balance_error(status, body)
    assert not is_balance_error(400, '{"error":{"message":"max_tokens too large"}}')


def test_gemini_402_is_the_same_hard_stop(tmp_path: Path) -> None:
    clk = FakeClock(1_800_000_000.0)
    lim = PersistentLimiter(
        Limits("m", 1000, 10_000_000, 10_000, "x", margin=1.0), tmp_path / "l", clk
    )
    tr = FakeTransport([http(402, "{}")])
    client = GeminiClient(GeminiConfig(model="m"), ApiKey(SECRET), lim, tr, clk)
    with pytest.raises(InsufficientBalance):
        client.generate(CONTENTS)
    assert len(tr.requests) == 1


def test_the_key_is_scrubbed_from_error_details(tmp_path: Path) -> None:
    client, _, _ = make(tmp_path, [http(400, f'{{"error":"bad {SECRET}"}}')])
    with pytest.raises(ProviderError) as exc:
        client.generate(CONTENTS)
    assert SECRET not in str(exc.value) and "***" in str(exc.value)
    assert SECRET not in repr(ApiKey(SECRET)) and SECRET not in str(ApiKey(SECRET))


def test_keys_come_from_their_own_variable_and_the_shared_file(tmp_path: Path) -> None:
    f = tmp_path / "env"
    f.write_text("export GEMINI_API_KEY=g-key\nexport OTHER_PROVIDER_KEY='o-key'\n")
    f.chmod(0o600)
    assert load_api_key({}, f, variable="OTHER_PROVIDER_KEY").reveal() == "o-key"
    assert load_api_key({}, f).reveal() == "g-key"
    assert (
        load_api_key({"OTHER_PROVIDER_KEY": "from-env"}, f, variable="OTHER_PROVIDER_KEY").reveal()
        == "from-env"
    )
    f.write_text("export GEMINI_API_KEY=g-key\n")
    with pytest.raises(ApiKeyError):
        load_api_key({}, f, variable="OTHER_PROVIDER_KEY")
    f.chmod(0o644)
    with pytest.raises(ApiKeyError):
        load_api_key({}, f, variable="OTHER_PROVIDER_KEY")


def test_connection_fields_come_from_the_limits_entry() -> None:
    entry = {"api_url": URL, "key_variable": "V", "key_header": "h", "extra_headers": {"a": 1}}
    assert connection_from_entry(entry) == {
        "api_url": URL,
        "key_header": "h",
        "extra_headers": {"a": "1"},
    }
    with pytest.raises(KeyError):
        connection_from_entry({"api_url": URL})


# ---------------------------------------------------------------- the driver sees one record shape


def gemini_body(text: str) -> str:
    return ok_body(text, 100, 20)


def run_one(tmp_path: Path, client: Any, model: str) -> list[dict[str, Any]]:
    log = CallLog(tmp_path / "log")
    items = [
        {
            "instance_id": "i1",
            "arm": "rrf",
            "prompt": "fix x",
            "paths": ["a/b.py"],
            "budget": 8000,
            "first_stage": "rrf",
            "template_version": "t",
        }
    ]
    cfg = RunConfig(model=model, seed=0, temperature=0.0, runs=1)
    summary = run_units(items, log, client, cfg, lambda t: "2026-11-12")
    assert summary.stopped == "complete"
    return list(log.rows())


def test_both_adapters_give_the_driver_the_same_record_shape(tmp_path: Path) -> None:
    # a first reply that is not an edit, then a good one: exercises the follow-up path too
    a_client, _, _ = make(tmp_path / "a", [msg_body("no edit"), msg_body(GOOD)])
    clk = FakeClock(1_800_000_000.0)
    lim = PersistentLimiter(
        Limits("g", 1000, 10_000_000, 10_000, "x", margin=1.0), tmp_path / "gl", clk
    )
    g_client = GeminiClient(
        GeminiConfig(model="g"),
        ApiKey("k"),
        lim,
        FakeTransport([gemini_body("no edit"), gemini_body(GOOD)]),
        clk,
    )
    a_rows = run_one(tmp_path / "a", a_client, "messages-model")
    g_rows = run_one(tmp_path / "g", g_client, "gemini-x")
    assert len(a_rows) == len(g_rows) == 2
    for a, g in zip(a_rows, g_rows, strict=True):
        assert set(a) == set(g)
        for key in ("input_tokens", "output_tokens", "thought_tokens", "attempt", "final"):
            assert a[key] == g[key], key
        assert type(a["latency_s"]) is type(g["latency_s"])
        assert a["kind"] == g["kind"] == "reply"
    assert [r["patch_ok"] for r in a_rows] == [False, True]
    assert a_rows[0]["format_error"] == "no_edit_block"
    # the driver's own reader gets the same Reply from either log
    from ril.agent.providers.driver import reply_from_rows

    ra = reply_from_rows(a_rows, CallLog(tmp_path / "a" / "log"))
    rg = reply_from_rows(g_rows, CallLog(tmp_path / "g" / "log"))
    assert ra is not None and rg is not None
    assert (ra.text, ra.usable, ra.calls, ra.input_tokens, ra.output_tokens) == (
        rg.text,
        rg.usable,
        rg.calls,
        rg.input_tokens,
        rg.output_tokens,
    )


def test_usage_feeds_the_spend_guard_and_the_cap_stops_the_run(tmp_path: Path) -> None:
    client, tr, _ = make(tmp_path, [msg_body(GOOD, 1_000_000, 100_000)] * 3)
    price = Price("m", 1.0, 5.0, True, "2026-11-12")
    guard = SpendGuard(cap_usd=2.0, price=price, max_output_tokens=4096)
    guarded = GuardedClient(client, guard)
    log = CallLog(tmp_path / "log")
    items = [
        {"instance_id": f"i{k}", "arm": "rrf", "prompt": "fix", "paths": ["a/b.py"]}
        for k in range(3)
    ]
    summary = run_units(items, log, guarded, RunConfig("m", 0, 0.0, runs=1), lambda t: "d")
    # the guard bounds a call by its worst case, not by the usage of the last one: after 1.5 USD of
    # a 2.0 cap a second call (worst case 0.02) is allowed, the third is refused at 3.0 spent
    assert summary.stopped == "spend_cap"
    assert guard.spent == pytest.approx(2 * (1.0 * 1 + 5.0 * 0.1))
    assert len(tr.requests) == 2 and summary.units_finished == 2 and guard.refused == 1


def test_insufficient_balance_ends_the_run_cleanly_and_is_resumable(tmp_path: Path) -> None:
    client, _, _ = make(tmp_path, [msg_body(GOOD), http(402, "{}")])
    log = CallLog(tmp_path / "log")
    items = [
        {"instance_id": f"i{k}", "arm": "rrf", "prompt": "fix", "paths": ["a/b.py"]}
        for k in range(2)
    ]
    summary = run_units(items, log, client, RunConfig("m", 0, 0.0, runs=1), lambda t: "d")
    assert summary.stopped == "insufficient_balance" and summary.units_finished == 1
    assert len(list(log.rows())) == 1  # nothing was logged for the refused call
    again, _, _ = make(tmp_path / "again", [msg_body(GOOD)])
    resumed = run_units(items, log, again, RunConfig("m", 0, 0.0, runs=1), lambda t: "d")
    assert resumed.stopped == "complete" and resumed.units_skipped == 1
    assert len(list(log.rows())) == 2


def test_sources_never_contain_a_key_shaped_literal() -> None:
    src = Path(__file__).resolve().parents[2] / "ril" / "agent" / "providers" / "messages_api.py"
    text = src.read_text(encoding="utf-8")
    assert "sk-" not in text
