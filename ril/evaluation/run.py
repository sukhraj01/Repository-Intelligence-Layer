"""One CPU evaluation entry point for named retrieval splits (docs/EVAL_API.md)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from ril.bench.latency_harness import LATENCY_COLUMNS, THROUGHPUT_COLUMNS, append_rows
from ril.evaluation.core_bench import CoreBenchQuery, build_index, evaluate_scores, read_split
from ril.evaluation.metrics import ndcg_at_k, recall_at_k
from ril.evaluation.rewrite import CachedScores, anchor_counts, folder_hashes
from ril.evaluation.stats import clustered_mean_ci, clustered_paired_diff_ci
from ril.parsing.repo_id import normalize_repo_id
from ril.retrieval.bm25_index import BM25Index, BM25Params, tokenize

VERSION = "retrieval-eval/v1"
Record = dict[str, Any]
Score = Callable[[CoreBenchQuery], np.ndarray[Any, np.dtype[np.float64]]]
DEV_REPOSITORIES = {
    "internetarchive/openlibrary",
    "qutebrowser/qutebrowser",
    "ansible/ansible",
    "conan-io/conan",
    "deepset-ai/haystack",
    "streamlink/streamlink",
}


def _scorer(index: BM25Index | None, cached: CachedScores | None, condition: str) -> Score:
    def score(query: CoreBenchQuery) -> np.ndarray[Any, np.dtype[np.float64]]:
        if index is not None:
            return index.scores(tokenize(query.text))
        assert cached is not None
        return cached.score(query, condition)

    return score


def _measured(score: Score, samples: list[float]) -> Score:
    def measured(query: CoreBenchQuery) -> np.ndarray[Any, np.dtype[np.float64]]:
        began = time.perf_counter()
        result = score(query)
        samples.append((time.perf_counter() - began) * 1000)
        return result

    return measured


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def cpu_environment(config_hash: str) -> Record:
    """Capture CPU and git metadata without importing any model runtime."""
    cpu = platform.processor() or platform.machine()
    info = Path("/proc/cpuinfo")
    if info.exists():
        cpu = next(
            (
                line.split(":", 1)[1].strip()
                for line in info.read_text().splitlines()
                if line.startswith("model name")
            ),
            cpu,
        )
    try:
        commit, branch = _git("rev-parse", "HEAD"), _git("branch", "--show-current")
        dirty = int(bool(_git("status", "--porcelain")))
    except (OSError, subprocess.CalledProcessError):
        commit, branch, dirty = os.environ.get("RIL_COMMIT", "unknown"), "unknown", 1
    return {
        "timestamp_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": commit,
        "dirty": dirty,
        "branch": branch,
        "host": os.environ.get("RIL_HOST_ALIAS", "local-cpu"),
        "cpu_model": cpu,
        "cpu_cores": os.cpu_count() or 0,
        "ram_gb": round(os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / 2**30, 1),
        "gpu_name": "none",
        "gpu_driver": "",
        "cuda_version": "",
        "python": platform.python_version(),
        "torch": "not imported",
        "config_hash": config_hash,
    }


def _dump(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, sort_keys=True, indent=2, allow_nan=False) + "\n")


def run_config(config_path: str) -> Record:
    """Evaluate all configured folders once; emit paired metrics and standard timing CSV rows."""
    cfg = yaml.safe_load(Path(config_path).read_text())
    if not isinstance(cfg, dict):
        raise ValueError("configuration must be a mapping")
    required = {
        "experiment_id",
        "split",
        "role",
        "seed",
        "data_root",
        "folders",
        "retriever",
        "output",
    }
    allowed = required | {
        "rewrite",
        "bootstrap_draws",
        "prefilter_k",
        "warmup_n",
        "repeats",
        "log_path",
    }
    if required - cfg.keys() or cfg.keys() - allowed:
        raise ValueError("missing or unknown configuration keys")
    if cfg["role"] not in {"dev", "test", "fixture"}:
        raise ValueError("role must be dev, test or fixture")
    if not cfg["folders"] or not isinstance(cfg["seed"], int) or cfg["seed"] < 0:
        raise ValueError("need folders and a nonnegative integer seed")
    retriever = cfg["retriever"]
    kind = retriever["kind"]
    if kind not in {"bm25", "cached_dense"}:
        raise ValueError("retriever kind must be bm25 or cached_dense")
    allowed_retriever = (
        {"kind", "k1", "b"}
        if kind == "bm25"
        else {"kind", "cache_root", "encoder", "revision", "max_tokens"}
    )
    if set(retriever) - allowed_retriever:
        raise ValueError("unknown retriever configuration keys")
    rewrite_enabled = cfg.get("rewrite", False)
    if not isinstance(rewrite_enabled, bool):
        raise ValueError("rewrite must be a boolean")
    if kind == "cached_dense" and not rewrite_enabled:
        raise ValueError("cached dense input requires the paired Rewrite split")
    draws, warmup, repeats = (
        cfg.get("bootstrap_draws", 2000),
        cfg.get("warmup_n", 1),
        cfg.get("repeats", 3),
    )
    prefilter = cfg.get("prefilter_k", 10000)
    if any(not isinstance(x, int) for x in (draws, warmup, repeats, prefilter)):
        raise ValueError("draws, warmup_n, repeats and prefilter_k must be integers")
    if draws < 1 or warmup < 0 or repeats < 1 or prefilter < 1:
        raise ValueError("invalid resampling or timing count")
    chash = hashlib.sha256(
        json.dumps({"version": VERSION, "config": cfg}, sort_keys=True).encode()
    ).hexdigest()
    env = cpu_environment(chash)
    rows: list[Record] = []
    latency: list[Record] = []
    throughput: list[Record] = []
    inputs: list[Record] = []
    seen: set[tuple[str, str, str]] = set()
    for spec in cfg["folders"]:
        spec = {**spec, "repo": normalize_repo_id(spec["repo"])}
        if cfg["role"] == "dev" and spec["repo"] not in DEV_REPOSITORIES:
            raise ValueError("dev role is restricted to the registered development repositories")
        if cfg["role"] == "fixture" and (
            spec["dataset"] != "fixture" or not spec["repo"].startswith("example/")
        ):
            raise ValueError(
                "fixture role requires synthetic example repositories and fixture dataset"
            )
        for level in spec["levels"]:
            identity = (level, spec["dataset"], spec["folder"])
            if identity in seen:
                raise ValueError("duplicate folder and level")
            seen.add(identity)
            original = read_split(cfg["data_root"], *identity)
            rewritten = (
                read_split(cfg["data_root"], *identity, rewrite=True)
                if rewrite_enabled
                else original
            )
            if not original.queries:
                raise ValueError("configured folder has no labelled queries")
            label_hash = hashlib.sha256(
                json.dumps(
                    {
                        "qrels": {k: sorted(v) for k, v in original.qrels.items()},
                        "candidates": {q.query_id: q.candidates for q in original.queries},
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest()
            hashes = folder_hashes(original, rewritten)
            inputs.append(
                {
                    "level": level,
                    "repo": spec["repo"],
                    **hashes,
                    "labels_sha256": label_hash,
                    "dropped_queries_without_qrels": original.dropped_queries,
                }
            )
            started = time.perf_counter()
            index = (
                build_index(
                    original,
                    BM25Params(
                        k1=float(retriever.get("k1", 1.5)), b=float(retriever.get("b", 0.75))
                    ),
                )
                if kind == "bm25"
                else None
            )
            cache_path = (
                Path(retriever.get("cache_root", "."))
                / level
                / spec["dataset"]
                / f"{spec['folder']}.npz"
            )
            cached = (
                CachedScores(str(cache_path), original, rewritten)
                if kind == "cached_dense"
                else None
            )
            if cached is not None and any(
                cached.metadata[k] != retriever[k] for k in ("encoder", "revision", "max_tokens")
            ):
                raise ValueError("configured encoder and revision differ from dense cache")
            build_seconds = time.perf_counter() - started
            if cached is not None:
                with cache_path.open("rb") as handle:
                    inputs[-1]["score_cache_sha256"] = hashlib.file_digest(
                        handle, "sha256"
                    ).hexdigest()
                inputs[-1]["encoder_metadata"] = cached.metadata
            workload = f"{cfg['split']}:{level}:{spec['dataset']}:{spec['folder']}"
            throughput.append(
                {
                    **env,
                    "workload_id": workload,
                    "stage": "bm25_index" if index is not None else "cached_scores_load",
                    "units": len(original.corpus_ids),
                    "seconds": build_seconds,
                    "units_per_s": len(original.corpus_ids) / max(build_seconds, 1e-12),
                }
            )
            for condition, folder in (("original", original), ("rewrite", rewritten)):
                if condition == "rewrite" and not rewrite_enabled:
                    continue

                score = _scorer(index, cached, condition)
                for i in range(warmup):
                    score(folder.queries[i % len(folder.queries)])
                samples: list[float] = []

                measured = _measured(score, samples)
                records = evaluate_scores(folder, measured, prefilter_k=prefilter)
                for _ in range(repeats - 1):
                    for q in folder.queries:
                        measured(q)
                latency.append(
                    {
                        **env,
                        "query_set_id": (
                            f"{workload}:{condition}:{hashes[condition + '_sha256'][:12]}"
                        ),
                        "n_queries": len(folder.queries),
                        "warmup_n": warmup,
                        "cache_state": "warm",
                        "stage": "bm25" if index is not None else "cached_scores_lookup",
                        **{f"p{p}_ms": float(np.percentile(samples, p)) for p in (50, 95, 99)},
                        "n": len(samples),
                    }
                )
                for rec, orig_q, rewrite_q in zip(
                    records, original.queries, rewritten.queries, strict=True
                ):
                    ranks = [p["protocol"] for p in rec["positives"].values()]
                    rows.append(
                        {
                            "level": level,
                            "dataset": spec["dataset"],
                            "folder": spec["folder"],
                            "repo": spec["repo"],
                            "query_id": rec["query_id"],
                            "condition": condition,
                            "ndcg10": ndcg_at_k(ranks, 10, rec["n_positives"]),
                            "recall100": recall_at_k(ranks, 100, rec["n_positives"]),
                            **anchor_counts(orig_q.text, rewrite_q.text),
                        }
                    )
    metrics: list[Record] = []
    for level in sorted({r["level"] for r in rows}):
        subset = [r for r in rows if r["level"] == level]
        for condition in ("original", "rewrite"):
            selected = [r for r in subset if r["condition"] == condition]
            if not selected:
                continue
            repos = [r["repo"] for r in selected]
            for metric in ("ndcg10", "recall100"):
                ci = clustered_mean_ci(
                    [r[metric] for r in selected], repos, draws=draws, seed=cfg["seed"]
                )
                metrics.append(
                    {
                        "level": level,
                        "condition": condition,
                        "metric": metric,
                        "n": len(selected),
                        "repositories": len(set(repos)),
                        "mean": ci[0],
                        "low": ci[1],
                        "high": ci[2],
                    }
                )
        if rewrite_enabled:
            original_rows = {
                (r["dataset"], r["folder"], r["query_id"]): r
                for r in subset
                if r["condition"] == "original"
            }
            new_rows = {
                (r["dataset"], r["folder"], r["query_id"]): r
                for r in subset
                if r["condition"] == "rewrite"
            }
            keys = sorted(original_rows)
            if original_rows.keys() != new_rows.keys():
                raise ValueError("paired query keys differ")
            for metric in ("ndcg10", "recall100"):
                ci = clustered_paired_diff_ci(
                    [new_rows[k][metric] for k in keys],
                    [original_rows[k][metric] for k in keys],
                    [original_rows[k]["repo"] for k in keys],
                    draws=draws,
                    seed=cfg["seed"],
                )
                metrics.append(
                    {
                        "level": level,
                        "condition": "rewrite_minus_original",
                        "metric": metric,
                        "n": len(keys),
                        "repositories": len({original_rows[k]["repo"] for k in keys}),
                        "mean": ci[0],
                        "low": ci[1],
                        "high": ci[2],
                    }
                )
    result = {
        "version": VERSION,
        "config_hash": chash,
        "git_hash": env["commit"],
        "dirty": env["dirty"],
        "seed": cfg["seed"],
        "split": cfg["split"],
        "role": cfg["role"],
        "retriever": retriever,
        "interval": "95% repository-clustered percentile bootstrap",
        "bootstrap_draws": draws,
        "latency_scope": "tokenization and BM25 scoring"
        if kind == "bm25"
        else "cached score row access only; excludes encoding and dense search",
        "input_hashes": inputs,
        "metrics": metrics,
        "query_rows": rows,
        "latency_rows": latency,
        "throughput_rows": throughput,
    }
    out = Path(cfg["output"])
    out.mkdir(parents=True, exist_ok=True)
    (out / "config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=True))
    _dump(out / "hardware.json", env)
    _dump(out / "results.json", result)
    append_rows(out / "latency_log.csv", LATENCY_COLUMNS, latency)
    append_rows(out / "throughput_log.csv", THROUGHPUT_COLUMNS, throughput)
    if cfg.get("log_path"):
        _dump(Path(cfg["log_path"]), result)
    return result


def main() -> None:
    """Run one stated configuration; no sweep or model encoding occurs here."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    result = run_config(args.config)
    sys.stdout.write(
        json.dumps(
            {k: result[k] for k in ("config_hash", "git_hash", "split", "metrics")}, sort_keys=True
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
