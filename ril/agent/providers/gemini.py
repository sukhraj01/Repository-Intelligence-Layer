"""Client for the Gemini ``generateContent`` API (developer API), for the RQ3 pilot.

Implements ``docs/RQ3_PILOT.md`` ("Provider adapter"). The key is read only from
``~/.ril_llm_env`` (a line ``export GEMINI_API_KEY=...``, permission 600) or the environment
variable, travels only in a request header, is held in an object whose text form is masked,
and is scrubbed from every string that reaches an exception or a log. All requests go
through a persistent limiter (``limiter.py``); 429 and 5xx responses are retried with
exponential backoff and counted.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import stat
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ril.agent.providers.limiter import Clock, PersistentLimiter, SystemClock
from ril.util.log import get_logger

log = get_logger("providers.gemini")

API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"
KEY_VARIABLE = "GEMINI_API_KEY"
DEFAULT_KEY_FILE = "~/.ril_llm_env"
CHARS_PER_TOKEN_ESTIMATE = 3.0
"""Conservative characters-per-token used only to reserve limiter budget before the call."""


class ApiKeyError(Exception):
    """The key is missing or its file is unsafe; the message never contains the key."""


class ApiKey:
    """A secret with a masked ``repr`` and ``str``; ``reveal`` only builds the header."""

    __slots__ = ("_v",)

    def __init__(self, value: str) -> None:
        if not value.strip():
            raise ApiKeyError("the API key is empty")
        self._v = value.strip()

    def reveal(self) -> str:
        return self._v

    def __repr__(self) -> str:
        return "ApiKey(***)"

    __str__ = __repr__

    def scrub(self, text: str) -> str:
        return text.replace(self._v, "***")


def load_api_key(
    env: Mapping[str, str] | None = None,
    path: str | Path = DEFAULT_KEY_FILE,
    variable: str = KEY_VARIABLE,
) -> ApiKey:
    """The provider's environment variable if set, else its line in the key file (refused unless
    the file is mode 600). ``variable`` names the provider's variable; the file may hold several."""
    environ = os.environ if env is None else env
    if environ.get(variable, "").strip():
        return ApiKey(environ[variable])
    p = Path(path).expanduser()
    if not p.exists():
        raise ApiKeyError(f"no {variable} in the environment and no key file at {p}")
    if p.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise ApiKeyError(f"key file {p} is readable by others; run: chmod 600 {p}")
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("export "):
            s = s[len("export ") :].strip()
        if s.startswith(f"{variable}="):
            return ApiKey(s.split("=", 1)[1].strip().strip("'\""))
    raise ApiKeyError(f"key file {p} has no line 'export {variable}=...'")


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: str
    headers: Mapping[str, str]


class TransportError(Exception):
    """A network failure (no HTTP response); the message is scrubbed by the client."""


class Transport(Protocol):
    def post(
        self, url: str, headers: Mapping[str, str], body: str, timeout: float
    ) -> HttpResponse: ...


class UrllibTransport:
    """Real transport (standard library). Not used in tests, which use a recorded fake."""

    def post(self, url: str, headers: Mapping[str, str], body: str, timeout: float) -> HttpResponse:
        req = urllib.request.Request(
            url, data=body.encode("utf-8"), headers=dict(headers), method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed https root)
                return HttpResponse(
                    resp.status, resp.read().decode("utf-8", "replace"), dict(resp.headers)
                )
        except urllib.error.HTTPError as err:
            return HttpResponse(err.code, err.read().decode("utf-8", "replace"), dict(err.headers))
        except (urllib.error.URLError, TimeoutError, OSError) as err:
            raise TransportError(type(err).__name__) from None


@dataclass(frozen=True)
class GeminiConfig:
    model: str
    temperature: float = 0.0
    seed: int = 0
    max_output_tokens: int = 4096
    timeout_s: float = 180.0
    max_retries: int = 5
    backoff_base_s: float = 4.0
    backoff_cap_s: float = 120.0
    thinking_config: Mapping[str, Any] | None = None
    """Sent verbatim as ``generationConfig.thinkingConfig`` when set; omitted (the request bytes of
    the pilot) when ``None``, so the provider's default applies."""


@dataclass(frozen=True)
class CallResult:
    """One logical call (all its retries). ``error`` is None for a usable response."""

    text: str
    finish_reason: str
    input_tokens: int
    output_tokens: int
    thought_tokens: int
    status: int
    retries: int
    n_429: int
    n_5xx: int
    latency_s: float
    error: str | None
    request_sha256: str


class ProviderError(Exception):
    """A response that no retry will fix (authentication, bad request, unknown model)."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(f"HTTP {status}: {detail}")
        self.status = status


class InsufficientBalance(ProviderError):
    """The account has no credit left (HTTP 402 or the provider's credit-balance message).

    A hard stop of the run, never retried; the driver ends cleanly and the log stays resumable."""


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def request_body(config: GeminiConfig, contents: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    generation: dict[str, Any] = {
        "temperature": config.temperature,
        "seed": config.seed,
        "maxOutputTokens": config.max_output_tokens,
    }
    if config.thinking_config is not None:
        generation["thinkingConfig"] = dict(config.thinking_config)
    return {"contents": list(contents), "generationConfig": generation}


def parse_response(body: str) -> tuple[str, str, int, int, int, str | None]:
    """(text, finish reason, input, output, thought tokens, error code) of a 200 response."""
    try:
        data = json.loads(body)
        usage = data.get("usageMetadata", {}) or {}
        inp = int(usage.get("promptTokenCount", 0))
        thought = int(usage.get("thoughtsTokenCount", 0))
        out = int(usage.get("candidatesTokenCount", 0)) + thought
    except (ValueError, TypeError, AttributeError):
        return "", "", 0, 0, 0, "malformed_response"
    if (data.get("promptFeedback") or {}).get("blockReason"):
        return "", "PROMPT_BLOCKED", inp, out, thought, "blocked"
    cands = data.get("candidates") or []
    if not cands:
        return "", "", inp, out, thought, "malformed_response"
    cand = cands[0]
    finish = str(cand.get("finishReason", ""))
    parts = ((cand.get("content") or {}).get("parts")) or []
    text = "".join(
        str(p.get("text", "")) for p in parts if isinstance(p, dict) and not p.get("thought")
    )
    if not text and finish in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "RECITATION"):
        return "", finish, inp, out, thought, "blocked"
    if not text:
        return "", finish, inp, out, thought, "malformed_response"
    return text, finish, inp, out, thought, None


class GeminiClient:
    def __init__(
        self,
        config: GeminiConfig,
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
        url = f"{API_ROOT}/{self.config.model}:generateContent"
        headers = {"Content-Type": "application/json", "x-goog-api-key": self._key.reveal()}
        n429 = n5xx = retries = 0
        last_status = 0
        detail = ""
        for attempt in range(self.config.max_retries + 1):
            grant = self.limiter.acquire(est, wait_for_daily=wait_for_daily)
            t0 = self.clock.time()
            try:
                resp = self.transport.post(url, headers, body, self.config.timeout_s)
            except TransportError as err:
                self.limiter.settle(grant, est)
                last_status, detail = 0, self._scrub(str(err))
                retry_after = None
            else:
                t1 = self.clock.time()
                last_status = resp.status
                if resp.status == 200:
                    text, finish, inp, out, thought, error = parse_response(resp.body)
                    self.limiter.settle(grant, inp if inp else est)
                    return CallResult(
                        text,
                        finish,
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
                if resp.status == 429:
                    n429 += 1
                elif resp.status >= 500:
                    n5xx += 1
                elif resp.status == 402:
                    raise InsufficientBalance(resp.status, detail)
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
