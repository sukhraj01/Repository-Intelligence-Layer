"""BM25 tokenisation and k1/b on the CORE-Bench development folders, chunk level (session A1).

The development-set selection of ``docs/experiments/A.md`` section A1-DEV, under the rule fixed in
``configs/experiments/a_bm25_dev.yaml`` before any run. Each cell is a tokenizer and a (k1, b):

* ``ref``           reference tokenisation (``ril.retrieval.bm25_index.tokenize``), the index of E1
* ``split``         identifiers split, whole identifier kept (``tokenize_code``)
* ``split_noorig``  identifiers split, whole identifier dropped

Documents are tokenised as the reference does (an empty title joined to the chunk text) and the
query with the same tokenizer as the documents. Ranking and the two readings (protocol and
filter-first) are those of ``ril.evaluation.core_bench``; the records have the format of the E1
chunk runs, so ``ril.analysis.e1_tables`` reads them. ``ref`` at k1 1.5 / b 0.75 is the E1 run and
must reproduce it exactly (the regression control).

A folder is read and tokenised once per tokenizer; every (k1, b) cell of that tokenizer builds its
index from the same token lists. One JSON file per (folder, level, cell); a finished file with the
same configuration hash is not redone. Records hold ids, ranks and timings, never text.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections import defaultdict
from collections.abc import Callable
from typing import Any

import numpy as np

from ril.analysis.e1_tables import chunk_query_rows, reading_ranks, scores_of
from ril.analysis.rq1_docstring_pilot import clustered_diff_ci
from ril.bench.latency_harness import percentile
from ril.evaluation.core_bench import rank_positives, read_folder
from ril.evaluation.metrics import mean_ci, paired_diff_ci
from ril.retrieval.bm25_index import BM25Index, BM25Params, tokenize, tokenize_code
from ril.util.machine import hardware

Record = dict[str, Any]
Cell = tuple[str, float, float]
LEVEL_DIR = {"L2": "LEVEL-2", "L3": "LEVEL-3"}
DEFAULT_K1_B = (1.5, 0.75)

TOKENIZERS: dict[str, Callable[[str], list[str]]] = {
    "ref": tokenize,
    "split": tokenize_code,
    "split_noorig": lambda text: tokenize_code(text, keep_original=False),
}


def cell_name(cell: Cell) -> str:
    tok, k1, b = cell
    return f"{tok}_k1_{k1}_b_{b}"


def stage_cells(cfg: Record, stage: str, tokenizer: str | None = None) -> list[Cell]:
    """Cells of stage 1 (tokenizers at the default) or stage 2 (the grid on one tokenizer)."""
    if stage == "stage1":
        s1 = cfg["stage1"]
        return [(t, float(s1["k1"]), float(s1["b"])) for t in s1["tokenizers"]]
    if tokenizer is None:
        raise ValueError("stage 2 needs the tokenizer chosen in stage 1")
    s2 = cfg["stage2"]
    return [(tokenizer, float(k1), float(b)) for k1 in s2["k1"] for b in s2["b"]]


def config_hash(cfg: Record) -> str:
    """SHA-256 prefix of everything that changes a record (folders, roles, prefilter, metrics)."""
    keep = {k: cfg[k] for k in ("folders", "prefilter_k", "metrics", "bm25") if k in cfg}
    return hashlib.sha256(json.dumps(keep, sort_keys=True).encode()).hexdigest()[:12]


def _out_path(out_dir: str, spec: Record, level: str, cell: Cell) -> str:
    name = f"{level}__{spec['dataset']}__{spec['folder']}.json"
    return os.path.join(out_dir, cell_name(cell), name)


def _current(path: str, chash: str) -> bool:
    if not os.path.exists(path):
        return False
    with open(path, encoding="utf-8") as handle:
        return bool(json.load(handle).get("config_hash") == chash)


def run_cells(
    cfg: Record, data_root: str, out_dir: str, cells: list[Cell], *, only: str | None = None
) -> int:
    """Run every cell on every (dev folder, level); returns the number of files written."""
    chash = config_hash(cfg)
    k = int(cfg["prefilter_k"])
    written = 0
    for spec in cfg["folders"]:
        if spec["role"] != "dev":
            raise ValueError(f"A1-DEV reads development folders only, not {spec['folder']}")
        if only is not None and spec["folder"] != only:
            continue
        for level in spec["levels"]:
            path = os.path.join(
                data_root, "data", LEVEL_DIR[level], spec["dataset"], spec["folder"]
            )
            todo = [c for c in cells if not _current(_out_path(out_dir, spec, level, c), chash)]
            if not todo or not os.path.isdir(path):
                continue
            written += _run_folder(path, spec, level, todo, out_dir, chash, k)
    return written


def _run_folder(
    path: str, spec: Record, level: str, cells: list[Cell], out_dir: str, chash: str, k: int
) -> int:
    t0 = time.perf_counter()
    folder = read_folder(path)
    load_s = time.perf_counter() - t0
    pos_of = {cid: i for i, cid in enumerate(folder.corpus_ids)}
    by_tok: dict[str, list[Cell]] = defaultdict(list)
    for c in cells:
        by_tok[c[0]].append(c)
    written = 0
    for tok, tok_cells in by_tok.items():
        tokenizer = TOKENIZERS[tok]
        t0 = time.perf_counter()
        docs = [tokenizer("\n" + t) for t in folder.corpus_texts]
        tokenize_s = time.perf_counter() - t0
        queries = [(q, tokenizer(q.text)) for q in folder.queries]
        for cell in tok_cells:
            t0 = time.perf_counter()
            index = BM25Index(docs, BM25Params(k1=cell[1], b=cell[2]))
            build_s = time.perf_counter() - t0
            records, query_ms = [], []
            for q, q_tokens in queries:
                t0 = time.perf_counter()
                scores = index.scores(q_tokens)
                query_ms.append(1000 * (time.perf_counter() - t0))
                cand = (
                    None
                    if q.candidates is None
                    else np.fromiter(
                        (pos_of[c] for c in q.candidates if c in pos_of), dtype=np.int64
                    )
                )
                pos = sorted(pos_of[c] for c in folder.qrels[q.query_id] if c in pos_of)
                ranks = rank_positives(scores, cand, pos, k)
                records.append(
                    {
                        "query_id": q.query_id,
                        "n_candidates": len(folder.corpus_ids) if cand is None else int(len(cand)),
                        "n_positives": len(folder.qrels[q.query_id]),
                        "n_positives_in_corpus": len(pos),
                        "query_tokens": len(q_tokens),
                        "positives": {folder.corpus_ids[p]: r for p, r in ranks.items()},
                    }
                )
            out = _out_path(out_dir, spec, level, cell)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "config_hash": chash,
                        "cell": cell_name(cell),
                        "tokenizer": tok,
                        "k1": cell[1],
                        "b": cell[2],
                        "level": level,
                        "dataset": spec["dataset"],
                        "folder": spec["folder"],
                        "role": spec["role"],
                        "corpus_chunks": len(folder.corpus_ids),
                        "corpus_tokens": int(sum(len(d) for d in docs)),
                        "queries": len(folder.queries),
                        "load_seconds": round(load_s, 3),
                        "tokenize_seconds": round(tokenize_s, 3),
                        "build_seconds": round(build_s, 3),
                        "query_ms": [round(x, 3) for x in query_ms],
                        "hardware": hardware(),
                        "records": records,
                    },
                    handle,
                )
            written += 1
    return written


# --------------------------------------------------------------------------- reading


def load_cell(out_dir: str, cell: Cell) -> list[Record]:
    """The run files of one cell (one per folder and level)."""
    sub = os.path.join(out_dir, cell_name(cell))
    if not os.path.isdir(sub):
        return []
    runs = []
    for name in sorted(os.listdir(sub)):
        with open(os.path.join(sub, name), encoding="utf-8") as handle:
            runs.append(json.load(handle))
    return runs


def _query_vectors(runs: list[Record]) -> tuple[list[tuple[str, str, str]], np.ndarray, np.ndarray]:
    """``(level, folder, query) keys``, nDCG@10 and Recall@100 per query, protocol reading."""
    rows = sorted(chunk_query_rows(runs), key=lambda r: (r["level"], r["folder"], r["query_id"]))
    sc = [scores_of(reading_ranks(r, "protocol"), r["n_positives"]) for r in rows]
    keys = [(r["level"], r["folder"], r["query_id"]) for r in rows]
    return keys, np.array([s[0] for s in sc]), np.array([s[1] for s in sc])


def _by_repository(keys: list[tuple[str, str, str]], values: np.ndarray) -> dict[str, np.ndarray]:
    groups: dict[str, list[float]] = defaultdict(list)
    for (_level, folder, _q), v in zip(keys, values, strict=True):
        groups[folder].append(float(v))
    return {f: np.array(v) for f, v in sorted(groups.items())}


def summarise_cells(
    out_dir: str, cells: list[Cell], baseline: Cell, *, seed: int = 0, draws: int = 2000
) -> list[Record]:
    """One row per cell: pooled and per-level metrics, paired differences, cost and latency."""
    base_runs = load_cell(out_dir, baseline)
    base_keys, base_nd, _ = _query_vectors(base_runs)
    rows = []
    for cell in cells:
        runs = load_cell(out_dir, cell)
        if not runs:
            continue
        keys, nd, rc = _query_vectors(runs)
        if keys != base_keys:
            raise ValueError(f"{cell_name(cell)} covers other queries than {cell_name(baseline)}")
        m, lo, hi = mean_ci(nd, draws=draws, seed=seed)
        d = paired_diff_ci(nd, base_nd, draws=draws, seed=seed)
        a, b = _by_repository(keys, nd), _by_repository(keys, base_nd)
        cd = clustered_diff_ci([(a[f], b[f]) for f in a], draws=draws, seed=seed)
        level = {lv: [i for i, k in enumerate(keys) if k[0] == lv] for lv in ("L2", "L3")}
        query_ms = [x for r in runs for x in r["query_ms"]]
        chunks = sum(r["corpus_chunks"] for r in runs)
        rows.append(
            {
                "cell": cell_name(cell),
                "tokenizer": cell[0],
                "k1": cell[1],
                "b": cell[2],
                "queries": len(keys),
                "repositories": len(a),
                "ndcg10": round(100 * m, 4),
                "ndcg10_lo": round(100 * lo, 4),
                "ndcg10_hi": round(100 * hi, 4),
                "recall100": round(100 * float(rc.mean()), 4),
                **{
                    f"ndcg10_{lv}": round(100 * float(nd[ix].mean()), 4) if ix else None
                    for lv, ix in level.items()
                },
                **{
                    f"recall100_{lv}": round(100 * float(rc[ix].mean()), 4) if ix else None
                    for lv, ix in level.items()
                },
                "diff_vs_baseline": round(100 * d[0], 4),
                "diff_lo": round(100 * d[1], 4),
                "diff_hi": round(100 * d[2], 4),
                "clustered_lo": round(100 * cd[1], 4),
                "clustered_hi": round(100 * cd[2], 4),
                "tokenize_chunks_per_s": round(
                    chunks / max(sum(r["tokenize_seconds"] for r in runs), 1e-9)
                ),
                "build_chunks_per_s": round(
                    chunks / max(sum(r["build_seconds"] for r in runs), 1e-9)
                ),
                **{f"query_ms_p{p}": round(percentile(query_ms, p), 3) for p in (50, 95, 99)},
            }
        )
    return rows


def regression_check(
    out_dir: str, folders: list[str], expected_ndcg10: float, expected_queries: int
) -> Record:
    """``ref`` at the default on the E1 dev folders against the stored E1 dev sweep row."""
    runs = [r for r in load_cell(out_dir, ("ref", *DEFAULT_K1_B)) if r["folder"] in folders]
    keys, nd, _ = _query_vectors(runs)
    got = round(100 * float(nd.mean()), 4) if len(keys) else None
    return {
        "folders": sorted(folders),
        "queries": len(keys),
        "ndcg10": got,
        "expected_queries": expected_queries,
        "expected_ndcg10": expected_ndcg10,
        "exact": len(keys) == expected_queries and got == expected_ndcg10,
    }


def choose(rows: list[Record], baseline: str) -> Record:
    """The selection rule of the configuration: best criterion, adopted only if its clustered
    interval against the baseline lies above 0."""
    best = max(rows, key=lambda r: r["ndcg10"])
    adopt = best["cell"] != baseline and best["clustered_lo"] > 0
    return {
        "best": best["cell"],
        "adopted": best["cell"] if adopt else baseline,
        "reason": "clustered interval above 0" if adopt else "baseline kept (rule not met)",
    }
