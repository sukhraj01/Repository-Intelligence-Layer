"""Unit-level BM25 variants and field weights on the development set (D119, E-FREEZE-AND-LATENCY).

Implements the part of decision D119 that needs unit texts: BM25 variants run one factor at a time
over the code units of each development instance, with the default of the E1 sweep as the control
in every job, and the fused cell (RRF of the BM25 variant with the stored dense scores) again. The
instance cache (``ril.evaluation.e3_prepare``) holds scores, not texts, so the texts are rebuilt at
the base commit with the same parser and the same sorted-unit-id order; the control cell must then
reproduce the cache's stored BM25 scores bit for bit (``reproduces``), which also proves that the
units and their order are those of the stored dense scores. A mismatch fails the instance and
nothing is written for it.

Cells (a factor changes, everything else is the control: reference tokenisation of the unit
``source``, k1 1.5, b 0.75):

* ``tok_split`` and ``tok_split_noorig``: identifiers split (whole identifier kept or dropped),
  documents and queries;
* ``k1_*`` and ``b_*``: the extremes of the A1-DEV grid;
* ``fw_*``: integer field weights added to the body through ``field_tokens`` (name twice; path
  once; the A1-PILOT setting name twice, signature once, path once), reference tokenisation.

Keys of an evaluation file, per cell: ``bm25|<cell>`` and ``rrf|<cell>``; plus ``dense``. Metrics
per gold reading of ``e3_prepare.READINGS`` as in the ladder, so the files read with
``ril.analysis.e3_tables.load_eval_dir``. Development role only.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

from ril.evaluation.chunk_unit_pilot import checkout_commit, hardware
from ril.evaluation.e1_run import folder_path, load_config
from ril.evaluation.e3_eval import read_eval, write_eval
from ril.evaluation.e3_prepare import READINGS, _all_query_texts, read_cache
from ril.evaluation.x2_eval import _Scorer, positions, rrf_scores
from ril.parsing.code_unit import CodeUnit
from ril.parsing.repository_parser import parse_repository
from ril.retrieval.bm25_index import (
    BM25Index,
    BM25Params,
    field_tokens,
    tokenize,
    tokenize_code,
)

UNIT_BM25_VERSION = "unit-bm25/v1"
Record = dict[str, Any]
Arr = np.ndarray[Any, Any]
Tokenizer = Callable[[str], list[str]]


@dataclass(frozen=True)
class Cell:
    """One BM25 configuration over unit texts."""

    name: str
    tokenizer: str = "ref"
    k1: float = 1.5
    b: float = 0.75
    weights: tuple[tuple[str, int], ...] = ()
    """Field weights; empty means the body (``source``) alone, the control's index."""


CONTROL = Cell("control")
CELLS: tuple[Cell, ...] = (
    CONTROL,
    Cell("tok_split", tokenizer="split"),
    Cell("tok_split_noorig", tokenizer="split_noorig"),
    Cell("k1_0.9", k1=0.9),
    Cell("k1_2.0", k1=2.0),
    Cell("b_0.4", b=0.4),
    Cell("b_0.9", b=0.9),
    Cell("fw_name2", weights=(("name", 2), ("body", 1))),
    Cell("fw_path1", weights=(("path", 1), ("body", 1))),
    Cell("fw_pilot", weights=(("name", 2), ("signature", 1), ("path", 1), ("body", 1))),
)
RRF_K = 100
"""The dev selection of E-DENSE-FUSION for CodeRankEmbed at 1,024 tokens (as the ladder)."""
DENSE_VARIANT = "coderankembed__t1024"


def tokenizer_of(name: str) -> Tokenizer:
    if name == "ref":
        return tokenize
    if name == "split":
        return tokenize_code
    if name == "split_noorig":
        return lambda t: tokenize_code(t, keep_original=False)
    raise ValueError(f"unknown tokenizer {name!r}")


def unit_documents(units: list[CodeUnit], cell: Cell) -> list[list[str]]:
    """Token lists of every unit under ``cell`` (the order of ``units``)."""
    tok = tokenizer_of(cell.tokenizer)
    if not cell.weights:
        return [tok(u.source) for u in units]
    weights = dict(cell.weights)
    return [
        field_tokens(
            {"name": u.name, "signature": u.signature, "path": u.file, "body": u.source},
            weights,
            tok,
        )
        for u in units
    ]


def cell_scores(index: BM25Index, query: str, cell: Cell) -> Arr:
    return index.scores(tokenizer_of(cell.tokenizer)(query))


def all_keys() -> list[str]:
    keys = ["dense"]
    for c in CELLS:
        keys += [f"bm25|{c.name}", f"rrf|{c.name}"]
    return keys


def unit_bm25_hash(cache_hash: str) -> str:
    """SHA-256 over what decides an evaluation file besides the data."""
    payload = {
        "version": UNIT_BM25_VERSION,
        "cells": [[c.name, c.tokenizer, c.k1, c.b, [list(w) for w in c.weights]] for c in CELLS],
        "rrf_k": RRF_K,
        "dense": DENSE_VARIANT,
        "cache": cache_hash,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def evaluate_units(
    units: list[CodeUnit],
    queries: dict[str, str],
    arrays: dict[str, Arr],
    meta: Record,
    dense: dict[str, Arr],
) -> tuple[Record, dict[str, Arr], list[Record]]:
    """Score every cell on every level of one instance; returns info, arrays and control checks.

    ``checks`` has one row per level with whether the control's scores equal the cache's stored
    BM25 scores (``reproduces``) and the largest absolute difference.
    """
    n = len(units)
    if n != int(meta["units"]):
        raise ValueError(f"{meta['instance']}: rebuilt {n} units, cache {meta['units']}")
    indexes: dict[tuple[str, tuple[tuple[str, int], ...]], list[list[str]]] = {}
    built: dict[str, BM25Index] = {}
    for c in CELLS:
        key = (c.tokenizer, c.weights)
        if key not in indexes:
            indexes[key] = unit_documents(units, c)
        built[c.name] = BM25Index(indexes[key], BM25Params(k1=c.k1, b=c.b))
    out: dict[str, Arr] = {}
    info: Record = {"levels": {}}
    checks: list[Record] = []
    for level in meta["levels"]:
        golds = {r: arrays[f"gold_{level}_{r}"] for r in READINGS}
        if not any(len(g) for g in golds.values()) or level not in queries:
            continue
        d = dense[f"dense_{level}"].astype(np.float64)
        if len(d) != n:
            raise ValueError(f"{meta['instance']}: dense has {len(d)} units, rebuilt {n}")
        pd = positions(d)
        sc = _Scorer(golds)
        sc.add("dense", d)
        for c in CELLS:
            scores = cell_scores(built[c.name], queries[level], c)
            if c.name == "control":
                stored = arrays[f"scores_{level}"].astype(np.float64)
                diff = float(np.max(np.abs(scores - stored))) if n else 0.0
                checks.append(
                    {
                        "instance": meta["instance"],
                        "level": level,
                        "reproduces": bool(np.array_equal(scores, stored)),
                        "max_abs_diff": diff,
                    }
                )
            sc.add(f"bm25|{c.name}", scores)
            sc.add(f"rrf|{c.name}", rrf_scores([positions(scores), pd], RRF_K))
        if sc.keys != all_keys():
            raise RuntimeError("key order of the level differs from all_keys()")
        out[f"metrics_{level}"] = np.asarray(sc.rows, dtype=np.float64)
        out[f"aux_{level}"] = np.zeros((0, 1 + len(READINGS)), dtype=np.float64)
        info["levels"][level] = {f"gold_{r}": int(len(golds[r])) for r in READINGS}
        info["levels"][level]["gold_units"] = int(len(golds["units"]))
    out["keys"] = np.asarray(all_keys(), dtype=str)
    out["aux_keys"] = np.asarray([], dtype=str)
    return info, out, checks


def run_unit_bm25(
    e1_config_path: str,
    data_root: str,
    repo_cache: str,
    cache_dir: str,
    dense_root: str,
    work_dir: str,
    out_dir: str,
    *,
    shard: tuple[int, int] = (0, 1),
    limit: int | None = None,
) -> list[Record]:
    """Evaluate every development instance of ``cache_dir`` that has stored dense scores.

    Resumable: a file with the same evaluation hash is kept. Returns one record per instance that
    could not be evaluated (reason) and writes ``checks_s<i>.json`` with every control check.
    """
    e1_cfg = load_config(e1_config_path)
    specs = {(s["dataset"], s["folder"]): s for s in e1_cfg["folders"]}
    names = sorted(n for n in os.listdir(cache_dir) if n.endswith(".npz"))
    failures: list[Record] = []
    checks: list[Record] = []
    qtext: dict[tuple[str, str, str], dict[str, str]] = {}
    done = 0
    for ordinal, name in enumerate(names):
        if ordinal % shard[1] != shard[0]:
            continue
        arrays, cmeta = read_cache(os.path.join(cache_dir, name))
        if cmeta["role"] != "dev":
            continue
        if limit is not None and done >= limit:
            break
        instance = cmeta["instance"]
        ehash = unit_bm25_hash(str(cmeta["config_hash"]))
        out = os.path.join(out_dir, name)
        if os.path.exists(out) and read_eval(out)[0].get("eval_hash") == ehash:
            continue
        dpath = os.path.join(dense_root, DENSE_VARIANT, name)
        if not os.path.exists(dpath):
            failures.append({"instance": instance, "reason": "no_dense_scores"})
            continue
        spec = specs.get((cmeta["dataset"], cmeta["folder"]))
        base_commit = str(cmeta.get("base_commit", ""))
        if spec is None or not base_commit:
            failures.append({"instance": instance, "reason": "no_spec_or_base_commit"})
            continue
        repo_dir = spec["repo"].replace("/", "__")
        work = os.path.join(work_dir, f"{repo_dir}__u{shard[0]}")
        status = checkout_commit(os.path.join(repo_cache, f"{repo_dir}.git"), work, base_commit)
        if status != "ok":
            failures.append({"instance": instance, "reason": status})
            continue
        queries: dict[str, str] = {}
        for lv in spec["levels"]:
            key = (lv, spec["dataset"], spec["folder"])
            if key not in qtext:
                qpath = os.path.join(folder_path(data_root, lv, spec), "queries.jsonl")
                qtext[key] = _all_query_texts(qpath) if os.path.exists(qpath) else {}
            if instance in qtext[key]:
                queries[lv] = qtext[key][instance]
        units = sorted(parse_repository(work, spec["repo"]).units, key=lambda u: u.id)
        with np.load(dpath, allow_pickle=False) as dz:
            dense = {k: dz[k] for k in dz.files if k.startswith("dense_")}
        try:
            info, res, chk = evaluate_units(units, queries, arrays, cmeta, dense)
        except ValueError as exc:
            failures.append({"instance": instance, "reason": f"error:{exc}"})
            continue
        checks += chk
        if not all(c["reproduces"] for c in chk):
            failures.append({"instance": instance, "reason": "control_not_reproduced"})
            continue
        info.update(
            eval_hash=ehash,
            cache_hash=str(cmeta["config_hash"]),
            instance=instance,
            role=cmeta["role"],
            dataset=cmeta["dataset"],
            folder=cmeta["folder"],
            repo_id=cmeta["repo_id"],
            units=cmeta["units"],
        )
        write_eval(out, info, res)
        done += 1
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, f"checks_s{shard[0]}.json"), "w", encoding="utf-8") as fh:
        json.dump(
            {
                "version": UNIT_BM25_VERSION,
                "checks": checks,
                "failures": failures,
                "hardware": hardware(),
                "evaluated": done,
            },
            fh,
        )
    return failures


def list_eval_files(path: str) -> list[str]:
    return sorted(glob.glob(os.path.join(path, "*.npz")))
