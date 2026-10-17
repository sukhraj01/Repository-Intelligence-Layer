"""Held-out repository list and the repository-level disjointness filter.

Implements ``specs/held_out_repos.md`` and ``docs/04_data_and_ground_truth.md`` ("The overlap: a
trap and an opportunity"). Disjointness is by repository, not by instance: a model that saw one
django function has an advantage on every django instance.

Canonical repository form: ``owner/name``, case-folded (GitHub treats owner and name
case-insensitively). ``Owner/Repo``, ``owner__repo`` and ``https://github.com/Owner/Repo.git``
all collapse to ``owner/repo``.

Matching rules (decisions D1 and D3 of ``specs/held_out_repos.md``, list schema 2):

* exact canonical names of the core tier (CORE-Bench L2/L3 and SWE-bench Verified);
* plus current-name resolution: a pool repository and a held-out repository match if they are the
  same repository under today's name (``ril.training.rename_resolution`` supplies the aliases);
* plus the Loc-Bench tier, a separate list that can be switched off;
* the fork network is a sensitivity report (:func:`rule_counts`) and is never a filter.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TypeVar

from ril.parsing.repo_id import normalize_repo_id

T = TypeVar("T")

_PR_SUFFIX_RE = re.compile(r"-\d+$")
_PRO_SUFFIX_RE = re.compile(r"-[0-9a-f]{7,40}(?:-v[0-9a-zA-Z_.]+)?$")


def canonical_repo(name: str) -> str:
    """Return the canonical ``owner/name`` (case-folded) for a repository spelling.

    The rule lives in ``ril.parsing.repo_id`` (decision D5 of ``specs/code_unit.md``); this name
    is kept for the held-out code and tests.
    """
    return normalize_repo_id(name)


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


def _blocked_keys(held_out: Iterable[str], aliases: Mapping[str, str] | None) -> set[str]:
    """Held-out names plus their current names (when the alias map knows them)."""
    blocked = {canonical_repo(r) for r in held_out}
    if aliases:
        blocked |= {aliases[b] for b in list(blocked) if b in aliases}
    return blocked


def is_held_out(repo: str, blocked: set[str], aliases: Mapping[str, str] | None = None) -> bool:
    """True if ``repo`` (canonical) or its current name is in ``blocked``."""
    if repo in blocked:
        return True
    return bool(aliases) and aliases.get(repo, repo) in blocked  # type: ignore[union-attr]


def filter_pool(
    pool: Sequence[T],
    held_out: Iterable[str],
    repo_of: Callable[[T], str],
    aliases: Mapping[str, str] | None = None,
) -> tuple[list[T], list[T], FilterReport]:
    """Remove every pool record whose repository is held out.

    ``repo_of`` returns a repository spelling for a record; it is canonicalised here, and a
    record whose repository cannot be read raises ``ValueError`` (never silently kept).
    ``aliases`` maps old repository names to current names (decision D1): a record matches if its
    name or its current name is held out, or if a held-out name has that current name.
    Returns ``(kept, dropped, report)``, preserving the pool order.
    """
    blocked = _blocked_keys(held_out, aliases)
    kept: list[T] = []
    dropped: list[T] = []
    seen: set[str] = set()
    kept_repos: set[str] = set()
    dropped_counts: Counter[str] = Counter()
    for rec in pool:
        repo = canonical_repo(repo_of(rec))
        seen.add(repo)
        if is_held_out(repo, blocked, aliases):
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
    repo_counts: Mapping[str, int],
    held_out: Iterable[str],
    aliases: Mapping[str, str] | None = None,
) -> tuple[dict[str, int], FilterReport]:
    """Apply the filter to a ``{repository: instance count}`` pool summary.

    Equivalent to ``filter_pool`` over the expanded instances, without materialising them.
    Repository spellings that collapse to the same canonical name are summed.
    """
    merged: Counter[str] = Counter()
    for repo, n in repo_counts.items():
        merged[canonical_repo(repo)] += n
    blocked = _blocked_keys(held_out, aliases)
    kept = {r: n for r, n in sorted(merged.items()) if not is_held_out(r, blocked, aliases)}
    dropped = {r: n for r, n in sorted(merged.items()) if is_held_out(r, blocked, aliases)}
    report = FilterReport(
        instances_before=sum(merged.values()),
        instances_after=sum(kept.values()),
        repos_before=len(merged),
        repos_after=len(kept),
        dropped_repos=dropped,
    )
    return kept, report


@dataclass(frozen=True)
class HeldOutLists:
    """The tiers of the held-out list (schema 2) and the alias map used for matching.

    ``core`` is CORE-Bench L2/L3 and SWE-bench Verified; ``loc_bench`` is the separate Loc-Bench
    tier (decision D3), stored without the repositories already in ``core``.
    """

    core: frozenset[str]
    loc_bench: frozenset[str]
    aliases: Mapping[str, str]

    def blocked(self, include_loc_bench: bool = True) -> frozenset[str]:
        """Names a pool repository is compared against for the default rule set."""
        return self.core | self.loc_bench if include_loc_bench else self.core


def load_held_out_lists(doc: Mapping[str, object]) -> HeldOutLists:
    """Read the tiers from a parsed ``held_out_repos.json`` of schema 2."""
    if doc.get("schema_version") != 2:
        raise ValueError(f"held-out list schema 2 expected, got {doc.get('schema_version')!r}")
    tiers = doc["tiers"]
    assert isinstance(tiers, dict)
    core = frozenset(doc["repos"])  # type: ignore[call-overload]
    loc = frozenset(tiers["loc_bench"]["repos"])
    aliases = dict(doc.get("aliases", {}))  # type: ignore[call-overload]
    return HeldOutLists(core=core, loc_bench=loc, aliases=aliases)


@dataclass(frozen=True)
class RuleRow:
    """Survival of one pool under one cumulative rule set."""

    rule: str
    instances_after: int
    repos_after: int
    repos_dropped: int
    instances_dropped: int


def rule_counts(
    repo_counts: Mapping[str, int],
    lists: HeldOutLists,
    pool_aliases: Mapping[str, str],
    pool_forks: Mapping[str, tuple[str, ...]],
) -> list[RuleRow]:
    """Survival of a pool under each rule, cumulatively, plus the fork-network sensitivity row.

    Rows: ``exact`` (core names), ``+current_name`` (D1, using the held-out and pool aliases),
    ``+loc_bench`` (D3, the default rule set), and ``sensitivity: +fork_network`` (pool
    repositories whose fork parent or source is held out; reported only, never applied).
    ``pool_aliases`` and ``pool_forks`` cover only the repositories resolved so far, so every
    row after ``exact`` is a lower bound on what full resolution would drop.
    """
    aliases = {**lists.aliases, **pool_aliases}
    merged: Counter[str] = Counter()
    for repo, n in repo_counts.items():
        merged[canonical_repo(repo)] += n
    total_inst = sum(merged.values())

    def row(rule: str, drop: Callable[[str], bool]) -> RuleRow:
        kept = {r: n for r, n in merged.items() if not drop(r)}
        return RuleRow(
            rule=rule,
            instances_after=sum(kept.values()),
            repos_after=len(kept),
            repos_dropped=len(merged) - len(kept),
            instances_dropped=total_inst - sum(kept.values()),
        )

    core = _blocked_keys(lists.core, aliases)
    both = _blocked_keys(lists.core | lists.loc_bench, aliases)

    def by_fork(r: str) -> bool:
        return is_held_out(r, both, aliases) or any(x in both for x in pool_forks.get(r, ()))

    return [
        row("exact", lambda r: r in lists.core),
        row("+current_name", lambda r: is_held_out(r, core, aliases)),
        row("+loc_bench", lambda r: is_held_out(r, both, aliases)),
        row("sensitivity: +fork_network", by_fork),
    ]
