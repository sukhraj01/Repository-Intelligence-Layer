"""Rank comparison of the mined set against the published pool (stage M3, reading rule first).

Implements ``docs/experiments/B.md`` E-MINE-PILOT. The measure is the share of directories with no
positive in the top ``k`` under a teacher: the minimum ``rank`` over a directory's positives (the
published definition of ``ril.training.pool_ranks``: 1 plus the non-positive functions scored
strictly higher) exceeds ``k``. The interval is over directories (Wilson, a directory is one
independent draw); a repository-clustered bootstrap is reported beside it because directories of
one repository are not independent.

Reading rule (written before M3 runs, ``results/mining/README.md``): the comparison counts only
with at least ``MIN_DIRECTORIES`` mined directories that have a positive; below that the result is
reported as "too small to compare" together with the yield needed.

Kept compatible with Python 3.10 (the cluster's compute nodes).
"""

from __future__ import annotations

import hashlib
import math
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ril.data_mining.files import corpus_size
from ril.data_mining.pack import list_dirs
from ril.training import pool_ranks as pr

MIN_DIRECTORIES = 100
Z95 = 1.959963984540054
BOOTSTRAP_DRAWS = 2000


def min_ranks(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """``{directory: smallest rank among its positives}`` from rank records of one teacher."""
    out: dict[str, int] = {}
    for row in rows:
        ranks = [int(r["rank"]) for r in row["ranks"]]
        if ranks:
            out[str(row["dir"])] = min(ranks)
    return out


def wilson(successes: int, n: int) -> tuple[float, float]:
    """95% Wilson interval of a proportion (``(0, 0)`` for ``n == 0``)."""
    if n == 0:
        return 0.0, 0.0
    p = successes / n
    denom = 1 + Z95**2 / n
    centre = (p + Z95**2 / (2 * n)) / denom
    half = Z95 * math.sqrt(p * (1 - p) / n + Z95**2 / (4 * n**2)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def cluster_bootstrap(
    flags: Mapping[str, bool], repo_of: Mapping[str, str], seed: int = 0
) -> tuple[float, float]:
    """95% percentile interval of the share, resampling repositories with replacement.

    Deterministic: draws come from a SHA-256 stream keyed by ``seed`` (no global random state).
    """
    by_repo: dict[str, list[bool]] = {}
    for d, flag in flags.items():
        by_repo.setdefault(repo_of[d], []).append(flag)
    repos = sorted(by_repo)
    if not repos:
        return 0.0, 0.0
    shares: list[float] = []
    for b in range(BOOTSTRAP_DRAWS):
        hits = total = 0
        for i in range(len(repos)):
            digest = hashlib.sha256(f"{seed}:{b}:{i}".encode()).digest()
            repo = repos[int.from_bytes(digest[:8], "big") % len(repos)]
            hits += sum(by_repo[repo])
            total += len(by_repo[repo])
        shares.append(hits / total if total else 0.0)
    shares.sort()
    return shares[int(0.025 * BOOTSTRAP_DRAWS)], shares[int(0.975 * BOOTSTRAP_DRAWS) - 1]


@dataclass(frozen=True)
class ShareRow:
    """One teacher and cut: the share, its intervals and the directory count."""

    teacher: str
    k: int
    directories: int
    no_positive_in_top_k: int
    share: float
    wilson_low: float
    wilson_high: float
    cluster_low: float
    cluster_high: float


def share_row(
    teacher: str, k: int, ranks: Mapping[str, int], repo_of: Mapping[str, str], seed: int = 0
) -> ShareRow:
    """Share of directories whose best positive ranks beyond ``k``, with both intervals."""
    flags = {d: r > k for d, r in ranks.items()}
    n, hits = len(flags), sum(flags.values())
    lo, hi = wilson(hits, n)
    clo, chi = cluster_bootstrap(flags, repo_of, seed)
    return ShareRow(teacher, k, n, hits, hits / n if n else 0.0, lo, hi, clo, chi)


def reading_rule(directories_with_positive: int, yield_per_pr: float) -> dict[str, Any]:
    """Whether the comparison counts, and if not the number of pull requests needed.

    ``yield_per_pr`` is directories-with-a-positive per mined pull request (measured in M2).
    """
    ok = directories_with_positive >= MIN_DIRECTORIES
    needed = math.ceil(MIN_DIRECTORIES / yield_per_pr) if yield_per_pr > 0 else None
    return {
        "counts": ok,
        "reading": "comparable" if ok else "too small to compare",
        "directories_with_positive": directories_with_positive,
        "minimum": MIN_DIRECTORIES,
        "prs_needed_at_measured_yield": needed,
    }


def rank_sample(root: str) -> dict[str, Any]:
    """A selection file (as ``pool_rank_jobs`` reads it) covering every directory of a run root."""
    import json

    insts = []
    for name in list_dirs(root):
        base = os.path.join(root, "pr", name)
        with open(os.path.join(base, "pr_meta.json"), encoding="utf-8") as handle:
            meta = json.load(handle)
        size = corpus_size(base)
        insts.append(
            pr.PoolInstance(
                dir=name,
                repo=str(meta["repo"]),
                pr=int(meta["pr"]),
                corpus_bytes=size,
                positives=int(meta["counters"]["positives"]),
                held_out=False,
                size_bin=0,
            )
        )
    return {
        "sample": [pr.instance_record(i) for i in insts],
        "listing_prefix": "train/python/",
        "note": "every directory of the mined run; no strata",
    }
