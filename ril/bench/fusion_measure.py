"""Latency of rank fusion, same-file expansion and the recency prior on a repository snapshot.

Implements ``specs/latency_harness.md`` for the stages ``rrf_fusion``, ``same_file_expansion`` and
``recency_prior`` (the rungs of the RQ1 ladder that had no latency row, ``docs/experiments/B.md``
E-RQ1-LADDER and E-FREEZE-AND-LATENCY). Each stage calls the function the ladder itself uses
(``ril.evaluation.x2_eval``, ``ril.evaluation.s1_graph_role``, ``ril.retrieval.recency``), so the
row describes the code that produced the ladder values. What a row covers, and what is prepared
outside the timing:

* ``rrf_fusion``: from the BM25 score vector and the dense score vector of one query to the 100
  best units of the fused ranking: both whole rankings (a full sort each), the reciprocal rank sum
  with ``k`` (100 in the RQ3 contexts and the dev selection, 60 in the RQ2 evaluation; one
  setting is timed, the ``k`` is a scalar and does not change the cost), and the selection;
* ``same_file_expansion``: from a fused ranking (``order``, prepared) to the 50 units of the
  files of the top 5 units, best first (``same_file_by_score``);
* ``recency_prior``: from a fused score vector to the 100 best units after the prior: the prior
  ``exp(-age / tau)`` over every unit (recomputed per call, a snapshot constant that a service
  would cache, so this is an upper bound), the blend ``score / max + lam * prior`` and the full
  sort that gives the ranking.

Inputs. BM25 scores are those of the real index of the snapshot (reference form) for the query of
the query set. Dense scores are stored scores of the untrained encoder on development instances
(a score vector of CodeRankEmbed, 1,024 tokens, per instance), resized to the snapshot's unit
count by drawing stored values with replacement (seeded); the cost of a sort and of a sum depends
on the unit count and the value distribution, not on which unit holds which value (the same
convention as the ``dense_search`` rows at the django scale). Ages are those of the snapshot's own
git history. A ``bm25`` stage is timed in the same run as the regression control.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

from ril.bench.latency_harness import (
    LATENCY_COLUMNS,
    BenchConfig,
    RegressionThreshold,
    StageRegistry,
    append_rows,
    capture_environment,
    run_latency,
)
from ril.bench.retrieval_measure import TOP_K
from ril.config.paths import configs_dir
from ril.evaluation.e3_prepare import snapshot_time, unit_graph_arrays
from ril.evaluation.s1_graph_role import same_file_by_score
from ril.evaluation.x2_eval import positions, rrf_scores
from ril.parsing.build import BuildConfig, build_repository
from ril.retrieval import bm25_index
from ril.retrieval.bm25_index import BM25Index, order_by_score, tokenize
from ril.retrieval.recency import ages_in_days, blend, recency_prior

RRF_K = 100
SEEDS = 5
CAP = 50
LAM = 0.2
TAU_DAYS = 30.0
Arr = np.ndarray[Any, Any]


def dense_pool(paths: list[str], key: str = "dense_L2") -> list[Arr]:
    """Stored dense score vectors (float32), one per file."""
    out: list[Arr] = []
    for p in sorted(paths):
        with np.load(p) as z:
            out.append(np.asarray(z[key], dtype=np.float32))
    if not out:
        raise ValueError("no stored dense score file found")
    return out


def resize_scores(pool: list[Arr], n: int, rng: np.random.Generator) -> Arr:
    """A score vector of length ``n`` made of stored values drawn with replacement."""
    src = pool[int(rng.integers(len(pool)))]
    return np.asarray(src[rng.integers(0, len(src), size=n)], dtype=np.float64)


class FusionStages:
    """A snapshot's BM25 index, file map and ages, and the three stage functions over them."""

    def __init__(self, root: str, repo_id: str, dense_files: list[str]) -> None:
        result = build_repository(root, BuildConfig(repo_id=repo_id, seed=0))
        units, _, _, _ = unit_graph_arrays(result)
        self.n = len(units)
        files = sorted({u.file for u in units})
        idx = {f: i for i, f in enumerate(files)}
        self.file_of_unit = np.asarray([idx[u.file] for u in units], dtype=np.int32)
        self.age_days = ages_in_days([u.last_modified for u in units], snapshot_time(root))
        self.with_age = int(np.isfinite(self.age_days).sum())
        self.index = BM25Index(tokenize(u.source) for u in units)
        self.pool = dense_pool(dense_files)
        self.cache: dict[str, tuple[Arr, Arr, Arr, Arr]] = {}

    def reset(self) -> None:
        bm25_index._STEM_CACHE.clear()

    def prepare(self, queries: list[str], seed: int) -> None:
        """BM25 scores, dense scores, fused scores and fused order of every query (not timed)."""
        rng = np.random.default_rng(seed)
        for q in queries:
            bm = self.index.scores(tokenize(q))
            dense = resize_scores(self.pool, self.n, rng)
            fused = rrf_scores([positions(bm), positions(dense)], RRF_K)
            self.cache[q] = (bm, dense, fused, order_by_score(fused))

    def bm25(self, query: str) -> Any:
        return self.index.top_k(tokenize(query), TOP_K)

    def rrf_fusion(self, query: str) -> Any:
        bm, dense, _, _ = self.cache[query]
        fused = rrf_scores([positions(bm), positions(dense)], RRF_K)
        return order_by_score(fused)[:TOP_K]

    def same_file_expansion(self, query: str) -> Any:
        _, _, _, order = self.cache[query]
        seeds = [int(u) for u in order[:SEEDS]]
        return same_file_by_score(self.file_of_unit, order, seeds, CAP)

    def recency_prior(self, query: str) -> Any:
        _, _, fused, _ = self.cache[query]
        prior = recency_prior(self.age_days, TAU_DAYS)
        return order_by_score(blend(fused, prior, LAM))[:TOP_K]


def registry_for(stages: FusionStages) -> StageRegistry:
    """The three new stages and the BM25 regression control."""
    reg = StageRegistry()
    reg.register("bm25", stages.bm25, reset=stages.reset)
    reg.register("rrf_fusion", stages.rrf_fusion)
    reg.register("same_file_expansion", stages.same_file_expansion)
    reg.register("recency_prior", stages.recency_prior)
    return reg


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("repo_dir")
    ap.add_argument("repo_id")
    ap.add_argument("label", help="query set retrieval-<label>-v1 (the file must exist)")
    ap.add_argument("--dense-glob", required=True, help="glob of stored dense score .npz files")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--log", default="results/latency/latency_log.csv")
    ap.add_argument("--no-append", action="store_true")
    args = ap.parse_args(argv)
    qfile = configs_dir() / "bench" / "query_sets" / f"retrieval-{args.label}-v1.txt"
    queries = qfile.read_text(encoding="utf-8").splitlines()
    stages = FusionStages(args.repo_dir, args.repo_id, glob.glob(args.dense_glob))
    stages.prepare(queries, args.seed)
    config = BenchConfig(
        seed=args.seed,
        query_set=f"fusion-{args.label}-v1",
        warmup_n=5,
        repeats=3,
        throughput_repeats=1,
        regression=RegressionThreshold(rel_threshold=0.5, abs_floor_ms=0.5),
    )
    env = capture_environment(config.config_hash())
    rows = run_latency(registry_for(stages), config, queries, env)
    if not args.no_append:
        append_rows(Path(args.log), LATENCY_COLUMNS, rows)
    summary = {
        "label": args.label,
        "units": stages.n,
        "units_with_age": stages.with_age,
        "dense_vectors": len(stages.pool),
        "query_set_sha256": hashlib.sha256(qfile.read_bytes()).hexdigest(),
        "rows": [
            {k: r[k] for k in ("stage", "cache_state", "p50_ms", "p95_ms", "p99_ms", "n")}
            for r in rows
        ],
    }
    sys.stdout.write(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
