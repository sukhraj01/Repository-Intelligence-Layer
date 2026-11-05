"""Cached GitHub transport, pagination and closing-issue collection."""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

Record = dict[str, Any]


def digest(value: object) -> str:
    """Hash canonical JSON, including configuration and request identities."""
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def atomic_json(path: Path, value: object) -> None:
    """Replace a complete JSON document without exposing partial checkpoints."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    temporary.replace(path)


@dataclass(frozen=True)
class Response:
    status: int
    data: Any
    headers: Mapping[str, str]


class Transport(Protocol):
    def __call__(self, method: str, url: str, body: Record | None) -> Response: ...


class GitHubTransport:
    """Read-only requests; authentication exists only in the HTTP header."""

    def __call__(self, method: str, url: str, body: Record | None) -> Response:
        if not url.startswith("https://api.github.com/"):
            raise ValueError("GitHub API origin required")
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "ril-data-mining"}
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise ValueError("GITHUB_TOKEN is required for live mining")
        headers["Authorization"] = f"Bearer {token}"
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return Response(response.status, json.load(response), dict(response.headers))
        except urllib.error.HTTPError as exc:
            # Do not persist arbitrary server messages or request headers.
            return Response(exc.code, {}, dict(exc.headers))


class RecordedTransport:
    """Replay explicitly synthetic response recordings, refusing unknown requests."""

    def __init__(self, document: Record):
        if document.get("source_kind") != "synthetic_recorded_responses":
            raise ValueError("synthetic recording label required")
        self.responses = document["responses"]
        self.positions: dict[str, int] = {}

    def __call__(self, method: str, url: str, body: Record | None) -> Response:
        key = digest([method, url, body])
        rows = self.responses[key]
        position = self.positions.get(key, 0)
        self.positions[key] = position + 1
        row = rows[min(position, len(rows) - 1)]
        return Response(int(row["status"]), row["data"], row.get("headers", {}))


class Client:
    """Durable success cache and bounded retries with rate-reset handling.

    Sleeps are split into at most 60 seconds. HTTP failures leave no success checkpoint;
    a later invocation retries them. Counters persist across resumptions.
    """

    def __init__(
        self,
        root: Path,
        transport: Transport,
        *,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
        retries: int = 5,
    ):
        self.root = root
        self.transport = transport
        self.clock = clock
        self.sleep = sleep
        self.retries = retries
        self.counter_path = root / "calls.json"
        self.counts = (
            json.loads(self.counter_path.read_text())
            if self.counter_path.exists()
            else {"api_calls": 0, "cache_hits": 0, "wait_seconds": 0.0}
        )
        self.not_before = 0.0

    def _wait(self, seconds: float) -> None:
        left = max(0.0, seconds)
        while left > 0:
            step = min(60.0, left)
            self.sleep(step)
            self.counts["wait_seconds"] += step
            left -= step
        atomic_json(self.counter_path, self.counts)

    def request(self, path: str, body: Record | None = None) -> Any:
        """GET a REST resource or POST a read-only GraphQL query."""
        url = path if path.startswith("https://") else f"https://api.github.com{path}"
        if not url.startswith("https://api.github.com/"):
            raise ValueError("pagination changed API origin")
        method = "GET" if body is None else "POST"
        key = digest([method, url, body])
        cached = self.root / "responses" / f"{key}.json"
        if cached.exists():
            self.counts["cache_hits"] += 1
            atomic_json(self.counter_path, self.counts)
            return json.loads(cached.read_text())
        for attempt in range(self.retries + 1):
            self._wait(self.not_before - self.clock())
            self.counts["api_calls"] += 1
            atomic_json(self.counter_path, self.counts)
            try:
                response = self.transport(method, url, body)
            except (OSError, TimeoutError):
                if attempt == self.retries:
                    raise RuntimeError("GitHub transport retries exhausted") from None
                self._wait(2.0**attempt)
                continue
            headers = {k.lower(): v for k, v in response.headers.items()}
            reset = float(headers.get("x-ratelimit-reset", "0"))
            if headers.get("x-ratelimit-remaining") == "0":
                self.not_before = max(self.not_before, reset + 1)
            if response.status == 200:
                if isinstance(response.data, dict) and response.data.get("errors"):
                    raise RuntimeError("GraphQL returned errors; no checkpoint saved")
                payload = {"data": response.data, "link": headers.get("link", "")}
                atomic_json(cached, payload)
                return payload
            if response.status not in (403, 429, 500, 502, 503, 504):
                raise RuntimeError(f"GitHub HTTP {response.status}")
            if attempt == self.retries:
                raise RuntimeError(f"GitHub HTTP {response.status}; retries exhausted")
            self._wait(
                max(float(headers.get("retry-after", "0")), reset - self.clock() + 1, 2.0**attempt)
            )
        raise AssertionError("unreachable")

    def pages(self, path: str, key: str | None = None) -> Iterator[Any]:
        """Follow Link pagination; refuse search results reported as incomplete."""
        seen: set[str] = set()
        while path:
            if path in seen:
                raise ValueError("pagination cycle")
            seen.add(path)
            payload = self.request(path)
            data = payload["data"]
            if isinstance(data, dict) and data.get("incomplete_results"):
                raise ValueError("incomplete repository search; retry or partition the search")
            yield from data[key] if key else data
            path = ""
            for link in payload["link"].split(","):
                if 'rel="next"' in link:
                    path = link.strip().split(">", 1)[0].lstrip("<")


ISSUE_QUERY = """query($owner:String!,$name:String!,$number:Int!,$cursor:String){
 repository(owner:$owner,name:$name){pullRequest(number:$number){
 closingIssuesReferences(first:100,after:$cursor){nodes{number title body url
 repository{nameWithOwner}} pageInfo{hasNextPage endCursor}}}}}"""


def linked_issues(client: Client, repo: str, number: int) -> list[Record]:
    """All closing references, including cross-repository issues and pagination."""
    owner, name = repo.split("/")
    cursor: str | None = None
    seen: set[str] = set()
    issues: list[Record] = []
    while True:
        payload = client.request(
            "/graphql",
            {
                "query": ISSUE_QUERY,
                "variables": {"owner": owner, "name": name, "number": number, "cursor": cursor},
            },
        )
        connection = payload["data"]["data"]["repository"]["pullRequest"]["closingIssuesReferences"]
        issues.extend(connection["nodes"])
        page = connection["pageInfo"]
        if not page["hasNextPage"]:
            return sorted({r["url"]: r for r in issues}.values(), key=lambda r: r["url"])
        cursor = page["endCursor"]
        if not cursor or cursor in seen:
            raise ValueError("invalid closing-issue cursor")
        seen.add(cursor)


def search_path(query: str) -> str:
    """Fixed repository ordering and full page size for a reproducible pilot."""
    return "/search/repositories?" + urllib.parse.urlencode(
        {"q": query, "sort": "stars", "order": "desc", "per_page": 100}
    )


def response_record(response: Response) -> Record:
    """JSON form for synthetic transport fixtures."""
    return asdict(response)
