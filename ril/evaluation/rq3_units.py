"""Unit records, BM25 scores and text stores for the executable subset of Verified (RQ3).

Implements the build half of ``docs/RQ3_PILOT.md`` "Executable evaluation (D106)" and entry
``E-RQ3-UNITS`` of ``docs/experiments/B.md`` (decision D107). For every instance of the frozen
subset the base commit is parsed with the parser, unit definition and BM25 settings of the dev
pipeline (``e1_run`` unit stage, ``e3_prepare``, ``x2_dense``): units in sorted-id order, class
units in the ``full`` form, BM25 scores of the issue text, and the hash of every unit text. Nothing
here evaluates a retrieval result and no agent is called.

Labelled instances (a CORE-Bench L2 or L3 folder row) also get the gold readings, through the
existing chunk-to-unit mapping, unchanged; unlabelled ones get scores only. Distinct unit texts are
counted per repository and over all snapshots so the encoding cost is read from the distinct
count (``docs/RQ2_PROTOCOL.md`` D79, D80), not estimated from unit counts.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import glob
import json
import os
import time
from collections.abc import Iterable, Sequence
from typing import Any

import numpy as np

from ril.evaluation.chunk_unit_pilot import (
    checkout_commit,
    hardware,
    read_corpus_texts,
    read_qrels,
)
from ril.evaluation.e1_run import _query_texts, config_hash, folder_path, load_config, params_of
from ril.evaluation.e3_prepare import cache_current, prepare_hash, prepare_instance, write_cache
from ril.evaluation.unit_retrieval import analyse_units
from ril.evaluation.x2_dense import (
    VectorStore,
    prepare_units,
    query_key,
    read_store,
    score_units,
)

RQ3_UNITS_VERSION = "rq3-units/v1"
DATASET = "SWE-bench_Verified"
Record = dict[str, Any]

GPU_BLOCK4_HOURS = 6.0
"""Ledger block for RQ3 encoding (D107): a project ledger, not a cluster limit (D79)."""
MEASURED_TEXTS_PER_S = 109.0
"""Encoding rate measured on the eight-repository build (E-EVAL-REPOS-BUILD), texts per second."""

VERIFIED_FOLDER = {
    "astropy/astropy": "astropy__astropy",
    "django/django": "django__django",
    "matplotlib/matplotlib": "matplotlib__matplotlib",
    "mwaskom/seaborn": "mwaskom__seaborn",
    "pallets/flask": "pallets__flask",
    "psf/requests": "psf__requests",
    "pydata/xarray": "pydata__xarray",
    "pylint-dev/pylint": "pylint",
    "pytest-dev/pytest": "pytest",
    "scikit-learn/scikit-learn": "scikit",
    "sphinx-doc/sphinx": "sphinx",
    "sympy/sympy": "sympy__sympy",
}
"""CORE-Bench folder of each Verified repository (as in ``e1_bm25_reproduction.yaml``)."""


# --------------------------------------------------------------------------- inputs


def member_ids(subset: Record) -> list[str]:
    """Instance ids of the frozen subset, sorted."""
    return sorted(str(m["instance_id"]) for m in subset["executable"])


def build_inputs(
    subset: Record, rows: Iterable[Record], repos: set[str] | None = None
) -> tuple[dict[str, Record], dict[str, str]]:
    """``(meta, queries)`` of the subset members from rows of the Verified table.

    ``meta[instance]`` holds ``repo``, ``base_commit``, ``patch``, ``dataset`` and ``folder`` (the
    layout the unit stage reads); ``queries[instance]`` is the issue text of the table. Members
    outside ``repos`` (a set of ``owner/name``) are left out when it is given.
    """
    wanted = {str(m["instance_id"]): str(m["repo"]) for m in subset["executable"]}
    meta: dict[str, Record] = {}
    queries: dict[str, str] = {}
    for row in rows:
        iid = str(row["instance_id"])
        if iid not in wanted or (repos is not None and wanted[iid] not in repos):
            continue
        repo = wanted[iid]
        meta[iid] = {
            "repo": repo,
            "base_commit": str(row["base_commit"]),
            "patch": str(row["patch"]),
            "dataset": DATASET,
            "folder": VERIFIED_FOLDER[repo],
        }
        queries[iid] = str(row["problem_statement"])
    missing = sorted(
        i for i, r in wanted.items() if (repos is None or r in repos) and i not in meta
    )
    if missing:
        raise ValueError(f"{len(missing)} subset members are not in the table, e.g. {missing[:3]}")
    return meta, queries


# --------------------------------------------------------------------------- resource readings


def reset_peak_rss() -> None:
    """Reset the kernel's peak resident-size mark of this process (Linux; a no-op elsewhere)."""
    try:
        with open("/proc/self/clear_refs", "w", encoding="ascii") as handle:
            handle.write("5")
    except OSError:
        pass


def peak_rss_mb() -> float | None:
    """Peak resident size of this process since the last reset, in MB (Linux), else None."""
    try:
        with open("/proc/self/status", encoding="ascii") as handle:
            for line in handle:
                if line.startswith("VmHWM:"):
                    return round(int(line.split()[1]) / 1024, 1)
    except OSError:
        return None
    return None


# --------------------------------------------------------------------------- unit and cache stage


def prepare_members(
    config_path: str,
    data_root: str,
    meta: dict[str, Record],
    queries: dict[str, str],
    repo_cache: str,
    cache_dir: str,
    e1_dir: str,
    work_dir: str,
    out_dir: str,
    *,
    shard: tuple[int, int] = (0, 1),
    limit: int | None = None,
) -> list[Record]:
    """Unit records (labelled instances) and instance caches of every member, resumable.

    Per instance: check out the base commit; for an instance with positives in a CORE-Bench folder
    run the unit stage (``analyse_units``, the existing chunk-to-unit mapping) and keep its record
    under ``e1_dir``; build the cache of ``e3_prepare`` (units, graph, BM25 scores) with the issue
    text as the L2 query, folder query texts for the levels the folder has. ``shard = (i, k)``
    takes every k-th member in sorted order. Seconds and peak resident size go into the cache
    meta. Returns the failures.
    """
    cfg = load_config(config_path)
    params = params_of(cfg)
    chash = prepare_hash(cfg, params)
    e1_hash = config_hash(cfg)
    specs = {s["folder"]: s for s in cfg["folders"] if s.get("units")}
    members = sorted(i for i, m in meta.items() if m["folder"] in specs)
    mine = [i for n, i in enumerate(members) if n % shard[1] == shard[0]]
    qrels: dict[tuple[str, str], dict[str, list[str]]] = {}
    ctext: dict[tuple[str, str], dict[str, str]] = {}
    qtext: dict[tuple[str, str], dict[str, str]] = {}
    for folder in sorted({meta[i]["folder"] for i in mine}):
        spec = specs[folder]
        for lv in spec["levels"]:
            path = folder_path(data_root, lv, spec)
            if not os.path.isfile(os.path.join(path, "qrels.jsonl")):
                continue
            allq = read_qrels(os.path.join(path, "qrels.jsonl"))
            q = {i: ids for i, ids in allq.items() if i in meta and meta[i]["folder"] == folder}
            qrels[(lv, folder)] = q
            wanted = {cid for ids in q.values() for cid in ids}
            ctext[(lv, folder)] = read_corpus_texts(os.path.join(path, "corpus.jsonl"), wanted)
            qtext[(lv, folder)] = _query_texts(os.path.join(path, "queries.jsonl"), set(q))
    failures: list[Record] = []
    done = 0
    for instance in mine:
        if limit is not None and done >= limit:
            break
        out = os.path.join(cache_dir, f"{instance}.npz")
        if cache_current(out, chash):
            continue
        info = meta[instance]
        spec = specs[info["folder"]]
        repo_dir = info["repo"].replace("/", "__")
        work = os.path.join(work_dir, f"{repo_dir}__s{shard[0]}")
        status = checkout_commit(
            os.path.join(repo_cache, f"{repo_dir}.git"), work, info["base_commit"]
        )
        if status != "ok":
            failures.append({"instance": instance, "reason": status})
            continue
        reset_peak_rss()
        t_unit = time.perf_counter()
        levels_q: dict[str, str] = {}
        levels_pos: dict[str, dict[str, str]] = {}
        for lv in spec["levels"]:
            key = (lv, info["folder"])
            if instance in qrels.get(key, {}):
                levels_pos[lv] = {
                    cid: ctext[key][cid] for cid in qrels[key][instance] if cid in ctext[key]
                }
                levels_q[lv] = qtext[key].get(instance, "")
        if levels_pos:
            rec = analyse_units(
                work, info["repo"], instance, levels_q, levels_pos, info["patch"], params=params
            )
            rec.update(
                config_hash=e1_hash,
                role="test",
                dataset=DATASET,
                folder=info["folder"],
                base_commit=info["base_commit"],
            )
            _dump(os.path.join(e1_dir, f"{instance}.json"), rec)
        else:
            rec = {"instance": instance, "positives": [], "unit_ranks": {}}
        seconds_unit = time.perf_counter() - t_unit
        l2_source = "core_bench" if levels_q.get("L2") else "verified_table"
        text_l2 = levels_q.get("L2") or queries[instance]
        query_levels = dict(levels_q)
        query_levels["L2"] = text_l2
        try:
            arrays, meta_out = prepare_instance(
                work, info["repo"], query_levels, rec, params, chash, score_without_gold=True
            )
        except (OSError, ValueError, RuntimeError) as exc:  # a parse or checkout fault
            failures.append({"instance": instance, "reason": f"prepare:{type(exc).__name__}:{exc}"})
            continue
        meta_out.update(
            instance=instance,
            role="test",
            dataset=DATASET,
            folder=info["folder"],
            base_commit=info["base_commit"],
            labelled_levels=sorted(levels_pos),
            l2_query_source=l2_source,
            l2_text_equals_table=(
                None if l2_source != "core_bench" else text_l2 == queries[instance]
            ),
            unit_stage_seconds=round(seconds_unit, 2),
            peak_rss_mb=peak_rss_mb(),
            rq3_units_version=RQ3_UNITS_VERSION,
        )
        write_cache(out, arrays, meta_out)
        _dump(
            os.path.join(out_dir, "issue_text", f"{instance}.json"),
            {"h": query_key("L2", DATASET, info["folder"], instance), "t": text_l2},
        )
        done += 1
    os.makedirs(out_dir, exist_ok=True)
    _dump(
        os.path.join(out_dir, f"rq3_units_failures_s{shard[0]}.json"),
        {"failures": failures, "prepared": done, "hardware": hardware(), "config_hash": chash},
    )
    return failures


def _dump(path: str, obj: object) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(obj, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
    os.replace(tmp, path)


# --------------------------------------------------------------------------- text stores


def prepare_unit_texts(
    config_path: str,
    meta: dict[str, Record],
    repo_cache: str,
    cache_dir: str,
    work_dir: str,
    prep_dir: str,
    *,
    shard: tuple[int, int] = (0, 1),
) -> Record:
    """Unit-text hashes per instance and the text stores, ``full`` class form only (D107)."""
    return prepare_units(
        config_path,
        {"test"},
        meta,
        repo_cache,
        cache_dir,
        work_dir,
        prep_dir,
        shard=shard,
        forms=("full",),
    )


def prepare_query_store(out_dir: str, prep_dir: str) -> Record:
    """One query store per folder (level L2, key as ``x2_dense.query_key``) from the issue texts
    the caches were scored with (``issue_text/<instance>.json`` under ``out_dir``); rewritten whole,
    so a rerun gives the same files."""
    by_folder: dict[str, dict[str, str]] = {}
    for path in sorted(glob.glob(os.path.join(out_dir, "issue_text", "*.json"))):
        with open(path, encoding="utf-8") as handle:
            row = json.load(handle)
        folder = str(row["h"]).split("|")[2]
        by_folder.setdefault(folder, {})[str(row["h"])] = str(row["t"])
    for folder, rows in sorted(by_folder.items()):
        store = os.path.join(prep_dir, "queries", f"L2__{DATASET}__{folder}.jsonl")
        os.makedirs(os.path.dirname(store), exist_ok=True)
        with open(f"{store}.tmp", "w", encoding="utf-8") as handle:
            for key in sorted(rows):
                handle.write(json.dumps({"h": key, "t": rows[key]}) + "\n")
        os.replace(f"{store}.tmp", store)
    return {"queries": {f: len(r) for f, r in sorted(by_folder.items())}}


# --------------------------------------------------------------------------- counts and the rule


def distinct_counts(prep_dir: str, already: set[str] | None = None) -> Record:
    """Distinct unit texts per repository and in all, and the saving from de-duplication.

    Reads the per-instance hash arrays (``units/*.npz``) and the text stores. ``already`` is a set
    of hashes that already have a vector (texts of instances built earlier); the count of texts
    still to encode excludes them.
    """
    per_repo: dict[str, Record] = {}
    all_hashes: set[str] = set()
    for path in sorted(glob.glob(os.path.join(prep_dir, "units", "*.npz"))):
        with np.load(path, allow_pickle=False) as d:
            m = json.loads(str(d["meta"]))
            hs = [str(x) for x in d["hashes_full"]]
        slot = per_repo.setdefault(m["repo_dir"], {"instances": 0, "unit_slots": 0, "_h": set()})
        slot["instances"] += 1
        slot["unit_slots"] += len(hs)
        slot["_h"].update(hs)
        all_hashes.update(hs)
    rows: dict[str, Record] = {}
    for repo, slot in sorted(per_repo.items()):
        distinct = len(slot["_h"])
        rows[repo] = {
            "instances": slot["instances"],
            "unit_slots": slot["unit_slots"],
            "distinct_texts": distinct,
            "distinct_share": round(distinct / max(1, slot["unit_slots"]), 4),
        }
    slots = sum(r["unit_slots"] for r in rows.values())
    todo = len(all_hashes - (already or set()))
    return {
        "per_repo": rows,
        "unit_slots": slots,
        "distinct_texts": len(all_hashes),
        "saving_factor": round(slots / max(1, len(all_hashes)), 2),
        "distinct_to_encode": todo,
    }


def implied_gpu_hours(texts: int, rate: float = MEASURED_TEXTS_PER_S) -> float:
    """GPU-hours to encode ``texts`` at ``rate`` texts per second."""
    return texts / rate / 3600.0


def encoding_rule(texts_to_encode: int, texts_total: int) -> Record:
    """The rule fixed before the run (D107): encode only if the implied GPU-hours at the measured
    rate are at most the block limit. The rate is the eight-repository build's 109 texts/s; at 178
    or 229 texts/s the figure would be lower, so the rule is the conservative reading."""
    hours = implied_gpu_hours(texts_to_encode)
    return {
        "texts_to_encode": texts_to_encode,
        "texts_total": texts_total,
        "rate_texts_per_s": MEASURED_TEXTS_PER_S,
        "implied_gpu_hours": round(hours, 3),
        "implied_gpu_hours_at_178": round(implied_gpu_hours(texts_to_encode, 178.0), 3),
        "implied_gpu_hours_at_229": round(implied_gpu_hours(texts_to_encode, 229.0), 3),
        "implied_gpu_hours_total_texts": round(implied_gpu_hours(texts_total), 3),
        "limit_gpu_hours": GPU_BLOCK4_HOURS,
        "allowed": hours <= GPU_BLOCK4_HOURS,
    }


def score_members(prep_dir: str, enc_dir: str, out_dir: str, max_tokens: int) -> Record:
    """Dense scores (``dense_L2``) of every prepared member, ``full`` class form, in the layout the
    pilot-E3 evaluation reads; resumable per instance."""
    return score_units(prep_dir, enc_dir, out_dir, max_tokens, roles={"test"}, forms=("full",))


# --------------------------------------------------------------------------- vector check


def missing_vectors(prep_dir: str, enc_dir: str, extra_stores: Sequence[str] = ()) -> Record:
    """Per-text check: every unit text of every prepared instance has a vector (count missing).

    ``extra_stores`` are further merged vector files (earlier builds) searched after the store of
    the instance's repository.
    """
    stores: dict[str, VectorStore] = {}
    missing = 0
    checked = 0
    instances_missing: list[str] = []
    for path in sorted(glob.glob(os.path.join(prep_dir, "units", "*.npz"))):
        with np.load(path, allow_pickle=False) as d:
            m = json.loads(str(d["meta"]))
            hs = [str(x) for x in d["hashes_full"]]
        repo = m["repo_dir"]
        if repo not in stores:
            files = [os.path.join(enc_dir, f"units__{repo}.npz"), *extra_stores]
            stores = {repo: VectorStore([f for f in files if os.path.exists(f)])}
        index = stores[repo].index
        lost = sum(1 for h in hs if h not in index)
        checked += len(hs)
        missing += lost
        if lost:
            instances_missing.append(m["instance"])
    return {"texts_checked": checked, "missing": missing, "instances_missing": instances_missing}


def store_texts(prep_dir: str) -> int:
    """Number of distinct unit texts in the text stores of a prepared directory."""
    seen: set[str] = set()
    for p in sorted(glob.glob(os.path.join(prep_dir, "texts_units", "*.jsonl"))):
        seen.update(read_store([p]))
    return len(seen)


__all__ = [
    "RQ3_UNITS_VERSION",
    "build_inputs",
    "distinct_counts",
    "encoding_rule",
    "implied_gpu_hours",
    "member_ids",
    "missing_vectors",
    "prepare_members",
    "prepare_query_store",
    "prepare_unit_texts",
    "score_members",
    "store_texts",
]
