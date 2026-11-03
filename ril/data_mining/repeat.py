"""Repeat part of a finished run and compare the bytes (check of a code change on real data).

Implements ``docs/experiments/B.md`` E-MINE-PILOT (scale-up preparation). The pull requests that a
reference run root mined, for its first ``n_repos`` repositories, are mined again by the current
code into a new run root (listings copied from the reference, so no listing call is made), and
every file of every directory is compared with the reference. The peak resident memory of the process is
reported, so a change meant to lower it is measured on the same pull requests.

Kept compatible with Python 3.10 (the cluster's compute nodes).
"""

from __future__ import annotations

import os
import resource
import shutil
from collections.abc import Sequence
from typing import Any

from ril.data_mining.config import MiningConfig
from ril.data_mining.github_api import ApiClient
from ril.data_mining.links import PullRequest
from ril.data_mining.miner import dir_name
from ril.data_mining.pack import list_dirs
from ril.data_mining.runner import mine_selected
from ril.data_mining.snapshot import SnapshotProvider
from ril.data_mining.store import MiningStore


def peak_mb() -> float:
    """Peak resident set of this process in MB (Linux reports kilobytes)."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def repeat(
    reference: str,
    out: str,
    *,
    repos: Sequence[str],
    config: MiningConfig,
    client: ApiClient,
    snapshots: SnapshotProvider,
    lookahead: int = 1,
) -> dict[str, Any]:
    """Mine again the reference's mined pull requests of ``repos`` into ``out``; compare bytes."""
    ref = MiningStore(reference)
    new = MiningStore(out)
    os.makedirs(os.path.join(out, "listing"), exist_ok=True)
    state = ref.load_state()
    selected: list[PullRequest] = []
    for repo in repos:
        shutil.copyfile(ref.listing_path(repo), new.listing_path(repo))
        _, prs = new.load_listing(repo)
        selected += [p for p in prs if state.get(p.key, {}).get("status") == "mined"]
    new.ensure_run(config.config_hash(), "repeat")
    summary = mine_selected(
        selected, client=client, snapshots=snapshots, store=new, config=config, lookahead=lookahead
    )
    same = different = missing = 0
    differing: list[str] = []
    for p in selected:
        name = dir_name(p.repo, p.number)
        a, b = os.path.join(reference, "pr", name), os.path.join(out, "pr", name)
        if not os.path.isdir(b):
            missing += 1
            continue
        equal = True
        for base, _dirs, files in os.walk(a):
            for f in files:
                rel = os.path.relpath(os.path.join(base, f), a)
                other = os.path.join(b, rel)
                if not os.path.exists(other) or not _same(os.path.join(base, f), other):
                    equal = False
        if equal and sorted(os.listdir(b)) == sorted(os.listdir(a)):
            same += 1
        else:
            different += 1
            differing.append(name)
    return {
        "repositories": len(repos),
        "selected": len(selected),
        "attempted": summary.attempted,
        "outcomes": summary.outcomes,
        "directories_identical": same,
        "directories_different": different,
        "directories_missing": missing,
        "different": differing[:20],
        "peak_rss_mb": round(peak_mb(), 1),
        "directories_in_new_root": len(list_dirs(out)),
    }


def _same(a: str, b: str) -> bool:
    with open(a, "rb") as fa, open(b, "rb") as fb:
        while True:
            ca, cb = fa.read(1 << 20), fb.read(1 << 20)
            if ca != cb:
                return False
            if not ca:
                return True
