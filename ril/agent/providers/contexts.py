"""Assembled contexts per (instance, arm) for the pilot.

Implements ``docs/RQ3_PILOT.md`` ("Prepare").

``context_rows`` is pure: ranked lists in, rows out (context text, its hash, the files it
shows). The text is produced by ``ril.assembly.assemble`` unchanged, the same function and
configuration for every arm, so what differs between arms is the ranked list and nothing
after it (ADR-014).
``contexts_from_cache`` regenerates the rows on the cluster from the stored first-stage scores
(the cache holds no unit text, so each instance is checked out at its base commit, as in
E-ASSEMBLY).
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from typing import Any

from ril.assembly.assemble import Candidate, UnitText, assemble, snapshot_of
from ril.assembly.config import AssemblyConfig
from ril.assembly.tokens import Tokenizer

Record = dict[str, Any]


def context_rows(
    instance_id: str,
    issue: str,
    units: Sequence[UnitText],
    ranked: Mapping[str, Sequence[Candidate]],
    cfg: AssemblyConfig,
    tok: Tokenizer,
) -> list[Record]:
    """One row per arm: the assembled context of that arm's ranked list."""
    snap = snapshot_of(units)
    rows: list[Record] = []
    for arm in sorted(ranked):
        out = assemble(ranked[arm], snap, cfg, tok)
        m = out.manifest
        rows.append(
            {
                "instance_id": instance_id,
                "arm": arm,
                "first_stage": arm,
                "issue": issue,
                "context": out.context,
                "context_sha256": m.context_sha256,
                "files": sorted({e.file for e in m.entries}),
                "budget": cfg.budget,
                "max_unit_tokens": cfg.max_unit_tokens,
                "tokenizer": tok.name,
                "config_hash": m.config_hash,
                "n_included": len(m.entries),
                "total_tokens": m.total_tokens,
            }
        )
    return rows


def issues_from_core_bench(raw_root: str) -> dict[str, str]:
    """Issue text by instance id from ``<raw_root>/LEVEL-2/<dataset>/<repo>/queries.jsonl``.

    The L2 query of an instance is its issue text (``_id`` = instance id, ``text``); the text is
    used as stored, with no clean-up.
    """
    import glob
    import json

    out: dict[str, str] = {}
    for path in sorted(glob.glob(os.path.join(raw_root, "LEVEL-2", "*", "*", "queries.jsonl"))):
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    row = json.loads(line)
                    out[str(row["_id"])] = str(row["text"])
    return out


def contexts_from_cache(
    cache_dir: str,
    dense_root: str,
    repo_cache: str,
    work_dir: str,
    issues: Mapping[str, str],
    *,
    level: str,
    budget: int,
    max_unit_tokens: int,
    n_candidates: int,
    dense_variant: str,
    rrf_k: int,
    roles: Sequence[str],
    instance_ids: Sequence[str] | None = None,
    arms: Sequence[str] = ("bm25", "rrf"),
    limit: int | None = None,
    seed: int = 0,
) -> tuple[list[Record], list[Record]]:
    """(rows, failures) for the cached instances of ``roles`` that have an issue text.

    Eligible: role and level match, an issue text exists and, for the ``rrf`` arm, stored dense
    scores exist. With ``limit`` the instances are drawn from the sorted eligible ids (seeded, so
    the draw does not depend on directory order) and only those are checked out and assembled.
    """
    import random

    import numpy as np

    from ril.assembly.measure import candidates_of, first_stage_scores, snapshot_units
    from ril.assembly.tokens import ApproxTokenizer
    from ril.evaluation.chunk_unit_pilot import checkout_commit
    from ril.evaluation.e3_prepare import read_cache

    tok = ApproxTokenizer()
    cfg = AssemblyConfig(budget=budget, max_unit_tokens=max_unit_tokens)
    wanted = set(instance_ids) if instance_ids is not None else None
    rows: list[Record] = []
    failures: list[Record] = []
    eligible: dict[str, str] = {}
    for name in sorted(os.listdir(cache_dir)):
        if not name.endswith(".npz"):
            continue
        _, meta = read_cache(os.path.join(cache_dir, name))
        iid = str(meta["instance"])
        if meta["role"] in roles and level in meta["levels"] and iid in issues:
            has_dense = os.path.exists(os.path.join(dense_root, dense_variant, name))
            if (wanted is None or iid in wanted) and (has_dense or "rrf" not in arms):
                eligible[iid] = name
    chosen = sorted(eligible)
    if limit is not None:
        chosen = sorted(random.Random(seed).sample(chosen, min(limit, len(chosen))))
    for iid in chosen:
        name = eligible[iid]
        arrays, meta = read_cache(os.path.join(cache_dir, name))
        repo_dir = str(meta["repo_id"]).replace("/", "__")
        work = os.path.join(work_dir, repo_dir)
        status = checkout_commit(
            os.path.join(repo_cache, f"{repo_dir}.git"), work, str(meta["base_commit"])
        )
        if status != "ok":
            failures.append({"instance": iid, "reason": status})
            continue
        units = snapshot_units(work, str(meta["repo_id"]))
        if len(units) != int(meta["units"]):
            failures.append(
                {"instance": iid, "reason": f"unit_count {len(units)} != {meta['units']}"}
            )
            continue
        dense_path = os.path.join(dense_root, dense_variant, name)
        dense = None
        if os.path.exists(dense_path):
            with np.load(dense_path, allow_pickle=False) as dz:
                dense = dz[f"dense_{level}"] if f"dense_{level}" in dz.files else None
        ids = [u.unit_id for u in units]
        ranked: dict[str, list[Candidate]] = {}
        for arm in arms:
            if arm == "rrf" and dense is None:
                failures.append({"instance": iid, "reason": "no_dense"})
                ranked = {}
                break
            scores = first_stage_scores(arm, arrays[f"scores_{level}"], dense, rrf_k)
            ranked[arm] = candidates_of(arm, scores, ids, n_candidates, arm == "rrf")
        if ranked:
            rows += context_rows(iid, issues[iid], units, ranked, cfg, tok)
    return rows, failures
