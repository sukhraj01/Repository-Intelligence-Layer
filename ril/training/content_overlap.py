"""Content-overlap audit between a training pool and held-out code (decision D1).

Reported, not a filter: it measures how much code in a pool repository also occurs in held-out
repositories, which is what a fork, a vendored copy or a mirror under another name looks like and
what name matching cannot see. The SweRank paper also removed near-identical repositories by
source-code overlap (read in full, ``knowledge/papers/swerank-2505.07849.md``, Sec. 3.1).

Method. A line is *informative* if, after stripping and collapsing whitespace, it is at least
``MIN_LINE_CHARS`` long and not a comment. The held-out side is a set of 64-bit hashes of its
informative lines (it works for fixed-window chunks as well as functions, since it needs no unit
boundaries). A pool unit (a function) is *covered* if at least ``COVER_THRESHOLD`` of its
informative lines occur in the index and it has at least ``MIN_LINES`` of them. A pool repository's
score is the share of its scored units that are covered. Controls are part of the design: a held-out
chunk offered as a pool unit must score 1.0, and unrelated repositories give the chance level.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

MIN_LINE_CHARS = 25
MIN_LINES = 3
COVER_THRESHOLD = 0.8
_WS_RE = re.compile(r"\s+")


def informative_lines(text: str) -> list[str]:
    """Normalised lines worth comparing: long enough and not a comment."""
    out: list[str] = []
    for raw in text.splitlines():
        line = _WS_RE.sub(" ", raw).strip()
        if len(line) >= MIN_LINE_CHARS and not line.startswith("#"):
            out.append(line)
    return out


def line_hash(line: str) -> int:
    """Stable 64-bit hash of a normalised line (not ``hash()``, which varies per process)."""
    return int.from_bytes(hashlib.blake2b(line.encode("utf-8"), digest_size=8).digest(), "big")


def build_index(texts: Iterable[str]) -> set[int]:
    """Hashes of every informative line of the held-out texts."""
    index: set[int] = set()
    for t in texts:
        index.update(line_hash(ln) for ln in informative_lines(t))
    return index


def unit_coverage(text: str, index: set[int]) -> tuple[int, int]:
    """``(informative lines, of those found in the index)`` for one pool unit."""
    lines = informative_lines(text)
    return len(lines), sum(1 for ln in lines if line_hash(ln) in index)


@dataclass(frozen=True)
class RepoOverlap:
    """Overlap of one pool repository with the held-out index."""

    repo: str
    units_scored: int
    units_covered: int

    @property
    def share(self) -> float:
        """Share of scored units that are covered (0.0 if none could be scored)."""
        return self.units_covered / self.units_scored if self.units_scored else 0.0


def audit_repo(
    repo: str,
    unit_texts: Sequence[str],
    index: set[int],
    threshold: float = COVER_THRESHOLD,
    min_lines: int = MIN_LINES,
) -> RepoOverlap:
    """Score one pool repository (units under ``min_lines`` informative lines are skipped)."""
    scored = covered = 0
    for text in unit_texts:
        n, hit = unit_coverage(text, index)
        if n < min_lines:
            continue
        scored += 1
        covered += hit / n >= threshold
    return RepoOverlap(repo, scored, covered)


def audit_pool(units_by_repo: Mapping[str, Sequence[str]], index: set[int]) -> list[RepoOverlap]:
    """Audit every repository, ordered by overlap share (highest first) then name."""
    rows = [audit_repo(r, t, index) for r, t in sorted(units_by_repo.items())]
    return sorted(rows, key=lambda x: (-x.share, x.repo))
