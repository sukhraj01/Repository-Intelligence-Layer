"""Named evaluation sets of the RQ2 final experiment and the stage each may be used in.

One run cannot score every set (``docs/RQ2_LAUNCH_PLAN.md`` gap 2): the training jobs score the
development set only, and the eight repositories (D100) and the executable 377 of Verified (D127)
are scored once, from the retained models, after the dev analysis (the sealed order of D100).
This module names the sets, says where each lives under an account's home, and refuses a set
outside its stage. Nothing here imports torch; the paths are the layout of the stored builds
(``ril_x2``, ``ril_t1``, ``ril_eval``, ``ril_rq3u``, ``ril_rq3u_x``), checked on the cluster by
``scripts/rq2_plan.py eval``.

The executable 377 is built from three stored parts (the 36 instances with earlier records, the
337 built for five repositories, the four xarray instances). A part that lists more instances
than the subset (the earlier part holds every instance of the six folders) is filtered to the
executable instance ids when the rows are read (``executable_instances_v1.json``), never when
they are scored.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

EVAL_SETS_VERSION = "eval-sets/v1"
TRAINING = "training"
FINAL = "final"


@dataclass(frozen=True)
class EvalPart:
    """One stored build a set is scored on: configuration, prepared stores, instance cache."""

    part: str
    e1_config: str
    """Repository-relative path of the folder configuration."""
    prep: str
    """Home-relative directory of the prepared text stores."""
    e3_cache: str
    """Home-relative directory of the instance caches."""
    data_root: str
    """Home-relative directory of the raw folders (read only by chunk-level scoring)."""
    compressed_texts: bool = False
    """The unit-text stores are stored gzipped and must be unpacked to node-local space first."""


@dataclass(frozen=True)
class EvalSetSpec:
    name: str
    stage: str  # training | final
    roles: tuple[str, ...]
    parts: tuple[EvalPart, ...]
    deliberate_test: str | None
    """The label ``eval_checkpoint`` requires for role ``test`` (None for the dev set)."""
    decision: str


DEV = EvalSetSpec(
    "dev",
    TRAINING,
    ("dev",),
    (
        EvalPart(
            "dev_five",
            "configs/experiments/e1_bm25_reproduction.yaml",
            "ril_x2/prep",
            "work/e3_cache_dev5",
            "ril_x2/raw",
        ),
    ),
    None,
    "D131",
)
"""The pilots' five repositories (ansible not added): the instance cache is the dev subset of the
E3 cache, linked by ``scripts/curve_subset_cache.py`` as in the pilots."""

EIGHT = EvalSetSpec(
    "eight",
    FINAL,
    ("test",),
    (
        EvalPart(
            "eight",
            "configs/experiments/eval_repos_v1_build.yaml",
            "ril_eval/prep",
            "ril_eval/e3_cache",
            "ril_eval/raw",
        ),
    ),
    "RQ2 final: the eight evaluation repositories, scored once after the dev analysis",
    "D100",
)

VERIFIED_377 = EvalSetSpec(
    "exec377",
    FINAL,
    ("test",),
    (
        EvalPart(
            "stored36",
            "configs/experiments/e1_bm25_reproduction.yaml",
            "ril_x2/prep",
            "ril_t1/work/e3_cache",
            "ril_x2/raw",
        ),
        EvalPart(
            "built337",
            "configs/experiments/rq3_units_v1.yaml",
            "ril_rq3u/prep",
            "ril_rq3u/e3_cache",
            "ril_rq3u/raw",
            compressed_texts=True,
        ),
        EvalPart(
            "built_xarray",
            "configs/experiments/rq3_units_v1_xarray.yaml",
            "ril_rq3u_x/prep",
            "ril_rq3u_x/e3_cache",
            "ril_rq3u_x/raw",
            compressed_texts=True,
        ),
    ),
    "RQ2 final: executable 377 of Verified, scored once after the dev analysis",
    "D127",
)

SETS: dict[str, EvalSetSpec] = {s.name: s for s in (DEV, EIGHT, VERIFIED_377)}


class EvalSetRefused(ValueError):
    """A set was asked for in a stage it may not be used in, or does not exist."""


def get(name: str) -> EvalSetSpec:
    if name not in SETS:
        raise EvalSetRefused(f"unknown evaluation set {name!r}; known: {sorted(SETS)}")
    return SETS[name]


def for_training(name: str) -> EvalSetSpec:
    """The set a training job may score: the dev set only (D127). Final sets are refused."""
    spec = get(name)
    if spec.stage != TRAINING:
        raise EvalSetRefused(
            f"{name!r} is a final set: it is scored once, from a retained model, by "
            "scripts/rq2_final_sets.py after the dev analysis (D100, D127)"
        )
    return spec


@dataclass(frozen=True)
class ResolvedPart:
    part: str
    e1_config: str
    prep: str
    e3_cache: str
    data_root: str
    compressed_texts: bool


def resolve(spec: EvalSetSpec, home: str, work: str | None = None) -> list[ResolvedPart]:
    """Absolute paths of a set's parts under ``home`` (``work`` for the derived dev cache)."""
    out: list[ResolvedPart] = []
    for p in spec.parts:
        cache = p.e3_cache
        base = work if (work is not None and cache.startswith("work/")) else home
        cache = cache.removeprefix("work/") if base == work else cache
        out.append(
            ResolvedPart(
                p.part,
                p.e1_config,
                os.path.join(home, p.prep),
                os.path.join(base, cache),
                os.path.join(home, p.data_root),
                p.compressed_texts,
            )
        )
    return out
