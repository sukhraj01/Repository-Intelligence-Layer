"""Turn a ranked list of candidate units into the context an agent reads.

Implements ``specs/assembly.md`` and ``docs/09_architecture.md`` "Online retrieval" (last step).
The policy is the same for every retriever, so that the only thing that varies between RQ2 arms
(and RQ3 runs) is the ranked list:

1. take candidates in rank order; skip a repeated unit, an unknown unit, an empty one;
2. cut the unit's text at ``max_unit_tokens`` (whole lines, then a marker);
3. include it if header, text and separator still fit in the remaining budget, otherwise skip it
   and go on with the next candidate (no other reordering);
4. order the included blocks by file path and line, so each file reads top to bottom;
5. verify the finished string against the budget.

No graph or same-file expansion happens here (decision D102; E-GRAPH-ROLE).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass

from ril.assembly.config import AssemblyConfig
from ril.assembly.tokens import Tokenizer

SEPARATOR = "\n\n"
HEADER_PREFIX = "### "
SKIP_REASONS: tuple[str, ...] = (
    "duplicate",
    "unknown_unit",
    "empty_text",
    "does_not_fit",
    "final_check",
)


@dataclass(frozen=True)
class Candidate:
    """One entry of the ranked list; ``stages`` names what produced it (kept, not used)."""

    unit_id: str
    score: float
    stages: tuple[str, ...] = ()


@dataclass(frozen=True)
class UnitText:
    """What the assembler needs of a unit; class units arrive in header form (D102)."""

    unit_id: str
    file: str
    start_line: int
    end_line: int
    unit_type: str
    qualified_name: str
    source: str


@dataclass(frozen=True)
class ManifestEntry:
    """A unit in the context, in context order."""

    unit_id: str
    rank: int
    file: str
    start_line: int
    end_line: int
    tokens: int
    truncated: bool
    stages: tuple[str, ...]


@dataclass(frozen=True)
class Skipped:
    """A candidate that is not in the context, with the reason."""

    unit_id: str
    rank: int
    reason: str
    tokens_needed: int = 0


@dataclass(frozen=True)
class Manifest:
    """What went into the context; ``total_tokens`` counts the finished string."""

    budget: int
    max_unit_tokens: int
    tokenizer: str
    config_hash: str
    total_tokens: int
    context_sha256: str
    entries: tuple[ManifestEntry, ...]
    skipped: tuple[Skipped, ...]

    def to_json(self) -> str:
        """Canonical JSON (sorted keys, compact), the same bytes for the same manifest."""
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))

    def unit_ids(self) -> list[str]:
        return [e.unit_id for e in self.entries]

    def files(self) -> set[str]:
        return {e.file for e in self.entries}


@dataclass(frozen=True)
class Assembled:
    context: str
    manifest: Manifest


def block_header(unit: UnitText, rank: int) -> str:
    """The header line of a block: path and lines, kind and qualified name, retrieval rank."""
    return (
        f"{HEADER_PREFIX}{unit.file}:{unit.start_line}-{unit.end_line} "
        f"{unit.unit_type} {unit.qualified_name} (rank {rank})"
    )


def _marker(lines_left: int) -> str:
    return f"# ... truncated, {lines_left} more lines"


def truncate_text(text: str, limit: int, tok: Tokenizer) -> tuple[str, bool]:
    """``text`` cut to at most ``limit`` tokens; whole lines, then a marker with the lines left.

    A text within the limit is returned unchanged. If not even the first line fits, that line is
    cut by characters. The result (marker included) never counts more than ``limit`` tokens.
    """
    if tok.count(text) <= limit:
        return text, False
    lines = text.split("\n")

    def build(k: int) -> str:
        return "\n".join(lines[:k] + [_marker(len(lines) - k)])

    # largest k in [1, len - 1] with build(k) within the limit; 0 means none fits
    lo, hi = 0, len(lines) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if tok.count(build(mid)) <= limit:
            lo = mid
        else:
            hi = mid - 1
    if lo >= 1:
        return build(lo), True
    first = lines[0]
    a, b = 0, len(first)
    while a < b:
        mid = (a + b + 1) // 2
        if tok.count(first[:mid] + "\n" + _marker(len(lines) - 1)) <= limit:
            a = mid
        else:
            b = mid - 1
    return first[:a] + "\n" + _marker(len(lines) - 1), True


_Chosen = tuple[int, Candidate, UnitText, str, int, bool]


def assemble(
    candidates: Sequence[Candidate],
    snapshot: Mapping[str, UnitText],
    config: AssemblyConfig,
    tok: Tokenizer,
) -> Assembled:
    """Assemble the context of ``candidates`` (rank order) from ``snapshot`` within the budget."""
    sep_cost = tok.count(SEPARATOR)
    remaining = config.budget
    seen: set[str] = set()
    chosen: list[_Chosen] = []
    skipped: list[Skipped] = []
    for rank, cand in enumerate(candidates, start=1):
        if cand.unit_id in seen:
            skipped.append(Skipped(cand.unit_id, rank, "duplicate"))
            continue
        seen.add(cand.unit_id)
        unit = snapshot.get(cand.unit_id)
        if unit is None:
            skipped.append(Skipped(cand.unit_id, rank, "unknown_unit"))
            continue
        if not unit.source.strip():
            skipped.append(Skipped(cand.unit_id, rank, "empty_text"))
            continue
        body, truncated = truncate_text(unit.source, config.max_unit_tokens, tok)
        block = block_header(unit, rank) + "\n" + body
        tokens = tok.count(block)
        if tokens + sep_cost > remaining:
            skipped.append(Skipped(cand.unit_id, rank, "does_not_fit", tokens + sep_cost))
            continue
        remaining -= tokens + sep_cost
        chosen.append((rank, cand, unit, block, tokens, truncated))

    chosen.sort(key=lambda c: (c[2].file, c[2].start_line, c[2].end_line, c[2].unit_id))
    context = SEPARATOR.join(c[3] for c in chosen)
    # the per-block accounting is exact for an additive tokenizer; verify the finished string
    while chosen and tok.count(context) > config.budget:
        worst = max(range(len(chosen)), key=lambda i: chosen[i][0])
        rank, cand, _, _, tokens, _ = chosen.pop(worst)
        skipped.append(Skipped(cand.unit_id, rank, "final_check", tokens))
        context = SEPARATOR.join(c[3] for c in chosen)
    entries = tuple(
        ManifestEntry(
            unit_id=c.unit_id,
            rank=rank,
            file=u.file,
            start_line=u.start_line,
            end_line=u.end_line,
            tokens=tokens,
            truncated=truncated,
            stages=c.stages,
        )
        for rank, c, u, _, tokens, truncated in chosen
    )
    manifest = Manifest(
        budget=config.budget,
        max_unit_tokens=config.max_unit_tokens,
        tokenizer=tok.name,
        config_hash=config.config_hash(tok.name),
        total_tokens=tok.count(context) if chosen else 0,
        context_sha256=hashlib.sha256(context.encode("utf-8")).hexdigest(),
        entries=entries,
        skipped=tuple(sorted(skipped, key=lambda s: s.rank)),
    )
    return Assembled(context, manifest)


def snapshot_of(units: Iterable[UnitText]) -> dict[str, UnitText]:
    """Index units by id; a repeated id is an error (ids are unique in a snapshot)."""
    out: dict[str, UnitText] = {}
    for u in units:
        if u.unit_id in out:
            raise ValueError(f"duplicate unit id in snapshot: {u.unit_id}")
        out[u.unit_id] = u
    return out
