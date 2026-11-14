"""Trained arms of RQ3: which retained models enter, what they cost, and their per-instance scores.

Implements ``docs/RQ3_PILOT.md`` ("Trained arms", D113, D129, D142) and ``docs/RQ2_LAUNCH_PLAN.md``
section 11. The retained RQ2 models (18 mined ones on account C, D142) are encoded against the
executable 377 of Verified; the result is one array of unit scores per instance and model, in the
layout of the stored untrained scores, from which ``ril.assembly.rq3_trained_contexts`` builds the
contexts: RRF of the stored BM25 scores and the model's scores, like the untrained arm (D152, Q74).
Nothing else about retrieval changes: the unit records, BM25 caches, assembly policy and budgets
are those of E-RQ3-CONTEXTS (ADR-014, D102, D103, D108).

The scores come from the sealed final-sets job when it kept them
(``ril.evaluation.score_retention``, DEV-042, at no GPU cost); the encode stage below is the
fallback for a model whose scores are missing or do not verify, within the Block 4 cap
(:func:`resolve_scores`, :func:`plan_jobs`).

Four rules live in code:

* the encode stage follows the sealed order of D100 and D127: it refuses to start without the id of
  the finished dev analysis and a matching record that covers the model
  (``ril.evaluation.final_sets``), because the scores it writes are scores of the executable 377;
* a model whose files do not match its manifest is refused, and the manifest's hash is written next
  to the scores, so the contexts can be traced to one model;
* the plan prints the jobs and their cost against Block 4 without submitting anything: a model
  with verified retained scores costs nothing, the others are listed in the order of Q73
  (:data:`ORDER_Q73`);
* retained scores are used only when the record names the model's checkpoint hash and every file
  hashes to the record.

The planning half imports no torch. :func:`encode_model` needs torch and a GPU (or a CPU for a
small dry run) and is the only function that does.
"""

from __future__ import annotations

import glob
import json
import os
import re
import shutil
import tempfile
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from ril.evaluation import eval_sets, final_sets, score_retention
from ril.training import retention
from ril.training.rq2_plan import CELLS

RQ3_TRAINED_VERSION = "rq3-trained/v1"
ARM_PREFIX = "tr_"
"""Prefix of a trained arm's name; contexts, prompts and results are keyed by the arm name."""
SET_NAME = "exec377"
DENSE_KEY = score_retention.DENSE_KEY
"""Key of the unit scores in a score file (L3 text equals L2 text for every member, D108)."""
SCORES_SUBDIR = "dense_scores"
MODEL_RECORD = "model.json"
DONE_NAME = "DONE.json"

BLOCK4_CAP_GPU_H = 6.0
"""Ledger cap of Block 4 (D107, ``docs/COMPUTE.md``): a ledger, not a cluster limit."""
BLOCK4_SPENT_GPU_H = 0.377
"""Spent by the untrained encoder's encoding of the 341 built instances (E-RQ3-UNITS)."""
COST_PER_MODEL_GPU_H = 0.68
"""Planning constant fixed in the brief of this task: the six-folder store of the executable 377
(0.377 measured for the 341 built instances, about 0.29 projected for the 36 earlier ones)."""

NAME_RE = re.compile(r"^[a-z0-9_]+$")
Record = dict[str, Any]
Arr = np.ndarray[Any, Any]

MINED_CELL_ORDER: tuple[str, ...] = tuple(c.cell_id for c in CELLS if c.family == "mined")
"""Arm order of a seed job (D141): RAW, FILTER-BM25, subsample, WEIGHT, CURRICULUM, FILTER-SRS."""
PRIMARY_CELLS: tuple[str, ...] = ("mined_raw", "mined_filter_bm25")
"""The confirmatory contrast of D113 and D139 (FILTER-BM25 against RAW)."""
SECOND_TIER_CELLS: tuple[str, ...] = ("mined_weight", "mined_curriculum")
"""The cells that follow the primary pair in the order of Q73 (WEIGHT and CURRICULUM)."""
ORDER_Q73 = "pair_seed100"
ORDERS = (ORDER_Q73, "protocol", "primary_first")
"""``pair_seed100`` (the lead's order, Q73, the default), ``protocol``, ``primary_first``."""
Q73_RULE: tuple[str, ...] = (
    "1. RAW and FILTER-BM25 at every seed (the primary contrast), by seed then arm order",
    "2. WEIGHT and CURRICULUM at the first seed (100)",
    "3. the remaining seeds of WEIGHT and CURRICULUM",
    "4. any other cell (subsample, FILTER-SweRankEmbed-Small), last: the list does not name them",
    "stop at the first model whose cost would take Block 4 over its cap",
)


class TrainedArmsRefused(ValueError):
    """A rule of this module was not respected (bad name, manifest mismatch, missing scores)."""


def arm_name(run_id: str) -> str:
    """The arm name of a retained model: ``tr_`` + run id (``tr_mined_raw_u100_s100``).

    The name is used as a key (``<arm>|<budget>``) and as a path part, so it carries only
    lower-case letters, digits and underscores.
    """
    name = f"{ARM_PREFIX}{run_id}"
    if not NAME_RE.match(name):
        raise TrainedArmsRefused(f"run id {run_id!r} does not give a valid arm name")
    return name


@dataclass(frozen=True)
class RetainedModel:
    """One retained model as the manifest of its folder describes it."""

    run_id: str
    cell_id: str
    seed: int
    updates: int
    folder: str
    model_sha256: str
    config_hash: str
    commit: str

    @property
    def arm(self) -> str:
        return arm_name(self.run_id)

    @property
    def primary(self) -> bool:
        return self.cell_id in PRIMARY_CELLS


def model_from_folder(folder: str) -> RetainedModel:
    """Read the manifest of a retained folder (the files are not hashed here)."""
    m = final_sets.read_manifest(folder)
    rid = final_sets.retained_run_id(m)
    cell = str(m["cell"]).removeprefix("rq2f_")
    return RetainedModel(
        run_id=rid,
        cell_id=cell,
        seed=int(m["seed"]),
        updates=int(m["updates"]),
        folder=folder,
        model_sha256=str(m.get("sha256", "")),
        config_hash=str(m.get("config_hash", "")),
        commit=str(m.get("commit", "")),
    )


def models_from_root(root: str, only: Sequence[str] | None = None) -> list[RetainedModel]:
    """Every retained model under ``root`` (optionally only the named run ids), unordered."""
    out = [model_from_folder(f) for f in retention.list_retained(root)]
    if only:
        wanted = set(only)
        unknown = sorted(wanted - {m.run_id for m in out})
        if unknown:
            raise TrainedArmsRefused(f"no retained model for run ids {unknown}")
        out = [m for m in out if m.run_id in wanted]
    return out


def cell_rank(cell_id: str) -> int:
    """Position of a cell in the seed job's arm order; unknown cells sort last."""
    return MINED_CELL_ORDER.index(cell_id) if cell_id in MINED_CELL_ORDER else len(MINED_CELL_ORDER)


def order_models(models: Sequence[RetainedModel], order: str = ORDER_Q73) -> list[RetainedModel]:
    """The order in which models are encoded.

    ``pair_seed100`` (default, the lead's order of Q73, ``Q73_RULE``): RAW and FILTER-BM25 at all
    seeds, then WEIGHT and CURRICULUM at the first seed, then their remaining seeds, then every
    other cell; inside a tier by seed, then the arm order of a seed job (D141). ``protocol``: by
    seed, then by that arm order. ``primary_first``: the confirmatory pair at every seed first,
    then the others in protocol order. The order matters only for the fallback encode stage, where
    the cap can stop the list.
    """
    if order not in ORDERS:
        raise TrainedArmsRefused(f"unknown order {order!r}; known: {list(ORDERS)}")
    base = sorted(models, key=lambda m: (m.seed, cell_rank(m.cell_id), m.run_id))
    if order == "protocol":
        return base
    if order == "primary_first":
        return [m for m in base if m.primary] + [m for m in base if not m.primary]
    first = min((m.seed for m in models), default=0)

    def tier(m: RetainedModel) -> int:
        if m.primary:
            return 0
        if m.cell_id in SECOND_TIER_CELLS:
            return 1 if m.seed == first else 2
        return 3

    return sorted(base, key=tier)  # stable: inside a tier the protocol order stands


def plan_jobs(
    models: Sequence[RetainedModel],
    *,
    order: str = ORDER_Q73,
    cap: float = BLOCK4_CAP_GPU_H,
    spent: float = BLOCK4_SPENT_GPU_H,
    per_model: float = COST_PER_MODEL_GPU_H,
    retained: Mapping[str, str] | None = None,
) -> Record:
    """Jobs, cost per job and cumulative cost against the cap. Submits nothing, needs no id.

    ``retained`` maps run ids to the directory of their verified retained scores (DEV-042,
    :func:`ril.evaluation.score_retention.usable_models`): such a model costs 0 GPU-hours and needs
    no encode job. For the others ``fits`` is true while the cumulative encode cost plus what
    Block 4 has already spent stays at or under the cap, and once a model does not fit no later
    encode job is listed as fitting (the list stops there).
    """
    kept = retained or {}
    rows: list[Record] = []
    cum = 0.0
    stopped = False
    for n, m in enumerate(order_models(models, order), start=1):
        have = m.run_id in kept
        cost = 0.0 if have else per_model
        fits = True
        if not have:
            cum += cost  # the running total keeps growing, so the overage is visible
            fits = not stopped and spent + cum <= cap + 1e-9
            stopped = stopped or not fits
        rows.append(
            {
                "n": n,
                "run_id": m.run_id,
                "arm": m.arm,
                "cell": m.cell_id,
                "seed": m.seed,
                "primary": m.primary,
                "scores": "retained" if have else "encode",
                "gpu_hours": cost,
                "cumulative_gpu_hours": round(cum, 4),
                "block4_total_gpu_hours": round(spent + cum, 4),
                "fits": fits,
                "model_sha256": m.model_sha256,
                "config_hash": m.config_hash,
            }
        )
    encode = [r for r in rows if r["scores"] == "encode"]
    need = per_model * len(encode)
    return {
        "version": RQ3_TRAINED_VERSION,
        "order": order,
        "order_rule": list(Q73_RULE) if order == ORDER_Q73 else [f"order {order}"],
        "cap_gpu_hours": cap,
        "spent_gpu_hours": spent,
        "cost_per_model_gpu_hours": per_model,
        "models": len(rows),
        "models_with_retained_scores": len(rows) - len(encode),
        "models_to_encode": len(encode),
        "models_within_cap": sum(1 for r in rows if r["fits"]),
        "encode_models_within_cap": sum(1 for r in encode if r["fits"]),
        "total_gpu_hours_all": round(need, 4),
        "block4_total_if_all": round(spent + need, 4),
        "over_cap_by": round(max(0.0, spent + need - cap), 4),
        "max_models_by_cap": int(max(0.0, (cap - spent) // per_model + 1e-9)),
        "jobs": rows,
    }


# ------------------------------------------------------------------ the encode stage (torch)


def scores_dir(out_root: str, run_id: str) -> str:
    """Where the per-instance scores of one model live: ``<out_root>/<run_id>/dense_scores``."""
    return os.path.join(out_root, run_id, SCORES_SUBDIR)


read_subset_ids = score_retention.read_subset_ids
"""Instance ids of the executable subset (``executable_instances_v1.json``), sorted."""


def check_scores(directory: str, ids: Sequence[str]) -> Record:
    """Whether every member has a score file with the key and the same number of units as its
    neighbours' bookkeeping says; returns ``{present, missing, no_key}`` (ids)."""
    missing: list[str] = []
    no_key: list[str] = []
    for iid in ids:
        path = os.path.join(directory, f"{iid}.npz")
        if not os.path.exists(path):
            missing.append(iid)
            continue
        with np.load(path, allow_pickle=False) as d:
            if DENSE_KEY not in d.files:
                no_key.append(iid)
    return {
        "present": len(ids) - len(missing) - len(no_key),
        "missing": missing,
        "no_key": no_key,
    }


def keep_only(directory: str, ids: Sequence[str]) -> int:
    """Remove score files of instances outside ``ids`` from ``directory`` (a node-local copy).

    The stored six-folder part holds every instance of its folders; the contexts need the 377.
    Returns the number of files removed.
    """
    keep = {f"{i}.npz" for i in ids}
    removed = 0
    for path in glob.glob(os.path.join(directory, "*.npz")):
        if os.path.basename(path) not in keep:
            os.remove(path)
            removed += 1
    return removed


def encoded_run_ids(encode_root: str | None) -> list[str]:
    """Run ids with a finished encode stage under ``encode_root`` (a ``DONE.json`` each)."""
    if not encode_root or not os.path.isdir(encode_root):
        return []
    return sorted(
        n
        for n in os.listdir(encode_root)
        if os.path.isfile(os.path.join(encode_root, n, DONE_NAME))
    )


def retained_run_ids(retained_scores: str | None) -> list[str]:
    """Run ids with a scores record under the retained-scores root (not yet verified)."""
    if not retained_scores or not os.path.isdir(retained_scores):
        return []
    return sorted(
        n
        for n in os.listdir(retained_scores)
        if os.path.isfile(os.path.join(retained_scores, n, score_retention.RECORD_NAME))
    )


def resolve_scores(
    run_id: str,
    ids: Sequence[str],
    *,
    encode_root: str | None = None,
    retained_scores: str | None = None,
    model_sha256: str | None = None,
) -> Record | None:
    """Where the scores of one model for the 377 are read from, or ``None`` if nowhere.

    The scores kept by the final-sets job come first (DEV-042) and are used only if they verify:
    the record names the model's checkpoint hash (when ``model_sha256`` is known), is complete for
    ``ids`` and every file hashes to the record. Otherwise the output of the encode stage is used
    if it finished (the fallback, which costs GPU-hours). The result names the source, the
    directory, the checkpoint hash the scores belong to and, when the retained scores were skipped,
    why (``retained_problems``).
    """
    problems: list[str] = []
    if retained_scores and os.path.isdir(retained_scores):
        problems = score_retention.verify(
            retained_scores, run_id, ids, model_sha256=model_sha256 or None
        )
        if not problems:
            rec = score_retention.read_record(retained_scores, run_id) or {}
            return {
                "source": "retained",
                "run_id": run_id,
                "dir": score_retention.scores_dir(retained_scores, run_id),
                "model_sha256": rec.get("model_sha256"),
                "config_hash": rec.get("config_hash"),
                "scores_sha256": rec.get("scores_sha256"),
                "retained_problems": [],
            }
    done = os.path.join(encode_root or "", run_id, DONE_NAME)
    if encode_root and os.path.isfile(done):
        with open(done, encoding="utf-8") as handle:
            row: Record = json.load(handle)
        return {
            "source": "encoded",
            "run_id": run_id,
            "dir": scores_dir(encode_root, run_id),
            "model_sha256": row.get("model_sha256"),
            "config_hash": row.get("config_hash"),
            "scores_sha256": None,
            "retained_problems": problems,
        }
    return None


def model_record(model: RetainedModel, source: Mapping[str, Any]) -> Record:
    """The record the analysis plan reads (the fields of the encode stage's ``model.json``), from
    a retained manifest and a resolved scores source."""
    return {
        "version": RQ3_TRAINED_VERSION,
        "run_id": model.run_id,
        "arm": model.arm,
        "cell": model.cell_id,
        "seed": model.seed,
        "updates": model.updates,
        "model_sha256": model.model_sha256,
        "config_hash": model.config_hash,
        "scores_source": source.get("source"),
        "scores_sha256": source.get("scores_sha256"),
    }


def write_json_atomic(path: str, data: Mapping[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"  # one name per process: shards write the same file
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, sort_keys=True, default=str)
        handle.write("\n")
    os.replace(tmp, path)


def encode_model(
    folder: str,
    *,
    ids: Sequence[str],
    out_root: str,
    home: str,
    work: str,
    follows: str,
    record: Mapping[str, Any],
    commit: str,
    device: str = "cuda",
    encoder: Any | None = None,
    spec: eval_sets.EvalSetSpec | None = None,
    dry_run: bool = False,
) -> Record:
    """Encode the six-folder store of the executable 377 with one retained model and write the
    per-instance scores to ``<out_root>/<run_id>/dense_scores``; returns the model record.

    Refusals: a set that is not a final set, a model that does not match its manifest, a run that
    the dev analysis does not cover. Resumable: finished stores and score files are skipped and a
    finished model (its ``DONE.json``) is returned as it is. ``encoder`` is for tests and dry runs
    (anything with ``spec``, ``token_lengths``, ``encode_documents`` and ``encode_queries``); by
    default the retained model is loaded with ``ril.training.encoders.load_trained``.

    ``dry_run`` is for proving the path on a small model and a *training-stage* set (the dev set):
    it is the only way a set that is not a final set is accepted, the dev-analysis record is not
    required (nothing sealed is read) and the model record says ``dry_run``. A final set is never
    scored in a dry run: ``dry_run`` with a final set is refused.
    """
    from ril.evaluation.checkpoint_eval import stores_for
    from ril.evaluation.x2_dense import encode_store, score_units

    spec = spec or eval_sets.get(SET_NAME)
    if dry_run and spec.stage == eval_sets.FINAL:
        raise final_sets.FinalSetsRefused(f"a dry run never scores the final set {spec.name!r}")
    if not dry_run and spec.stage != eval_sets.FINAL:
        raise final_sets.FinalSetsRefused(f"{spec.name!r} is a training-stage set")
    problems = retention.verify_retained(folder)
    if problems:
        raise final_sets.FinalSetsRefused(
            f"retained model does not match its manifest: {problems[0]}"
        )
    model = model_from_folder(folder)
    if not dry_run and model.run_id not in record.get("runs", []):
        raise final_sets.FinalSetsRefused(f"{model.run_id} is not covered by the dev analysis")
    final_dir = scores_dir(out_root, model.run_id)
    done = os.path.join(out_root, model.run_id, DONE_NAME)
    if os.path.isfile(done):
        with open(done, encoding="utf-8") as handle:
            finished: Record = json.load(handle)
        return finished

    gate: Any = None
    if encoder is None:
        from ril.training.encoders import load_trained
        from ril.util.gpu import cuda_gate

        gate = cuda_gate() if device.startswith("cuda") else None
        encoder = load_trained(os.path.join(folder, retention.MODEL_SUBDIR), device=device)

    t0 = time.time()
    os.makedirs(work, exist_ok=True)
    node_scores = os.path.join(work, "scores", model.run_id)
    enc_dir = os.path.join(work, "enc", model.run_id)
    parts: list[Record] = []
    for part in eval_sets.resolve(spec, home):
        prep = part.prep
        tmp: str | None = None
        if part.compressed_texts:
            tmp = tempfile.mkdtemp(prefix="ril_rq3_trained_prep_", dir=work)
            prep = final_sets.unpack_prep(part.prep, tmp)
        try:
            stores = stores_for(part.e1_config, prep, list(spec.roles), False)
            encoded = [
                encode_store(
                    encoder,
                    files,
                    name,
                    enc_dir,
                    batch_size=64,
                    is_query=name.startswith("queries__"),
                )
                for name, files in sorted(stores.items())
            ]
            scored = score_units(
                prep,
                enc_dir,
                node_scores,
                int(encoder.spec.max_tokens),
                roles=set(spec.roles),
                forms=("full",),
            )
        finally:
            if tmp is not None:
                shutil.rmtree(tmp, ignore_errors=True)
        parts.append({"part": part.part, "stores": len(encoded), "scored": scored})
    removed = keep_only(node_scores, ids)
    check = check_scores(node_scores, ids)
    if check["missing"] or check["no_key"]:
        raise TrainedArmsRefused(
            f"{model.run_id}: scores missing for {len(check['missing'])} and without "
            f"{DENSE_KEY} for {len(check['no_key'])} of {len(ids)} instances"
        )
    os.makedirs(os.path.dirname(final_dir), exist_ok=True)
    stage = f"{final_dir}.tmp"
    shutil.rmtree(stage, ignore_errors=True)
    shutil.copytree(node_scores, stage)
    shutil.rmtree(final_dir, ignore_errors=True)
    os.replace(stage, final_dir)
    row: Record = {
        "version": RQ3_TRAINED_VERSION,
        "run_id": model.run_id,
        "arm": model.arm,
        "cell": model.cell_id,
        "seed": model.seed,
        "updates": model.updates,
        "folder": os.path.basename(folder),
        "model_sha256": model.model_sha256,
        "config_hash": model.config_hash,
        "model_commit": model.commit,
        "set": spec.name,
        "dry_run": dry_run,
        "follows_dev_analysis": follows,
        "dev_record_sha256": record.get("record_sha256"),
        "commit": commit,
        "device": device,
        "gate": gate,
        "instances": len(ids),
        "extra_files_removed": removed,
        "parts": parts,
        "max_tokens": int(encoder.spec.max_tokens),
        "seconds": round(time.time() - t0, 1),
    }
    write_json_atomic(os.path.join(out_root, model.run_id, MODEL_RECORD), row)
    write_json_atomic(done, row)
    return row
