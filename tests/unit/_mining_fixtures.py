"""Hand-built fixtures for the PR-mining tests (synthetic: not recordings of the live API).

Every response shape below follows the documented GitHub GraphQL and REST responses. They are
labelled synthetic: a pass proves the code against these shapes, not against the live service.
"""

from __future__ import annotations

import difflib
import json
import os
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from ril.data_mining.github_api import HttpResponse, TransportError
from ril.parsing.code_unit import CodeUnit
from ril.parsing.repository_parser import parse_repository


def make_patch(old: str, new: str) -> str:
    """A unified diff in the form of the compare endpoint's ``patch`` (hunks only, 3 context)."""
    lines = list(difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm="", n=3))
    return "\n".join(lines[2:])


def units_of(tmp_path: Any, files: Mapping[str, str], repo: str = "acme/widgets") -> list[CodeUnit]:
    """Parse ``files`` with the project parser and return every unit."""
    for path, text in files.items():
        full = os.path.join(str(tmp_path), *path.split("/"))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(text)
    return parse_repository(str(tmp_path), repo).units


def file_entry(
    filename: str,
    status: str = "modified",
    patch: str | None = None,
    previous: str | None = None,
    changes: int | None = None,
) -> dict[str, Any]:
    """One entry of the compare response's ``files`` list."""
    row: dict[str, Any] = {"filename": filename, "status": status}
    if patch is not None:
        row["patch"] = patch
        row["changes"] = changes if changes is not None else patch.count("\n") + 1
    elif changes is not None:
        row["changes"] = changes
    if previous:
        row["previous_filename"] = previous
    return row


def compare_doc(merge_base: str, head: str, files: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """A compare response."""
    return {
        "merge_base_commit": {"sha": merge_base},
        "commits": [{"sha": head}],
        "files": list(files),
    }


def issue_node(
    number: int,
    title: str = "Widget area is wrong",
    body: str = "area() returns the wrong value",
    repo: str = "acme/widgets",
    edited: str | None = None,
) -> dict[str, Any]:
    """A closing-issue node."""
    return {
        "number": number,
        "title": title,
        "body": body,
        "createdAt": "2024-01-01T00:00:00Z",
        "lastEditedAt": edited,
        "repository": {"nameWithOwner": repo},
    }


def pr_node(
    number: int,
    issues: Sequence[Mapping[str, Any]],
    base: str = "b" * 40,
    head: str = "h" * 40,
    body: str = "",
    created: str = "2024-02-01T00:00:00Z",
) -> dict[str, Any]:
    """A pull-request node of the listing query."""
    return {
        "number": number,
        "title": f"PR {number}",
        "body": body,
        "createdAt": created,
        "mergedAt": "2024-02-02T00:00:00Z",
        "baseRefOid": base,
        "headRefOid": head,
        "changedFiles": 1,
        "additions": 1,
        "deletions": 1,
        "closingIssuesReferences": {"totalCount": len(issues), "nodes": list(issues)},
    }


def graphql_page(
    repo: str,
    nodes: Sequence[Mapping[str, Any]],
    next_cursor: str | None = None,
    current: str | None = None,
) -> dict[str, Any]:
    """A listing-query response (``data`` wrapped in the GraphQL envelope)."""
    return {
        "data": {
            "repository": {
                "nameWithOwner": current or repo,
                "isArchived": False,
                "isFork": False,
                "pullRequests": {
                    "totalCount": len(nodes),
                    "pageInfo": {"hasNextPage": next_cursor is not None, "endCursor": next_cursor},
                    "nodes": list(nodes),
                },
            },
            "rateLimit": {"cost": 1, "remaining": 4990, "resetAt": "2024-02-02T01:00:00Z"},
        }
    }


Route = Callable[[str, bytes | None], HttpResponse]


def json_response(
    doc: Any, status: int = 200, headers: Mapping[str, str] | None = None
) -> HttpResponse:
    """A JSON response with rate-limit headers."""
    h = {
        "x-ratelimit-remaining": "4900",
        "x-ratelimit-limit": "5000",
        "x-ratelimit-reset": "9999999999",
    }
    h.update(headers or {})
    return HttpResponse(status, h, json.dumps(doc).encode("utf-8"))


class FakeTransport:
    """Scripted transport: routes by method and path prefix, records every call."""

    def __init__(self) -> None:
        self.routes: list[tuple[str, str, Route]] = []
        self.calls: list[tuple[str, str]] = []
        self.headers: list[Mapping[str, str]] = []
        self.queue: list[HttpResponse | TransportError] = []

    def add(self, method: str, prefix: str, route: Route) -> None:
        self.routes.append((method, prefix, route))

    def send(
        self, method: str, url: str, headers: Mapping[str, str], body: bytes | None
    ) -> HttpResponse:
        self.calls.append((method, url))
        self.headers.append(dict(headers))
        if self.queue:
            item = self.queue.pop(0)
            if isinstance(item, TransportError):
                raise item
            return item
        path = url.split("api.github.com", 1)[-1]
        for m, prefix, route in self.routes:
            if m == method and path.startswith(prefix):
                return route(url, body)
        return json_response({"message": "Not Found"}, status=404)


class FakeClock:
    """Clock that records sleeps instead of sleeping; time advances by the sleeps."""

    def __init__(self, start: float = 1_000_000.0) -> None:
        self.t = start
        self.slept: list[float] = []

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.t += seconds
