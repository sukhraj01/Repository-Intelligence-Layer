"""Mining configuration: every parameter of a run in one hashed record (no magic constants).

Implements ``docs/experiments/B.md`` E-MINE-PILOT, designs D60 to D66. ``provisional`` marks the
values the engineer has not settled; none of them enters ``configs/frozen/``.

Kept compatible with Python 3.10 (the cluster's compute nodes).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

MINING_VERSION = "pr-mining/v1"
CORPUS_KINDS_FUNCTIONS: tuple[str, ...] = ("function", "method")
CORPUS_KINDS_ALL: tuple[str, ...] = ("function", "method", "class", "module")


@dataclass(frozen=True)
class MiningConfig:
    """Parameters of one mining run."""

    seed: int = 0
    n_repos: int = 200
    """Repositories taken from the seeded order of the pool's repository population (D60)."""
    max_prs: int = 2000
    """Pull requests mined (compare, snapshot, parse): a seeded sample of the linked ones."""
    pool_size: int = 5000
    """Directories of the published pool whose repositories form the population (D41)."""
    published_first: bool = False
    """Validation stage: linked pull requests that the published pool holds are mined first, so
    the agreement with the pool rests on all of them (DEV-019). Off in the pilot (seeded sample)."""
    corpus_kinds: tuple[str, ...] = CORPUS_KINDS_FUNCTIONS
    """Unit kinds in ``corpus.jsonl`` and ``qrels``; the published pool holds functions only.
    Positives of other kinds go to the side table (``provisional``: open question)."""
    include_loc_bench: bool = True
    """Loc-Bench tier of the held-out list switched on (D65)."""
    provisional: tuple[str, ...] = field(default_factory=lambda: ("ADR-001",))

    def to_dict(self) -> dict[str, Any]:
        """Plain dict (tuples as lists) for JSON."""
        d = asdict(self)
        d["corpus_kinds"] = list(self.corpus_kinds)
        d["provisional"] = list(self.provisional)
        d["version"] = MINING_VERSION
        return d

    def config_hash(self) -> str:
        """SHA-256 of the canonical JSON of the config."""
        text = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> MiningConfig:
        """Build from a YAML/JSON mapping; unknown keys are an error."""
        known = {f for f in cls.__dataclass_fields__}
        extra = set(raw) - known - {"version", "title", "note"}
        if extra:
            raise ValueError(f"unknown mining config keys: {sorted(extra)}")
        kwargs = {k: v for k, v in raw.items() if k in known}
        for name in ("corpus_kinds", "provisional"):
            if name in kwargs:
                kwargs[name] = tuple(kwargs[name])
        return cls(**kwargs)
