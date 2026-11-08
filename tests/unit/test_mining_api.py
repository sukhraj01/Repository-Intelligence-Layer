"""API client behaviour against scripted responses and a fake clock (E-MINE-PILOT, M0 gate)."""

from __future__ import annotations

import json

import pytest

from ril.data_mining.github_api import (
    ApiClient,
    ApiError,
    ClientConfig,
    EtagStore,
    HttpResponse,
    NotFound,
    TransportError,
    token_from_env,
    token_present,
)
from tests.unit._mining_fixtures import FakeClock, FakeTransport, json_response

CFG = ClientConfig(retries=3, network_retries=None, min_interval=0.0)


def client(tr: FakeTransport, clock: FakeClock, **kw) -> ApiClient:
    return ApiClient(tr, clock=clock, config=kw.pop("config", CFG), **kw)


def test_get_returns_json_and_counts_the_call() -> None:
    tr, clock = FakeTransport(), FakeClock()
    tr.add("GET", "/repos/a/b/compare", lambda u, b: json_response({"ok": 1}))
    c = client(tr, clock)
    assert c.get_json("/repos/a/b/compare/x...y", {"per_page": 100, "page": 1}) == {"ok": 1}
    assert c.budget.calls == 1 and c.budget.by_endpoint == {"repos/compare": 1}
    assert "page=1" in tr.calls[0][1] and "per_page=100" in tr.calls[0][1]


def test_etag_conditional_request_serves_cached_body_on_304(tmp_path) -> None:
    tr, clock = FakeTransport(), FakeClock()
    store = EtagStore(str(tmp_path))
    tr.queue = [
        json_response({"v": 1}, headers={"etag": '"abc"'}),
        HttpResponse(304, {"x-ratelimit-remaining": "4899"}, b""),
    ]
    c = client(tr, clock, etags=store)
    assert c.get_json("/repos/a/b/pulls/1") == {"v": 1}
    assert c.get_json("/repos/a/b/pulls/1") == {"v": 1}
    assert tr.headers[0].get("If-None-Match") is None
    assert tr.headers[1]["If-None-Match"] == '"abc"'
    assert c.budget.not_modified == 1


def test_server_errors_retry_with_backoff_then_succeed() -> None:
    tr, clock = FakeTransport(), FakeClock()
    tr.queue = [
        HttpResponse(502, {}, b"bad"),
        HttpResponse(503, {}, b"bad"),
        json_response({"ok": 1}),
    ]
    c = client(tr, clock)
    assert c.get_json("/repos/a/b/x") == {"ok": 1}
    assert clock.slept == [2.0, 4.0] and c.budget.retries == 2


def test_network_errors_retry_then_raise() -> None:
    tr, clock = FakeTransport(), FakeClock()
    tr.queue = [TransportError("reset")] * 4
    c = client(tr, clock)
    with pytest.raises(TransportError):
        c.get_json("/repos/a/b/x")
    assert len(tr.calls) == 4


def test_network_outage_is_ridden_out_up_to_the_network_retry_limit() -> None:
    tr, clock = FakeTransport(), FakeClock()
    tr.queue = [TransportError("name resolution")] * 6 + [json_response({"ok": 1})]
    cfg = ClientConfig(retries=3, network_retries=6, min_interval=0.0)
    c = client(tr, clock, config=cfg)
    assert c.get_json("/repos/a/b/x") == {"ok": 1}
    assert clock.slept == [2.0, 4.0, 8.0, 16.0, 32.0, 64.0]
    tr2, clock2 = FakeTransport(), FakeClock()
    tr2.queue = [TransportError("name resolution")] * 8
    with pytest.raises(TransportError):
        client(tr2, clock2, config=cfg).get_json("/repos/a/b/x")
    assert len(tr2.calls) == 7  # the first call plus six retries


def test_server_errors_after_a_network_outage_still_stop_at_the_retry_limit() -> None:
    tr, clock = FakeTransport(), FakeClock()
    tr.queue = [TransportError("reset")] * 5 + [HttpResponse(502, {}, b"bad")] * 6
    cfg = ClientConfig(retries=3, network_retries=6, min_interval=0.0)
    with pytest.raises(ApiError):
        client(tr, clock, config=cfg).get_json("/repos/a/b/x")
    assert len(tr.calls) == 6  # five resets, then one 502 past the server-error limit


def test_default_client_tolerates_a_quarter_hour_outage() -> None:
    cfg = ClientConfig()
    assert cfg.network_retries == 12 and cfg.retries == 8
    assert sum(min(cfg.backoff_cap, cfg.backoff_base * 2**i) for i in range(12)) > 840


def test_not_found_is_not_retried() -> None:
    tr, clock = FakeTransport(), FakeClock()
    c = client(tr, clock)
    with pytest.raises(NotFound):
        c.get_json("/repos/a/b/missing")
    assert len(tr.calls) == 1 and clock.slept == []


def test_other_client_errors_raise_without_retry() -> None:
    tr, clock = FakeTransport(), FakeClock()
    tr.queue = [HttpResponse(422, {}, b"unprocessable")]
    with pytest.raises(ApiError) as err:
        client(tr, clock).get_json("/repos/a/b/x")
    assert err.value.status == 422 and len(tr.calls) == 1


def test_retry_after_is_honoured() -> None:
    tr, clock = FakeTransport(), FakeClock()
    tr.queue = [HttpResponse(403, {"retry-after": "7"}, b"slow down"), json_response({"ok": 1})]
    assert client(tr, clock).get_json("/repos/a/b/x") == {"ok": 1}
    assert clock.slept == [8.0]


def test_exhausted_primary_limit_sleeps_to_reset() -> None:
    tr, clock = FakeTransport(), FakeClock(start=1000.0)
    tr.queue = [
        HttpResponse(403, {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1030"}, b"limit"),
        json_response({"ok": 1}),
    ]
    assert client(tr, clock).get_json("/repos/a/b/x") == {"ok": 1}
    assert clock.slept == [31.0]


def test_secondary_rate_limit_backs_off_exponentially() -> None:
    tr, clock = FakeTransport(), FakeClock()
    body = b'{"message": "You have exceeded a secondary rate limit"}'
    tr.queue = [HttpResponse(403, {}, body), HttpResponse(403, {}, body), json_response({"ok": 1})]
    assert client(tr, clock).get_json("/repos/a/b/x") == {"ok": 1}
    assert clock.slept == [60.0, 120.0]


def test_plain_forbidden_is_a_refusal_not_a_limit() -> None:
    tr, clock = FakeTransport(), FakeClock()
    tr.queue = [HttpResponse(403, {}, b'{"message": "Repository access blocked"}')]
    with pytest.raises(ApiError):
        client(tr, clock).get_json("/repos/a/b/x")
    assert clock.slept == [] and len(tr.calls) == 1


def test_client_waits_for_reset_when_the_reserve_is_reached() -> None:
    tr, clock = FakeTransport(), FakeClock(start=1000.0)
    tr.add(
        "GET",
        "/repos",
        lambda u, b: json_response(
            {"ok": 1}, headers={"x-ratelimit-remaining": "5", "x-ratelimit-reset": "1100"}
        ),
    )
    c = client(tr, clock, config=ClientConfig(retries=3, min_interval=0.0, reserve=10))
    c.get_json("/repos/a/b/1")
    c.get_json("/repos/a/b/2")
    assert clock.slept == [101.0]


def test_wait_beyond_max_wait_raises() -> None:
    tr, clock = FakeTransport(), FakeClock(start=1000.0)
    tr.queue = [
        HttpResponse(403, {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "999999"}, b"x")
    ]
    with pytest.raises(ApiError):
        client(tr, clock).get_json("/repos/a/b/x")


def test_graphql_returns_data_and_adds_cost() -> None:
    tr, clock = FakeTransport(), FakeClock()
    doc = {"data": {"repository": {}, "rateLimit": {"cost": 7, "remaining": 4000}}}
    tr.add("POST", "/graphql", lambda u, b: json_response(doc))
    c = client(tr, clock)
    data = c.graphql("query { x }", {"a": 1})
    assert data["rateLimit"]["cost"] == 7 and c.budget.graphql_cost == 7
    assert c.budget.graphql_calls == 1 and c.budget.remaining == 4000


def test_graphql_rate_limited_error_waits_and_retries() -> None:
    tr, clock = FakeTransport(), FakeClock(start=1000.0)
    limited = {"errors": [{"type": "RATE_LIMITED", "message": "API rate limit exceeded"}]}
    ok = {"data": {"repository": {}}}
    tr.queue = [
        json_response(limited, headers={"x-ratelimit-reset": "1020", "x-ratelimit-remaining": "0"}),
        json_response(ok),
    ]
    assert client(tr, clock).graphql("q", {}) == {"repository": {}}
    assert clock.slept == [21.0]


def test_graphql_not_found_and_hard_errors() -> None:
    tr, clock = FakeTransport(), FakeClock()
    tr.queue = [
        json_response({"data": None, "errors": [{"type": "NOT_FOUND", "message": "no repo"}]}),
        json_response({"errors": [{"type": "X", "message": "boom"}]}),
    ]
    c = client(tr, clock)
    with pytest.raises(NotFound):
        c.graphql("q", {})
    with pytest.raises(ApiError):
        c.graphql("q", {})


def test_token_goes_in_the_header_only_and_never_in_repr_or_events(monkeypatch) -> None:
    secret = "sentinel-token-" + "S" * 24
    tr, clock = FakeTransport(), FakeClock()
    tr.add("GET", "/repos", lambda u, b: json_response({"ok": 1}))
    events: list[dict] = []
    c = ApiClient(tr, token=secret, clock=clock, config=CFG, sink=events.append)
    c.get_json("/repos/a/b/x")
    assert tr.headers[0]["Authorization"] == f"Bearer {secret}"
    assert secret not in repr(c)
    assert secret not in json.dumps(events) and secret not in json.dumps(c.budget.to_dict())
    anon = ApiClient(tr, clock=clock, config=CFG)
    anon.get_json("/repos/a/b/x")
    assert "Authorization" not in tr.headers[1]
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert token_from_env() is None and not token_present()
    monkeypatch.setenv("GITHUB_TOKEN", secret)
    assert token_present() and token_from_env() == secret


def test_pacing_sleeps_between_calls() -> None:
    tr, clock = FakeTransport(), FakeClock()
    tr.add("GET", "/repos", lambda u, b: json_response({}))
    c = client(tr, clock, config=ClientConfig(retries=1, min_interval=0.5))
    c.get_json("/repos/a/b/1")
    c.get_json("/repos/a/b/2")
    assert clock.slept == [0.5]


def test_cut_response_body_is_a_transport_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import http.client

    from ril.data_mining.github_api import UrllibTransport

    def cut(*args: object, **kwargs: object) -> object:
        raise http.client.IncompleteRead(b"x" * 10, 5)

    monkeypatch.setattr("urllib.request.urlopen", cut)
    with pytest.raises(TransportError):
        UrllibTransport().send("POST", "https://api.github.com/graphql", {}, b"{}")
