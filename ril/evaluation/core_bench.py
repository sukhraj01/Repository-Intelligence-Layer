"""CORE-Bench folder loader and chunk-level BM25 evaluation under the benchmark's protocol.

Implements ``docs/06_core_bench.md`` and the protocol read from the released toolkit
(``knowledge/datasets/core_bench.md`` "Evaluation protocol"): a folder is one evaluation split;
BM25 is built over the whole folder corpus; every query is scored against the whole folder; the
ranking is cut to the first ``prefilter_k`` (10,000) documents and *then* restricted to the
query's own candidate list (``filtered_corpus_id``); metrics use binary gain and are averaged over
queries. Queries without a qrel are dropped (as the toolkit does).

A second reading, ``filter_first``, ranks only the query's own candidates and so removes the
truncation; both ranks of every positive are recorded so that the difference between the two
readings can be measured. Rank ties are broken by corpus order; the best and worst rank a tie
could take are recorded as well.

Records hold ranks, scores and ids only (never chunk text), which keeps the licence rule
(non-commercial share-alike data: commit counts and derived tables only).

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import numpy as np

from ril.retrieval.bm25_index import BM25Index, BM25Params, tokenize

PROTOCOL_PREFILTER_K = 10_000
"""``top_k`` of the reference run (clamped to the corpus size)."""

Record = dict[str, Any]


@dataclass(frozen=True)
class CoreBenchQuery:
    """One query of a folder: its text and its candidate list (``None`` = the whole corpus)."""

    query_id: str
    text: str
    candidates: tuple[str, ...] | None


@dataclass
class CoreBenchFolder:
    """A loaded folder: corpus in file order, queries that have qrels, positives per query."""

    path: str
    corpus_ids: list[str]
    corpus_texts: list[str]
    queries: list[CoreBenchQuery]
    qrels: dict[str, set[str]]
    dropped_queries: int


def _jsonl(path: str) -> Iterator[dict[str, Any]]:
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                if isinstance(row, dict):
                    yield row


def read_qrels(path: str) -> dict[str, set[str]]:
    """``{query id: positive corpus ids}``; rows with a score of 0 or less are not positives."""
    out: dict[str, set[str]] = {}
    for row in _jsonl(path):
        if float(row.get("score", 1)) > 0:
            out.setdefault(str(row["query_id"]), set()).add(str(row["corpus_id"]))
    return out


def read_folder(path: str) -> CoreBenchFolder:
    """Load ``corpus.jsonl``, ``queries.jsonl`` and ``qrels.jsonl`` of a folder."""
    ids: list[str] = []
    texts: list[str] = []
    for row in _jsonl(os.path.join(path, "corpus.jsonl")):
        ids.append(str(row["_id"]))
        texts.append(str(row["text"]))
    qrels = read_qrels(os.path.join(path, "qrels.jsonl"))
    queries: list[CoreBenchQuery] = []
    dropped = 0
    for row in _jsonl(os.path.join(path, "queries.jsonl")):
        qid = str(row["_id"])
        if qid not in qrels:
            dropped += 1
            continue
        cand = row.get("filtered_corpus_id")
        queries.append(
            CoreBenchQuery(qid, str(row["text"]), None if cand is None else tuple(map(str, cand)))
        )
    return CoreBenchFolder(path, ids, texts, queries, qrels, dropped)


def build_index(folder: CoreBenchFolder, params: BM25Params | None = None) -> BM25Index:
    """BM25 over the folder corpus (the reference joins an empty title to the text)."""
    return BM25Index((tokenize("\n" + t) for t in folder.corpus_texts), params)


def rank_positives(
    scores: np.ndarray[Any, np.dtype[np.float64]],
    candidates: np.ndarray[Any, np.dtype[np.int64]] | None,
    positives: list[int],
    prefilter_k: int = PROTOCOL_PREFILTER_K,
) -> dict[int, Record]:
    """Ranks of the positive documents under the protocol and under filter-first.

    ``rank`` is 1-based among the query's candidates; ``protocol`` is ``None`` when the document
    lay beyond the first ``prefilter_k`` of the whole-folder ranking. ``lo``/``hi`` are the best
    and worst rank a tie with equal scores could take (filter-first).
    """
    n = len(scores)
    k = min(prefilter_k, n)
    cand_scores = scores if candidates is None else scores[candidates]
    all_idx = np.arange(n, dtype=np.int64)
    cand_idx = all_idx if candidates is None else candidates
    out: dict[int, Record] = {}
    for p in positives:
        s = scores[p]
        better = int((cand_scores > s).sum())
        tied_before = int(((cand_scores == s) & (cand_idx < p)).sum())
        tied_all = int((cand_scores == s).sum())
        in_cand = candidates is None or bool((cand_idx == p).any())
        rank = better + tied_before + 1
        g_rank = int((scores > s).sum()) + int(((scores == s) & (all_idx < p)).sum()) + 1
        out[p] = {
            "in_candidates": in_cand,
            "score": float(s),
            "filter_first": rank if in_cand else None,
            "lo": better + 1 if in_cand else None,
            "hi": better + tied_all if in_cand else None,
            "protocol": rank if (in_cand and g_rank <= k) else None,
            "folder_rank": g_rank,
        }
    return out


def evaluate_folder(
    folder: CoreBenchFolder,
    params: BM25Params | None = None,
    *,
    prefilter_k: int = PROTOCOL_PREFILTER_K,
) -> list[Record]:
    """Per-query records: the rank of every positive under both readings (no text)."""
    index = build_index(folder, params)
    pos_of = {cid: i for i, cid in enumerate(folder.corpus_ids)}
    out: list[Record] = []
    for q in folder.queries:
        q_tokens = tokenize(q.text)
        scores = index.scores(q_tokens)
        cand = (
            None
            if q.candidates is None
            else np.fromiter((pos_of[c] for c in q.candidates if c in pos_of), dtype=np.int64)
        )
        pos = sorted(pos_of[c] for c in folder.qrels[q.query_id] if c in pos_of)
        ranks = rank_positives(scores, cand, pos, prefilter_k)
        out.append(
            {
                "query_id": q.query_id,
                "n_candidates": len(folder.corpus_ids) if cand is None else int(len(cand)),
                "n_positives": len(folder.qrels[q.query_id]),
                "n_positives_in_corpus": len(pos),
                "query_tokens": len(q_tokens),
                "positives": {folder.corpus_ids[p]: r for p, r in ranks.items()},
            }
        )
    return out
