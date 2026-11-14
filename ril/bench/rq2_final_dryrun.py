"""CPU-only dry run of the whole final-sets scoring path (torch-free, nothing is encoded).

Implements the pre-flight of ``docs/DEVIATIONS.md`` DEV-043 (addendum). Before a GPU job scores
the sealed sets, every part and every retained model it will touch is checked, and the
post-encoding half of the path is run on stand-in unit scores: the label manifest, the level
stores, the unit records, ``run_x2_eval``, the table loader and the CSV writers
(``ril.evaluation.checkpoint_eval.eval_checkpoint`` with ``scores_ready``), the label-count check,
and the score retention over the three parts of the executable 377 (into a scratch root). Stand-in
scores are random numbers; the dry run reads no result of the sealed sets and writes none into
their result tree. It reports every (model, set, part) combination with the conditions that would
stop it, so that they are fixed together instead of one job at a time.
"""

from __future__ import annotations

import glob
import json
import os
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from ril.evaluation import eval_sets, final_sets, score_retention
from ril.evaluation.checkpoint_eval import eval_checkpoint
from ril.evaluation.e3_prepare import read_cache
from ril.evaluation.label_manifest import label_manifest
from ril.evaluation.x2_dense import query_key, read_store
from ril.training import retention

Record = dict[str, Any]


def _store_keys(prep: str, level: str, dataset: str, folder: str) -> set[str]:
    path = os.path.join(prep, "queries", f"{level}__{dataset}__{folder}.jsonl")
    return set(read_store([path])) if os.path.isfile(path) else set()


def check_part(
    part: eval_sets.ResolvedPart, roles: Sequence[str], scratch: str, variant: str
) -> tuple[Record, list[str]]:
    """Part-level conditions and the stand-in evaluation; returns (summary, problems)."""
    problems: list[str] = []
    for what, path in (
        ("e1 config", part.e1_config),
        ("prep", part.prep),
        ("cache", part.e3_cache),
    ):
        if not os.path.exists(path):
            problems.append(f"{what} missing: {path}")
    if problems:
        return {}, problems
    if part.compressed_texts and not os.path.isdir(os.path.join(part.prep, "texts_units_gz")):
        problems.append("texts_units_gz missing")
    manifest = label_manifest(part.e3_cache, roles)
    stores: dict[tuple[str, str, str], set[str]] = {}
    dense_dir = os.path.join(scratch, "eval", "dense", variant)
    os.makedirs(dense_dir, exist_ok=True)
    skipped: list[str] = []
    for path in sorted(glob.glob(os.path.join(part.e3_cache, "*.npz"))):
        if path.endswith(".tmp.npz"):
            continue
        arrays, meta = read_cache(path)
        if meta.get("role") not in roles:
            continue
        inst = str(meta["instance"])
        if not os.path.isfile(os.path.join(part.prep, "units", f"{inst}.npz")):
            problems.append(f"{inst}: no unit record under prep/units (no dense scores)")
            skipped.append(inst)
            continue
        out: dict[str, Any] = {}
        rng = np.random.default_rng(sum(map(ord, inst)))
        for level in meta["levels"]:
            ident = (level, str(meta["dataset"]), str(meta["folder"]))
            if ident not in stores:
                stores[ident] = _store_keys(part.prep, *ident)
            key = query_key(level, ident[1], ident[2], inst)
            has_gold = f"gold_{level}_units" in arrays and any(
                len(v) for k, v in arrays.items() if k.startswith(f"gold_{level}_")
            )
            if key in stores[ident]:
                out[f"dense_{level}"] = rng.random(int(meta["units"])).astype(np.float32)
            elif has_gold:
                problems.append(f"{inst}: labelled at {level} but no query text in the store")
        np.savez_compressed(os.path.join(dense_dir, f"{inst}.npz"), **out)
    cfg = {
        "variant": variant,
        "roles": list(roles),
        "rrf_k": 60,
        "batch_size": 64,
        "chunks": False,
        "seed": 0,
        "baselines": [],
        "deliberate_test": "dry run, stand-in scores",
    }
    summary: Record = {"label_manifest": {k: v for k, v in manifest.items() if k != "unlabelled"}}
    try:
        res = eval_checkpoint(
            None,
            cfg,
            e1_config=part.e1_config,
            prep_dir=part.prep,
            cache_dir=part.e3_cache,
            data_root=part.data_root,
            work_dir=os.path.join(scratch, "eval"),
            result_dir=os.path.join(scratch, "result", variant),
            allow_empty=manifest["labelled"] == 0,
            scores_ready=True,
        )
        final_sets.check_label_counts(manifest, int(res["unit_queries"]), variant)
        summary["unit_queries"] = res["unit_queries"]
        summary["x2_eval"] = res["x2_eval"]
    except Exception as err:  # reported, never swallowed: it is a finding of the dry run
        problems.append(f"evaluation stage: {type(err).__name__}: {err}")
    return summary, problems


def dry_run(
    *,
    home: str,
    retained_root: str,
    dev_record_path: str,
    subset_path: str,
    out_root: str,
    scores_root: str,
    scratch: str,
    follows: str,
    only: Sequence[str] | None = None,
    sets: Sequence[str] = ("eight", "exec377"),
    expected_l3: int | None = None,
) -> Record:
    """Every (model, set, part) combination with its state and the conditions that would stop it."""
    folders = retention.list_retained(retained_root)
    ids: dict[str, str] = {
        final_sets.retained_run_id(final_sets.read_manifest(f)): f for f in folders
    }
    if only:
        ids = {k: v for k, v in ids.items() if k in set(only)}
    record = final_sets.load_dev_analysis_record(dev_record_path, follows, sorted(ids))
    subset_ids = score_retention.read_subset_ids(subset_path)
    model_problems: dict[str, list[str]] = {}
    for rid, folder in sorted(ids.items()):
        found = list(retention.verify_retained(folder))
        if rid not in record.get("runs", []):
            found.append("not covered by the dev analysis")
        model_problems[rid] = found
    part_problems: dict[tuple[str, str], list[str]] = {}
    part_summary: dict[tuple[str, str], Record] = {}
    sim_root = os.path.join(scratch, "retained_scores")
    for name in sets:
        spec = eval_sets.get(name)
        for part in eval_sets.resolve(spec, home):
            variant = f"dry__{name}__{part.part}"
            summary, found = check_part(part, spec.roles, scratch, variant)
            part_problems[(name, part.part)] = found
            part_summary[(name, part.part)] = summary
            if name == score_retention.SET_NAME and summary:
                score_retention.retain_part(
                    score_retention.part_scores_dir(scratch, variant),
                    subset_ids,
                    scores_root=sim_root,
                    run_id="dry",
                    part=part.part,
                    model_sha256="dry",
                    config_hash="dry",
                    follows=follows,
                    dev_record_sha256=str(record["record_sha256"]),
                    commit="dry",
                )
    sim = score_retention.read_record(sim_root, "dry") or {}
    retention_problems: list[str] = []
    if "exec377" in sets:
        if not sim.get("complete"):
            retention_problems.append(
                f"retention over the parts is incomplete: missing {sim.get('missing')}"
            )
        if expected_l3 is not None and sim.get("l3_instances") != expected_l3:
            retention_problems.append(
                f"{sim.get('l3_instances')} members carry dense_L3, expected {expected_l3}"
            )
    combos: list[Record] = []
    for rid in sorted(ids):
        for name in sets:
            for spec_part in eval_sets.get(name).parts:
                part_name = spec_part.part
                done = os.path.isfile(os.path.join(out_root, rid, name, part_name, "DONE.json"))
                risks = list(model_problems[rid]) + list(part_problems[(name, part_name)])
                if name == score_retention.SET_NAME:
                    risks += retention_problems
                combos.append(
                    {
                        "run_id": rid,
                        "set": name,
                        "part": part_name,
                        "state": "done" if done else "to run",
                        "risks": risks,
                    }
                )
    return {
        "models": sorted(ids),
        "parts": {f"{k[0]}/{k[1]}": v for k, v in sorted(part_summary.items())},
        "simulated_retention": {
            k: sim.get(k) for k in ("instances", "expected", "complete", "l3_instances", "missing")
        },
        "scores_root_state": {
            rid: {
                k: (score_retention.read_record(scores_root, rid) or {}).get(k)
                for k in ("instances", "complete", "l3_instances")
            }
            for rid in sorted(ids)
        },
        "combos": combos,
        "problems": sum(len(c["risks"]) for c in combos),
    }


def to_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, indent=1, sort_keys=True, default=str)
