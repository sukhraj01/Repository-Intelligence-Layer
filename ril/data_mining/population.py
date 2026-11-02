"""The repository population of the mined set and the selection analysis (designs D60, D65).

Implements ``docs/experiments/B.md`` E-MINE-PILOT. The population is the set of repositories of the
published pool's first ``pool_size`` directories after the held-out filter (the 5,000-directory
pool of D41, seeded order ``sha256("<seed>:<directory>")``, the selection rule of
``ril.training.train_jobs``). Mining every linked merged pull request of those repositories makes
the published pool's per-PR selection measurable: for each repository, the share of its linked
pull requests that the pool kept.

Kept compatible with Python 3.10 (the cluster's compute nodes).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ril.training import pool_check as pc
from ril.training import pool_ranks as pr


@dataclass(frozen=True)
class Population:
    """Directories and repositories of the pool after the held-out filter."""

    directories: tuple[str, ...]
    """The selected directories, sorted."""
    repos: tuple[str, ...]
    """Their repositories, in the seeded order used to take the first ``n_repos``."""
    published: Mapping[str, frozenset[int]]
    """Per repository of the population, the pull request numbers the whole published pool (every
    directory left after the held-out filter, not only the selected ``pool_size``) holds."""
    counts: Mapping[str, int]
    """Stage counts: listed, held_out_dropped, selected, repos_listed, repos_held_out, repos."""


def select_population(
    names: Iterable[str],
    *,
    is_held_out: Callable[[str], bool],
    seed: int,
    pool_size: int,
) -> Population:
    """Apply the held-out filter, take the first ``pool_size`` directories by seeded key.

    An unreadable directory name raises ``ValueError`` (a silent drop would change the population).
    Counts are reported at repository and at directory (PR) level (D65).
    """
    listed = 0
    dropped = 0
    all_repos: set[str] = set()
    held_repos: set[str] = set()
    kept: list[tuple[str, str, int]] = []
    for name in sorted(set(names)):
        listed += 1
        split = pc.split_instance_dir(name)
        if split is None:
            raise ValueError(f"unreadable instance directory {name!r}")
        repo, number = split
        all_repos.add(repo)
        if is_held_out(repo):
            dropped += 1
            held_repos.add(repo)
            continue
        kept.append((name, repo, number))
    chosen = sorted(kept, key=lambda t: pr.seeded_key(seed, t[0]))[:pool_size]
    chosen_repos = {repo for _, repo, _ in chosen}
    published: dict[str, set[int]] = {}
    for _, repo, number in kept:
        if repo in chosen_repos:
            published.setdefault(repo, set()).add(number)
    repos = sorted(chosen_repos, key=lambda r: pr.seeded_key(seed, r))
    counts = {
        "directories_listed": listed,
        "directories_held_out": dropped,
        "directories_after_filter": len(kept),
        "directories_selected": len(chosen),
        "repos_listed": len(all_repos),
        "repos_held_out": len(held_repos),
        "repos_selected": len(repos),
    }
    return Population(
        directories=tuple(sorted(n for n, _, _ in chosen)),
        repos=tuple(repos),
        published={r: frozenset(v) for r, v in published.items()},
        counts=counts,
    )


def first_repos(population: Population, n: int) -> list[str]:
    """The first ``n`` repositories of the seeded order (D60 pilot: 200)."""
    return list(population.repos[:n])


@dataclass(frozen=True)
class SelectionRow:
    """One repository: linked merged pull requests and how many the published pool kept."""

    repo: str
    linked_prs: int
    kept_by_pool: int
    published_in_selection: int

    @property
    def kept_share(self) -> float:
        """Share of the repository's linked pull requests that the published pool kept."""
        return self.kept_by_pool / self.linked_prs if self.linked_prs else 0.0


def selection_rows(
    linked: Mapping[str, Sequence[int]], published: Mapping[str, frozenset[int]]
) -> list[SelectionRow]:
    """Per repository: linked PR numbers against the pool's kept PR numbers (sorted by repo).

    ``published_in_selection`` counts the pool's PRs of the repository that are *not* among the
    linked ones (the pool carries them although no closing reference was found): reported so the
    two links are comparable and never hidden.
    """
    rows: list[SelectionRow] = []
    for repo in sorted(linked):
        have = set(linked[repo])
        kept = published.get(repo, frozenset())
        rows.append(
            SelectionRow(
                repo=repo,
                linked_prs=len(have),
                kept_by_pool=len(have & kept),
                published_in_selection=len(kept - have),
            )
        )
    return rows


def selection_summary(rows: Sequence[SelectionRow]) -> dict[str, Any]:
    """Aggregate of the selection rows: totals and the pooled kept share."""
    linked = sum(r.linked_prs for r in rows)
    kept = sum(r.kept_by_pool for r in rows)
    extra = sum(r.published_in_selection for r in rows)
    return {
        "repos": len(rows),
        "linked_prs": linked,
        "kept_by_pool": kept,
        "kept_share": kept / linked if linked else 0.0,
        "published_not_linked": extra,
    }


def rename_report(queried: Mapping[str, str]) -> Counter[str]:
    """Counts of repositories whose current name differs from the queried one."""
    c: Counter[str] = Counter()
    for old, new in queried.items():
        c["renamed" if old.lower() != new.lower() else "same"] += 1
    return c
