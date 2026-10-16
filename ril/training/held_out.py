"""Held-out repository list and the repository-level disjointness filter.

Implements ``specs/held_out_repos.md`` and ``docs/04_data_and_ground_truth.md`` ("The overlap: a
trap and an opportunity"). Disjointness is by repository, not by instance: a model that saw one
django function has an advantage on every django instance.

Canonical repository form: ``owner/name``, case-folded (GitHub treats owner and name
case-insensitively). ``Owner/Repo``, ``owner__repo`` and ``https://github.com/Owner/Repo.git``
all collapse to ``owner/repo``. Whether forks and near-duplicates are also held out is an open
design question; this module only provides the exact-name filter and accepts any held-out set,
so the fork rule can be layered on by whoever decides it.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TypeVar

T = TypeVar("T")

_URL_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?github\.com/([^/\s]+)/([^/\s]+?)(?:\.git)?/?$", re.I
)
_PR_SUFFIX_RE = re.compile(r"-\d+$")
_PRO_SUFFIX_RE = re.compile(r"-[0-9a-f]{7,40}(?:-v[0-9a-zA-Z_.]+)?$")


def canonical_repo(name: str) -> str:
    """Return the canonical ``owner/name`` (case-folded) for a repository spelling.

    Accepts ``owner/name``, ``owner__name`` and a github.com URL. Raises ``ValueError`` for
    anything else (a bare truncated folder name such as ``scikit`` has no owner and is refused
    rather than guessed).
    """
    text = name.strip()
    m = _URL_RE.match(text)
    if m:
        owner, repo = m.group(1), m.group(2)
    elif "/" in text and text.count("/") == 1:
        owner, repo = text.split("/")
    elif "__" in text and "/" not in text:
        owner, repo = text.split("__", 1)
    else:
        raise ValueError(f"cannot read owner/name from {name!r}")
    if not owner or not repo or repo.endswith(".git") and len(repo) == 4:
        raise ValueError(f"cannot read owner/name from {name!r}")
    return f"{owner}/{repo}".casefold()


def repo_from_instance_id(instance_id: str) -> str | None:
    """Return the canonical repository encoded in an instance id, or ``None`` if not readable.

    Ids look like ``owner__name-<PR number>``; the Pro split uses ``instance_owner__name-<hash>``
    with an optional ``-v<hash>`` tail. Only the final suffix is removed, because a repository
    name may itself end in digits.
    """
    text = instance_id.strip()
    if text.startswith("instance_"):
        text = text[len("instance_") :]
        stripped = _PRO_SUFFIX_RE.sub("", text, count=1)
        if stripped == text:
            stripped = _PR_SUFFIX_RE.sub("", text, count=1)
        text = stripped
    else:
        text = _PR_SUFFIX_RE.sub("", text, count=1)
    if "__" not in text:
        return None
    try:
        return canonical_repo(text)
    except ValueError:
        return None


def build_held_out(sources: Mapping[str, Iterable[str]]) -> dict[str, object]:
    """Build the held-out structure from ``{source: repository spellings}``.

    The result maps each canonical repository to the sorted list of sources it appears in, plus
    per-source and union counts. Deterministic: only sorted containers are emitted.
    """
    appears: dict[str, set[str]] = {}
    per_source: dict[str, int] = {}
    for source, repos in sources.items():
        canon = {canonical_repo(r) for r in repos}
        per_source[source] = len(canon)
        for repo in canon:
            appears.setdefault(repo, set()).add(source)
    return {
        "canonical_form": "owner/name, case-folded",
        "n_repos": len(appears),
        "per_source_counts": dict(sorted(per_source.items())),
        "repos": {r: sorted(s) for r, s in sorted(appears.items())},
    }


def canonical_json(obj: object) -> bytes:
    """Serialize deterministically: sorted keys, 1-space indent, UTF-8, trailing newline."""
    return (json.dumps(obj, sort_keys=True, indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def sha256_hex(data: bytes) -> str:
    """Return the sha256 hex digest of ``data``."""
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class FilterReport:
    """Before/after counts of one filter application."""

    instances_before: int
    instances_after: int
    repos_before: int
    repos_after: int
    dropped_repos: dict[str, int] = field(default_factory=dict)

    @property
    def instances_surviving_pct(self) -> float:
        """Percent of instances kept (0.0 for an empty pool)."""
        return (
            100.0 * self.instances_after / self.instances_before if self.instances_before else 0.0
        )

    @property
    def repos_surviving_pct(self) -> float:
        """Percent of repositories kept (0.0 for an empty pool)."""
        return 100.0 * self.repos_after / self.repos_before if self.repos_before else 0.0

    def top_dropped(self, n: int = 20) -> list[tuple[str, int]]:
        """Return the ``n`` dropped repositories with most instances (ties by name)."""
        return sorted(self.dropped_repos.items(), key=lambda kv: (-kv[1], kv[0]))[:n]


def filter_pool(
    pool: Sequence[T],
    held_out: Iterable[str],
    repo_of: Callable[[T], str],
) -> tuple[list[T], list[T], FilterReport]:
    """Remove every pool record whose repository is held out.

    ``repo_of`` returns a repository spelling for a record; it is canonicalised here, and a
    record whose repository cannot be read raises ``ValueError`` (never silently kept).
    Returns ``(kept, dropped, report)``, preserving the pool order.
    """
    blocked = {canonical_repo(r) for r in held_out}
    kept: list[T] = []
    dropped: list[T] = []
    seen: set[str] = set()
    kept_repos: set[str] = set()
    dropped_counts: Counter[str] = Counter()
    for rec in pool:
        repo = canonical_repo(repo_of(rec))
        seen.add(repo)
        if repo in blocked:
            dropped.append(rec)
            dropped_counts[repo] += 1
        else:
            kept.append(rec)
            kept_repos.add(repo)
    report = FilterReport(
        instances_before=len(pool),
        instances_after=len(kept),
        repos_before=len(seen),
        repos_after=len(kept_repos),
        dropped_repos=dict(sorted(dropped_counts.items())),
    )
    return kept, dropped, report


def filter_repo_counts(
    repo_counts: Mapping[str, int], held_out: Iterable[str]
) -> tuple[dict[str, int], FilterReport]:
    """Apply the filter to a ``{repository: instance count}`` pool summary.

    Equivalent to ``filter_pool`` over the expanded instances, without materialising them.
    Repository spellings that collapse to the same canonical name are summed.
    """
    merged: Counter[str] = Counter()
    for repo, n in repo_counts.items():
        merged[canonical_repo(repo)] += n
    blocked = {canonical_repo(r) for r in held_out}
    kept = {r: n for r, n in sorted(merged.items()) if r not in blocked}
    dropped = {r: n for r, n in sorted(merged.items()) if r in blocked}
    report = FilterReport(
        instances_before=sum(merged.values()),
        instances_after=sum(kept.values()),
        repos_before=len(merged),
        repos_after=len(kept),
        dropped_repos=dropped,
    )
    return kept, report
