"""Client for a messages-style chat API (a list of role/content turns), for the RQ3 model check.

Implements ``docs/RQ3_PILOT.md`` (D155). Same interface as ``GeminiClient``
(``generate(contents, wait_for_daily=...)`` giving a ``CallResult``), so the driver, the follow-up
policy, the spend guard and the call log are shared. Callers keep the one conversation format of the
pilot (``role`` ``user`` / ``model`` with text ``parts``); this module turns it into message turns.

Everything specific to the provider (endpoint, header names, version header, key variable) is
configuration read from the limits entry of the model (``MessagesConfig``), not code: the tracked
source stays provider-neutral. The key is read only from the configured environment variable or its
line in ``~/.ril_llm_env`` (mode 600), travels only in a request header, is held in a masked object
and is scrubbed from every string that reaches an exception or a log. Requests pass the persistent
limiter; 429 and 5xx (529 "overloaded" among them) are retried with exponential backoff and counted;
402 and a credit-balance message are a hard stop (``InsufficientBalance``), never retried.

Usage accounting: ``input_tokens`` is the billed input (cache tokens added if the API reports them);
``output_tokens`` is the billed output, which includes thinking tokens, as for Gemini;
``thought_tokens`` is read from ``usage.thinking_tokens`` when the API reports it and is
otherwise 0 (the thinking share is then inside ``output_tokens`` and not separable).
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from ril.agent.providers.gemini import (
    ApiKey,
    CallResult,
    InsufficientBalance,
    ProviderError,
    Transport,
    TransportError,
    UrllibTransport,
    canonical,
)
from ril.agent.providers.limiter import Clock, PersistentLimiter, SystemClock
from ril.util.log import get_logger

log = get_logger("providers.messages")

CHARS_PER_TOKEN_ESTIMATE = 3.0
"""Conservative characters-per-token used only to reserve limiter budget before the call."""
BALANCE_MARKERS = ("credit balance is too low", "insufficient credit", "insufficient balance")
REFUSAL_STOPS = ("refusal",)
CONNECTION_FIELDS = ("api_url", "key_variable", "key_header")
"""Entries a messages-style model must have in the limits file (extra headers are optional)."""


@dataclass(frozen=True)
class MessagesConfig:
    model: str
    api_url: str
    key_header: str
    extra_headers: Mapping[str, str] = field(default_factory=dict)
    temperature: float = 0.0
    max_output_tokens: int = 4096
    timeout_s: float = 180.0
    max_retries: int = 5
    backoff_base_s: float = 4.0
    backoff_cap_s: float = 120.0
    thinking_config: Mapping[str, Any] | None = None
    """Sent verbatim as the request's ``thinking`` field when set; omitted when ``None``."""


def connection_from_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    """The connection fields of a limits entry; ``KeyError`` names the first missing one."""
    for key in CONNECTION_FIELDS:
        if not str(entry.get(key, "")).strip():
            raise KeyError(f"limits entry has no {key}")
    return {
        "api_url": str(entry["api_url"]),
        "key_header": str(entry["key_header"]),
        "extra_headers": {str(k): str(v) for k, v in (entry.get("extra_headers") or {}).items()},
    }


def to_messages(contents: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Pilot-format turns (``user`` / ``model`` with text parts) as message turns."""
    out: list[dict[str, Any]] = []
    for turn in contents:
        role = "assistant" if turn["role"] == "model" else "user"
        text = "".join(str(p.get("text", "")) for p in turn.get("parts", []))
        out.append({"role": role, "content": text})
    return out


def request_body(config: MessagesConfig, contents: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": config.model,
        "max_tokens": config.max_output_tokens,
        "temperature": config.temperature,
        "messages": to_messages(contents),
    }
    if config.thinking_config is not None:
        body["thinking"] = dict(config.thinking_config)
    return body


def is_balance_error(status: int, text: str) -> bool:
    """402, or an error body that says the credit balance is gone (some APIs send a 400)."""
    low = text.lower()
    return status == 402 or any(m in low for m in BALANCE_MARKERS)


def parse_response(body: str) -> tuple[str, str, int, int, int, str | None]:
    """(text, stop reason, input, output, thought tokens, error code) of a 200 response."""
    try:
        data = json.loads(body)
        usage = data.get("usage", {}) or {}
        inp = (
            int(usage.get("input_tokens", 0))
            + int(usage.get("cache_creation_input_tokens", 0) or 0)
            + int(usage.get("cache_read_input_tokens", 0) or 0)
        )
        out = int(usage.get("output_tokens", 0))
        thought = int(usage.get("thinking_tokens", 0) or 0)
        blocks = data.get("content") or []
        stop = str(data.get("stop_reason") or "")
    except (ValueError, TypeError, AttributeError):
        return "", "", 0, 0, 0, "malformed_response"
    text = "".join(
        str(b.get("text", "")) for b in blocks if isinstance(b, dict) and b.get("type") == "text"
    )
    if not text and stop in REFUSAL_STOPS:
        return "", stop, inp, out, thought, "blocked"
    if not text:
        return "", stop, inp, out, thought, "malformed_response"
    return text, stop, inp, out, thought, None


class MessagesClient:
    def __init__(
        self,
        config: MessagesConfig,
        key: ApiKey,
        limiter: PersistentLimiter,
        transport: Transport | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.config = config
        self._key = key
        self.limiter = limiter
        self.transport: Transport = transport or UrllibTransport()
        self.clock: Clock = clock or SystemClock()

    def _scrub(self, text: str) -> str:
        return self._key.scrub(text)

    def generate(
        self, contents: Sequence[Mapping[str, Any]], *, wait_for_daily: bool = False
    ) -> CallResult:
        """Send one request (retries 429, 5xx, network faults); ``DailyCapReached`` at the cap."""
        body = canonical(request_body(self.config, contents))
        sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
        est = math.ceil(len(body) / CHARS_PER_TOKEN_ESTIMATE)
        headers = {
            "content-type": "application/json",
            **self.config.extra_headers,
            self.config.key_header: self._key.reveal(),
        }
        n429 = n5xx = retries = 0
        last_status = 0
        for attempt in range(self.config.max_retries + 1):
            grant = self.limiter.acquire(est, wait_for_daily=wait_for_daily)
            t0 = self.clock.time()
            try:
                resp = self.transport.post(
                    self.config.api_url, headers, body, self.config.timeout_s
                )
            except TransportError as err:
                self.limiter.settle(grant, est)
                last_status = 0
                retry_after = None
                log.warning("network fault: %s", self._scrub(str(err)))
            else:
                t1 = self.clock.time()
                last_status = resp.status
                if resp.status == 200:
                    text, stop, inp, out, thought, error = parse_response(resp.body)
                    self.limiter.settle(grant, inp if inp else est)
                    return CallResult(
                        text,
                        stop,
                        inp,
                        out,
                        thought,
                        200,
                        retries,
                        n429,
                        n5xx,
                        t1 - t0,
                        error,
                        sha,
                    )
                self.limiter.settle(grant, est)
                detail = self._scrub(resp.body[:300])
                if is_balance_error(resp.status, detail):
                    raise InsufficientBalance(resp.status, detail)
                if resp.status == 429:
                    n429 += 1
                elif resp.status >= 500:
                    n5xx += 1
                else:
                    raise ProviderError(resp.status, detail)
                ra = {k.lower(): v for k, v in resp.headers.items()}.get("retry-after", "")
                retry_after = float(ra) if ra.replace(".", "", 1).isdigit() else None
            if attempt == self.config.max_retries:
                break
            retries += 1
            backoff = min(self.config.backoff_cap_s, self.config.backoff_base_s * 2**attempt)
            self.clock.sleep(max(backoff, retry_after or 0.0))
        log.warning("retries exhausted (last status %s)", last_status)
        return CallResult(
            "", "", 0, 0, 0, last_status, retries, n429, n5xx, 0.0, "retries_exhausted", sha
        )
