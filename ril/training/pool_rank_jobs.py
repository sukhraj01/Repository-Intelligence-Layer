"""Cluster job bodies of the pool-rank measurement (E-POOL-RANKS): sample, BM25, dense, dedup.

Exploratory. The stages are split so that no GPU is held while the CPU works (``docs/COMPUTE.md``):

* ``sample_job`` (local or CPU): strata and the seeded stratified sample from the pool-check
  metadata of every directory and the held-out list;
* ``bm25_job`` (CPU): fetch each selected directory by range request, BM25 ranks of its positives;
* ``dense_job`` (GPU): CUDA gate, then fetch ahead in threads while each teacher encodes the
  snapshot and the issue; ranks of the positives; throughput per directory;
* ``dedup_job`` (CPU): share of distinct function texts over all directories of a seeded set of
  repositories, which the full-pool cost estimate needs.

Every stage is resumable per directory (rows are appended; finished directories are skipped) and
writes ids, ranks, counts and timings only. The same bodies run on the sample and on the whole
pool (``selection='all'``, sharded by repository). Kept compatible with Python 3.10.
"""

from __future__ import annotations

import json
import os
import platform
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from ril.training import pool_check as pc
from ril.training import pool_ranks as pr

Record = dict[str, Any]


def held_out_predicate(held_out_path: str, rename_cache_path: str | None) -> Callable[[str], bool]:
    """Predicate ``repo -> held out`` under the default rule set (core + Loc-Bench tier, aliases).

    Aliases are the list's own plus those resolved in the rename cache (decision D1).
    """
    from ril.training.held_out import _blocked_keys, is_held_out, load_held_out_lists

    with open(held_out_path, encoding="utf-8") as handle:
        lists = load_held_out_lists(json.load(handle))
    aliases = dict(lists.aliases)
    if rename_cache_path and os.path.exists(rename_cache_path):
        from pathlib import Path

        from ril.training.rename_resolution import alias_map, load_cache

        aliases.update(alias_map(load_cache(Path(rename_cache_path))))
    blocked = _blocked_keys(lists.blocked(include_loc_bench=True), aliases)
    return lambda repo: is_held_out(repo, blocked, aliases)


def sample_job(
    meta_path: str,
    held_out_path: str,
    rename_cache_path: str | None,
    out_path: str,
    *,
    per_stratum: int,
    seed: int,
    bins: int = 4,
) -> Record:
    """Write the sample file: strata edges, pool totals per stratum, the chosen instances."""
    rows = pr.read_jsonl(meta_path)
    pred = held_out_predicate(held_out_path, rename_cache_path)
    instances, edges = pr.build_instances(rows, pred, bins)
    chosen = pr.stratified_sample(instances, per_stratum, seed)
    doc: Record = {
        "version": pr.POOL_RANKS_VERSION,
        "seed": seed,
        "per_stratum": per_stratum,
        "bins": bins,
        "size_edges_corpus_bytes": list(edges),
        "pool_instances": len(instances),
        "pool_positives": sum(i.positives for i in instances),
        "pool_held_out_instances": sum(1 for i in instances if i.held_out),
        "pool_strata": pr.stratum_totals(instances),
        "sample_strata": pr.stratum_totals(chosen),
        "sample": [pr.instance_record(i) for i in chosen],
    }
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(doc, handle, indent=1, sort_keys=True)
    return doc


def _selection(
    sample_path: str | None,
    meta_path: str | None,
    seed: int,
    shard: int,
    shards: int,
) -> list[pr.PoolInstance]:
    """The instances a stage works on: the sample, or every directory (``sample_path=None``)."""
    if sample_path:
        with open(sample_path, encoding="utf-8") as handle:
            doc = json.load(handle)
        insts = [pr.instance_from_record(r) for r in doc["sample"]]
    else:
        if meta_path is None:
            raise ValueError("meta_path is needed when no sample is given")
        insts, _ = pr.build_instances(pr.read_jsonl(meta_path), lambda _r: False)
    insts = [i for i in insts if pr.shard_of(i.repo, shards) == shard]
    return pr.order_by_repository(insts, seed)


def _listing(listing_path: str) -> tuple[str, dict[str, dict[str, Any]]]:
    with open(listing_path, encoding="utf-8") as handle:
        z = json.load(handle)
    return str(z["url"]), pc.pool_instances(z["members"], "python")


def bm25_job(
    listing_path: str,
    out_path: str,
    *,
    sample_path: str | None,
    meta_path: str | None = None,
    form: str = "code",
    seed: int = 0,
    shard: int = 0,
    shards: int = 1,
    ahead: int = 4,
    fetch: pr.Fetch = pr.http_fetch,
) -> Record:
    """BM25 ranks of the positives of every selected directory (CPU; resumable)."""
    url, members = _listing(listing_path)
    insts = _selection(sample_path, meta_path, seed, shard, shards)
    done = pr.done_dirs(out_path)
    todo = [i.dir for i in insts if i.dir not in done]
    err_path = out_path + ".errors.jsonl"
    t0 = time.perf_counter()
    n = 0
    for name, data, err in pr.prefetch(
        todo, lambda d: pr.fetch_instance(url, members[d], d, fetch, form), ahead
    ):
        if data is None:
            pr.append_jsonl(err_path, {"dir": name, "stage": "bm25", "error": err})
            continue
        t1 = time.perf_counter()
        scores = pr.bm25_scores(data.texts, data.query)
        pr.append_jsonl(
            out_path,
            pr.rank_record(
                "bm25", data, scores, {"form": form, "seconds": round(time.perf_counter() - t1, 3)}
            ),
        )
        n += 1
    return {
        "stage": "bm25",
        "selected": len(insts),
        "done_before": len(done),
        "written": n,
        "seconds": round(time.perf_counter() - t0, 1),
        "host": platform.node(),
    }


def dense_job(
    listing_path: str,
    out_path: str,
    log_path: str,
    *,
    teachers: Sequence[str],
    cut: int,
    sample_path: str | None,
    meta_path: str | None = None,
    form: str = "code",
    seed: int = 0,
    shard: int = 0,
    shards: int = 1,
    ahead: int = 4,
    batch_size: int = 64,
    fetch: pr.Fetch = pr.http_fetch,
) -> Record:
    """Dense ranks under each teacher (GPU; resumable per teacher and directory).

    Teachers run one after the other over the whole selection (one model in memory at a time);
    each teacher's rows carry the encode seconds and the number of texts actually encoded, from
    which the throughput is computed.
    """
    import torch  # type: ignore[import-not-found,unused-ignore]

    from ril.evaluation.chunk_unit_pilot import hardware
    from ril.evaluation.x2_jobs import cuda_gate, model_revision
    from ril.retrieval.dense_encoder import ENCODERS, DenseEncoder, local_snapshot

    log: Record = {"gate": cuda_gate(), "hardware": hardware(), "teachers": []}
    url, members = _listing(listing_path)
    insts = _selection(sample_path, meta_path, seed, shard, shards)
    by_dir = {i.dir: i for i in insts}
    err_path = out_path + ".errors.jsonl"
    for teacher in teachers:
        spec = ENCODERS[teacher].with_max_tokens(cut)
        done = {str(r["dir"]) for r in pr.read_jsonl(out_path) if r.get("teacher") == teacher}
        todo = [i.dir for i in insts if i.dir not in done]
        t_load = time.perf_counter()
        enc = DenseEncoder.load(
            spec, device="cuda", dtype="float16", local_dir=local_snapshot(spec)
        )
        info: Record = {
            "teacher": teacher,
            "model_id": spec.model_id,
            "revision_pinned": spec.revision,
            "revision_cache": model_revision(spec.model_id),
            "max_tokens": cut,
            "dtype": "float16",
            "batch_size": batch_size,
            "form": form,
            "load_seconds": round(time.perf_counter() - t_load, 1),
            "selected": len(insts),
            "done_before": len(done),
        }
        cache = pr.RepoVectorCache()
        torch.cuda.reset_peak_memory_stats()
        t0 = time.perf_counter()
        written = 0
        for name, data, err in pr.prefetch(
            todo, lambda d: pr.fetch_instance(url, members[d], d, fetch, form), ahead
        ):
            if data is None:
                pr.append_jsonl(err_path, {"dir": name, "stage": teacher, "error": err})
                continue
            torch.cuda.synchronize()
            t1 = time.perf_counter()
            qvec = enc.encode_query(data.query)
            scores, encoded = cache.scores(by_dir[name].repo, data.texts, qvec, enc, batch_size)
            torch.cuda.synchronize()
            pr.append_jsonl(
                out_path,
                pr.rank_record(
                    teacher,
                    data,
                    scores,
                    {
                        "form": form,
                        "max_tokens": cut,
                        "encoded": encoded,
                        "encode_seconds": round(time.perf_counter() - t1, 4),
                    },
                ),
            )
            written += 1
        info.update(
            {
                "written": written,
                "wall_seconds": round(time.perf_counter() - t0, 1),
                "cache_hits": cache.hits,
                "cache_misses": cache.misses,
                "peak_gpu_mem_mb": round(torch.cuda.max_memory_allocated() / 2**20, 1),
            }
        )
        log["teachers"].append(info)
        del enc
        torch.cuda.empty_cache()
        _dump(log_path, log)
    return log


def dedup_job(
    listing_path: str,
    meta_path: str,
    out_path: str,
    *,
    repos_per_bin: int,
    seed: int,
    form: str = "code",
    ahead: int = 8,
    fetch: pr.Fetch = pr.http_fetch,
) -> Record:
    """Distinct function texts over all directories of a seeded set of repositories (CPU).

    Repositories are binned by their number of directories (1, 2-9, 10-49, 50+) and
    ``repos_per_bin`` are drawn per bin by the seeded order; the result is a per-bin ratio
    (distinct / all texts), weighted later by each bin's share of the pool's functions.
    """
    import hashlib

    url, members = _listing(listing_path)
    insts, _ = pr.build_instances(pr.read_jsonl(meta_path), lambda _r: False)
    by_repo: dict[str, list[pr.PoolInstance]] = {}
    for i in insts:
        by_repo.setdefault(i.repo, []).append(i)
    bins = dedup_bins(by_repo)
    done = {str(r["repo"]) for r in pr.read_jsonl(out_path)}
    chosen: list[tuple[str, str]] = []
    for label, repos in sorted(bins.items()):
        for repo in sorted(repos, key=lambda r: pr.seeded_key(seed, r))[:repos_per_bin]:
            chosen.append((label, repo))
    for label, repo in chosen:
        if repo in done:
            continue
        dirs = sorted(i.dir for i in by_repo[repo])
        seen: set[str] = set()
        total = 0
        errors = 0
        for _name, data, _err in pr.prefetch(
            dirs, lambda d: pr.fetch_instance(url, members[d], d, fetch, form), ahead
        ):
            if data is None:
                errors += 1
                continue
            total += len(data.texts)
            seen.update(hashlib.sha1(t.encode("utf-8")).hexdigest() for t in data.texts)
        pr.append_jsonl(
            out_path,
            {
                "repo": repo,
                "bin": label,
                "dirs": len(dirs),
                "texts": total,
                "distinct": len(seen),
                "errors": errors,
            },
        )
    return {"stage": "dedup", "chosen": len(chosen)}


def dedup_bins(by_repo: Mapping[str, Sequence[Any]]) -> dict[str, list[str]]:
    """Repositories by number of directories: ``d1``, ``d2-9``, ``d10-49``, ``d50+``."""
    out: dict[str, list[str]] = {"d1": [], "d2-9": [], "d10-49": [], "d50+": []}
    for repo, dirs in by_repo.items():
        n = len(dirs)
        key = "d1" if n == 1 else "d2-9" if n < 10 else "d10-49" if n < 50 else "d50+"
        out[key].append(repo)
    return out


def _dump(path: str, obj: Record) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(f"{path}.tmp", "w", encoding="utf-8") as handle:
        json.dump(obj, handle, indent=1, sort_keys=True, default=str)
    os.replace(f"{path}.tmp", path)
