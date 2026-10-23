"""Per-instance cache for the graph-signal pilots E3 to E5 (exploratory).

Implements the first half of ``docs/EXPERIMENTS.md`` E-GRAPH-SIGNAL: for one benchmark instance,
check out the base commit, build the units and the typed graph of the snapshot (with the
exploratory ``tests``, ``configures`` and ``co_change`` families and the file history), score
every unit with BM25 for the issue text of each level, and write everything the evaluation needs
as arrays: BM25 scores, edge pairs per family over unit indices, the file of each unit, the age of
each unit's file at the snapshot, and the gold unit indices (read from the pilot-E1 record of the
same instance, which holds the mapped positives; the cache never holds chunk or source text).

The evaluation (``ril.evaluation.e3_eval``) then runs any grid on the cache without touching the
repository again, and enforces the dev/test split of the tuning discipline.

Unit order is the sorted unit id (the order of the BM25 index of pilot E1, so the baseline ranks
agree with ``unit_ranks.with_module`` of that pilot; the cache records the number of
disagreements, expected 0).

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import subprocess
import time
from typing import Any

import numpy as np
import yaml

from ril.evaluation.chunk_unit_pilot import checkout_commit, hardware
from ril.evaluation.core_bench import rank_positives
from ril.evaluation.e1_run import (
    LEVEL_DIR,
    _query_texts,
    folder_path,
    load_config,
    params_of,
)
from ril.parsing.build import BuildConfig, BuildResult, build_repository
from ril.parsing.call_graph import RESOLVER_NAME, RESOLVER_VERSION
from ril.parsing.code_unit import CODEUNIT_SCHEMA_VERSION, CodeUnit
from ril.parsing.exploratory_edges import co_change_edges
from ril.parsing.repo_graph import REPO_GRAPH_SCHEMA_VERSION
from ril.parsing.repository_parser import PARSER_VERSION
from ril.retrieval.bm25_index import BM25Index, BM25Params, tokenize
from ril.retrieval.recency import ages_in_days

PREPARE_VERSION = "e3-prepare/v1"
CO_CHANGE_SUPPORT = 3
"""Co-change support used for the ``co_change`` family (the ``all`` subset of pilot M)."""
READINGS = ("units", "units_all", "units_nomod", "units_all_nomod")
"""Gold readings (Q39, decision D18): pilot M's mapping, every overlapped unit, and each without
module units; ``units_all_nomod`` is D18's primary reading for graph questions, ``units_all`` the
CORE-Bench-faithful one beside it."""
NOMOD_OF = {"units_nomod": "units", "units_all_nomod": "units_all"}
"""Each reading without module units and the reading it is derived from."""
Record = dict[str, Any]

__all__ = [
    "PREPARE_VERSION",
    "LEVEL_DIR",
    "folder_path",
    "load_config",
    "prepare_hash",
    "prepare_instance",
    "run_prepare",
]


def prepare_hash(e1_cfg: Record, params: BM25Params) -> str:
    """SHA-256 over everything besides the data that decides a cache."""
    payload = {
        "version": PREPARE_VERSION,
        "bm25": {"k1": params.k1, "b": params.b},
        "co_change_support": CO_CHANGE_SUPPORT,
        "parser": PARSER_VERSION,
        "resolver": f"{RESOLVER_NAME}/{RESOLVER_VERSION}",
        "repo_graph_schema": REPO_GRAPH_SCHEMA_VERSION,
        "codeunit_schema": CODEUNIT_SCHEMA_VERSION,
        "e1_seed": e1_cfg["seed"],
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def snapshot_time(root: str) -> float:
    """Commit time (epoch seconds) of the checked-out commit."""
    done = subprocess.run(
        ["git", "-C", root, "show", "-s", "--format=%ct", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return float(done.stdout.strip())


def is_module_id(unit_id: str) -> bool:
    """Whether a unit id names the residual module unit of a file."""
    return unit_id.endswith("::<module>")


def gold_by_level(e1_record: Record) -> dict[str, dict[str, set[str]]]:
    """``{level: {reading: gold unit ids}}`` from the positives of a pilot-E1 instance record."""
    out: dict[str, dict[str, set[str]]] = {}
    for p in e1_record["positives"]:
        if p["status"] != "found":
            continue
        slot = out.setdefault(p["level"], {r: set() for r in READINGS})
        for r in ("units", "units_all"):
            slot[r].update(p[r])
        for nomod, src in NOMOD_OF.items():
            slot[nomod].update(u for u in p[src] if not is_module_id(u))
    return out


def unit_graph_arrays(
    result: BuildResult,
) -> tuple[list[CodeUnit], dict[str, int], int, dict[str, np.ndarray[Any, Any]]]:
    """Units in index order (sorted id), their indices, the node count and edge pairs per family.

    Edge pairs are resolved edges over unit indices (``inherit`` includes ``override``;
    ``co_change`` has support 3); nodes that are not units (directories, configuration files) get
    indices after the units.
    """
    units = sorted(result.parsed.units, key=lambda u: u.id)
    index_of = {u.id: i for i, u in enumerate(units)}
    nodes: dict[str, int] = dict(index_of)

    def node(nid: str) -> int:
        got = nodes.get(nid)
        if got is None:
            got = nodes[nid] = len(nodes)
        return got

    pairs: dict[str, set[tuple[int, int]]] = {}

    def add(family: str, a: str, b: str) -> None:
        if a != b:
            pairs.setdefault(family, set()).add((node(a), node(b)))

    graphs = [result.graph] + [g for g in (result.tests, result.configures) if g is not None]
    for g in graphs:
        for e in g.edges:
            if e.status != "resolved":
                continue
            add("inherit" if e.type == "override" else e.type, e.src, e.dst)
    if result.history is not None:
        for e in co_change_edges(result.parsed, result.history.commit_py_sets, CO_CHANGE_SUPPORT):
            if e.status == "resolved":
                add("co_change", e.src, e.dst)
    arrays: dict[str, np.ndarray[Any, Any]] = {}
    for family, items in sorted(pairs.items()):
        arrays[f"pairs_{family}"] = np.asarray(sorted(items), dtype=np.int32).reshape(-1, 2)
    return units, index_of, len(nodes), arrays


def prepare_instance(
    root: str,
    repo_id: str,
    queries: dict[str, str],
    e1_record: Record,
    params: BM25Params,
    chash: str,
) -> tuple[dict[str, np.ndarray[Any, Any]], Record]:
    """Arrays and metadata of one instance (``root`` is checked out at the base commit)."""
    seconds: dict[str, float] = {}
    t0 = time.perf_counter()
    result = build_repository(root, BuildConfig(repo_id=repo_id, seed=0))
    seconds.update({k: round(v, 3) for k, v in result.seconds.items()})
    units, index_of, n_nodes, arrays = unit_graph_arrays(result)
    n = len(units)
    files = sorted({u.file for u in units})
    file_idx = {f: i for i, f in enumerate(files)}
    arrays["file_of_unit"] = np.asarray([file_idx[u.file] for u in units], dtype=np.int32)
    snap = snapshot_time(root)
    arrays["age_days"] = ages_in_days([u.last_modified for u in units], snap)

    t1 = time.perf_counter()
    index = BM25Index((tokenize(u.source) for u in units), params)
    seconds["bm25_index"] = round(time.perf_counter() - t1, 3)

    gold = gold_by_level(e1_record)
    missing_gold = 0
    rank_mismatch = 0
    rank_checked = 0
    for level in sorted(queries):
        if level not in gold:
            continue
        scores = index.scores(tokenize(queries[level]))
        arrays[f"scores_{level}"] = scores
        for reading in READINGS:
            ids = sorted(gold[level][reading])
            kept = [index_of[i] for i in ids if i in index_of]
            missing_gold += len(ids) - len(kept)
            arrays[f"gold_{level}_{reading}"] = np.asarray(kept, dtype=np.int32)
        # agreement with the unit ranks of pilot E1 (same index, filter-first, module unit in)
        ref = e1_record["unit_ranks"].get(level, {}).get("with_module", {})
        if ref:
            wanted = sorted(index_of[i] for i in ref if i in index_of)
            by_pos = rank_positives(scores, None, wanted, 10**9)
            for uid, rec in ref.items():
                if uid in index_of:
                    rank_checked += 1
                    if by_pos[index_of[uid]]["filter_first"] != rec["rank"]:
                        rank_mismatch += 1
    meta: Record = {
        "version": PREPARE_VERSION,
        "config_hash": chash,
        "repo_id": repo_id,
        "commit": result.commit,
        "units": n,
        "nodes": n_nodes,
        "files": len(files),
        "snapshot_time": snap,
        "units_without_history": int(np.isinf(arrays["age_days"]).sum()),
        "edge_pairs": {k[6:]: int(v.shape[0]) for k, v in arrays.items() if k.startswith("pairs_")},
        "gold_ids_not_in_units": missing_gold,
        "e1_rank_checked": rank_checked,
        "e1_rank_mismatch": rank_mismatch,
        "seconds": seconds,
        "seconds_total": round(time.perf_counter() - t0, 3),
        "levels": sorted(k[7:] for k in arrays if k.startswith("scores_")),
        "hardware": hardware(),
    }
    return arrays, meta


def add_missing_readings(path: str, e1_record: Record) -> bool:
    """Add gold readings that an older cache file lacks (the readings without module units).

    The gold arrays hold unit indices in the order of the sorted gold ids, and the index order is
    the sorted unit-id order, so the ids of the pilot-E1 record line up with the stored indices.
    Returns True if the file changed.
    """
    arrays, meta = read_cache(path)
    gold = gold_by_level(e1_record)
    changed = False
    for level, readings in gold.items():
        for nomod, src in NOMOD_OF.items():
            have = arrays.get(f"gold_{level}_{src}")
            want = f"gold_{level}_{nomod}"
            if have is None or want in arrays:
                continue
            ids = sorted(readings[src])
            if len(ids) != len(have):
                raise ValueError(f"{path}: {level} gold ids and stored indices differ in number")
            arrays[want] = np.asarray(
                [int(i) for i, uid in zip(have, ids, strict=True) if not is_module_id(uid)],
                dtype=np.int32,
            )
            changed = True
    if changed:
        write_cache(path, arrays, meta)
    return changed


def write_cache(path: str, arrays: dict[str, np.ndarray[Any, Any]], meta: Record) -> None:
    """Write one cache file atomically."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp.npz"
    payload: dict[str, Any] = {"meta": np.asarray(json.dumps(meta, sort_keys=True)), **arrays}
    np.savez_compressed(tmp, **payload)
    os.replace(tmp, path)


def read_cache(path: str) -> tuple[dict[str, np.ndarray[Any, Any]], Record]:
    """Read a cache file back."""
    with np.load(path, allow_pickle=False) as data:
        arrays = {k: data[k] for k in data.files if k != "meta"}
        meta = json.loads(str(data["meta"]))
    return arrays, meta


def cache_current(path: str, chash: str) -> bool:
    """Whether a cache file exists and carries the configuration hash."""
    if not os.path.exists(path):
        return False
    try:
        return bool(read_cache(path)[1].get("config_hash") == chash)
    except (OSError, ValueError, KeyError):
        return False


def run_prepare(
    e1_config_path: str,
    roles: set[str],
    data_root: str,
    meta: dict[str, Record],
    repo_cache: str,
    cache_dir: str,
    work_dir: str,
    out_dir: str,
    e1_units_dir: str,
    *,
    only: str | None = None,
    limit: int | None = None,
    shard: tuple[int, int] = (0, 1),
) -> list[Record]:
    """Prepare the cache of every instance of the folders with ``units`` and a role in ``roles``.

    ``shard = (i, k)`` takes every k-th instance (in sorted order) starting at i, so several
    jobs can share a work list; each shard has its own working clones. Returns the failures.
    """
    e1_cfg = load_config(e1_config_path)
    params = params_of(e1_cfg)
    chash = prepare_hash(e1_cfg, params)
    specs = {
        (s["dataset"], s["folder"]): s
        for s in e1_cfg["folders"]
        if s.get("units")
        and s["role"] in roles
        and (not only or only in (s["folder"], f"{s['dataset']}/{s['folder']}"))
    }
    records: list[Record] = []
    for path in sorted(glob.glob(os.path.join(e1_units_dir, "*.json"))):
        with open(path, encoding="utf-8") as handle:
            rec = json.load(handle)
        if (rec["dataset"], rec["folder"]) in specs:
            records.append(rec)
    records.sort(key=lambda r: r["instance"])
    qtext_cache: dict[tuple[str, str, str], dict[str, str]] = {}
    failures: list[Record] = []
    done = 0
    for ordinal, rec in enumerate(records):
        if ordinal % shard[1] != shard[0]:
            continue
        if limit is not None and done >= limit:
            break
        spec = specs[(rec["dataset"], rec["folder"])]
        instance = rec["instance"]
        out = os.path.join(cache_dir, f"{instance}.npz")
        if cache_current(out, chash):
            continue
        info = meta.get(instance)
        if info is None:
            failures.append({"instance": instance, "reason": "no_metadata"})
            continue
        repo_dir = spec["repo"].replace("/", "__")
        work = os.path.join(work_dir, f"{repo_dir}__s{shard[0]}")
        status = checkout_commit(
            os.path.join(repo_cache, f"{repo_dir}.git"), work, info["base_commit"]
        )
        if status != "ok":
            failures.append({"instance": instance, "reason": status})
            continue
        queries: dict[str, str] = {}
        for lv in spec["levels"]:
            key = (lv, spec["dataset"], spec["folder"])
            if key not in qtext_cache:
                qpath = os.path.join(folder_path(data_root, lv, spec), "queries.jsonl")
                qtext_cache[key] = _all_query_texts(qpath) if os.path.exists(qpath) else {}
            if instance in qtext_cache[key]:
                queries[lv] = qtext_cache[key][instance]
        arrays, meta_out = prepare_instance(work, spec["repo"], queries, rec, params, chash)
        meta_out.update(
            instance=instance,
            role=spec["role"],
            dataset=spec["dataset"],
            folder=spec["folder"],
            base_commit=info["base_commit"],
        )
        write_cache(out, arrays, meta_out)
        done += 1
    os.makedirs(out_dir, exist_ok=True)
    fail_path = os.path.join(out_dir, f"prepare_failures_s{shard[0]}.json")
    with open(fail_path, "w", encoding="utf-8") as handle:
        json.dump(
            {"failures": failures, "hardware": hardware(), "config_hash": chash, "prepared": done},
            handle,
        )
    return failures


def _all_query_texts(path: str) -> dict[str, str]:
    wanted: set[str] = set()
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                wanted.add(json.loads(line)["_id"])
    return _query_texts(path, wanted)


def describe_config(path: str) -> Record:
    """Read a YAML experiment configuration."""
    with open(path, encoding="utf-8") as handle:
        doc = yaml.safe_load(handle)
    if not isinstance(doc, dict):
        raise ValueError(f"{path}: expected a mapping")
    return doc
