"""Assembly configuration. Implements ``specs/assembly.md`` ("Configuration").

The budget has no default: no value is chosen for the agent here (the grid below is for
measurement only). ``max_unit_tokens`` is ``provisional: D102`` until the RQ3 pilots.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

ASSEMBLY_VERSION = "assembly/v1"

DEFAULT_MAX_UNIT_TOKENS = 1000
"""Cap on the text of one unit, in tokens (``provisional: D102``; reasoned, not tuned)."""

BUDGET_GRID: tuple[int, ...] = (4000, 8000, 16000, 32000)
"""Budgets used by the measurement; not a choice for the agent."""

MIN_MAX_UNIT_TOKENS = 32
"""Smallest cap that still leaves room for the truncation marker."""


@dataclass(frozen=True)
class AssemblyConfig:
    """What decides the bytes of the context besides the inputs."""

    budget: int
    max_unit_tokens: int = DEFAULT_MAX_UNIT_TOKENS

    def __post_init__(self) -> None:
        if self.budget <= 0:
            raise ValueError("budget must be positive")
        if self.max_unit_tokens < MIN_MAX_UNIT_TOKENS:
            raise ValueError(f"max_unit_tokens must be at least {MIN_MAX_UNIT_TOKENS}")

    def config_hash(self, tokenizer_name: str) -> str:
        """SHA-256 of the canonical JSON of the configuration, version and tokenizer name."""
        payload = {**asdict(self), "version": ASSEMBLY_VERSION, "tokenizer": tokenizer_name}
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()
