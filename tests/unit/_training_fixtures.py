"""Synthetic pool, archive, feature table and X2 inputs for the training-stack tests.

Everything is generated: no dataset text. The synthetic issues name the functions they concern, so
a tiny bag-of-words encoder can learn the task in a few updates (the tests check plumbing, not
retrieval quality).
"""

from __future__ import annotations

import csv
import json
import os
import random
from typing import Any

import numpy as np

from ril.retrieval.bm25_index import BM25Index, tokenize
from ril.training import pool_ranks as pr
from ril.training.pool_reader import PoolExample
from tests.unit.test_pool_ranks import _zip_member

WORDS = (
    "parse render config cache token stream socket header cookie session retry timeout encode "
    "decode schema widget layout signal plugin loader archive index merge"
).split()


def _function(repo_i: int, f: int, rng: random.Random) -> tuple[str, str]:
    mod = f % 3
    name = f"{WORDS[f % len(WORDS)]}_{WORDS[(f * 7 + repo_i) % len(WORDS)]}_{f}"
    fid = f"pkg/mod{mod}.py/Klass{f % 2}/{name}" if f % 4 == 0 else f"pkg/mod{mod}.py/{name}"
    body = " ".join(rng.choice(WORDS) for _ in range(6))
    return fid, f"def {name}(x):\n    # {body}\n    return x"


def synthetic_examples(
    repos: int = 3, prs: int = 6, funcs: int = 24, seed: int = 0, owner: str = "own"
) -> list[PoolExample]:
    """Pull requests over ``repos`` repositories; 1-3 positives each; queries name the positives."""
    rng = random.Random(seed)
    out: list[PoolExample] = []
    for r in range(repos):
        table = [_function(r, f, rng) for f in range(funcs)]
        for p in range(prs):
            k = 1 + (p % 3)
            pos = sorted(rng.sample(range(funcs), k))
            names = [table[i][0].split("/")[-1].replace("_", " ") for i in pos]
            query = "Bug: " + " and ".join(names) + " fails with " + rng.choice(WORDS)
            cand = [i for i in range(funcs) if i not in pos]
            out.append(
                PoolExample(
                    instance_id=f"{owner}__repo{r}-{100 + p}",
                    repo=f"{owner}/repo{r}",
                    pr=100 + p,
                    query=query,
                    positive_ids=tuple(table[i][0] for i in pos),
                    positive_texts=tuple(table[i][1] for i in pos),
                    candidate_ids=tuple(table[i][0] for i in cand),
                    candidate_texts=tuple(table[i][1] for i in cand),
                )
            )
    return out


def fake_archive(
    examples: list[PoolExample],
) -> tuple[dict[str, Any], Any]:
    """An in-memory zip of the examples in the pool layout, its listing, and a range fetcher."""
    buf = b""
    members: list[dict[str, Any]] = []
    for ex in sorted(examples, key=lambda e: e.instance_id):
        d = ex.instance_id
        rows = []
        for fid, text in sorted(
            zip(
                ex.positive_ids + ex.candidate_ids,
                ex.positive_texts + ex.candidate_texts,
                strict=True,
            )
        ):
            rows.append(json.dumps({"_id": fid, "title": "", "text": f"{fid}\n{text}"}))
        corpus = "\n".join(rows).encode()
        queries = json.dumps({"_id": d, "text": ex.query, "metadata": {}}).encode()
        qrels = (
            "query-id\tcorpus-id\tscore\n" + "".join(f"{d}\t{p}\t1\n" for p in ex.positive_ids)
        ).encode()
        for name, data in (
            (f"train/python/{d}/corpus.jsonl", corpus),
            (f"train/python/{d}/queries.jsonl", queries),
            (f"train/python/{d}/qrels/test.tsv", qrels),
        ):
            blob, m = _zip_member(name, data, len(buf))
            buf += blob
            members.append(m)
    listing = {"url": "mem://pool", "members": members}

    def fetch(url: str, first: int, last: int) -> bytes:
        return buf[first : last + 1]

    return listing, fetch


def write_feature_table(
    path: str, examples: list[PoolExample], teachers: tuple[str, ...] = ("bm25",), ids: bool = False
) -> None:
    """Feature table in the tracked layout with BM25 ranks (``ids``: also the plain id column)."""
    rows: list[dict[str, Any]] = []
    for ex in examples:
        texts = list(ex.positive_texts) + list(ex.candidate_texts)
        scores = pr.bm25_scores(texts, ex.query)
        ranks = {r["positive"]: r for r in pr.positive_ranks(ex.ids, scores, ex.positive_ids)}
        for p in ex.positive_ids:
            row: dict[str, Any] = {
                "instance_id": ex.instance_id,
                "positive_key": pr.positive_key(p),
            }
            if ids:
                row["positive_id"] = p
            row.update(
                {
                    "repo": ex.repo,
                    "held_out": 0,
                    "stratum": "s0-k",
                    "functions": len(texts),
                    "positives_in_instance": len(ex.positive_ids),
                }
            )
            for t in teachers:
                row[f"rank_{t}"] = ranks[p]["rank"]
            for t in teachers:
                row[f"rank_all_{t}"] = ranks[p]["rank_all"]
            rows.append(row)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def train_config(**over: Any) -> dict[str, Any]:
    """A tiny CPU configuration (every value a test value, not a proposal)."""
    cfg: dict[str, Any] = {
        "exp_id": "t1_test",
        "rq": "rq2",
        "provisional": ["ADR-001", "ADR-002", "ADR-006"],
        "seed": 3,
        "model": {"kind": "tiny", "buckets": 512, "dim": 16, "max_tokens": 64},
        "batch": {"batch_size": 4, "negatives_per_example": 3, "max_positives": 2},
        "negatives": {"name": "random_repo"},
        "loss": {"form": "sum_in_numerator", "normaliser": "batch", "temperature": 0.05},
        "optimizer": {
            "name": "adamw",
            "lr": 0.05,
            "weight_decay": 0.0,
            "warmup_updates": 2,
            "schedule": "linear",
            "grad_clip": 1.0,
        },
        "budget": {"updates": 10},
        "checkpoint": {"every": 4, "keep": 2},
        "arm": {"name": "RAW"},
    }
    for k, v in over.items():
        cfg[k] = v
    return cfg


# --------------------------------------------------------------------------- X2 inputs


def x2_inputs(root: str, repo: str = "dev/repo", n_inst: int = 4, seed: int = 0) -> dict[str, str]:
    """A miniature X2 preparation of one development repository (units, queries, chunks, cache)."""
    from ril.evaluation.e3_prepare import READINGS, write_cache
    from ril.evaluation.x2_dense import append_store, query_key, text_hash

    rng = random.Random(seed)
    repo_dir = repo.replace("/", "__")
    dataset, folder = "SWE-dev", repo_dir
    prep, cache, data_root = (os.path.join(root, x) for x in ("prep", "cache", "data_root"))
    units = [_function(9, f, rng) for f in range(30)]
    texts = [t for _, t in units]
    seen: set[str] = set()
    append_store(os.path.join(prep, "texts_units", f"{repo_dir}.s0.jsonl"), texts, seen)
    append_store(os.path.join(prep, "texts_chunks", f"{repo_dir}.jsonl"), texts, set())
    qrows, qrels, qstore = [], [], []
    for i in range(n_inst):
        inst = f"{repo_dir}-{i}"
        gold = sorted(rng.sample(range(len(units)), 2))
        query = "Issue: " + " ".join(units[g][0].split("/")[-1].replace("_", " ") for g in gold)
        qstore.append(json.dumps({"h": query_key("L2", dataset, folder, inst), "t": query}))
        qrows.append({"_id": inst, "text": query})
        qrels += [{"query_id": inst, "corpus_id": f"c{g}", "score": 1} for g in gold]
        bm = BM25Index(tokenize(t) for t in texts)
        arrays: dict[str, Any] = {
            "scores_L2": np.asarray(bm.scores(tokenize(query)), dtype=np.float64),
            "file_of_unit": np.arange(len(units)) // 5,
            "age_days": np.zeros(len(units)),
        }
        for r in READINGS:
            arrays[f"gold_L2_{r}"] = np.asarray(gold, dtype=np.int32)
        meta = {
            "units": len(units),
            "levels": ["L2"],
            "instance": inst,
            "role": "dev",
            "config_hash": "synthetic",
            "dataset": dataset,
            "folder": folder,
            "repo_id": repo,
        }
        write_cache(os.path.join(cache, f"{inst}.npz"), arrays, meta)
        umeta = {
            "instance": inst,
            "repo_dir": repo_dir,
            "role": "dev",
            "dataset": dataset,
            "folder": folder,
            "levels": ["L2"],
            "units": len(units),
        }
        os.makedirs(os.path.join(prep, "units"), exist_ok=True)
        np.savez_compressed(
            os.path.join(prep, "units", f"{inst}.npz"),
            meta=np.asarray(json.dumps(umeta)),
            hashes_full=np.asarray([text_hash(t) for t in texts], dtype="U40"),
        )
    os.makedirs(os.path.join(prep, "queries"), exist_ok=True)
    with open(os.path.join(prep, "queries", f"L2__{dataset}__{folder}.jsonl"), "w") as handle:
        handle.write("\n".join(qstore) + "\n")
    fdir = os.path.join(data_root, "data", "LEVEL-2", dataset, folder)
    os.makedirs(fdir, exist_ok=True)
    with open(os.path.join(fdir, "corpus.jsonl"), "w") as handle:
        for i, t in enumerate(texts):
            handle.write(json.dumps({"_id": f"c{i}", "text": t}) + "\n")
    with open(os.path.join(fdir, "queries.jsonl"), "w") as handle:
        for q in qrows:
            handle.write(json.dumps(q) + "\n")
    with open(os.path.join(fdir, "qrels.jsonl"), "w") as handle:
        for q in qrels:
            handle.write(json.dumps(q) + "\n")
    e1 = os.path.join(root, "e1.yaml")
    with open(e1, "w") as handle:
        json.dump(
            {
                "bm25": {"k1": 1.5, "b": 0.75},
                "folders": [
                    {
                        "dataset": dataset,
                        "folder": folder,
                        "role": "dev",
                        "repo": repo,
                        "levels": ["L2"],
                        "units": True,
                    }
                ],
            },
            handle,
        )
    return {"prep": prep, "cache": cache, "data_root": data_root, "e1": e1}
