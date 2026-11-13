"""Retention of the executable-377 scores of the sealed final-sets scoring (torch-free).

Implements ``docs/RQ2_LAUNCH_PLAN.md`` ("Retained scores of the executable 377") and the decision
that records it (``docs/experiments/B.md`` E-RQ3-SCORE-RETENTION, DEV-042). The sealed job encodes
the executable 377 with each retained model and used to delete the per-instance unit scores at
exit. They are the same arrays the agent study's context pass needs, so the job now copies them,
for the executable 377 only, next to the retained models:

    <scores root>/<run id>/dense_scores/<instance>.npz     the score files, byte copies
    <scores root>/<run id>/parts/<part>.json               what each stored part contributed
    <scores root>/<run id>/scores_record.json              checkpoint hash, per-file SHA-256, digest

This changes what the job keeps, not what it computes: the copy happens after the metrics are
computed and touches none of the metric files. The order of the sealed scoring is unchanged (the
guard in ``ril.evaluation.final_sets`` still demands the dev-analysis record before any scoring);
reading the retained scores reveals nothing the sealed scoring has not already produced.

The scores root holds no ``manifest.json`` per model, so ``ril.training.retention.list_retained``
does not mistake it for a model folder. Only the executable 377 is retained; the eight
repositories are not.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

SCORE_RETENTION_VERSION = "score-retention/v1"
SET_NAME = "exec377"
"""The only set whose scores are retained."""
DENSE_KEY = "dense_L2"
"""Key of the unit scores in a score file (L3 text equals L2 text for every member, D108)."""
DENSE_KEY_L3 = "dense_L3"
"""Key of the L3 unit scores. A member the folder labels at L3 carries it next to ``dense_L2``;
the record counts them so that a store written without the key is seen (DEV-038: 224 L3)."""
SCORES_SUBDIR = "dense_scores"
PARTS_SUBDIR = "parts"
RECORD_NAME = "scores_record.json"
DEFAULT_SCORES_DIRNAME = "exec377_scores"
"""Default name of the scores root, a folder inside the retention directory."""
Record = dict[str, Any]


class ScoreRetentionError(ValueError):
    """Retained scores are missing, incomplete or do not match their record."""


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_subset_ids(path: str) -> list[str]:
    """Instance ids of the executable subset (``executable_instances_v1.json``), sorted."""
    with open(path, encoding="utf-8") as handle:
        subset = json.load(handle)
    return sorted(str(m["instance_id"]) for m in subset["executable"])


def part_scores_dir(work: str, variant: str) -> str:
    """Where ``eval_checkpoint`` leaves the per-instance scores of one (model, part) variant:
    ``<work>/eval/dense/<variant>`` for the ``work`` the final-sets job passes."""
    return os.path.join(work, "eval", "dense", variant)


def default_scores_root(retained_root: str) -> str:
    return os.path.join(retained_root, DEFAULT_SCORES_DIRNAME)


def model_dir(scores_root: str, run_id: str) -> str:
    return os.path.join(scores_root, run_id)


def scores_dir(scores_root: str, run_id: str) -> str:
    return os.path.join(scores_root, run_id, SCORES_SUBDIR)


def digest(files: Mapping[str, str]) -> str:
    """SHA-256 over the sorted ``instance sha256`` lines: one value for a set of score files."""
    text = "".join(f"{iid} {sha}\n" for iid, sha in sorted(files.items()))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_json_atomic(path: str, data: Mapping[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(f"{path}.tmp", "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, sort_keys=True, default=str)
        handle.write("\n")
    os.replace(f"{path}.tmp", path)


def _has_key(path: str) -> bool:
    with np.load(path, allow_pickle=False) as d:
        return DENSE_KEY in d.files


def _has_l3(path: str) -> bool:
    with np.load(path, allow_pickle=False) as d:
        return DENSE_KEY_L3 in d.files


def retain_part(
    src_dir: str,
    ids: Sequence[str],
    *,
    scores_root: str,
    run_id: str,
    part: str,
    model_sha256: str,
    config_hash: str,
    follows: str,
    dev_record_sha256: str,
    commit: str,
) -> Record:
    """Copy the score files of the instances in ``ids`` that ``src_dir`` holds; write the records.

    An instance already retained from an earlier part is kept as it is (the first part wins, as in
    the encode stage of the agent study) and counted under ``already``. A file without the dense
    key is not copied and is listed under ``no_key``. Returns the summary the scoring row carries:
    the digest of this part's files and the hash of the record file after the update.
    """
    wanted = set(ids)
    dest = scores_dir(scores_root, run_id)
    os.makedirs(dest, exist_ok=True)
    copied: dict[str, str] = {}
    already: list[str] = []
    no_key: list[str] = []
    if os.path.isdir(src_dir):
        for name in sorted(os.listdir(src_dir)):
            if not name.endswith(".npz") or name.endswith(".tmp.npz"):
                continue
            iid = name.removesuffix(".npz")
            if iid not in wanted:
                continue
            target = os.path.join(dest, name)
            if os.path.exists(target):
                already.append(iid)
                continue
            src = os.path.join(src_dir, name)
            if not _has_key(src):
                no_key.append(iid)
                continue
            tmp = f"{target}.tmp"
            shutil.copyfile(src, tmp)
            os.replace(tmp, target)
            copied[iid] = sha256_file(target)
    part_rec: Record = {
        "version": SCORE_RETENTION_VERSION,
        "run_id": run_id,
        "part": part,
        "copied": len(copied),
        "already": sorted(already),
        "no_key": sorted(no_key),
        "files": copied,
        "digest": digest(copied),
    }
    _write_json_atomic(
        os.path.join(model_dir(scores_root, run_id), PARTS_SUBDIR, f"{part}.json"), part_rec
    )
    record = write_record(
        scores_root,
        run_id,
        ids,
        model_sha256=model_sha256,
        config_hash=config_hash,
        follows=follows,
        dev_record_sha256=dev_record_sha256,
        commit=commit,
    )
    return {
        "dir": scores_dir(scores_root, run_id),
        "part": part,
        "part_instances": len(copied),
        "part_digest": part_rec["digest"],
        "scores_sha256": record["scores_sha256"],
        "record_sha256": sha256_file(os.path.join(model_dir(scores_root, run_id), RECORD_NAME)),
        "retained_instances": record["instances"],
        "complete": record["complete"],
    }


def write_record(
    scores_root: str,
    run_id: str,
    ids: Sequence[str],
    *,
    model_sha256: str,
    config_hash: str,
    follows: str,
    dev_record_sha256: str,
    commit: str,
) -> Record:
    """Rewrite the record of one model from the files now in its scores directory.

    Every file is hashed again, so the record always describes what is on disk. The record
    carries the checkpoint hash of the model that produced the scores.
    """
    dest = scores_dir(scores_root, run_id)
    files: dict[str, str] = {}
    for name in sorted(os.listdir(dest)) if os.path.isdir(dest) else []:
        if name.endswith(".npz") and not name.endswith(".tmp.npz"):
            files[name.removesuffix(".npz")] = sha256_file(os.path.join(dest, name))
    missing = sorted(set(ids) - set(files))
    extra = sorted(set(files) - set(ids))
    l3 = sorted(i for i in files if _has_l3(os.path.join(dest, f"{i}.npz")))
    rec: Record = {
        "version": SCORE_RETENTION_VERSION,
        "run_id": run_id,
        "set": SET_NAME,
        "dense_key": DENSE_KEY,
        "dense_keys": [DENSE_KEY, DENSE_KEY_L3],
        "l3_instances": len(l3),
        "l3_ids": l3,
        "model_sha256": model_sha256,
        "config_hash": config_hash,
        "follows_dev_analysis": follows,
        "dev_record_sha256": dev_record_sha256,
        "commit": commit,
        "instances": len(files),
        "expected": len(set(ids)),
        "missing": missing,
        "extra": extra,
        "complete": not missing and not extra,
        "files": files,
        "scores_sha256": digest(files),
    }
    _write_json_atomic(os.path.join(model_dir(scores_root, run_id), RECORD_NAME), rec)
    return rec


def read_record(scores_root: str, run_id: str) -> Record | None:
    path = os.path.join(model_dir(scores_root, run_id), RECORD_NAME)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as handle:
        rec: Record = json.load(handle)
    return rec


def verify(
    scores_root: str,
    run_id: str,
    ids: Sequence[str],
    *,
    model_sha256: str | None = None,
    expected_l3: int | None = None,
) -> list[str]:
    """Problems with a model's retained scores (empty list: usable for the context pass).

    Checks the record exists and is complete for ``ids``, that it names the model by checkpoint
    hash (when ``model_sha256`` is given), that every file hashes to the record, and (when
    ``expected_l3`` is given) that exactly that many members carry ``dense_L3``.
    """
    rec = read_record(scores_root, run_id)
    if rec is None:
        return ["no scores record"]
    problems: list[str] = []
    if model_sha256 is not None and rec.get("model_sha256") != model_sha256:
        problems.append("the scores belong to a different checkpoint")
    files: Mapping[str, str] = rec.get("files", {})
    missing = sorted(set(ids) - set(files))
    if missing:
        problems.append(f"{len(missing)} instances missing from the record (first: {missing[0]})")
    if expected_l3 is not None and rec.get("l3_instances") != expected_l3:
        problems.append(
            f"{rec.get('l3_instances')} members carry {DENSE_KEY_L3}, expected {expected_l3}"
        )
    if digest(files) != rec.get("scores_sha256"):
        problems.append("record digest differs from its file list")
    directory = scores_dir(scores_root, run_id)
    for iid in ids:
        if iid not in files:
            continue
        path = os.path.join(directory, f"{iid}.npz")
        if not os.path.isfile(path):
            problems.append(f"file missing: {iid}")
        elif sha256_file(path) != files[iid]:
            problems.append(f"file differs from the record: {iid}")
    return problems


def usable_models(
    scores_root: str | None,
    models: Sequence[tuple[str, str]],
    ids: Sequence[str],
) -> dict[str, str]:
    """``{run id: scores directory}`` of the models whose retained scores verify.

    ``models`` are ``(run id, checkpoint sha256)`` pairs. A model with no scores root, no record,
    an incomplete record, another checkpoint or a damaged file is absent from the result and is
    left to the encode stage.
    """
    out: dict[str, str] = {}
    if not scores_root or not os.path.isdir(scores_root):
        return out
    for run_id, sha in models:
        if not verify(scores_root, run_id, ids, model_sha256=sha):
            out[run_id] = scores_dir(scores_root, run_id)
    return out
