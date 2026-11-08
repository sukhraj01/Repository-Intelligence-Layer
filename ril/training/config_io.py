"""Training configuration: loading, hashing, comparability and the budget end (no torch).

Moved out of ``ril.training.training`` so that the plan-only launcher and the cell table can
validate and hash configurations on a machine without torch. ``ril.training.training`` re-exports
every name, and the configuration hash is unchanged (pinned by a test).
Implements ``docs/08_experimental_design.md`` "Held identical across arms".
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

TRAINING_VERSION = "training/v1"
PROVISIONAL = "provisional: ADR-001, ADR-002, ADR-006"
REQUIRED = (
    "exp_id",
    "rq",
    "seed",
    "model",
    "batch",
    "negatives",
    "loss",
    "optimizer",
    "budget",
    "checkpoint",
    "arm",
)
ARM_KEYS = frozenset({"arm"})
"""Configuration keys allowed to differ between the arms of one comparison."""
LABEL_KEYS = frozenset({"exp_id", "label", "notes"})
"""Keys that name a run and do not change what it computes."""
STORAGE_KEYS = frozenset({("checkpoint", "retain_final")})
"""Nested keys that only say where outputs are kept (``ril.training.retention``): not hashed."""
Record = dict[str, Any]


def _without_storage_keys(cfg: Mapping[str, Any]) -> Record:
    """The configuration without the storage options (they change no computed value)."""
    out: Record = {k: dict(v) if isinstance(v, Mapping) else v for k, v in cfg.items()}
    for section, key in STORAGE_KEYS:
        if isinstance(out.get(section), dict):
            out[section].pop(key, None)
    return out


def config_hash(cfg: Mapping[str, Any]) -> str:
    """SHA-256 over the canonical JSON of the parsed configuration and the code version.

    ``checkpoint.retain_final`` is left out: retaining the final model changes where a file is
    written and nothing that is computed, so a run keeps its hash and its result directory.
    """
    blob = json.dumps(
        {"version": TRAINING_VERSION, "config": _without_storage_keys(cfg)},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def load_train_config(path: str) -> Record:
    """Read and check a training configuration.

    Refuses: a missing required section; a ``provisional`` configuration under ``configs/frozen/``
    (provisional settings never enter the frozen configuration).
    """
    with open(path, encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle)
    if not isinstance(cfg, dict):
        raise ValueError(f"{path}: expected a mapping")
    missing = [k for k in REQUIRED if k not in cfg]
    if missing:
        raise ValueError(f"{path}: missing sections {missing}")
    parts = Path(path).resolve().parts
    if cfg.get("provisional") and "frozen" in parts and "configs" in parts:
        raise ValueError(f"{path}: a provisional configuration may not live in configs/frozen/")
    return cfg


def held_identical_view(cfg: Mapping[str, Any]) -> Record:
    """The configuration without the arm and the run labels: what must match across arms."""
    return {k: v for k, v in _without_storage_keys(cfg).items() if k not in ARM_KEYS | LABEL_KEYS}


def check_comparable(cfgs: Sequence[Mapping[str, Any]]) -> None:
    """Raise if two configurations differ anywhere but in the arm (and run labels).

    Why: RQ2 varies the supervision strategy and nothing else (``docs/08_experimental_design.md``
    "Held identical across arms"); this is the configuration-level half of that guarantee, the
    hooks test is the code-level half.
    """
    if not cfgs:
        return
    ref = held_identical_view(cfgs[0])
    for c in cfgs[1:]:
        view = held_identical_view(c)
        if view != ref:
            diff = sorted(k for k in set(ref) | set(view) if ref.get(k) != view.get(k))
            raise ValueError(f"configurations differ outside the arm: {diff}")


def planned_end(cfg: Mapping[str, Any]) -> int:
    """Update count at which a run is complete: ``budget.stop_after`` if set, else ``updates``.

    ``budget.stop_after`` ends the run early on the learning-rate schedule of ``budget.updates``
    (warm-up and linear decay are functions of the planned total, so a run that is meant to be
    "N updates of a longer schedule" keeps that schedule). The run is then finished: the final
    model is exported and the results written, without a learning-curve hook. It is part of the
    configuration hash.
    """
    updates = int(cfg["budget"]["updates"])
    end = int(cfg["budget"].get("stop_after") or updates)
    if not 0 < end <= updates:
        raise ValueError("budget.stop_after must be in 1..budget.updates")
    return end


def teacher_equals_base(cfg: Mapping[str, Any]) -> bool:
    """Whether an arm hook's K-rank teacher is the base checkpoint being fine-tuned (Q52).

    Recorded, not refused: a frozen copy of the starting weights is not the model being trained, but
    it is the model's own starting view of which examples are easy (SweRank filtered with the
    encoder it then fine-tuned). Whether that is allowed is ADR-002's.
    """
    base = cfg["model"].get("encoder")
    hooks = [cfg["arm"].get(k) or {} for k in ("filter", "weight", "ordering")]
    return base is not None and any(base in str(h.get("teacher") or "").split("+") for h in hooks)
