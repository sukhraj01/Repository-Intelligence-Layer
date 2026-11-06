"""GitHub API client for the PR-mined set: conditional requests, retries, rate-limit budget.

Implements ``docs/experiments/B.md`` E-MINE-PILOT, design D66 (rate-limit-aware, budget and sleeps
logged). One class, :class:`ApiClient`, over an injectable :class:`Transport` and
:class:`Clock`, so every behaviour is tested offline with scripted responses and a fake clock.

* **Conditional requests.** A GET whose URL was fetched before sends ``If-None-Match``; a 304 serves
  the stored body (a 304 does not count against the primary rate limit).
* **Retries.** Network errors and 5xx retry with exponential backoff; 404, 410 and 451 raise
  :class:`NotFound` at once; any other 4xx raises :class:`ApiError`.
* **Rate limits.** The primary limit is read from the ``x-ratelimit-*`` headers and the client
  sleeps until the reset when fewer than ``reserve`` calls remain; a 403 or 429 with ``retry-after``
  sleeps that long, with ``remaining`` 0 sleeps to the reset, and with a secondary-limit message
  backs off exponentially; a 403 with none of these is a real refusal and raises.
* **Token.** Read from the environment by :func:`token_from_env`, sent only in the
  ``Authorization`` header, never logged, never part of ``repr``.

Kept compatible with Python 3.10 (the cluster's compute nodes).
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import http.client
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

API_ROOT = "https://api.github.com"
GRAPHQL_PATH = "/graphql"
USER_AGENT = "ril-data-mining/1"
log = logging.getLogger(__name__)

Json = Any


class ApiError(RuntimeError):
    """A response that is a refusal or a failure the client will not retry further."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"HTTP {status}: {message[:200]}")
        self.status = status


class NotFound(ApiError):
    """404, 410 or 451: the resource is gone or blocked (callers quarantine, not retry)."""


class TransportError(OSError):
    """A network-level failure (DNS, reset, timeout); retried by the client."""


@dataclass(frozen=True)
class HttpResponse:
    """Status, lower-cased headers and the raw body of one response."""

    status: int
    headers: Mapping[str, str]
    body: bytes

    def text(self) -> str:
        """Body decoded as UTF-8 (replacing undecodable bytes)."""
        return self.body.decode("utf-8", "replace")


class Transport(Protocol):
    """One HTTP exchange. Raises :class:`TransportError` on network failure."""

    def send(
        self, method: str, url: str, headers: Mapping[str, str], body: bytes | None
    ) -> HttpResponse: ...


class Clock(Protocol):
    """Time source; replaced by a fake in tests so no test sleeps."""

    def now(self) -> float: ...

    def sleep(self, seconds: float) -> None: ...


class SystemClock:
    """Wall clock and real sleep."""

    def now(self) -> float:
        return time.time()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class UrllibTransport:
    """The real transport (stdlib only)."""

    def __init__(self, timeout: float = 60.0) -> None:
        self.timeout = timeout

    def send(
        self, method: str, url: str, headers: Mapping[str, str], body: bytes | None
    ) -> HttpResponse:
        req = urllib.request.Request(url, data=body, headers=dict(headers), method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return HttpResponse(
                    resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read()
                )
        except urllib.error.HTTPError as err:
            return HttpResponse(
                err.code, {k.lower(): v for k, v in err.headers.items()}, err.read()
            )
        except (
            urllib.error.URLError,
            http.client.HTTPException,  # IncompleteRead, RemoteDisconnected: a cut response body
            TimeoutError,
            ConnectionError,
        ) as err:
            raise TransportError(str(err)) from err


def token_from_env(name: str = "GITHUB_TOKEN") -> str | None:
    """The token from the environment, or ``None`` when unset or empty. Never printed."""
    value = os.environ.get(name, "")
    return value if value else None


def token_present(name: str = "GITHUB_TOKEN") -> bool:
    """Presence test only, for logs and the blocker report."""
    return token_from_env(name) is not None


# --------------------------------------------------------------------------- ETag store


class EtagStore:
    """Responses by request key, gzip-compressed, for conditional requests (``None`` dir: off)."""

    def __init__(self, directory: str | None) -> None:
        self.directory = directory

    def _path(self, key: str) -> str | None:
        if self.directory is None:
            return None
        return os.path.join(self.directory, key[:2], f"{key}.json.gz")

    def get(self, key: str) -> tuple[str, bytes] | None:
        """``(etag, body)`` stored under ``key``, or ``None``."""
        path = self._path(key)
        if path is None or not os.path.exists(path):
            return None
        try:
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                row = json.load(handle)
            return str(row["etag"]), base64.b64decode(row["body"])
        except (OSError, ValueError, KeyError):
            return None  # a damaged entry is a miss; the next fetch overwrites it

    def put(self, key: str, etag: str, body: bytes) -> None:
        """Store atomically (temporary file, then rename)."""
        path = self._path(key)
        if path is None:
            return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.tmp"
        row = {"etag": etag, "body": base64.b64encode(body).decode("ascii")}
        with gzip.GzipFile(tmp, "wb", mtime=0) as handle:
            handle.write(json.dumps(row, sort_keys=True).encode("utf-8"))
        os.replace(tmp, path)


def request_key(method: str, url: str, body: bytes | None) -> str:
    """Stable key of a request (method, URL, body)."""
    h = hashlib.sha256()
    h.update(method.encode())
    h.update(b"\0")
    h.update(url.encode())
    h.update(b"\0")
    h.update(body or b"")
    return h.hexdigest()


# --------------------------------------------------------------------------- budget


@dataclass
class Budget:
    """Counters of one client: calls, 304s, retries, sleeps, last rate-limit reading."""

    calls: int = 0
    rest_calls: int = 0
    graphql_calls: int = 0
    not_modified: int = 0
    retries: int = 0
    sleeps: int = 0
    slept_seconds: float = 0.0
    remaining: int | None = None
    limit: int | None = None
    reset_epoch: int | None = None
    graphql_cost: int = 0
    by_endpoint: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """JSON form (sorted keys by the writer)."""
        return {
            "calls": self.calls,
            "rest_calls": self.rest_calls,
            "graphql_calls": self.graphql_calls,
            "not_modified": self.not_modified,
            "retries": self.retries,
            "sleeps": self.sleeps,
            "slept_seconds": round(self.slept_seconds, 3),
            "graphql_cost": self.graphql_cost,
            "by_endpoint": dict(sorted(self.by_endpoint.items())),
        }


EventSink = Callable[[dict[str, Any]], None]


def endpoint_label(path: str) -> str:
    """Endpoint family of a request path, with owner, repository and ids removed."""
    parts = [p for p in path.split("?")[0].split("/") if p]
    if parts[:1] == ["graphql"]:
        return "graphql"
    if parts[:1] == ["repos"] and len(parts) >= 4:
        return "repos/" + parts[3]
    return parts[0] if parts else ""


@dataclass
class ClientConfig:
    """Retry and pacing parameters (no magic numbers in the client)."""

    retries: int = 5
    backoff_base: float = 2.0
    backoff_cap: float = 120.0
    secondary_base: float = 60.0
    secondary_cap: float = 900.0
    reserve: int = 10
    min_interval: float = 0.05
    max_wait: float = 3700.0
    """Longest single sleep taken for a rate-limit reset; a longer wait raises instead."""


class ApiClient:
    """GitHub REST and GraphQL calls with the behaviours listed in the module docstring."""

    def __init__(
        self,
        transport: Transport,
        *,
        token: str | None = None,
        clock: Clock | None = None,
        etags: EtagStore | None = None,
        config: ClientConfig | None = None,
        sink: EventSink | None = None,
        api_root: str = API_ROOT,
    ) -> None:
        self._transport = transport
        self._token = token
        self.clock: Clock = clock or SystemClock()
        self._etags = etags or EtagStore(None)
        self.config = config or ClientConfig()
        self._sink = sink
        self.api_root = api_root.rstrip("/")
        self.budget = Budget()
        self._last_call = 0.0

    def __repr__(self) -> str:
        return f"ApiClient(authenticated={self._token is not None}, calls={self.budget.calls})"

    @property
    def authenticated(self) -> bool:
        """Whether a token is configured (the value is never exposed)."""
        return self._token is not None

    # ---- public calls

    def get_json(self, path: str, params: Mapping[str, str | int] | None = None) -> Json:
        """GET ``path`` (with query ``params``) and return the parsed JSON body."""
        url = self.api_root + path
        if params:
            url += "?" + urllib.parse.urlencode(sorted(params.items()))
        resp = self._call("GET", url, None, conditional=True)
        return json.loads(resp.body.decode("utf-8")) if resp.body else None

    def graphql(self, query: str, variables: Mapping[str, Any]) -> Json:
        """POST a GraphQL query; returns ``data``. Raises on errors other than a retriable limit."""
        body = json.dumps({"query": query, "variables": dict(variables)}, sort_keys=True).encode()
        url = self.api_root + GRAPHQL_PATH
        for attempt in range(self.config.retries + 1):
            resp = self._call("POST", url, body, conditional=False)
            doc = json.loads(resp.body.decode("utf-8"))
            errors = doc.get("errors") or []
            types = {str(e.get("type") or "") for e in errors}
            if "RATE_LIMITED" in types:
                self._wait_for_reset("graphql-rate-limited")
                self.budget.remaining = None  # the window has reset; the old reading is stale
                continue
            if errors and "NOT_FOUND" in types and not doc.get("data"):
                raise NotFound(404, str(errors[0].get("message")))
            if errors and doc.get("data") is None:
                if attempt < self.config.retries and any(
                    "timeout" in str(e.get("message", "")).lower() for e in errors
                ):
                    self.budget.retries += 1
                    self._sleep(self._backoff(attempt), "graphql-timeout")
                    continue
                raise ApiError(200, "; ".join(str(e.get("message")) for e in errors))
            data = doc.get("data")
            if isinstance(data, dict) and isinstance(data.get("rateLimit"), dict):
                self.budget.graphql_cost += int(data["rateLimit"].get("cost") or 0)
                rem = data["rateLimit"].get("remaining")
                if rem is not None:
                    self.budget.remaining = int(rem)
            return data
        raise ApiError(200, "graphql rate limit did not clear")

    # ---- internals

    def _headers(self, extra: Mapping[str, str]) -> dict[str, str]:
        h = {"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT}
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        h.update(extra)
        return h

    def _backoff(self, attempt: int) -> float:
        return float(min(self.config.backoff_cap, self.config.backoff_base * (2**attempt)))

    def _sleep(self, seconds: float, why: str) -> None:
        if seconds <= 0:
            return
        self.budget.sleeps += 1
        self.budget.slept_seconds += seconds
        self._emit({"event": "sleep", "seconds": round(seconds, 3), "why": why})
        self.clock.sleep(seconds)

    def _emit(self, event: dict[str, Any]) -> None:
        if self._sink is not None:
            self._sink(event)

    def _pace(self) -> None:
        gap = self.clock.now() - self._last_call
        if gap < self.config.min_interval:
            self._sleep(self.config.min_interval - gap, "pace")

    def _wait_for_reset(self, why: str) -> None:
        reset = self.budget.reset_epoch
        wait = (reset - self.clock.now() + 1.0) if reset else self.config.secondary_base
        if wait > self.config.max_wait:
            raise ApiError(403, f"rate limit resets in {wait:.0f}s, beyond max_wait")
        self._sleep(max(wait, 1.0), why)

    def _read_limits(self, resp: HttpResponse) -> None:
        h = resp.headers
        if "x-ratelimit-remaining" in h:
            self.budget.remaining = int(h["x-ratelimit-remaining"])
        if "x-ratelimit-limit" in h:
            self.budget.limit = int(h["x-ratelimit-limit"])
        if "x-ratelimit-reset" in h:
            self.budget.reset_epoch = int(h["x-ratelimit-reset"])

    def _call(
        self, method: str, url: str, body: bytes | None, *, conditional: bool
    ) -> HttpResponse:
        key = request_key(method, url, body)
        cached = self._etags.get(key) if conditional else None
        endpoint = endpoint_label(urllib.parse.urlparse(url).path)
        for attempt in range(self.config.retries + 1):
            rem = self.budget.remaining
            if rem is not None and rem <= self.config.reserve and self.budget.reset_epoch:
                self._wait_for_reset("primary-reserve")
                self.budget.remaining = None
            self._pace()
            extra: dict[str, str] = {}
            if cached is not None:
                extra["If-None-Match"] = cached[0]
            if body is not None:
                extra["Content-Type"] = "application/json"
            try:
                resp = self._transport.send(method, url, self._headers(extra), body)
            except TransportError as err:
                self._last_call = self.clock.now()
                if attempt == self.config.retries:
                    raise
                self.budget.retries += 1
                self._sleep(self._backoff(attempt), f"network:{type(err).__name__}")
                continue
            self._last_call = self.clock.now()
            self.budget.calls += 1
            self.budget.by_endpoint[endpoint] = self.budget.by_endpoint.get(endpoint, 0) + 1
            if method == "POST":
                self.budget.graphql_calls += 1
            else:
                self.budget.rest_calls += 1
            self._read_limits(resp)
            self._emit(
                {
                    "event": "call",
                    "endpoint": endpoint,
                    "status": resp.status,
                    "remaining": self.budget.remaining,
                }
            )
            if resp.status == 304 and cached is not None:
                self.budget.not_modified += 1
                return HttpResponse(200, resp.headers, cached[1])
            if 200 <= resp.status < 300:
                etag = resp.headers.get("etag")
                if conditional and etag:
                    self._etags.put(key, etag, resp.body)
                return resp
            if resp.status in (404, 410, 451):
                raise NotFound(resp.status, resp.text())
            if resp.status in (403, 429):
                if not self._handle_limit(resp, attempt):
                    raise ApiError(resp.status, resp.text())
                continue
            if resp.status >= 500:
                if attempt == self.config.retries:
                    raise ApiError(resp.status, resp.text())
                self.budget.retries += 1
                self._sleep(self._backoff(attempt), f"http-{resp.status}")
                continue
            raise ApiError(resp.status, resp.text())
        raise ApiError(0, "retries exhausted")

    def _handle_limit(self, resp: HttpResponse, attempt: int) -> bool:
        """Sleep for a rate-limit refusal; ``False`` when the 403 is a real refusal."""
        if attempt == self.config.retries:
            return False
        retry_after = resp.headers.get("retry-after")
        message = resp.text().lower()
        self.budget.retries += 1
        if retry_after is not None:
            self._sleep(float(retry_after) + 1.0, "retry-after")
            return True
        if self.budget.remaining == 0 or resp.headers.get("x-ratelimit-remaining") == "0":
            self._wait_for_reset("primary-exhausted")
            self.budget.remaining = None
            return True
        if "secondary rate limit" in message or "abuse" in message:
            wait = min(self.config.secondary_cap, self.config.secondary_base * (2**attempt))
            self._sleep(wait, "secondary-rate-limit")
            return True
        self.budget.retries -= 1
        return False
