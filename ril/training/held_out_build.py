"""Summaries behind the held-out repository list: folders to repositories, overlaps, paired n.

Implements ``specs/held_out_repos.md`` ("Outputs", acceptance criteria) and
``docs/04_data_and_ground_truth.md`` ("The opportunity"). Works on per-folder records that hold
only instance ids (``queries_ids``) and qrels counts, never dataset text. A CORE-Bench folder
name is truncated and is not a repository name, so the repository of a folder is read from the
instance ids inside it; a folder whose ids give no readable repository is reported as unresolved
and is never guessed.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from ril.training.held_out import canonical_repo, repo_from_instance_id


@dataclass(frozen=True)
class FolderEvidence:
    """What the instance ids of one CORE-Bench folder say about its repositories."""

    level: str
    dataset: str
    folder: str
    repos: tuple[str, ...]
    unresolved_ids: tuple[str, ...]
    n_queries: int

    @property
    def folder_has_owner_separator(self) -> bool:
        """True if the folder name contains ``__`` (the ``owner__name`` form)."""
        return "__" in self.folder

    @property
    def folder_matches_repo(self) -> bool:
        """True if the folder name, read as ``owner__name``, equals its only repository."""
        if len(self.repos) != 1 or not self.folder_has_owner_separator:
            return False
        folder = self.folder.removeprefix("instance_")
        try:
            return canonical_repo(folder) == self.repos[0]
        except ValueError:
            return False


def folder_evidence(level: str, dataset: str, folder: str, ids: Iterable[str]) -> FolderEvidence:
    """Read the repositories of one folder from its query ids."""
    repos: set[str] = set()
    bad: list[str] = []
    n = 0
    for i in ids:
        n += 1
        repo = repo_from_instance_id(i)
        if repo is None:
            bad.append(i)
        else:
            repos.add(repo)
    return FolderEvidence(level, dataset, folder, tuple(sorted(repos)), tuple(bad), n)


def repos_by_source(evidence: Iterable[FolderEvidence]) -> dict[str, set[str]]:
    """Group canonical repositories by ``<level>:<dataset>`` source label."""
    out: dict[str, set[str]] = {}
    for ev in evidence:
        out.setdefault(f"{ev.level}:{ev.dataset}", set()).update(ev.repos)
    return out


def merge_level(by_source: Mapping[str, set[str]], level: str) -> set[str]:
    """Union of the repositories of every dataset of ``level``."""
    prefix = f"{level}:"
    merged: set[str] = set()
    for key, repos in by_source.items():
        if key.startswith(prefix):
            merged |= repos
    return merged


def pairwise_overlaps(sets: Mapping[str, set[str]]) -> dict[str, int]:
    """Return ``|A and B|`` for every unordered pair of named sets (keys sorted)."""
    names = sorted(sets)
    return {
        f"{a} & {b}": len(sets[a] & sets[b]) for i, a in enumerate(names) for b in names[i + 1 :]
    }


@dataclass(frozen=True)
class PairedN:
    """Instance counts available for a paired analysis."""

    l2_verified: int
    l3_verified: int
    l2_and_l3_verified: int
    l2_not_in_verified_metadata: int = 0
    l3_not_in_verified_metadata: int = 0
    notes: dict[str, int] = field(default_factory=dict)


def paired_n(
    l2_ids: Iterable[str],
    l3_ids: Iterable[str],
    verified_ids: Iterable[str],
) -> PairedN:
    """Count instances present in L2-Verified, L3-Verified and both, against Verified metadata.

    ``l2_ids`` / ``l3_ids`` are the query ids of the SWE-bench_Verified folders of each level;
    ``verified_ids`` are the ``instance_id`` values of the SWE-bench Verified dataset.
    """
    v = set(verified_ids)
    a, b = set(l2_ids), set(l3_ids)
    return PairedN(
        l2_verified=len(a & v),
        l3_verified=len(b & v),
        l2_and_l3_verified=len(a & b & v),
        l2_not_in_verified_metadata=len(a - v),
        l3_not_in_verified_metadata=len(b - v),
        notes={"l2_queries": len(a), "l3_queries": len(b), "verified_rows": len(v)},
    )


def count_by(values: Iterable[str]) -> dict[str, int]:
    """Counter as a sorted plain dict."""
    return dict(sorted(Counter(values).items()))
