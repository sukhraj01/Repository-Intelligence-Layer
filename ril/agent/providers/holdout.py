"""Held-out model-check slice of the executable subset. Implements ``docs/RQ3_PILOT.md`` (D111).

Fifty of the 377 executable instances are set aside by a seeded draw stratified over repositories.
They choose the model (D112) and exercise the grading path on real replies; they never enter a
confirmatory analysis, so the confirmatory sample is the other 327.

Allocation rule (fixed before any model call):

1. Repositories with at least ``MIN_REPO_SIZE`` executable instances contribute at least
   ``MIN_PER_REPO`` places.
2. The places are otherwise proportional to repository size: the shares ``n * size / total`` are
   computed; a large repository whose share is below the minimum is fixed at the minimum and the
   remaining places are shared proportionally over the remaining repositories (repeated until no
   share falls below the minimum).
3. Shares are rounded by the largest-remainder method on the unfixed repositories (ties broken by
   the repository name); a repository never gets more places than it has instances.
4. Inside a repository the instances are drawn uniformly, seeded, from the sorted instance ids.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from typing import Any

MIN_REPO_SIZE = 5
MIN_PER_REPO = 2
HOLDOUT_VERSION = "rq3-holdout/v1"


def allocate(sizes: Mapping[str, int], n: int) -> dict[str, int]:
    """Places per repository under the rule in the module docstring."""
    total = sum(sizes.values())
    if not 0 < n <= total:
        raise ValueError("n must be between 1 and the number of instances")
    fixed: dict[str, int] = {}
    free = sorted(sizes)
    while True:
        left = n - sum(fixed.values())
        weight = sum(sizes[r] for r in free)
        shares = {r: left * sizes[r] / weight for r in free}
        low = [
            r
            for r in free
            if sizes[r] >= MIN_REPO_SIZE and shares[r] < MIN_PER_REPO and r not in fixed
        ]
        if not low:
            break
        for r in low:
            fixed[r] = MIN_PER_REPO
            free.remove(r)
    if sum(fixed.values()) > n:
        raise ValueError("n is too small to give every large repository its minimum")
    out = dict(fixed)
    base = {r: int(shares[r]) for r in free}
    remaining = n - sum(fixed.values()) - sum(base.values())
    order = sorted(free, key=lambda r: (-(shares[r] - base[r]), r))
    for r in order[:remaining]:
        base[r] += 1
    out.update(base)
    for r, k in out.items():
        if k > sizes[r]:
            raise ValueError(f"{r}: {k} places for {sizes[r]} instances")
    return out


def draw_holdout(executable: Sequence[Mapping[str, Any]], n: int, seed: int) -> dict[str, Any]:
    """The frozen record: seed, rule version, places per repository and the sorted instances."""
    by_repo: dict[str, list[str]] = {}
    for r in executable:
        by_repo.setdefault(str(r["repo"]), []).append(str(r["instance_id"]))
    places = allocate({repo: len(ids) for repo, ids in by_repo.items()}, n)
    rng = random.Random(seed)
    picked: list[dict[str, str]] = []
    for repo in sorted(by_repo):
        ids = sorted(by_repo[repo])
        for iid in sorted(rng.sample(ids, places[repo])):
            picked.append({"instance_id": iid, "repo": repo})
    picked.sort(key=lambda r: (r["repo"], r["instance_id"]))
    return {
        "version": HOLDOUT_VERSION,
        "seed": seed,
        "n": n,
        "population": sum(len(v) for v in by_repo.values()),
        "min_repo_size": MIN_REPO_SIZE,
        "min_per_repo": MIN_PER_REPO,
        "by_repository": [
            {"repo": r, "executable": len(by_repo[r]), "held_out": places[r]}
            for r in sorted(by_repo)
        ],
        "instances": picked,
    }


def split(
    executable: Sequence[Mapping[str, Any]], holdout: Mapping[str, Any]
) -> tuple[list[str], list[str]]:
    """(held-out ids, confirmatory ids), both sorted; raises if the list names a stranger."""
    held = {str(r["instance_id"]) for r in holdout["instances"]}
    everyone = {str(r["instance_id"]) for r in executable}
    if not held <= everyone:
        raise ValueError("the held-out list names instances outside the executable subset")
    return sorted(held), sorted(everyone - held)
