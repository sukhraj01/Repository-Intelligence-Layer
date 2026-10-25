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
  run starts with the real CUDA matrix-product gate (``ril.util.gpu``).

The evaluation of a trained model is wired in ``scripts/train.py eval`` (the training package does
not import evaluation code: leakage check (d)).

Every output is ids, counts, scores and timings, except the example cache. Kept compatible with
Python 3.10.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from typing import Any

from ril.training import pool_ranks as pr
from ril.training.negatives import (
    Mined,
    ScoreFn,
    bm25_score_fn,
    dense_score_fn,
    mine,
    mine_from_scores,
    read_mined,
    write_mined,
)
from ril.training.pool_check import split_instance_dir
from ril.training.pool_reader import (
    PoolExample,
    ReaderStats,
    load_feature_table,
    load_listing,
    read_cache,
    read_pool,
    select_instances,
    write_cache,
)
from ril.training.supervision import QualitySignal, TableKRank

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
    include_held_out: bool = False,
) -> Record:
    """Write the selection file: kept directory names and the survival counts.

    ``include_held_out`` keeps the held-out repositories in (their count is still recorded): only
    for the deliberate leakage pilot (E-PILOT-LEAK), never for a pool that is reported as disjoint.
    """
    from ril.training.pool_rank_jobs import held_out_predicate

    _, members = load_listing(listing_path)
    table = load_feature_table(feature_table) if feature_table else None
    st = ReaderStats()
    pred = held_out_predicate(held_out_path, rename_cache_path)
    held = sorted(n for n in members if (sp := split_instance_dir(n)) and pred(sp[0]))
    names = select_instances(
        members,
        is_held_out=(lambda _r: False) if include_held_out else pred,
        table=table,
        stats=st,
    )
    if max_instances is not None and len(names) > max_instances:
        names = sorted(sorted(names, key=lambda n: pr.seeded_key(seed, n))[:max_instances])
    doc: Record = {
        "names": names,
        "stats": st.to_dict(),
        "max_instances": max_instances,
        "include_held_out": include_held_out,
        "held_out_directories_in_listing": len(held),
        "held_out_directories_selected": len(set(held) & set(names)),
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


def teacher_score_fn(
    teacher: str, *, cut: int, device: str, batch_size: int
) -> tuple[ScoreFn, Record | None]:
    """Score function of a teacher (``bm25`` or a registered dense encoder) and the GPU gate."""
    if teacher == "bm25":
        return bm25_score_fn, None
    from ril.retrieval.dense_encoder import ENCODERS, DenseEncoder, local_snapshot

    gate: Record | None = None
    if device.startswith("cuda"):
        from ril.util.gpu import cuda_gate

        gate = cuda_gate()
    spec = ENCODERS[teacher].with_max_tokens(cut)
    enc = DenseEncoder.load(
        spec,
        device=device,
        dtype="float16" if device.startswith("cuda") else "float32",
        local_dir=local_snapshot(spec),
    )
    return dense_score_fn(enc, batch_size), gate


def teacher_job(
    cache_path: str,
    ranks_out: str,
    mined_out: str,
    *,
    teacher: str,
    keep: int,
    cut: int = 1024,
    device: str = "cpu",
    batch_size: int = 64,
) -> Record:
    """One teacher pass over the example cache: K-ranks of every positive and mined candidates.

    Each snapshot is scored once (positives first, then every candidate); the ranks follow the
    E-POOL-RANKS definition (``pool_ranks.positive_ranks``: 1 + non-positive functions scored
    strictly higher) and are written as E-POOL-RANKS rank rows, the mined candidates as
    :func:`write_mined` rows. Examples are visited grouped by repository (the dense teachers'
    per-repository vector cache). Resumable per directory: rank rows and mined rows are appended
    and finished directories skipped; the mined file is rewritten at the end.
    """
    examples = sorted(read_cache(cache_path), key=lambda e: (e.repo, e.instance_id))
    rows_path = f"{mined_out}.rows.jsonl"
    done = {str(r["dir"]) for r in pr.read_jsonl(ranks_out) if r.get("teacher") == teacher}
    done_m = {str(r["instance_id"]) for r in pr.read_jsonl(rows_path)}
    todo = [e for e in examples if e.instance_id not in done or e.instance_id not in done_m]
    score_fn, gate = teacher_score_fn(teacher, cut=cut, device=device, batch_size=batch_size)
    t0 = time.perf_counter()
    for ex in todo:
        t1 = time.perf_counter()
        texts = list(ex.positive_texts) + list(ex.candidate_texts)
        s = score_fn(ex, texts)
        secs = round(time.perf_counter() - t1, 4)
        if ex.instance_id not in done:
            pr.append_jsonl(
                ranks_out,
                {
                    "dir": ex.instance_id,
                    "teacher": teacher,
                    "functions": len(texts),
                    "ranks": pr.positive_ranks(ex.ids, s, ex.positive_ids),
                    "form": "cache",
                    "max_tokens": cut if teacher != "bm25" else None,
                    "seconds": secs,
                },
            )
        if ex.instance_id not in done_m:
            m = mine_from_scores(ex, teacher, s, keep)
            pr.append_jsonl(
                rows_path,
                {
                    "instance_id": ex.instance_id,
                    "teacher": m.teacher,
                    "positive_scores": list(m.positive_scores),
                    "top_ids": list(m.top_ids),
                    "top_scores": list(m.top_scores),
                },
            )
    mined = {
        str(r["instance_id"]): Mined(
            teacher=str(r["teacher"]),
            positive_scores=tuple(float(x) for x in r["positive_scores"]),
            top_ids=tuple(r["top_ids"]),
            top_scores=tuple(float(x) for x in r["top_scores"]),
        )
        for r in pr.read_jsonl(rows_path)
    }
    write_mined(mined_out, mined)
    rec = {
        "teacher": teacher,
        "keep": keep,
        "cut": cut,
        "examples": len(examples),
        "done_before": len(examples) - len(todo),
        "scored_now": len(todo),
        "mined": len(mined),
        "gate": gate,
        "seconds": round(time.perf_counter() - t0, 1),
        "cache_sha256": _sha256(cache_path),
    }
    _dump(f"{mined_out}.json", rec)
    return rec


def feature_table_job(
    rank_paths: list[str],
    out_csv: str,
    *,
    teachers: list[str],
    held_out_path: str,
    rename_cache_path: str | None,
) -> Record:
    """Feature table (E-POOL-RANKS columns, keys only) from teacher-pass rank rows.

    A directory enters only if every listed teacher ranked it (a partial row would make one arm's
    hook fail on an example another arm keeps). ``stratum`` is empty: the selection is a seeded
    random subset, not the E-POOL-RANKS strata.
    """
    import csv

    from ril.training.pool_rank_jobs import held_out_predicate

    pred = held_out_predicate(held_out_path, rename_cache_path)
    by: dict[str, dict[str, Record]] = {}
    for p in rank_paths:
        for r in pr.read_jsonl(p):
            if str(r["teacher"]) in teachers:
                by.setdefault(str(r["dir"]), {})[str(r["teacher"])] = r
    complete = sorted(d for d, ts in by.items() if all(t in ts for t in teachers))
    cols = [
        "instance_id",
        "positive_key",
        "repo",
        "held_out",
        "stratum",
        "functions",
        "positives_in_instance",
        *[f"rank_{t}" for t in teachers],
        *[f"rank_all_{t}" for t in teachers],
    ]
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    rows = 0
    with open(f"{out_csv}.tmp", "w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=cols)
        w.writeheader()
        for d in complete:
            sp = split_instance_dir(d)
            if sp is None:
                raise ValueError(f"unreadable instance directory {d!r}")
            ref = by[d][teachers[0]]
            cells: dict[str, Record] = {}
            for t in teachers:
                for x in by[d][t]["ranks"]:
                    cells.setdefault(str(x["positive"]), {})[t] = x
            for pid in sorted(cells):
                cell = cells[pid]
                row: Record = {
                    "instance_id": d,
                    "positive_key": pr.positive_key(pid),
                    "repo": sp[0],
                    "held_out": int(pred(sp[0])),
                    "stratum": "",
                    "functions": int(ref["functions"]),
                    "positives_in_instance": len(cells),
                }
                for t in teachers:
                    row[f"rank_{t}"] = int(cell[t]["rank"])
                    row[f"rank_all_{t}"] = int(cell[t]["rank_all"])
                w.writerow(row)
                rows += 1
    os.replace(f"{out_csv}.tmp", out_csv)
    return {
        "directories_ranked": len(by),
        "directories_complete": len(complete),
        "positive_rows": rows,
        "teachers": teachers,
        "out": out_csv,
        "sha256": _sha256(out_csv),
    }


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
    score_fn, gate = teacher_score_fn(teacher, cut=cut, device=device, batch_size=batch_size)
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


@dataclass
class TrainInputs:
    """Inputs of training runs read once (a job that trains several configurations)."""

    cache_path: str
    examples: list[PoolExample]
    feature_table: str | None
    signals: dict[str, QualitySignal]
    mined_path: str | None
    mined: dict[str, Mined] | None
    hashes: Record


def load_inputs(
    cache_path: str, feature_table: str | None = None, mined_path: str | None = None
) -> TrainInputs:
    """Read the example cache, the feature table's quality signals and the mined scores."""
    return TrainInputs(
        cache_path=cache_path,
        examples=read_cache(cache_path),
        feature_table=feature_table,
        signals=signals_from_table(feature_table),
        mined_path=mined_path,
        mined=read_mined(mined_path) if mined_path else None,
        hashes={
            "cache_sha256": _sha256(cache_path),
            "feature_table_sha256": _sha256(feature_table) if feature_table else None,
            "mined_sha256": _sha256(mined_path) if mined_path else None,
        },
    )


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
    inputs: TrainInputs | None = None,
) -> Record:
    """One training run from the example cache (resumable: rerun the same command).

    ``inputs`` (from :func:`load_inputs`) replaces reading the cache, table and mined file again;
    it must have been loaded from the same paths.
    """
    import torch

    from ril.training.training import load_train_config, train

    cfg = load_train_config(config_path)
    gate: Record | None = None
    if device.startswith("cuda"):
        from ril.util.gpu import cuda_gate

        gate = cuda_gate()
    else:
        torch.set_num_threads(int(os.environ.get("RIL_THREADS", "4")))
    if inputs is None:
        inputs = load_inputs(cache_path, feature_table, mined_path)
    elif (inputs.cache_path, inputs.feature_table, inputs.mined_path) != (
        cache_path,
        feature_table,
        mined_path,
    ):
        raise ValueError("preloaded inputs come from other paths")
    extra = {
        "gate": gate,
        "inputs": {
            "config_path": config_path,
            "config_file_sha256": _sha256(config_path),
            **inputs.hashes,
        },
    }
    return train(
        cfg,
        inputs.examples,
        results_root=results_root,
        work_root=work_root,
        date=date,
        device=device,
        signals=inputs.signals,
        mined=inputs.mined,
        stop_after=stop_after,
        extra_log=extra,
    )
