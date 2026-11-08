"""Evaluation-repository selection (D100): applies the recorded rule to the inventory table.

Implements docs/RQ2_PROTOCOL.md section 11 (O8a) and E-EVAL-REPOS in docs/experiments/B.md.
Nothing else may choose or reorder: the pool is the Python-class repositories outside dev and
Verified with at least ``FLOOR_L2_QUERIES`` L2 queries, ordered by ``sha256("0:<repository>")``;
the first ``N_PRIMARY`` are the evaluation set, the next ``N_RESERVE`` the reserve.
"""

from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path

KEY_PREFIX = "0:"
FLOOR_L2_QUERIES = 5
N_PRIMARY = 8
N_RESERVE = 8
EXCLUDED_GROUPS = ("dev", "verified")
RULE_TEXT = (
    "Python-class repositories outside dev and Verified with at least 5 L2 queries, ordered by "
    'sha256("0:<repository>") ascending; the first eight are the evaluation set, the next eight '
    "the reserve (used only for a technical build failure recorded before any result is read)"
)


@dataclass(frozen=True)
class Selection:
    eligible: int
    primary: list[tuple[str, int]]
    reserve: list[tuple[str, int]]


def order_key(repository: str) -> str:
    return hashlib.sha256(f"{KEY_PREFIX}{repository}".encode()).hexdigest()


def select(inventory: Path) -> Selection:
    with inventory.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    pool = [
        (r["repository"], int(r["l2_queries"]))
        for r in rows
        if r["language_class"] == "python"
        and r["set_group"] not in EXCLUDED_GROUPS
        and int(r["l2_queries"]) >= FLOOR_L2_QUERIES
    ]
    pool.sort(key=lambda t: (order_key(t[0]), t[0]))
    return Selection(
        eligible=len(pool),
        primary=pool[:N_PRIMARY],
        reserve=pool[N_PRIMARY : N_PRIMARY + N_RESERVE],
    )


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
