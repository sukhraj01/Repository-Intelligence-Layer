"""Contexts of the trained arms (RQ3), built by the path of the untrained arms.

Implements ``docs/RQ3_PILOT.md`` ("Trained arms", D113) on top of ``ril.assembly.rq3_contexts``
(E-RQ3-CONTEXTS, D108): the same instance caches, unit records, ``build_instance``, assembly policy
(ADR-014, D102, D103), budgets and byte format. A trained arm is an :class:`Arm` that ranks the
units by the reciprocal-rank fusion of the stored BM25 scores and the unit scores of one retained
model (``dense_L2`` of its score file), at the same constant as the untrained ``rrf`` arm
(``rrf_k`` of the context spec: the frozen RQ3 configuration, ``configs/frozen/rq3_contexts.json``),
so the two are paired like for like: only the dense component differs (D152, Q74). Using the
model's scores alone would change the fusion structure as well as the retriever.

A *target* is one output directory with the arms built into it: the untrained arms (reading the
stored scores of the instance's group, which reproduces the stored files byte for byte) or one
retained model (reading that model's score file). A pass over the instances checks out and parses
each snapshot once and builds every target that still needs the instance, so several models cost
one parse. A target's instance file is kept when it carries the target's spec hash (resumable).

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from ril.assembly.assemble import UnitText
from ril.assembly.rq3_contexts import (
    Arm,
    ContextSpec,
    InputGroup,
    build_instance,
    decode_record,
    encode_record,
    locate,
    read_dense,
    rrf_arm_score,
    sha256_file,
    vector_checks,
    write_atomic,
)
from ril.assembly.tokens import ApproxTokenizer, Tokenizer
from ril.evaluation.e3_prepare import read_cache

TRAINED_CONTEXTS_VERSION = "rq3-trained-contexts/v1"
DENSE_KEY = "dense_L2"
Record = dict[str, Any]
Arr = np.ndarray[Any, Any]
UnitLoader = Callable[[Mapping[str, Any], str, str], "list[UnitText] | str"]
"""``(meta, repo_cache, work_dir) -> units`` or a failure reason (a string)."""


@dataclass(frozen=True)
class Target:
    """One output directory and the arms built into it.

    ``scores_dir`` is ``None`` for arms that read the stored scores of the instance's group (the
    untrained arms) and the directory of one model's per-instance score files otherwise.
    """

    name: str
    arms: tuple[Arm, ...]
    scores_dir: str | None = None


def trained_arm(name: str, rrf_k: int) -> Arm:
    """The arm of a retained model: RRF of the stored BM25 scores and that model's dense scores.

    Same score function, constant and signals as the untrained ``rrf`` arm
    (``ril.assembly.rq3_contexts.default_arms``); only the dense component is the model's. ``rrf_k``
    has no default so that a build cannot silently use another constant than the spec's.
    """
    return Arm(name, DENSE_KEY, rrf_arm_score(rrf_k), ("bm25", "dense"))


def trained_target(run_id: str, arm: str, scores_dir: str, rrf_k: int) -> Target:
    """A target for one retained model; its directory is named by the run id."""
    return Target(run_id, (trained_arm(arm, rrf_k),), scores_dir)


def model_scores(scores_dir: str, instance: str) -> Mapping[str, Arr] | None:
    """``{"dense_L2": scores}`` of one model on one instance, or ``None`` if there is no file."""
    path = os.path.join(scores_dir, f"{instance}.npz")
    if not os.path.exists(path):
        return None
    with np.load(path, allow_pickle=False) as d:
        if DENSE_KEY not in d.files:
            return None
        return {DENSE_KEY: d[DENSE_KEY]}


def target_path(out_root: str, target: Target, instance: str) -> str:
    return os.path.join(out_root, target.name, "instances", f"{instance}.json.gz")


def is_current(path: str, spec_hash: str) -> bool:
    """Whether ``path`` exists and carries ``spec_hash`` (a finished target instance)."""
    if not os.path.exists(path):
        return False
    with open(path, "rb") as handle:
        return decode_record(handle.read()).get("spec_hash") == spec_hash


def records_for_instance(
    meta: Mapping[str, Any],
    arrays: Mapping[str, Arr],
    group_dense: Mapping[str, Arr],
    units: Sequence[UnitText],
    targets: Sequence[Target],
    spec: ContextSpec,
    tok: Tokenizer,
) -> dict[str, Record | None]:
    """``{target name: record}`` of one instance; a target with no score file maps to ``None``."""
    out: dict[str, Record | None] = {}
    for t in targets:
        if t.scores_dir is None:
            dense: Mapping[str, Arr] = group_dense
        else:
            got = model_scores(t.scores_dir, str(meta["instance"]))
            if got is None:
                out[t.name] = None
                continue
            dense = got
        out[t.name] = build_instance(meta, arrays, dense, units, spec, t.arms, tok)
    return out


def locate_cache(groups: Sequence[InputGroup], instance: str) -> tuple[str, str] | None:
    """Cache path of ``instance`` from the first group that has it (no stored scores needed).

    A trained arm reads its scores from the model's own files, so the stored untrained scores of
    the group are not required (and are not staged on every account).
    """
    for g in groups:
        c = os.path.join(g.cache_dir, f"{instance}.npz")
        if os.path.exists(c):
            return c, ""
    return None


def load_units_real(
    meta: Mapping[str, Any], repo_cache: str, work_dir: str
) -> list[UnitText] | str:
    """Check the instance out at its base commit and parse it, as E-RQ3-CONTEXTS did."""
    from ril.assembly.measure import snapshot_units
    from ril.evaluation.chunk_unit_pilot import checkout_commit

    repo_dir = str(meta["repo_id"]).replace("/", "__")
    work = os.path.join(work_dir, repo_dir)
    status = checkout_commit(
        os.path.join(repo_cache, f"{repo_dir}.git"), work, str(meta["base_commit"])
    )
    if status != "ok":
        return status
    units = snapshot_units(work, str(meta["repo_id"]))
    if len(units) != int(meta["units"]):
        return f"unit_count {len(units)} != cache {meta['units']}"
    return list(units)


def run_build_targets(
    members: Sequence[str],
    groups: Sequence[InputGroup],
    repo_cache: str,
    work_dir: str,
    out_root: str,
    targets: Sequence[Target],
    spec: ContextSpec,
    *,
    shard: tuple[int, int] = (0, 1),
    only: Sequence[str] | None = None,
    load_units: UnitLoader = load_units_real,
) -> Record:
    """Build every target of every member of the shard; resumable per (target, instance).

    An instance is parsed once for all targets that still need it. A failure of the inputs
    (no caches, no checkout, no score file of a model) is listed and the pass goes on.
    """
    tok = ApproxTokenizer()
    hashes = {t.name: spec.spec_hash(tok.name, t.arms) for t in targets}
    mine = [m for n, m in enumerate(sorted(members)) if n % shard[1] == shard[0]]
    if only is not None:
        keep = set(only)
        mine = [m for m in mine if m in keep]
    counts: dict[str, dict[str, int]] = {
        t.name: {"built": 0, "reused": 0, "failed": 0} for t in targets
    }
    failures: list[Record] = []
    infos: list[Record] = []
    for instance in mine:
        need = [
            t for t in targets if not is_current(target_path(out_root, t, instance), hashes[t.name])
        ]
        for t in targets:
            if t not in need:
                counts[t.name]["reused"] += 1
        if not need:
            continue
        stored = any(t.scores_dir is None for t in need)
        paths = locate(groups, instance) if stored else locate_cache(groups, instance)
        if paths is None:
            for t in need:
                counts[t.name]["failed"] += 1
                failures.append({"instance": instance, "target": t.name, "reason": "no_inputs"})
            continue
        t0 = time.perf_counter()
        arrays, meta = read_cache(paths[0])
        group_dense = read_dense(paths[1]) if stored else {}
        loaded = load_units(meta, repo_cache, work_dir)
        if isinstance(loaded, str):
            for t in need:
                counts[t.name]["failed"] += 1
                failures.append({"instance": instance, "target": t.name, "reason": loaded})
            continue
        built = records_for_instance(meta, arrays, group_dense, loaded, need, spec, tok)
        seconds = round(time.perf_counter() - t0, 2)
        for t in need:
            rec = built[t.name]
            if rec is None:
                counts[t.name]["failed"] += 1
                failures.append({"instance": instance, "target": t.name, "reason": "no_scores"})
                continue
            write_atomic(target_path(out_root, t, instance), encode_record(rec))
            counts[t.name]["built"] += 1
        infos.append(
            {"instance": instance, "seconds": seconds, **vector_checks(arrays, group_dense)}
        )
    return {"counts": counts, "failures": failures, "infos": infos, "spec_hashes": hashes}


def compare_with_stored(
    stored_dir: str, rebuilt_root: str, target: Target, instances: Sequence[str]
) -> Record:
    """SHA-256 of the stored instance files (``<stored_dir>/instances``) against the files of a
    rebuilt target, per instance; used to show that the untrained arms built by this path equal
    the stored contexts byte for byte."""
    rows: list[Record] = []
    for iid in instances:
        a = sha256_file(os.path.join(stored_dir, "instances", f"{iid}.json.gz"))
        b = sha256_file(target_path(rebuilt_root, target, iid))
        rows.append({"instance": iid, "stored": a, "rebuilt": b, "equal": a == b})
    return {"n": len(rows), "differ": sum(1 for r in rows if not r["equal"]), "rows": rows}


# --------------------------------------------------------------------------- configuration


def spec_from_config(cfg: Mapping[str, Any]) -> ContextSpec:
    """The context spec of E-RQ3-CONTEXTS (``rq3_contexts_v1.yaml``), unchanged."""
    a = cfg["assembly"]
    if a.get("tokenizer", "approx") != "approx":
        raise ValueError("the contexts are counted with the approximate tokenizer")
    return ContextSpec(
        budgets=tuple(int(b) for b in a["budgets"]),
        max_unit_tokens=int(a["max_unit_tokens"]),
        candidates=int(a["candidates"]),
        rrf_k=int(a["rrf_k"]),
        query_level=str(a["query_level"]),
    )


def groups_from_config(cfg: Mapping[str, Any]) -> tuple[InputGroup, ...]:
    return tuple(
        InputGroup(os.path.expanduser(g["cache_dir"]), os.path.expanduser(g["dense_dir"]))
        for g in cfg["groups"]
    )


def untrained_target(cfg: Mapping[str, Any], spec: ContextSpec, name: str = "untrained") -> Target:
    """The stored arms (bm25, dense, rrf) as a target that reads the groups' stored scores."""
    from ril.assembly.rq3_contexts import default_arms

    arms = tuple(
        x for x in default_arms(spec.rrf_k, str(cfg["dense_key"])) if x.name in cfg["arms"]
    )
    return Target(name, arms, None)
