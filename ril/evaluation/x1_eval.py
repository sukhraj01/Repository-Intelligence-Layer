"""Evaluation of the X1 variants: class-unit source forms and ambiguous-site policies (exploratory).

Implements the evaluation half of ``docs/EXPERIMENTS.md`` E-CLASS-SOURCE and E-AMBIG-POLICY. A
*variant* is one class-unit source form (``full``, ``header``, ``header_sigs``; Q28) and one
reader-side policy for ambiguous ``invoke`` sites (``keep``, ``drop``, ``rebucket``, ``max3``;
Q35, Q36; ``ril.parsing.ambiguity_policy``). For every instance the pilot-E3 cache (edges of every
family, files, ages) is combined with the X1 extras (BM25 scores per form, ambiguous sites, four
gold readings) into the arrays of that variant, and ``ril.evaluation.e3_eval.evaluate_instance``
runs the stated grid on it, so the expansion, the list forms and the chance controls are exactly
those of pilot E3. ``full`` with ``drop`` is pilot E3 itself (its ``units`` numbers reproduce).

Before anything is scored the two files are checked against each other: same unit count, the
``full`` BM25 scores equal to the E3 cache's scores, and the resolved invoke pairs equal in number.

The tuning discipline of pilot E3 applies: a configuration that names ``test`` instances must be a
``confirm`` configuration with one graph setting, a ``stated`` variant and at most one
``reference`` variant, written before the run.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any

import numpy as np

from ril.evaluation.e3_eval import (
    EvalSpec,
    evaluate_instance,
    read_eval,
    spec_from_config,
    write_eval,
)
from ril.evaluation.e3_prepare import READINGS, read_cache
from ril.parsing.ambiguity_policy import EVIDENCE_KINDS, MAX_SET, POLICIES
from ril.parsing.repository_parser import CLASS_SOURCE_FORMS

X1_EVAL_VERSION = "x1-eval/v1"
Record = dict[str, Any]


@dataclass(frozen=True)
class Variant:
    """One class-unit source form and one ambiguous-site policy."""

    name: str
    form: str = "full"
    policy: str = "drop"
    evidence: tuple[str, ...] = EVIDENCE_KINDS  # kinds that re-bucket a site (policy rebucket)

    def __post_init__(self) -> None:
        if self.form not in CLASS_SOURCE_FORMS:
            raise ValueError(f"{self.name}: unknown class-source form {self.form!r}")
        if self.policy not in POLICIES:
            raise ValueError(f"{self.name}: unknown policy {self.policy!r}")
        if not set(self.evidence) <= set(EVIDENCE_KINDS):
            raise ValueError(f"{self.name}: unknown evidence kind in {self.evidence}")


@dataclass(frozen=True)
class X1Spec:
    """The graph grid (shared by all variants) and the variants."""

    spec: EvalSpec
    variants: tuple[Variant, ...]


def x1_spec(cfg: Record) -> X1Spec:
    """Build and validate the specification; refuses a sweep on test instances."""
    spec = spec_from_config(cfg)
    variants = tuple(
        Variant(
            name,
            str(v.get("form", "full")),
            str(v.get("policy", "drop")),
            tuple(v.get("evidence", EVIDENCE_KINDS)),
        )
        for name, v in sorted(cfg["variants"].items())
    )
    if not variants:
        raise ValueError("no variants")
    if spec.confirm:
        names = {v.name for v in variants}
        stated = cfg.get("stated")
        reference = cfg.get("reference")
        if stated not in names:
            raise ValueError("confirm: the stated variant must be one of the variants")
        if not names <= {stated, reference}:
            raise ValueError("confirm: only the stated variant and one reference variant")
    return X1Spec(spec, variants)


def policy_invoke_pairs(
    extras: dict[str, np.ndarray[Any, Any]], variant: Variant
) -> np.ndarray[Any, Any]:
    """(caller, candidate) unit-index pairs the variant's policy adds, shape (k, 2)."""
    ev = extras["amb_evidence"].astype(bool)
    size = extras["amb_size"]
    keep: np.ndarray[Any, Any]
    if variant.policy == "keep":
        keep = np.ones(len(size), dtype=bool)
    elif variant.policy == "drop":
        keep = np.zeros(len(size), dtype=bool)
    elif variant.policy == "rebucket":
        cols = [EVIDENCE_KINDS.index(k) for k in variant.evidence]
        keep = np.asarray(~ev[:, cols].any(axis=1)) if cols else np.ones(len(size), dtype=bool)
    else:  # max3
        keep = np.asarray(size <= MAX_SET)
    site = extras["amb_cand_site"]
    sel = keep[site] if len(site) else np.zeros(0, dtype=bool)
    src = extras["amb_src"][site[sel]]
    dst = extras["amb_cand_unit"][sel]
    pairs = np.stack([src, dst], axis=1) if len(src) else np.zeros((0, 2), dtype=np.int64)
    return np.asarray(pairs[pairs[:, 0] != pairs[:, 1]])


def check_alignment(
    e3: dict[str, np.ndarray[Any, Any]],
    e3_meta: Record,
    x1: dict[str, np.ndarray[Any, Any]],
    x1_meta: Record,
) -> None:
    """Raise unless the extras describe the same units and BM25 ranking as the E3 cache."""
    name = e3_meta.get("instance", "?")
    if int(e3_meta["units"]) != int(x1_meta["units"]):
        raise ValueError(f"{name}: unit counts differ ({e3_meta['units']} vs {x1_meta['units']})")
    for level in e3_meta["levels"]:
        a, b = e3.get(f"scores_{level}"), x1.get(f"scores_{level}_full")
        if a is None or b is None or not np.array_equal(a, b):
            raise ValueError(f"{name}: {level} BM25 scores of the full form differ from the cache")
    have = int(e3["pairs_invoke"].shape[0]) if "pairs_invoke" in e3 else 0
    if have != int(x1_meta["resolved_invoke_pairs"]):
        raise ValueError(f"{name}: resolved invoke pairs differ ({have} vs extras)")


def variant_arrays(
    e3: dict[str, np.ndarray[Any, Any]],
    e3_meta: Record,
    x1: dict[str, np.ndarray[Any, Any]],
    variant: Variant,
) -> dict[str, np.ndarray[Any, Any]]:
    """The cache arrays of one variant (scores of its form, invoke pairs of its policy)."""
    out = {k: v for k, v in e3.items() if not k.startswith(("scores_", "gold_"))}
    for level in e3_meta["levels"]:
        out[f"scores_{level}"] = x1[f"scores_{level}_{variant.form}"]
        for r in READINGS:
            out[f"gold_{level}_{r}"] = x1[f"gold_{level}_{r}"]
    if variant.policy != "drop":
        add = policy_invoke_pairs(x1, variant)
        base = e3.get("pairs_invoke", np.zeros((0, 2), dtype=np.int32))
        merged = np.unique(np.concatenate([base.astype(np.int64), add.astype(np.int64)]), axis=0)
        out["pairs_invoke"] = merged.astype(np.int32)
    return out


def _hash(cfg: Record, variant: Variant, e3_hash: str, x1_hash: str) -> str:
    payload = {
        "version": X1_EVAL_VERSION,
        "config": {k: v for k, v in cfg.items() if k != "variants"},
        "variant": [variant.name, variant.form, variant.policy, list(variant.evidence)],
        "e3": e3_hash,
        "x1": x1_hash,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def run_x1_eval(cfg: Record, e3_cache: str, x1_cache: str, out_dir: str) -> dict[str, int]:
    """Evaluate every instance with extras whose role is in the specification; resumable."""
    xs = x1_spec(cfg)
    counts = {"evaluated": 0, "reused": 0, "skipped_role": 0, "no_e3_cache": 0}
    for name in sorted(os.listdir(x1_cache)):
        if not name.endswith(".npz"):
            continue
        x1, x1_meta = read_cache(os.path.join(x1_cache, name))
        if x1_meta["role"] not in xs.spec.roles:
            counts["skipped_role"] += 1
            continue
        e3_path = os.path.join(e3_cache, name)
        if not os.path.exists(e3_path):
            counts["no_e3_cache"] += 1
            continue
        e3, e3_meta = read_cache(e3_path)
        check_alignment(e3, e3_meta, x1, x1_meta)
        for variant in xs.variants:
            out = os.path.join(out_dir, variant.name, name)
            ehash = _hash(cfg, variant, str(e3_meta["config_hash"]), str(x1_meta["config_hash"]))
            if os.path.exists(out) and read_eval(out)[0].get("eval_hash") == ehash:
                counts["reused"] += 1
                continue
            arrays = variant_arrays(e3, e3_meta, x1, variant)
            info, res = evaluate_instance(arrays, e3_meta, xs.spec)
            info.update(
                eval_hash=ehash,
                variant=variant.name,
                form=variant.form,
                policy=variant.policy,
                instance=e3_meta["instance"],
                role=e3_meta["role"],
                dataset=e3_meta["dataset"],
                folder=e3_meta["folder"],
                repo_id=e3_meta["repo_id"],
                units=e3_meta["units"],
                invoke_pairs=int(arrays.get("pairs_invoke", np.zeros((0, 2))).shape[0]),
                e1_rank_mismatch=e3_meta["e1_rank_mismatch"],
            )
            write_eval(out, info, res)
            counts["evaluated"] += 1
    return counts
