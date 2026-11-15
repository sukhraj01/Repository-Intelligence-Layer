"""Contexts of the oracle calibration arm (RQ3, E-RQ3-ORACLE, D168).

Implements ``docs/RQ3_PILOT.md`` (retrieved contexts) for an exploratory positive control: the
units of the files that the gold patch modifies are placed first in the candidate list, the rest of
the budget is filled by the untrained ``rrf`` ranking of E-RQ3-CONTEXTS, and the list goes through
``ril.assembly.assemble`` unchanged (first fit, unit cap, blocks ordered by file and line, same
budget, tokenizer and truncation rule as every other arm). A unit already placed is skipped when
the ranking offers it again (the assembler's duplicate rule). Block headers carry the position in
this candidate list as their rank, as they do in every arm.

Gold files come from the paths of the gold patch's diff headers (``gold_files_from_patch``); only
paths are stored, never patch text. A file the patch creates has no pre-patch content; a modified
file with no parsed unit (not Python) contributes nothing; both are counted per instance.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from ril.assembly.assemble import Assembled, Candidate, UnitText, assemble, snapshot_of
from ril.assembly.config import AssemblyConfig
from ril.assembly.gold import gold_in_context
from ril.assembly.rq3_contexts import (
    LEVELS,
    RQ3_CONTEXTS_VERSION,
    Arm,
    ContextSpec,
    InputGroup,
    candidates_for,
    decode_record,
    encode_record,
    level_gold,
    locate,
    read_dense,
    rrf_arm_score,
    write_atomic,
)
from ril.assembly.tokens import ApproxTokenizer, Tokenizer
from ril.evaluation.e3_prepare import read_cache

ORACLE_VERSION = "rq3-oracle-contexts/v1"
ORACLE_ARM = "oracle"
DENSE_KEY = "dense_L2"
GOLD_FILES_VERSION = "rq3-oracle-gold-files/v1"
Record = dict[str, Any]
Arr = np.ndarray[Any, Any]

_DIFF_HEADER = re.compile(r"^diff --git a/(.+?) b/(.+)$")


def gold_files_from_patch(patch: str) -> tuple[list[str], list[str]]:
    """``(modified, created)`` paths of a unified diff, each sorted and without repeats.

    ``modified`` holds the files with a pre-patch version (edited, renamed from, or deleted: the
    old path); ``created`` holds files the patch adds. Only the ``diff --git`` header and the
    ``new file mode`` line of each file block are read.
    """
    modified: set[str] = set()
    created: set[str] = set()
    current: tuple[str, str] | None = None
    for line in patch.splitlines():
        head = _DIFF_HEADER.match(line)
        if head:
            current = (head.group(1), head.group(2))
            modified.add(current[0])
        elif current is not None and line.startswith("new file mode"):
            modified.discard(current[0])
            created.add(current[1])
            current = None
    return sorted(modified), sorted(created)


def gold_files_sha256(files_by_instance: Mapping[str, Sequence[str]]) -> str:
    blob = json.dumps(
        {k: sorted(v) for k, v in sorted(files_by_instance.items())},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def oracle_candidates(
    gold_files: Sequence[str], units: Sequence[UnitText], ranked: Sequence[Candidate]
) -> tuple[list[Candidate], dict[str, list[str]]]:
    """Candidate list: units of the gold files (file, then line order) first, then ``ranked``.

    Returns the list and ``{gold file: its unit ids}``. Gold units carry the stage ``oracle``.
    """
    want = set(gold_files)
    by_file: dict[str, list[UnitText]] = {}
    for u in units:
        if u.file in want:
            by_file.setdefault(u.file, []).append(u)
    first: list[Candidate] = []
    ids: dict[str, list[str]] = {}
    for f in sorted(by_file):
        ordered = sorted(by_file[f], key=lambda u: (u.start_line, u.end_line, u.unit_id))
        ids[f] = [u.unit_id for u in ordered]
        first.extend(Candidate(u.unit_id, 0.0, ("oracle",)) for u in ordered)
    return first + list(ranked), ids


def gold_file_stats(
    out: Assembled,
    gold_files: Sequence[str],
    created: Sequence[str],
    units_of: Mapping[str, Sequence[str]],
) -> Record:
    """What became of the gold files in one assembled context (counts, never text)."""
    m = out.manifest
    included = {e.unit_id: e for e in m.entries}
    skipped = {s.unit_id: s.reason for s in m.skipped}
    all_units = [u for f in sorted(units_of) for u in units_of[f]]
    in_ctx = [u for u in all_units if u in included]
    cut = [u for u in in_ctx if included[u].truncated]
    left_out = [u for u in all_units if u not in included]
    files_with_units = sorted(units_of)
    files_without_units = sorted(set(gold_files) - set(files_with_units))
    files_in = [f for f in files_with_units if any(u in included for u in units_of[f])]
    complete = bool(all_units) and not cut and not left_out
    return {
        "gold_files": sorted(gold_files),
        "files_created": sorted(created),
        "n_gold_files": len(gold_files),
        "n_files_created": len(created),
        "n_files_without_units": len(files_without_units),
        "files_without_units": files_without_units,
        "n_gold_file_units": len(all_units),
        "n_gold_units_in": len(in_ctx),
        "n_gold_units_cut": len(cut),
        "n_gold_units_left_out": len(left_out),
        "left_out_reasons": sorted({skipped.get(u, "not_offered") for u in left_out}),
        "n_files_in": len(files_in),
        "all_gold_file_units_intact": complete,
        "gold_files_affected": bool(cut or left_out),
    }


def build_oracle_instance(
    meta: Mapping[str, Any],
    arrays: Mapping[str, Arr],
    dense: Mapping[str, Arr],
    units: Sequence[UnitText],
    spec: ContextSpec,
    tok: Tokenizer,
    modified: Sequence[str],
    created: Sequence[str],
    gold_sha: str = "",
) -> Record:
    """Record of one instance: the oracle context at every budget, manifests and coverage rows."""
    ids = [u.unit_id for u in units]
    files = {u.unit_id: u.file for u in units}
    snap = snapshot_of(units)
    bm25 = arrays[f"scores_{spec.query_level}"]
    d = dense.get(DENSE_KEY)
    if d is None:
        raise ValueError(f"{meta['instance']}: no dense scores {DENSE_KEY!r}")
    if len(d) != len(units):
        raise ValueError(f"{meta['instance']}: dense has {len(d)} units, snapshot {len(units)}")
    rrf = Arm("rrf", DENSE_KEY, rrf_arm_score(spec.rrf_k), ("bm25", "dense"))
    ranked = candidates_for(rrf, bm25, d, ids, spec.candidates)
    cands, units_of = oracle_candidates(modified, units, ranked)
    golds = {lv: level_gold(arrays, lv, ids, files) for lv in LEVELS}
    arm = Arm(ORACLE_ARM, DENSE_KEY, rrf.score, ("oracle", "bm25", "dense"))
    contexts: Record = {}
    rows: list[Record] = []
    stats: Record = {}
    for budget in spec.budgets:
        out = assemble(cands, snap, AssemblyConfig(budget, spec.max_unit_tokens), tok)
        contexts[f"{ORACLE_ARM}|{budget}"] = {
            "context": out.context,
            "manifest": json.loads(out.manifest.to_json()),
        }
        stats[str(budget)] = gold_file_stats(out, modified, created, units_of)
        for level in LEVELS:
            for reading, (gold_units, gold_files) in golds[level].items():
                g = gold_in_context(out.manifest, gold_units, gold_files)
                rows.append(
                    {
                        "instance": meta["instance"],
                        "level": level,
                        "arm": ORACLE_ARM,
                        "budget": budget,
                        "reading": reading,
                        "n_gold_units": g.n_units,
                        "units_in": g.units_in,
                        "units_intact": g.units_intact,
                        "n_gold_files": g.n_files,
                        "files_in": g.files_in,
                    }
                )
    return {
        "version": RQ3_CONTEXTS_VERSION,
        "oracle_version": ORACLE_VERSION,
        "instance": meta["instance"],
        "repo_id": meta["repo_id"],
        "base_commit": meta["base_commit"],
        "units": len(units),
        "spec_hash": spec.spec_hash(tok.name, [arm]),
        "gold_files_sha256": gold_sha,
        "tokenizer": tok.name,
        "contexts": contexts,
        "coverage": rows,
        "oracle": stats,
    }


def is_current(path: str, spec_hash: str, gold_sha: str) -> bool:
    if not os.path.exists(path):
        return False
    with open(path, "rb") as handle:
        rec = decode_record(handle.read())
    return rec.get("spec_hash") == spec_hash and rec.get("gold_files_sha256") == gold_sha


@dataclass(frozen=True)
class OracleInputs:
    """Where one build reads from (the same inputs as the untrained contexts)."""

    groups: Sequence[InputGroup]
    repo_cache: str
    work_dir: str
    out_dir: str


def run_build_oracle(
    members: Sequence[str],
    gold: Mapping[str, Mapping[str, Any]],
    inputs: OracleInputs,
    spec: ContextSpec,
    *,
    shard: tuple[int, int] = (0, 1),
    only: Sequence[str] | None = None,
    load_units: Any = None,
) -> Record:
    """Build every member of the shard; resumable per instance, failures listed, pass goes on.

    ``gold`` maps an instance id to ``{"modified": [...], "created": [...]}``. An instance with no
    gold entry fails (``no_gold_files``): the arm needs the patch's paths for every instance.
    """
    from ril.assembly.rq3_trained_contexts import load_units_real

    loader = load_units or load_units_real
    tok = ApproxTokenizer()
    arm = Arm(ORACLE_ARM, DENSE_KEY, rrf_arm_score(spec.rrf_k), ("oracle", "bm25", "dense"))
    shash = spec.spec_hash(tok.name, [arm])
    gsha = gold_files_sha256({k: v["modified"] for k, v in gold.items()})
    mine = [m for n, m in enumerate(sorted(members)) if n % shard[1] == shard[0]]
    if only is not None:
        keep = set(only)
        mine = [m for m in mine if m in keep]
    counts = {"built": 0, "reused": 0, "failed": 0}
    failures: list[Record] = []
    infos: list[Record] = []
    for instance in mine:
        path = os.path.join(inputs.out_dir, "instances", f"{instance}.json.gz")
        if is_current(path, shash, gsha):
            counts["reused"] += 1
            continue
        if instance not in gold:
            counts["failed"] += 1
            failures.append({"instance": instance, "reason": "no_gold_files"})
            continue
        paths = locate(inputs.groups, instance)
        if paths is None:
            counts["failed"] += 1
            failures.append({"instance": instance, "reason": "no_inputs"})
            continue
        t0 = time.perf_counter()
        arrays, meta = read_cache(paths[0])
        dense = read_dense(paths[1])
        loaded = loader(meta, inputs.repo_cache, inputs.work_dir)
        if isinstance(loaded, str):
            counts["failed"] += 1
            failures.append({"instance": instance, "reason": loaded})
            continue
        g = gold[instance]
        rec = build_oracle_instance(
            meta, arrays, dense, loaded, spec, tok, g["modified"], g["created"], gsha
        )
        write_atomic(path, encode_record(rec))
        counts["built"] += 1
        infos.append({"instance": instance, "seconds": round(time.perf_counter() - t0, 2)})
    return {"counts": counts, "failures": failures, "infos": infos, "spec_hash": shash}
