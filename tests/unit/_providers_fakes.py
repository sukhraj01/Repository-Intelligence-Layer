"""Shared fakes for the provider tests: a manual clock and a scripted (recorded) transport."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any

from ril.agent.providers.gemini import HttpResponse, TransportError


class FakeClock:
    def __init__(self, start: float) -> None:
        self.now = start
        self.slept: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += max(0.0, seconds)


def ok_body(text: str, inp: int = 100, out: int = 20, finish: str = "STOP") -> str:
    return json.dumps(
        {
            "candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": finish}],
            "usageMetadata": {"promptTokenCount": inp, "candidatesTokenCount": out},
        }
    )


class FakeTransport:
    """Replays queued responses (or calls a function); records every request it sees."""

    def __init__(self, script: list[Any] | Callable[[str], Any]) -> None:
        self.script = script
        self.requests: list[tuple[str, Mapping[str, str], str]] = []

    def post(self, url: str, headers: Mapping[str, str], body: str, timeout: float) -> HttpResponse:
        self.requests.append((url, dict(headers), body))
        item = self.script(body) if callable(self.script) else self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, HttpResponse):
            return item
        return HttpResponse(200, item, {})


def http(status: int, body: str = "{}", headers: Mapping[str, str] | None = None) -> HttpResponse:
    return HttpResponse(status, body, dict(headers or {}))


__all__ = ["FakeClock", "FakeTransport", "TransportError", "http", "ok_body"]
