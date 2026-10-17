"""Latency of the real BM25 stage and the real graph-expansion stages on a repository snapshot.

Implements ``specs/latency_harness.md`` for the stages ``bm25``, ``graph_expansion``,
``graph_expand_1hop`` and ``graph_expand_2hop`` with a real index (units of one snapshot, module
units included, reference tokenisation) and real hop-decay expansion
(``ril.retrieval.graph_expansion``: every edge family, gamma 0.5, at most 50 units, top-3 BM25
seeds). A row describes a stage on one machine and one query set, nothing else:

* ``bm25``: tokenise the query, score every unit, select the 100 best;
* ``graph_expand_1hop`` / ``graph_expand_2hop``: breadth-first expansion from the three seeds the
  query's BM25 ranking gives (seeds are prepared outside the timing), hop-decay scoring and
  selection of at most 50 units;
* ``graph_expansion``: ``bm25`` followed by the 2-hop expansion, as one call.

The query set is built from the repository's own identifiers (words of the qualified names and
parameter names of 200 seeded units), so it contains no benchmark text. Cold means the stage's own
cache (the stemmer cache) is cleared before every call; the expansion keeps no cache.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
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
from ril.config.paths import configs_dir
from ril.evaluation.e3_eval import FAMILIES
from ril.evaluation.e3_prepare import unit_graph_arrays
from ril.parsing.build import BuildConfig, build_repository
from ril.retrieval import bm25_index
from ril.retrieval.bm25_index import BM25Index, order_by_score, tokenize
from ril.retrieval.graph_expansion import (
    FamilyGraph,
    bfs_distances,
    combine_uniform,
    select_expansion,
)

N_QUERIES = 200
TOP_K = 100
SEEDS = 3
GAMMA = 0.5
CAP = 50
_WORDS = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+")


def words_of(identifier: str) -> list[str]:
    """Lower-case word pieces of an identifier (``make_response`` -> make, response)."""
    return [w.lower() for w in _WORDS.findall(identifier)]


def build_queries(unit_names: list[tuple[str, list[str]]], n: int, seed: int) -> list[str]:
    """``n`` queries of 4 to 8 identifier words from seeded units (name pieces, then parameters)."""
    rng = random.Random(seed)
    pool = [(q, ps) for q, ps in unit_names if len(words_of(q)) >= 2]
    out: list[str] = []
    while len(out) < n:
        q, ps = rng.choice(pool)
        parts = words_of(q) + [w for p in ps for w in words_of(p)]
        k = min(len(parts), rng.randint(4, 8))
        text = " ".join(parts[:k])
        if len(text.split()) >= 3:
            out.append(text)
    return out


class Stages:
    """A snapshot's BM25 index and graph, and the stage functions over them."""

    def __init__(self, root: str, repo_id: str) -> None:
        result = build_repository(root, BuildConfig(repo_id=repo_id, seed=0))
        units, _, _, arrays = unit_graph_arrays(result)
        self.n = len(units)
        self.index = BM25Index(tokenize(u.source) for u in units)
        pairs = {
            k[6:]: [(int(a), int(b)) for a, b in v]
            for k, v in arrays.items()
            if k.startswith("pairs_")
        }
        self.graph = FamilyGraph.from_pairs(self.n, pairs)
        self.names = [(u.qualified_name, _param_names(u.signature)) for u in units]
        self.seed_cache: dict[str, tuple[list[int], list[float], Any]] = {}

    def reset(self) -> None:
        bm25_index._STEM_CACHE.clear()

    def bm25(self, query: str) -> Any:
        return self.index.top_k(tokenize(query), TOP_K)

    def prepare_seeds(self, queries: list[str]) -> None:
        """Seeds and positions of each query (outside the timing of the expansion stages)."""
        for q in queries:
            scores = self.index.scores(tokenize(q))
            order = order_by_score(scores)
            pos = np.empty(self.n, dtype=np.int64)
            pos[order] = np.arange(self.n)
            seeds = [int(u) for u in order[:SEEDS] if scores[u] > 0]
            top = float(scores[order[0]]) if self.n else 1.0
            self.seed_cache[q] = (seeds, [float(scores[u]) / top for u in seeds], pos)

    def expand(self, query: str, hops: int) -> Any:
        seeds, snorm, pos = self.seed_cache[query]
        dists = [bfs_distances(self.graph, FAMILIES, s, hops) for s in seeds]
        g = combine_uniform(dists, snorm, GAMMA, hops)
        return select_expansion(g, seeds, pos, self.n, CAP)

    def end_to_end(self, query: str) -> Any:
        scores = self.index.scores(tokenize(query))
        top = float(scores.max()) if self.n else 1.0
        order = order_by_score(scores)
        pos = np.empty(self.n, dtype=np.int64)
        pos[order] = np.arange(self.n)
        seeds = [int(u) for u in order[:SEEDS] if scores[u] > 0]
        snorm = [float(scores[u]) / top for u in seeds]
        dists = [bfs_distances(self.graph, FAMILIES, s, 2) for s in seeds]
        return select_expansion(combine_uniform(dists, snorm, GAMMA, 2), seeds, pos, self.n, CAP)


def _param_names(signature: str) -> list[str]:
    inner = signature[signature.find("(") + 1 : signature.rfind(")")] if "(" in signature else ""
    names = []
    for part in inner.split(","):
        token = part.strip().lstrip("*").split(":")[0].split("=")[0].strip()
        if token.isidentifier() and token not in ("self", "cls"):
            names.append(token)
    return names


def registry_for(stages: Stages) -> StageRegistry:
    """The four real stages over one snapshot."""
    reg = StageRegistry()
    reg.register("bm25", stages.bm25, reset=stages.reset)
    reg.register("graph_expand_1hop", lambda q: stages.expand(q, 1), reset=stages.reset)
    reg.register("graph_expand_2hop", lambda q: stages.expand(q, 2), reset=stages.reset)
    reg.register("graph_expansion", stages.end_to_end, reset=stages.reset)
    return reg


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("repo_dir")
    ap.add_argument("repo_id")
    ap.add_argument("label")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--log", default="results/latency/latency_log.csv")
    ap.add_argument("--no-append", action="store_true")
    args = ap.parse_args(argv)
    stages = Stages(args.repo_dir, args.repo_id)
    queries = build_queries(stages.names, N_QUERIES, args.seed)
    qdir = configs_dir() / "bench" / "query_sets"
    qid = f"retrieval-{args.label}-v1"
    qfile = qdir / f"{qid}.txt"
    if not qfile.exists():
        qfile.write_text("\n".join(queries) + "\n", encoding="utf-8")
    queries = qfile.read_text(encoding="utf-8").splitlines()
    stages.prepare_seeds(queries)
    config = BenchConfig(
        seed=args.seed,
        query_set=qid,
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
