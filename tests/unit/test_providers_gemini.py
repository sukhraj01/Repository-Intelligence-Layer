"""Gemini client on a recorded fake transport: retries, bad replies, the key stays secret."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from ril.agent.providers.gemini import (
    ApiKey,
    ApiKeyError,
    GeminiClient,
    GeminiConfig,
    ProviderError,
    TransportError,
    load_api_key,
    parse_response,
)
from ril.agent.providers.limiter import Limits, PersistentLimiter
from tests.unit._providers_fakes import FakeClock, FakeTransport, http, ok_body

SECRET = "AIzaSy-TEST-SECRET-0123456789"
CONTENTS = [{"role": "user", "parts": [{"text": "hello"}]}]


def make(
    tmp_path: Path, script: list[object], max_retries: int = 5
) -> tuple[GeminiClient, FakeTransport, FakeClock]:
    clk = FakeClock(1_800_000_000.0)
    lim = PersistentLimiter(
        Limits("m", 1000, 10_000_000, 10_000, "x", margin=1.0), tmp_path / "lim.jsonl", clk
    )
    tr = FakeTransport(list(script))
    client = GeminiClient(
        GeminiConfig(model="m", max_retries=max_retries), ApiKey(SECRET), lim, tr, clk
    )
    return client, tr, clk


def test_success_records_tokens_and_sends_the_key_only_in_a_header(tmp_path: Path) -> None:
    client, tr, _ = make(tmp_path, [ok_body("hi", 120, 7)])
    r = client.generate(CONTENTS)
    assert (r.text, r.input_tokens, r.output_tokens, r.status, r.retries, r.error) == (
        "hi",
        120,
        7,
        200,
        0,
        None,
    )
    url, headers, body = tr.requests[0]
    assert SECRET not in url and SECRET not in body and headers["x-goog-api-key"] == SECRET
    assert json.loads(body)["generationConfig"] == {
        "temperature": 0.0,
        "seed": 0,
        "maxOutputTokens": 4096,
    }


def test_429_and_5xx_are_retried_with_backoff_and_counted(tmp_path: Path) -> None:
    client, _, clk = make(
        tmp_path, [http(429, headers={"Retry-After": "30"}), http(503), ok_body("x")]
    )
    r = client.generate(CONTENTS)
    assert (r.n_429, r.n_5xx, r.retries, r.status, r.error) == (1, 1, 2, 200, None)
    assert clk.slept[0] == 30.0 and clk.slept[1] == 8.0  # Retry-After beats 4 s; then 4 * 2**1


def test_a_network_fault_is_retried(tmp_path: Path) -> None:
    client, _, _ = make(tmp_path, [TransportError("TimeoutError"), ok_body("x")])
    assert client.generate(CONTENTS).retries == 1


def test_retries_exhausted_is_reported_not_raised(tmp_path: Path) -> None:
    client, tr, _ = make(tmp_path, [http(429)] * 3, max_retries=2)
    r = client.generate(CONTENTS)
    assert r.error == "retries_exhausted" and r.n_429 == 3 and len(tr.requests) == 3


def test_a_client_error_raises_and_the_message_hides_the_key(tmp_path: Path) -> None:
    client, _, _ = make(tmp_path, [http(400, f'{{"error":"bad key {SECRET}"}}')])
    with pytest.raises(ProviderError) as err:
        client.generate(CONTENTS)
    assert SECRET not in str(err.value) and err.value.status == 400


def test_the_key_never_reaches_logs_or_files(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    client, _, _ = make(
        tmp_path, [http(500, f"echo {SECRET}"), TransportError(f"conn {SECRET}"), ok_body("x")]
    )
    with caplog.at_level("DEBUG"):
        client.generate(CONTENTS)
    assert SECRET not in caplog.text
    for p in tmp_path.rglob("*"):
        if p.is_file():
            assert SECRET not in p.read_text(encoding="utf-8")
    assert SECRET not in repr(ApiKey(SECRET)) and SECRET not in str(ApiKey(SECRET))


@pytest.mark.parametrize(
    ("body", "error"),
    [
        ("not json", "malformed_response"),
        (json.dumps({"candidates": []}), "malformed_response"),
        (json.dumps({"promptFeedback": {"blockReason": "SAFETY"}}), "blocked"),
        (json.dumps({"candidates": [{"finishReason": "SAFETY"}]}), "blocked"),
        (
            json.dumps({"candidates": [{"content": {"parts": []}, "finishReason": "STOP"}]}),
            "malformed_response",
        ),
    ],
)
def test_malformed_and_blocked_replies(body: str, error: str) -> None:
    assert parse_response(body)[5] == error


def test_thought_tokens_count_as_output_and_are_not_text() -> None:
    body = json.dumps(
        {
            "candidates": [
                {
                    "content": {"parts": [{"text": "think", "thought": True}, {"text": "answer"}]},
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 5,
                "thoughtsTokenCount": 40,
            },
        }
    )
    text, _, inp, out, thought, err = parse_response(body)
    assert (text, inp, out, thought, err) == ("answer", 10, 45, 40, None)


def test_key_file_is_read_and_must_be_mode_600(tmp_path: Path) -> None:
    f = tmp_path / "env"
    f.write_text(f"# comment\nexport GEMINI_API_KEY='{SECRET}'\n", encoding="utf-8")
    os.chmod(f, 0o644)
    with pytest.raises(ApiKeyError) as err:
        load_api_key({}, f)
    assert SECRET not in str(err.value)
    os.chmod(f, 0o600)
    assert load_api_key({}, f).reveal() == SECRET
    assert (
        load_api_key({"GEMINI_API_KEY": "from-env"}, f).reveal() == "from-env"
    )  # environment wins
    with pytest.raises(ApiKeyError):
        load_api_key({}, tmp_path / "missing")
    f.write_text("export OTHER=1\n", encoding="utf-8")
    with pytest.raises(ApiKeyError):
        load_api_key({}, f)
