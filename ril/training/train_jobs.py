"""Job bodies of the training stack: select, cache, mine, train, evaluate (local or cluster).

Exploratory apparatus for RQ2 (``provisional: ADR-001, ADR-002, ADR-006``). The stages are split
so that no GPU is held while the CPU or the network works (``docs/COMPUTE.md``):

* ``select_job`` (CPU, local or cluster): directory names of the pool kept by the held-out list
  (D1, D3) and, if given, the feature table; optionally a seeded subset of at most
  ``max_instances``.
* ``cache_job`` (CPU, cluster): stream the selected directories by range request into an untracked
  example cache (holds text; never leaves the cluster).
* ``mine_job`` (CPU for BM25, GPU for a dense teacher): teacher scores of positives and top
  candidates, for teacher-mined negative policies.
* ``train_job`` (GPU, or CPU for the tiny model): one run of ``ril.training.training.train``; a GPU
  run starts with the real CUDA matrix-product gate of ``ril.evaluation.x2_jobs``.
* ``eval_job``: the configuration's ``evaluation`` section through
  ``ril.evaluation.checkpoint_eval`` into the run's result directory.

Every output is ids, counts, scores and timings, except the example cache. Kept compatible with
Python 3.10.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Mapping
from typing import Any

from ril.training import pool_ranks as pr
from ril.training.negatives import (
    ScoreFn,
    bm25_score_fn,
    dense_score_fn,
    mine,
    read_mined,
    write_mined,
)
from ril.training.pool_reader import (
    ReaderStats,
    load_feature_table,
    load_listing,
    read_cache,
    read_pool,
    select_instances,
    write_cache,
)
from ril.training.supervision import QualitySignal, TableKRank
from ril.training.training import load_train_config, merge_results, train

Record = dict[str, Any]


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _dump(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(f"{path}.tmp", "w", encoding="utf-8") as handle:
        json.dump(obj, handle, indent=1, sort_keys=True, default=str)
        handle.write("\n")
    os.replace(f"{path}.tmp", path)


def select_job(
    listing_path: str,
    held_out_path: str,
    rename_cache_path: str | None,
    out_path: str,
    *,
    feature_table: str | None,
    max_instances: int | None,
    seed: int,
) -> Record:
    """Write the selection file: kept directory names and the survival counts."""
    from ril.training.pool_rank_jobs import held_out_predicate

    _, members = load_listing(listing_path)
    table = load_feature_table(feature_table) if feature_table else None
    st = ReaderStats()
    names = select_instances(
        members,
        is_held_out=held_out_predicate(held_out_path, rename_cache_path),
        table=table,
        stats=st,
    )
    if max_instances is not None and len(names) > max_instances:
        names = sorted(sorted(names, key=lambda n: pr.seeded_key(seed, n))[:max_instances])
    doc: Record = {
        "names": names,
        "stats": st.to_dict(),
        "max_instances": max_instances,
        "seed": seed,
        "held_out_sha256": _sha256(held_out_path),
        "rename_cache_sha256": _sha256(rename_cache_path)
        if rename_cache_path and os.path.exists(rename_cache_path)
        else None,
        "feature_table_sha256": _sha256(feature_table) if feature_table else None,
        "listing_sha256": _sha256(listing_path),
    }
    _dump(out_path, doc)
    return {k: v for k, v in doc.items() if k != "names"} | {"selected": len(names)}


def cache_job(
    listing_path: str,
    selection_path: str,
    out_cache: str,
    *,
    feature_table: str | None,
    form: str,
    ahead: int = 4,
    fetch: pr.Fetch = pr.http_fetch,
) -> Record:
    """Stream the selected directories into the example cache; counts next to it."""
    url, members = load_listing(listing_path)
    with open(selection_path, encoding="utf-8") as handle:
        names = list(json.load(handle)["names"])
    table = load_feature_table(feature_table) if feature_table else None
    st = ReaderStats()
    t0 = time.perf_counter()
    n = write_cache(
        out_cache,
        read_pool(url, members, names, fetch=fetch, form=form, ahead=ahead, table=table, stats=st),
    )
    rec = {
        "written": n,
        "stats": st.to_dict(),
        "form": form,
        "seconds": round(time.perf_counter() - t0, 1),
        "cache_sha256": _sha256(out_cache),
    }
    _dump(f"{out_cache}.json", rec)
    return rec


def mine_job(
    cache_path: str,
    out_path: str,
    *,
    teacher: str,
    keep: int,
    cut: int = 1024,
    device: str = "cpu",
    batch_size: int = 64,
) -> Record:
    """Teacher scores (positives, top ``keep`` candidates) of every cached example."""
    examples = sorted(read_cache(cache_path), key=lambda e: (e.repo, e.instance_id))
    gate: Record | None = None
    score_fn: ScoreFn
    if teacher == "bm25":
        score_fn = bm25_score_fn
    else:
        from ril.retrieval.dense_encoder import ENCODERS, DenseEncoder, local_snapshot

        if device.startswith("cuda"):
            from ril.evaluation.x2_jobs import cuda_gate

            gate = cuda_gate()
        spec = ENCODERS[teacher].with_max_tokens(cut)
        enc = DenseEncoder.load(
            spec,
            device=device,
            dtype="float16" if device.startswith("cuda") else "float32",
            local_dir=local_snapshot(spec),
        )
        score_fn = dense_score_fn(enc, batch_size)
    t0 = time.perf_counter()
    rows = {e.instance_id: mine(e, teacher, score_fn, keep) for e in examples}
    write_mined(out_path, rows)
    rec = {
        "teacher": teacher,
        "keep": keep,
        "cut": cut,
        "examples": len(rows),
        "gate": gate,
        "seconds": round(time.perf_counter() - t0, 1),
        "cache_sha256": _sha256(cache_path),
    }
    _dump(f"{out_path}.json", rec)
    return rec


def signals_from_table(feature_table: str | None) -> dict[str, QualitySignal]:
    """One K-rank signal per teacher column of the feature table."""
    if not feature_table:
        return {}
    table = load_feature_table(feature_table)
    return {t: TableKRank(table, t) for t in table.teachers}


def train_job(
    config_path: str,
    cache_path: str,
    *,
    results_root: str,
    work_root: str,
    device: str,
    date: str,
    feature_table: str | None = None,
    mined_path: str | None = None,
    stop_after: int | None = None,
) -> Record:
    """One training run from the example cache (resumable: rerun the same command)."""
    import torch

    cfg = load_train_config(config_path)
    gate: Record | None = None
    if device.startswith("cuda"):
        from ril.evaluation.x2_jobs import cuda_gate

        gate = cuda_gate()
    else:
        torch.set_num_threads(int(os.environ.get("RIL_THREADS", "4")))
    examples = read_cache(cache_path)
    mined = read_mined(mined_path) if mined_path else None
    extra = {
        "gate": gate,
        "inputs": {
            "config_path": config_path,
            "config_file_sha256": _sha256(config_path),
            "cache_sha256": _sha256(cache_path),
            "feature_table_sha256": _sha256(feature_table) if feature_table else None,
            "mined_sha256": _sha256(mined_path) if mined_path else None,
        },
    }
    return train(
        cfg,
        examples,
        results_root=results_root,
        work_root=work_root,
        date=date,
        device=device,
        signals=signals_from_table(feature_table),
        mined=mined,
        stop_after=stop_after,
        extra_log=extra,
    )


def eval_job(
    config_path: str,
    model_dir: str,
    result_dir: str,
    *,
    e1_config: str,
    prep_dir: str,
    cache_dir: str,
    data_root: str,
    work_dir: str,
    device: str,
    baseline_enc_dirs: Mapping[str, str] | None = None,
    dense_root: str | None = None,
) -> Record:
    """Evaluate a trained model directory with the configuration's ``evaluation`` section."""
    from ril.evaluation.checkpoint_eval import eval_checkpoint
    from ril.training.encoders import load_trained

    cfg = load_train_config(config_path)
    ev = dict(cfg["evaluation"])
    ev.setdefault("variant", f"{cfg['exp_id']}__{os.path.basename(result_dir)}")
    gate: Record | None = None
    if device.startswith("cuda"):
        from ril.evaluation.x2_jobs import cuda_gate

        gate = cuda_gate()
    enc = load_trained(model_dir, device=device)
    out = eval_checkpoint(
        enc,
        ev,
        e1_config=e1_config,
        prep_dir=prep_dir,
        cache_dir=cache_dir,
        data_root=data_root,
        work_dir=work_dir,
        result_dir=result_dir,
        baseline_enc_dirs=baseline_enc_dirs,
        dense_root=dense_root,
    )
    out["gate"] = gate
    merge_results(result_dir, "evaluation", out)
    return out
