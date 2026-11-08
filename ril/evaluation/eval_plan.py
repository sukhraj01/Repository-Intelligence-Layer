"""Plan-only check of the evaluation sets a checkpoint is scored on (no model, no torch).

Lists, per evaluation set, the unit-text stores and query stores ``eval_checkpoint`` would encode,
their sizes, the number of unit texts and queries, and what is missing, so a launch can stop before
a GPU job starts. Implements ``docs/RQ2_PROTOCOL.md`` section 4 and ``docs/RQ2_LAUNCH_PLAN.md``.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ril.evaluation.checkpoint_eval import stores_for
from ril.evaluation.e1_run import load_config

TEXTS_PER_SECOND_MEASURED = 109.0
"""Overall encoding rate of the eight-repository build (E-EVAL-REPOS-BUILD), the lowest in use."""


@dataclass(frozen=True)
class EvalSet:
    name: str
    e1_config: str
    prep_dir: str
    roles: tuple[str, ...]
    e3_cache: str


def _lines(path: str) -> int:
    with open(path, "rb") as handle:
        return sum(1 for _ in handle)


def _distinct_texts(files: Sequence[str]) -> int:
    """Distinct text hashes (``h``) over the shards of one repository, as the encoder sees them.

    The shards ``sN`` hold the class-source forms of one repository, which share most texts;
    counting lines overstates the encoding by about 3 times (233,064 lines against 69,961 distinct
    texts for the eight repositories, E-EVAL-REPOS-BUILD).
    """
    seen: set[str] = set()
    for path in files:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    seen.add(str(json.loads(line)["h"]))
                except (ValueError, KeyError, TypeError):
                    seen.add(line)
    return len(seen)


def plan_set(
    s: EvalSet, *, chunks: bool = False, rate: float = TEXTS_PER_SECOND_MEASURED
) -> dict[str, Any]:
    """What one evaluation set needs; ``missing`` is non-empty when the launch must not start."""
    missing: list[str] = []
    for label, path in (
        ("e1_config", s.e1_config),
        ("prep_dir", s.prep_dir),
        ("e3_cache", s.e3_cache),
    ):
        if not os.path.exists(path):
            missing.append(f"{label}: {path}")
    if missing:
        return {"set": s.name, "roles": list(s.roles), "missing": missing}
    cfg = load_config(s.e1_config)
    wanted_repos = sorted(
        {
            str(f["repo"]).replace("/", "__")
            for f in cfg["folders"]
            if f["role"] in s.roles and f.get("units")
        }
    )
    stores = stores_for(s.e1_config, s.prep_dir, list(s.roles), chunks)
    unit_texts = 0
    unit_lines = 0
    queries = 0
    for name, files in stores.items():
        if name.startswith("units__"):
            unit_texts += _distinct_texts(files)
            unit_lines += sum(_lines(f) for f in files)
        elif name.startswith("queries__"):
            queries += sum(_lines(f) for f in files)
    have = {n.removeprefix("units__") for n in stores if n.startswith("units__")}
    missing += [f"unit texts of {r}" for r in wanted_repos if r not in have]
    cache_files = len(os.listdir(s.e3_cache))
    return {
        "set": s.name,
        "roles": list(s.roles),
        "repositories": wanted_repos,
        "unit_text_stores": len(have),
        "unit_texts": unit_texts,
        "unit_lines": unit_lines,
        "query_texts": queries,
        "instance_cache_files": cache_files,
        "encode_seconds_at_rate": round(unit_texts / rate, 1),
        "encode_gpu_hours_at_rate": round(unit_texts / rate / 3600, 3),
        "missing": missing,
    }


def plan_sets(sets: Sequence[EvalSet], **kw: Any) -> Mapping[str, Any]:
    rows = [plan_set(s, **kw) for s in sets]
    return {
        "sets": rows,
        "ready": all(not r["missing"] for r in rows),
        "encode_gpu_hours_per_checkpoint": round(
            sum(r.get("encode_gpu_hours_at_rate", 0.0) for r in rows), 3
        ),
    }
