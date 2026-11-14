"""Label manifest of one prepared part: which members have gold, per level (torch-free).

Implements the empty-part rule of ``docs/DEVIATIONS.md`` DEV-043 (addendum). A part of the
executable 377 whose members carry queries but no labels has nothing to evaluate; the scoring job
may then accept an empty evaluation folder, and only then. The manifest is read from the instance
caches with the rule ``ril.evaluation.x2_eval.evaluate_instance`` applies (a level counts when at
least one gold reading is non-empty), so the manifest and the evaluation cannot disagree.
"""

from __future__ import annotations

import glob
import json
import os
from collections.abc import Collection
from typing import Any

import numpy as np

from ril.evaluation.e3_prepare import READINGS

Record = dict[str, Any]


def label_manifest(cache_dir: str, roles: Collection[str]) -> Record:
    """``{members, labelled, levels: {level: n}, unlabelled}`` of the caches of the given roles."""
    members = 0
    labelled = 0
    levels: dict[str, int] = {}
    unlabelled: list[str] = []
    for path in sorted(glob.glob(os.path.join(cache_dir, "*.npz"))):
        if path.endswith(".tmp.npz"):
            continue
        with np.load(path, allow_pickle=False) as data:
            meta = json.loads(str(data["meta"]))
            if meta.get("role") not in roles:
                continue
            members += 1
            got = False
            for level in meta["levels"]:
                names = [f"gold_{level}_{r}" for r in READINGS]
                if all(n in data.files for n in names) and any(len(data[n]) for n in names):
                    levels[level] = levels.get(level, 0) + 1
                    got = True
        if got:
            labelled += 1
        else:
            unlabelled.append(str(meta["instance"]))
    if members == 0:
        raise ValueError(f"no instance caches of roles {sorted(roles)} under {cache_dir}")
    return {
        "members": members,
        "labelled": labelled,
        "levels": dict(sorted(levels.items())),
        "unlabelled": unlabelled,
    }
