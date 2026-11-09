"""Scoring the retained models on the final sets, after the dev analysis and not before.

Implements the sealed order of D100 and D127 (``docs/RQ2_LAUNCH_PLAN.md`` section 9): the eight
evaluation repositories and the executable 377 of Verified are evaluated once, from the retained
models, after the dev analysis is complete. Three guards live in code, not in a procedure:

* the scoring refuses to start without the id of the dev-analysis entry it follows, and that id must
  match a record the analysis wrote (:func:`write_dev_analysis_record`) which says the analysis is
  complete and lists the run being scored;
* every score row is written next to the id it followed and the record's digest (one index row per
  model and part, :func:`index_row`), so a result cannot exist without its predecessor;
* the reader (:func:`read_final_sets`) returns nothing unless it is given that same id.

The torch-free half (records, index, reader, plan) is tested locally; :func:`evaluate_retained`
loads the model and runs on the cluster. A finished (model, part) pair is skipped on a rerun, so a
technical fault is repeated visibly and a normal rerun never scores twice.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import shutil
import tempfile
import time
from collections.abc import Mapping, Sequence
from typing import Any

from ril.evaluation import eval_sets, sealed
from ril.training import retention

FINAL_SETS_VERSION = "final-sets/v1"
DEV_RECORD_VERSION = "dev-analysis-record/v1"
INDEX_NAME = "final_sets_index.jsonl"
Record = dict[str, Any]


class FinalSetsRefused(ValueError):
    """The final-sets order was not respected (no id, a wrong id, or an unfinished analysis)."""


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def check_id(analysis_id: str | None) -> str:
    """The id of the dev analysis this scoring follows, through the shared guard (D100)."""
    try:
        return sealed.require_dev_analysis(analysis_id)
    except sealed.SealedOrderError as err:
        raise FinalSetsRefused(
            "the final sets are scored only after the dev analysis: give the id of the "
            "dev-analysis entry they follow (--follows-dev-analysis ID)"
        ) from err


def write_dev_analysis_record(
    path: str, analysis_id: str, run_ids: Sequence[str], results_sha256: str
) -> Record:
    """Written by the dev analysis when it is complete (the contract this module reads).

    ``run_ids`` are the runs the analysis covered; ``results_sha256`` digests the dev result files
    it read, so a later change to them is visible.
    """
    rec: Record = {
        "version": DEV_RECORD_VERSION,
        "id": check_id(analysis_id),
        "status": "complete",
        "runs": sorted(run_ids),
        "results_sha256": results_sha256,
    }
    with open(f"{path}.tmp", "w", encoding="utf-8") as handle:
        json.dump(rec, handle, indent=1, sort_keys=True)
        handle.write("\n")
    os.replace(f"{path}.tmp", path)
    return rec


def load_dev_analysis_record(path: str, analysis_id: str | None, run_ids: Sequence[str]) -> Record:
    """The record of the dev analysis, or a refusal: wrong id, unfinished, or run not covered."""
    want = check_id(analysis_id)
    if not os.path.isfile(path):
        raise FinalSetsRefused(f"no dev-analysis record at {path}")
    with open(path, encoding="utf-8") as handle:
        rec: Record = json.load(handle)
    if rec.get("version") != DEV_RECORD_VERSION:
        raise FinalSetsRefused(f"unknown dev-analysis record version {rec.get('version')!r}")
    if rec.get("id") != want:
        raise FinalSetsRefused(f"the record is for {rec.get('id')!r}, not {want!r}")
    if rec.get("status") != "complete":
        raise FinalSetsRefused("the dev analysis is not marked complete")
    missing = sorted(set(run_ids) - set(rec.get("runs", [])))
    if missing:
        raise FinalSetsRefused(f"runs not covered by the dev analysis: {missing}")
    rec["record_sha256"] = _sha256_file(path)
    return rec


def retained_run_id(manifest: Mapping[str, Any]) -> str:
    """``mined_raw_u100_s100`` from a manifest (cell ``rq2f_mined_raw``, seed, updates)."""
    cell = str(manifest["cell"]).removeprefix("rq2f_")
    return f"{cell}_u{int(manifest['updates'])}_s{int(manifest['seed'])}"


def read_manifest(folder: str) -> Record:
    with open(os.path.join(folder, retention.MANIFEST_NAME), encoding="utf-8") as handle:
        m: Record = json.load(handle)
    return m


def index_row(
    *,
    run_id: str,
    folder: str,
    manifest: Mapping[str, Any],
    spec: eval_sets.EvalSetSpec,
    part: str,
    follows: str,
    record_sha256: str,
    commit: str,
    result_dir: str,
    queries: int,
    seconds: float,
) -> Record:
    return {
        "version": FINAL_SETS_VERSION,
        "run_id": run_id,
        "folder": os.path.basename(folder),
        "model_sha256": manifest.get("sha256"),
        "config_hash": manifest.get("config_hash"),
        "set": spec.name,
        "part": part,
        "roles": list(spec.roles),
        "follows_dev_analysis": follows,
        "dev_record_sha256": record_sha256,
        "commit": commit,
        "result_dir": result_dir,
        "queries": queries,
        "seconds": round(seconds, 1),
    }


def read_final_sets(index_path: str, dev_analysis_id: str | None) -> list[Record]:
    """The index rows of the final-sets results, only for the id they followed.

    Refuses without an id, and refuses an id that differs from the one recorded in any row: the
    analysis of the final sets cannot read results that do not name the dev analysis it follows.
    """
    want = check_id(dev_analysis_id)
    rows: list[Record] = []
    with open(index_path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    bad = sorted({str(r.get("follows_dev_analysis")) for r in rows} - {want})
    if bad:
        raise FinalSetsRefused(f"results follow {bad}, not {want!r}")
    return rows


def plan(folders: Sequence[str], set_names: Sequence[str], out_root: str) -> list[Record]:
    """One entry per (retained model, set part): what would be scored and where it would land."""
    out: list[Record] = []
    for folder in folders:
        m = read_manifest(folder)
        rid = retained_run_id(m)
        for name in set_names:
            spec = eval_sets.get(name)
            for part in spec.parts:
                out.append(
                    {
                        "run_id": rid,
                        "folder": folder,
                        "set": name,
                        "part": part.part,
                        "result_dir": os.path.join(out_root, rid, name, part.part),
                    }
                )
    return out


def unpack_prep(prep: str, dest: str) -> str:
    """Node-local copy of a prepared-store directory whose unit texts are stored gzipped.

    Everything but ``texts_units_gz`` is linked, the texts are unpacked into ``texts_units``.
    """
    os.makedirs(os.path.join(dest, "texts_units"), exist_ok=True)
    for name in os.listdir(prep):
        if name == "texts_units_gz":
            continue
        target = os.path.join(dest, name)
        if not os.path.exists(target):
            os.symlink(os.path.join(prep, name), target)
    gz_dir = os.path.join(prep, "texts_units_gz")
    if os.path.isdir(gz_dir):
        for name in sorted(os.listdir(gz_dir)):
            if not name.endswith(".gz"):
                continue
            out = os.path.join(dest, "texts_units", name.removesuffix(".gz"))
            if not os.path.exists(out):
                with gzip.open(os.path.join(gz_dir, name), "rb") as src, open(out, "wb") as dst:
                    shutil.copyfileobj(src, dst)
    return dest


def evaluate_retained(
    folder: str,
    set_name: str,
    *,
    out_root: str,
    home: str,
    work: str,
    follows: str,
    record: Mapping[str, Any],
    commit: str,
    device: str = "cuda",
) -> list[Record]:
    """Score one retained model on every part of a final set; returns the index rows written.

    Needs torch and a GPU (``ril.training.encoders.load_trained``); refuses a model whose files do
    not match its manifest, and a set that is not a final set. A part whose done marker exists is
    skipped.
    """
    spec = eval_sets.get(set_name)
    if spec.stage != eval_sets.FINAL:
        raise FinalSetsRefused(f"{set_name!r} is a training-stage set")
    problems = retention.verify_retained(folder)
    if problems:
        raise FinalSetsRefused(f"retained model does not match its manifest: {problems[0]}")
    manifest = read_manifest(folder)
    rid = retained_run_id(manifest)
    if rid not in record.get("runs", []):
        raise FinalSetsRefused(f"{rid} is not covered by the dev analysis")

    from ril.evaluation.checkpoint_eval import eval_checkpoint
    from ril.training.encoders import load_trained
    from ril.util.gpu import cuda_gate

    gate = cuda_gate() if device.startswith("cuda") else None
    encoder = load_trained(os.path.join(folder, retention.MODEL_SUBDIR), device=device)
    rows: list[Record] = []
    for part in eval_sets.resolve(spec, home):
        result_dir = os.path.join(out_root, rid, spec.name, part.part)
        done = os.path.join(result_dir, "DONE.json")
        if os.path.isfile(done):
            continue
        t0 = time.time()
        prep = part.prep
        tmp: str | None = None
        if part.compressed_texts:
            tmp = tempfile.mkdtemp(prefix="ril_final_prep_", dir=work)
            prep = unpack_prep(part.prep, tmp)
        try:
            out = eval_checkpoint(
                encoder,
                {
                    "variant": f"{rid}__{spec.name}__{part.part}",
                    "roles": list(spec.roles),
                    "rrf_k": 60,
                    "batch_size": 64,
                    "chunks": False,
                    "seed": 0,
                    "baselines": [],
                    "deliberate_test": f"{spec.deliberate_test}; follows {follows}",
                },
                e1_config=part.e1_config,
                prep_dir=prep,
                cache_dir=part.e3_cache,
                data_root=part.data_root,
                work_dir=os.path.join(work, "eval"),
                result_dir=result_dir,
            )
        finally:
            if tmp is not None:
                shutil.rmtree(tmp, ignore_errors=True)
        row = index_row(
            run_id=rid,
            folder=folder,
            manifest=manifest,
            spec=spec,
            part=part.part,
            follows=follows,
            record_sha256=str(record["record_sha256"]),
            commit=commit,
            result_dir=result_dir,
            queries=int(out["unit_queries"]),
            seconds=time.time() - t0,
        )
        row["gate"] = gate
        with open(os.path.join(result_dir, "result.json"), "w", encoding="utf-8") as handle:
            json.dump(out, handle, indent=1, sort_keys=True, default=str)
        with open(done, "w", encoding="utf-8") as handle:
            json.dump(row, handle, indent=1, sort_keys=True)
        with open(os.path.join(out_root, INDEX_NAME), "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
        rows.append(row)
    return rows
