"""A BM25 variant inside RRF(BM25, dense) on the development folders (session A1, E-A1-FUSED).

Implements the fused cell of ``prompts/team/rulings/A_rulings_3.md`` step (a): a BM25 improvement
that disappears inside the fused first stage is not an improvement of the system. Rule and cells are
fixed in ``configs/experiments/a_bm25_fused.yaml`` before the run.

Filter-first reading, as the chunk level of E-DENSE-FUSION
(``ril.evaluation.x2_dense.score_chunks``): each query is ranked among its own candidate list; the
fused rank is RRF ``1/(k+r_bm25) + 1/(k+r_dense)`` with ties broken by the BM25 rank. The control
cell (default tokenizer and parameters) must reproduce the stored ranks of that scoring exactly; the
dense scores are read from the stored encoded vectors, nothing is encoded here.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import glob
import json
import os
import time
from collections import defaultdict
from typing import Any

import numpy as np

from ril.analysis.e1_tables import scores_of
from ril.analysis.rq1_bm25_dev import TOKENIZERS, cell_name
from ril.analysis.rq1_docstring_pilot import clustered_diff_ci
from ril.evaluation.core_bench import read_folder
from ril.evaluation.e1_run import folder_path
from ril.evaluation.metrics import paired_diff_ci
from ril.evaluation.x2_dense import VectorStore, query_key, rank_among, text_hash
from ril.retrieval.bm25_index import BM25Index, BM25Params
from ril.util.machine import hardware

Record = dict[str, Any]
Cell = tuple[str, float, float]
SYSTEMS_BM25 = "bm25"


def cells_of(cfg: Record) -> list[Cell]:
    """Control first, then the variants of the configuration."""
    raw = [cfg["bm25_cells"]["control"], *cfg["bm25_cells"]["variants"]]
    return [(str(t), float(k1), float(b)) for t, k1, b in raw]


def system_names(cfg: Record) -> list[str]:
    """``bm25`` and one fused system per dense store, named ``rrf_<alias>_k<k>``."""
    return [SYSTEMS_BM25] + [f"rrf_{a}_k{d['rrf_k']}" for a, d in cfg["dense"].items()]


def fused_ranks(rb: np.ndarray[Any, Any], rd: np.ndarray[Any, Any], k: int) -> np.ndarray[Any, Any]:
    """1-based ranks by RRF of two rank vectors over the same candidates, ties by the first list."""
    fused = 1.0 / (k + rb) + 1.0 / (k + rd)
    order = np.lexsort((rb, -fused))
    out = np.empty(len(rb), dtype=np.int64)
    out[order] = np.arange(1, len(rb) + 1)
    return out


def run_folder(
    cfg: Record, spec: Record, level: str, data_root: str, enc_root: str, out_dir: str
) -> bool:
    """Score every cell and system on one (folder, level); one JSON file; False if present."""
    name = f"{level}__{spec['dataset']}__{spec['folder']}"
    out = os.path.join(out_dir, f"{name}.json")
    path = folder_path(data_root, level, spec)
    if os.path.exists(out) or not os.path.isdir(path):
        return False
    t0 = time.perf_counter()
    folder = read_folder(path)
    hashes = [text_hash(t) for t in folder.corpus_texts]
    repo_dir = spec["repo"].replace("/", "__")
    dense: dict[str, tuple[np.ndarray[Any, Any], VectorStore, int]] = {}
    for alias, d in cfg["dense"].items():
        edir = os.path.join(enc_root, d["store"])
        mat = VectorStore([os.path.join(edir, f"chunks__{repo_dir}.npz")]).matrix(hashes)
        qs = VectorStore(sorted(glob.glob(os.path.join(edir, "queries__*.npz"))))
        dense[alias] = (mat, qs, int(d["rrf_k"]))
    pos_of = {cid: i for i, cid in enumerate(folder.corpus_ids)}
    n = len(folder.corpus_ids)
    cells = cells_of(cfg)
    query_tokens: dict[str, list[list[str]]] = {}
    for tok in dict.fromkeys(c[0] for c in cells):
        query_tokens[tok] = [TOKENIZERS[tok](q.text) for q in folder.queries]
    doc_tokens: dict[str, list[list[str]]] = {}
    cell_indexes: dict[str, BM25Index] = {}
    for cell in cells:
        if cell[0] not in doc_tokens:
            doc_tokens[cell[0]] = [TOKENIZERS[cell[0]]("\n" + t) for t in folder.corpus_texts]
        cell_indexes[cell_name(cell)] = BM25Index(
            doc_tokens[cell[0]], BM25Params(k1=cell[1], b=cell[2])
        )
    records: list[Record] = []
    for qi, q in enumerate(folder.queries):
        cand = (
            np.arange(n, dtype=np.int64)
            if q.candidates is None
            else np.fromiter(
                sorted({pos_of[c] for c in q.candidates if c in pos_of}), dtype=np.int64
            )
        )
        where = {int(c): i for i, c in enumerate(cand)}
        pos = sorted(pos_of[c] for c in folder.qrels[q.query_id] if c in pos_of)
        pos = [p for p in pos if p in where]
        rd: dict[str, np.ndarray[Any, Any]] = {}
        for alias, (mat, qs, _k) in dense.items():
            qv = qs.matrix([query_key(level, spec["dataset"], spec["folder"], q.query_id)])[0]
            rd[alias] = rank_among(mat @ qv, cand)
        rec: Record = {
            "query_id": q.query_id,
            "n_candidates": int(len(cand)),
            "n_positives": len(folder.qrels[q.query_id]),
            "n_positives_in_candidates": len(pos),
            "cells": {},
        }
        for cell in cells:
            tok_q = query_tokens[cell[0]][qi]
            rb = rank_among(cell_indexes[cell_name(cell)].scores(tok_q), cand)
            sys_ranks = {SYSTEMS_BM25: [int(rb[where[p]]) for p in pos]}
            for alias, (_m, _qs, k) in dense.items():
                rr = fused_ranks(rb, rd[alias], k)
                sys_ranks[f"rrf_{alias}_k{k}"] = [int(rr[where[p]]) for p in pos]
            rec["cells"][cell_name(cell)] = sys_ranks
        records.append(rec)
    os.makedirs(out_dir, exist_ok=True)
    with open(f"{out}.tmp", "w", encoding="utf-8") as handle:
        json.dump(
            {
                "level": level,
                "dataset": spec["dataset"],
                "folder": spec["folder"],
                "role": spec["role"],
                "corpus_chunks": n,
                "seconds": round(time.perf_counter() - t0, 2),
                "hardware": hardware(),
                "records": records,
            },
            handle,
        )
    os.replace(f"{out}.tmp", out)
    return True


def run_all(cfg: Record, data_root: str, enc_root: str, out_dir: str) -> int:
    """Every dev folder and level of the configuration; returns the files written."""
    written = 0
    for spec in cfg["folders"]:
        if spec["role"] != "dev":
            raise ValueError(f"E-A1-FUSED reads development folders only, not {spec['folder']}")
        for level in spec["levels"]:
            written += int(run_folder(cfg, spec, level, data_root, enc_root, out_dir))
    return written


# --------------------------------------------------------------------------- reading


def load_runs(out_dir: str) -> list[Record]:
    """Run files in path order."""
    runs = []
    for path in sorted(glob.glob(os.path.join(out_dir, "*.json"))):
        with open(path, encoding="utf-8") as handle:
            runs.append(json.load(handle))
    return runs


def query_rows(runs: list[Record]) -> list[Record]:
    """One row per (cell, system, level, folder, query), metrics in percent."""
    rows: list[Record] = []
    for run in runs:
        for rec in run["records"]:
            for cname, systems in rec["cells"].items():
                for system, ranks in systems.items():
                    full: list[int | None] = list(ranks)
                    full += [None] * (rec["n_positives"] - len(full))
                    nd, rc = scores_of(full, rec["n_positives"])
                    rows.append(
                        {
                            "cell": cname,
                            "system": system,
                            "level": run["level"],
                            "folder": run["folder"],
                            "query_id": rec["query_id"],
                            "positives": rec["n_positives"],
                            "positives_in_candidates": rec["n_positives_in_candidates"],
                            "ndcg10": round(100 * float(nd), 6),
                            "recall100": round(100 * float(rc), 6),
                        }
                    )
    return sorted(
        rows, key=lambda r: (r["cell"], r["system"], r["level"], r["folder"], r["query_id"])
    )


def _vec(rows: list[Record], cell: str, system: str, level: str | None, metric: str) -> Record:
    sel = [r for r in rows if r["cell"] == cell and r["system"] == system]
    if level is not None:
        sel = [r for r in sel if r["level"] == level]
    return {
        "keys": [(r["level"], r["folder"], r["query_id"]) for r in sel],
        "values": np.array([r[metric] for r in sel], dtype=float) / 100.0,
    }


def difference_table(
    rows: list[Record], cfg: Record, *, seed: int = 0, draws: int = 2000
) -> list[Record]:
    """Per system, variant cell, level and metric: mean, control mean and the paired difference
    with a query-level and a repository-clustered interval (points)."""
    cells = [cell_name(c) for c in cells_of(cfg)]
    control = cells[0]
    out: list[Record] = []
    for system in system_names(cfg):
        for level in ("L2", "L3", None):
            for metric in ("ndcg10", "recall100"):
                base = _vec(rows, control, system, level, metric)
                for cname in cells[1:]:
                    cur = _vec(rows, cname, system, level, metric)
                    if cur["keys"] != base["keys"]:
                        raise ValueError(f"{cname} covers other queries than {control}")
                    groups: dict[str, list[int]] = defaultdict(list)
                    for i, (_lv, folder, _q) in enumerate(cur["keys"]):
                        groups[folder].append(i)
                    qd = paired_diff_ci(cur["values"], base["values"], draws=draws, seed=seed)
                    cd = clustered_diff_ci(
                        [(cur["values"][ix], base["values"][ix]) for ix in groups.values()],
                        draws=draws,
                        seed=seed,
                    )
                    out.append(
                        {
                            "system": system,
                            "level": level or "pooled",
                            "metric": metric,
                            "cell": cname,
                            "control": control,
                            "queries": len(cur["keys"]),
                            "repositories": len(groups),
                            "mean": round(100 * float(cur["values"].mean()), 4),
                            "control_mean": round(100 * float(base["values"].mean()), 4),
                            "diff": round(100 * qd[0], 4),
                            "q_lo": round(100 * qd[1], 4),
                            "q_hi": round(100 * qd[2], 4),
                            "c_lo": round(100 * cd[1], 4),
                            "c_hi": round(100 * cd[2], 4),
                        }
                    )
    return out


def regression_against_stored(
    runs: list[Record], cfg: Record, stored_dir: str, control: str
) -> Record:
    """The control cell's ranks against the stored E-DENSE-FUSION chunk scoring, query by query."""
    keys = {
        "bm25": "bm25",
        **{
            f"rrf_{a}_k{d['rrf_k']}": f"rrf{d['rrf_k']}__{d['store']}"
            for a, d in cfg["dense"].items()
        },
    }
    checked = 0
    mismatched: list[str] = []
    for run in runs:
        path = os.path.join(stored_dir, f"{run['level']}__{run['dataset']}__{run['folder']}.json")
        with open(path, encoding="utf-8") as handle:
            stored = {r["query_id"]: r for r in json.load(handle)["records"]}
        for rec in run["records"]:
            old = stored[rec["query_id"]]
            for system, key in keys.items():
                checked += 1
                if rec["cells"][control][system] != old[key]:
                    mismatched.append(f"{run['level']}/{run['folder']}/{rec['query_id']}/{system}")
    return {
        "checked": checked,
        "mismatched": len(mismatched),
        "examples": mismatched[:5],
        "exact": checked > 0 and not mismatched,
    }
