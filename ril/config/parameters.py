"""Run-level configuration: a frozen, hashable record loaded from YAML.

Implements docs/ARCHITECTURE.md "config": the configuration hash is recorded with every run.
Only run-plumbing lives here (seed, run name). Experiment parameters are added by the sessions
that own them, in ``configs/``, not as defaults in code.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class RunConfig:
    """Minimal run description shared by every entry point."""

    seed: int = 0
    name: str = "default"

    def to_dict(self) -> dict[str, Any]:
        """Return the configuration as a plain dict."""
        return asdict(self)

    def config_hash(self) -> str:
        """Return a stable SHA-256 over the canonical JSON form (key order independent)."""
        canonical = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_run_config(path: Path) -> RunConfig:
    """Load a ``RunConfig`` from a YAML mapping; unknown keys are rejected."""
    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected a mapping at the top level")
    return RunConfig(**raw)
