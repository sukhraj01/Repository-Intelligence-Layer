"""Current-name resolution of repository names (decision D1 of ``specs/held_out_repos.md``).

A repository that was renamed or transferred after a dataset was built still carries its old name
in that dataset, so an exact-name filter lets it through. GitHub answers a lookup of the old name
with a redirect to the repository under its current name; this module records that answer, per
repository, in a small tracked cache (``data/held_out/rename_cache.json``) and turns the cache into
an alias map ``old name -> current name``.

Design points:

* The network sits behind a ``Transport`` so every code path is tested with a fake and the job runs
  unchanged with or without a token. ``GITHUB_TOKEN`` is read from the environment when the
  transport is built, sent only as a request header, and never stored, logged or put in an error.
* The cache holds names and flags only (no tokens, no dataset text). It is deterministic: sorted
  keys, one date per entry, atomic replacement. Entries with a final answer (found, not found) are
  never looked up again; entries that failed for a transient reason are retried.
* Resolution stops when the rate limit is exhausted and says which names were not checked, so a
  run without a token is a lower bound and a rerun with one completes it.
* Fork status is recorded because the fork network is reported as a sensitivity analysis (D1); it
  is never used as a filter.

Standard library only and compatible with the cluster's Python 3.9, so the same module runs there.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ril.parsing.repo_id import normalize_repo_id

CACHE_SCHEMA = 1
TOKEN_ENV = "GITHUB_TOKEN"
API_ROOT = "https://api.github.com"
FINAL_STATUSES = frozenset({200, 404, 451})
"""Answers that will not change on a retry: found, gone, blocked for legal reasons."""


@dataclass(frozen=True)
class Response:
    """What a transport returns: status, the rate-limit header, and the decoded JSON body."""

    status: int
    remaining: int | None
    body: Mapping[str, Any]


class Transport(Protocol):
    """One GET against the API. Raises ``OSError`` for network failures."""

    def get(self, path: str) -> Response: ...


class GitHubTransport:
    """Real transport over ``urllib``. The token, if any, is held in a private attribute only."""

    def __init__(self, token: str | None = None, timeout: float = 30.0) -> None:
        self._token = token
        self._timeout = timeout

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> GitHubTransport:
        """Build a transport from ``GITHUB_TOKEN`` (empty or missing means unauthenticated)."""
        env = os.environ if environ is None else environ
        return cls(env.get(TOKEN_ENV) or None)

    @property
    def authenticated(self) -> bool:
        """True if a token is configured (the value is never exposed)."""
        return self._token is not None

    def __repr__(self) -> str:
        return f"GitHubTransport(authenticated={self.authenticated})"

    def get(self, path: str) -> Response:
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "ril-held-out-check"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        req = urllib.request.Request(API_ROOT + path, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as r:  # noqa: S310
                rem = r.headers.get("X-RateLimit-Remaining")
                return Response(r.status, int(rem) if rem is not None else None, json.load(r))
        except urllib.error.HTTPError as exc:
            rem = exc.headers.get("X-RateLimit-Remaining") if exc.headers else None
            return Response(exc.code, int(rem) if rem is not None else None, {})
        except urllib.error.URLError as exc:
            # Do not chain: the request object (and so its headers) must not leak into logs.
            raise OSError(f"network error: {type(exc.reason).__name__}") from None


def rate_limit_remaining(transport: Transport) -> int | None:
    """Remaining core requests per ``GET /rate_limit`` (``None`` if the answer is unreadable)."""
    resp = transport.get("/rate_limit")
    core = resp.body.get("resources", {}).get("core", {}) if resp.status == 200 else {}
    value = core.get("remaining")
    return int(value) if value is not None else resp.remaining


def _record(queried: str, resp: Response, date: str) -> dict[str, Any]:
    if resp.status != 200:
        return {"status": resp.status, "checked": date}
    body = resp.body
    full = body.get("full_name")
    return {
        "status": 200,
        "current": normalize_repo_id(full) if full else queried,
        "fork": bool(body.get("fork")),
        "parent": (body.get("parent") or {}).get("full_name"),
        "source": (body.get("source") or {}).get("full_name"),
        "checked": date,
    }


def load_cache(path: Path) -> dict[str, dict[str, Any]]:
    """Read the cache (``{}`` if the file does not exist)."""
    if not path.exists():
        return {}
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("schema") != CACHE_SCHEMA:
        raise ValueError(f"unsupported rename cache schema in {path}: {doc.get('schema')!r}")
    return dict(doc["entries"])


def save_cache(path: Path, entries: Mapping[str, Mapping[str, Any]], note: str = "") -> None:
    """Write the cache deterministically and atomically."""
    doc = {
        "schema": CACHE_SCHEMA,
        "what": "current GitHub name, fork flag and fork parent/source per queried repository",
        "note": note,
        "entries": {k: dict(entries[k]) for k in sorted(entries)},
    }
    text = json.dumps(doc, sort_keys=True, indent=1, ensure_ascii=False) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


@dataclass(frozen=True)
class ResolveStats:
    """Outcome of one resolution run."""

    requested: int
    already_final: int
    looked_up: int
    not_checked: tuple[str, ...]
    failed: tuple[str, ...]
    stopped_by_rate_limit: bool


def resolve_names(
    names: Iterable[str],
    cache: dict[str, dict[str, Any]],
    transport: Transport,
    date: str,
    max_requests: int | None = None,
    reserve: int = 0,
    on_progress: Callable[[int], None] | None = None,
) -> ResolveStats:
    """Look up every name that has no final answer yet; update ``cache`` in place.

    ``names`` are processed in the order given (callers put the most useful first). The run stops
    when ``max_requests`` is reached or when the API reports no more than ``reserve`` requests
    remaining; names not reached are returned in ``not_checked``. Network failures and server
    errors are recorded in ``failed`` and retried by a later run.
    """
    ordered: list[str] = []
    seen: set[str] = set()
    for n in names:
        c = normalize_repo_id(n)
        if c not in seen:
            seen.add(c)
            ordered.append(c)
    todo = [n for n in ordered if cache.get(n, {}).get("status") not in FINAL_STATUSES]
    done = 0
    failed: list[str] = []
    stopped = False
    not_checked: list[str] = []
    for i, name in enumerate(todo):
        if max_requests is not None and done >= max_requests:
            not_checked = todo[i:]
            break
        try:
            resp = transport.get(f"/repos/{name}")
        except OSError:
            failed.append(name)
            continue
        done += 1
        if resp.status in (403, 429) and (resp.remaining == 0 or resp.remaining is None):
            stopped = True
            not_checked = todo[i:]
            break
        if resp.status in FINAL_STATUSES or resp.status == 200:
            cache[name] = _record(name, resp, date)
        else:
            failed.append(name)
        if on_progress is not None:
            on_progress(done)
        if resp.remaining is not None and resp.remaining <= reserve:
            stopped = True
            not_checked = todo[i + 1 :]
            break
    return ResolveStats(
        requested=len(ordered),
        already_final=len(ordered) - len(todo),
        looked_up=done,
        not_checked=tuple(not_checked),
        failed=tuple(failed),
        stopped_by_rate_limit=stopped,
    )


def alias_map(cache: Mapping[str, Mapping[str, Any]]) -> dict[str, str]:
    """``{queried name: current name}`` for every entry whose current name differs."""
    return {
        k: v["current"]
        for k, v in sorted(cache.items())
        if v.get("status") == 200 and v.get("current") and v["current"] != k
    }


def fork_roots(cache: Mapping[str, Mapping[str, Any]]) -> dict[str, tuple[str, ...]]:
    """``{name: (parent, source)}`` (canonical, de-duplicated) for forks only."""
    out: dict[str, tuple[str, ...]] = {}
    for k, v in sorted(cache.items()):
        if v.get("status") == 200 and v.get("fork"):
            roots = []
            for key in ("parent", "source"):
                if v.get(key):
                    c = normalize_repo_id(v[key])
                    if c not in roots:
                        roots.append(c)
            out[k] = tuple(roots)
    return out


def priority_order(
    names: Sequence[str], held: Iterable[str], weights: Mapping[str, int] | None = None
) -> list[str]:
    """Order pool names so the most useful lookups come first.

    Names whose repository-name part equals a held-out repository's name part come first (a
    transfer keeps the name part; Wave 1 found every measured case this way). The rest follow by
    descending ``weights`` (instances per repository, so a rate-limited run covers the most pool
    mass first), then alphabetically. This only decides what a rate-limited run reaches first;
    it filters nothing.
    """
    held_names = {h.split("/", 1)[1] for h in held}
    w = {normalize_repo_id(k): v for k, v in (weights or {}).items()}
    canon = sorted({normalize_repo_id(n) for n in names}, key=lambda n: (-w.get(n, 0), n))
    first = [n for n in canon if n.split("/", 1)[1] in held_names]
    rest = [n for n in canon if n.split("/", 1)[1] not in held_names]
    return first + rest
