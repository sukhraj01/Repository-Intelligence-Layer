"""Runner for pilot E1/E2: chunk-level and unit-level BM25 on CORE-Bench folders (exploratory).

Implements the runs of ``docs/EXPERIMENTS.md`` E-BM25-REPRO and E-LABEL-NOISE. Two resumable
stages, each writing one small JSON file per work item (ids, ranks, paths, lines; no text):

* ``run_chunk_level``: for each configured folder, BM25 over the folder corpus and the rank of
  every positive under the protocol reading and the filter-first reading (``core_bench``);
* ``run_unit_level``: for each instance of the configured repositories, a checkout at the base
  commit and the unit-level analysis (``unit_retrieval``).

A finished item with the same configuration hash is read back, not redone. The configuration
file names the repositories and their role (``test`` or ``dev``); the dev/test split is part of
the configuration hash, so a changed split cannot be mistaken for the same run.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any
from urllib.parse import unquote

import yaml

from ril.evaluation.chunk_unit_pilot import (
    checkout_commit,
    hardware,
    read_corpus_texts,
)
from ril.evaluation.core_bench import (
    PROTOCOL_PREFILTER_K,
    evaluate_folder,
    read_folder,
    read_qrels,
)
from ril.evaluation.unit_retrieval import analyse_units
from ril.parsing.code_unit import CODEUNIT_SCHEMA_VERSION
from ril.parsing.repository_parser import PARSER_VERSION
from ril.retrieval.bm25_index import BM25Params

E1_VERSION = "e1/v1"
Record = dict[str, Any]
LEVEL_DIR = {"L2": "LEVEL-2", "L3": "LEVEL-3"}


def load_config(path: str) -> Record:
    """Read the experiment configuration (YAML)."""
    with open(path, encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle)
    if not isinstance(cfg, dict):
        raise ValueError(f"{path}: expected a mapping")
    for spec in cfg.get("folders", []):
        spec["folder"] = unquote(spec["folder"])  # '.' is written %2E in tracked configs
    return cfg


def config_hash(cfg: Record) -> str:
    """SHA-256 of the canonical JSON of the configuration and the code versions."""
    payload = {
        "version": E1_VERSION,
        "bm25": cfg["bm25"],
        "prefilter_k": cfg.get("prefilter_k", PROTOCOL_PREFILTER_K),
        "folders": cfg["folders"],
        "seed": cfg["seed"],
        "parser": PARSER_VERSION,
        "codeunit_schema": CODEUNIT_SCHEMA_VERSION,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def params_of(cfg: Record) -> BM25Params:
    """BM25 parameters of the configuration."""
    return BM25Params(k1=float(cfg["bm25"]["k1"]), b=float(cfg["bm25"]["b"]))


def folder_path(data_root: str, level: str, spec: Record) -> str:
    """Directory of a folder spec at a level under ``data_root``."""
    return os.path.join(data_root, "data", LEVEL_DIR[level], spec["dataset"], spec["folder"])


def _dump(path: str, obj: object) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(obj, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
    os.replace(tmp, path)


def _load_if_current(path: str, chash: str) -> Record | None:
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        doc = json.load(handle)
    return doc if isinstance(doc, dict) and doc.get("config_hash") == chash else None


def _wanted(spec: Record, only: str | None) -> bool:
    """Whether a folder spec is selected by ``only`` (a folder name or ``dataset/folder``)."""
    return not only or only in (spec["folder"], f"{spec['dataset']}/{spec['folder']}")


def run_chunk_level(cfg: Record, data_root: str, out_dir: str, *, only: str | None = None) -> int:
    """Chunk-level BM25 for every (folder, level) of the configuration; return the item count."""
    chash = config_hash(cfg)
    params = params_of(cfg)
    k = int(cfg.get("prefilter_k", PROTOCOL_PREFILTER_K))
    done = 0
    for spec in cfg["folders"]:
        if not _wanted(spec, only):
            continue
        for level in spec["levels"]:
            path = folder_path(data_root, level, spec)
            out = os.path.join(
                out_dir, "chunk", f"{level}__{spec['dataset']}__{spec['folder']}.json"
            )
            if _load_if_current(out, chash) is not None or not os.path.isdir(path):
                done += 1 if os.path.isdir(path) else 0
                continue
            t0 = time.perf_counter()
            folder = read_folder(path)
            t_load = time.perf_counter() - t0
            records = evaluate_folder(folder, params, prefilter_k=k)
            _dump(
                out,
                {
                    "config_hash": chash,
                    "level": level,
                    "dataset": spec["dataset"],
                    "folder": spec["folder"],
                    "role": spec["role"],
                    "corpus_chunks": len(folder.corpus_ids),
                    "queries": len(folder.queries),
                    "dropped_queries_without_qrels": folder.dropped_queries,
                    "load_seconds": round(t_load, 2),
                    "total_seconds": round(time.perf_counter() - t0, 2),
                    "hardware": hardware(),
                    "records": records,
                },
            )
            done += 1
    return done


def run_unit_level(
    cfg: Record,
    data_root: str,
    meta: dict[str, Record],
    cache_dir: str,
    work_dir: str,
    out_dir: str,
    *,
    only: str | None = None,
) -> dict[str, list[Record]]:
    """Unit-level analysis of every instance of the folders marked ``units: true``."""
    chash = config_hash(cfg)
    params = params_of(cfg)
    failures: dict[str, list[Record]] = {}
    for spec in cfg["folders"]:
        if not spec.get("units") or not _wanted(spec, only):
            continue
        folders = {lv: folder_path(data_root, lv, spec) for lv in spec["levels"]}
        qrels = {
            lv: read_qrels(os.path.join(f, "qrels.jsonl"))
            for lv, f in folders.items()
            if os.path.isdir(f)
        }
        texts: dict[str, dict[str, str]] = {}
        qtext: dict[str, dict[str, str]] = {}
        for lv, q in qrels.items():
            wanted = {cid for ids in q.values() for cid in ids}
            texts[lv] = read_corpus_texts(os.path.join(folders[lv], "corpus.jsonl"), wanted)
            qtext[lv] = _query_texts(os.path.join(folders[lv], "queries.jsonl"), set(q))
        repo_dir = spec["repo"].replace("/", "__")
        bare = os.path.join(cache_dir, f"{repo_dir}.git")
        fails: list[Record] = []
        prefix = repo_dir.lower() + "-" if spec.get("instances_of_repo") else ""
        for instance in sorted({i for q in qrels.values() for i in q}):
            if prefix and not instance.lower().startswith(prefix):
                continue  # shared folder: keep this repository only
            out = os.path.join(out_dir, "units", f"{instance}.json")
            if _load_if_current(out, chash) is not None:
                continue
            info = meta.get(instance)
            if info is None:
                fails.append({"instance": instance, "reason": "no_metadata"})
                continue
            work = os.path.join(work_dir, repo_dir)
            status = checkout_commit(bare, work, info["base_commit"])
            if status != "ok":
                fails.append({"instance": instance, "reason": status})
                continue
            levels = {
                lv: {cid: texts[lv][cid] for cid in q[instance] if cid in texts[lv]}
                for lv, q in qrels.items()
                if instance in q
            }
            rec = analyse_units(
                work,
                spec["repo"],
                instance,
                {lv: qtext[lv].get(instance, "") for lv in levels},
                levels,
                info["patch"],
                params=params,
            )
            rec.update(
                config_hash=chash,
                role=spec["role"],
                dataset=spec["dataset"],
                folder=spec["folder"],
                base_commit=info["base_commit"],
                missing_corpus_rows={
                    lv: sum(1 for cid in q[instance] if cid not in texts[lv])
                    for lv, q in qrels.items()
                    if instance in q
                },
            )
            _dump(out, rec)
        failures[spec["folder"]] = fails
    _dump(
        os.path.join(out_dir, "unit_failures.json"), {"failures": failures, "hardware": hardware()}
    )
    return failures


def _query_texts(path: str, wanted: set[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if row["_id"] in wanted:
                out[row["_id"]] = row["text"]
    return out


def run_dev_sweep(
    cfg: Record,
    data_root: str,
    out_dir: str,
    grid: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    """Chunk-level runs of the ``dev`` folders over a grid of (k1, b); one sub-directory each.

    Only folders with role ``dev`` are touched: the tuning discipline of the wave brief keeps
    every sweep off the test repositories. Each cell has its own configuration hash.
    """
    dev_only = {**cfg, "folders": [s for s in cfg["folders"] if s["role"] == "dev"]}
    done: list[tuple[float, float]] = []
    for k1, b in grid:
        cell = {**dev_only, "bm25": {**cfg["bm25"], "k1": k1, "b": b}}
        sub = os.path.join(out_dir, f"sweep_k1_{k1}_b_{b}")
        run_chunk_level(cell, data_root, sub)
        done.append((k1, b))
    return done


def run_confirm(cfg: Record, data_root: str, out_dir: str, k1: float, b: float) -> int:
    """One chunk-level run of the ``test`` folders at a stated (k1, b), for confirmation only."""
    test_only = {
        **cfg,
        "folders": [s for s in cfg["folders"] if s["role"] == "test"],
        "bm25": {**cfg["bm25"], "k1": k1, "b": b},
    }
    return run_chunk_level(test_only, data_root, out_dir)
