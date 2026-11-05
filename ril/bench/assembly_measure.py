"""Latency of the real ``assemble`` stage and a BM25-only ``end_to_end`` on a repository snapshot.

Implements ``specs/latency_harness.md`` for the stages ``assemble`` and ``end_to_end``. Same
queries as ``ril.bench.retrieval_measure`` (``retrieval-<label>-v1``, copied under the id
``assembly-<label>-b<budget>-v1`` because rows are comparable only within one id). A row describes
a stage on one machine, one snapshot and one query set, nothing else:

* ``bm25``: tokenise the query, score every unit, select the 200 best (the same selection as
  ``retrieval_measure``, with 200 instead of 100 candidates);
* ``assemble``: the 200 candidates of the query (prepared outside the timing) turned into the
  context under the budget (``ril.assembly.assemble``, class units in header form, approximate
  tokenizer, unit cap ``DEFAULT_MAX_UNIT_TOKENS``);
* ``end_to_end``: ``bm25`` followed by candidate construction and ``assemble``, as one call. It is
  composed of the two real stages only; there is no dense search, fusion or rerank in it.

Cold means the BM25 stemmer cache is cleared before every call; assembly keeps no cache.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from ril.assembly.assemble import Candidate, UnitText, assemble, snapshot_of
from ril.assembly.config import DEFAULT_MAX_UNIT_TOKENS, AssemblyConfig
from ril.assembly.measure import snapshot_units
from ril.assembly.tokens import ApproxTokenizer
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
from ril.retrieval import bm25_index
from ril.retrieval.bm25_index import BM25Index, tokenize

CANDIDATES = 200
DEFAULT_BUDGET = 8000


class Stages:
    """A snapshot's BM25 index and assembly snapshot, and the stage functions over them."""

    def __init__(self, root: str, repo_id: str, budget: int) -> None:
        from ril.parsing.build import BuildConfig, build_repository

        result = build_repository(root, BuildConfig(repo_id=repo_id, with_history=False, seed=0))
        units = sorted(result.parsed.units, key=lambda u: u.id)  # index form: class source full
        self.ids = [u.id for u in units]
        self.index = BM25Index(tokenize(u.source) for u in units)
        shown: list[UnitText] = snapshot_units(root, repo_id)  # display form: class header
        if [u.unit_id for u in shown] != self.ids:
            raise RuntimeError("index and display forms disagree on the units")
        self.snapshot = snapshot_of(shown)
        self.tok = ApproxTokenizer()
        self.config = AssemblyConfig(budget=budget, max_unit_tokens=DEFAULT_MAX_UNIT_TOKENS)
        self.prepared: dict[str, list[Candidate]] = {}

    def reset(self) -> None:
        bm25_index._STEM_CACHE.clear()

    def bm25(self, query: str) -> Any:
        return self.index.top_k(tokenize(query), CANDIDATES)

    def candidates(self, order: Any, scores: Any = None) -> list[Candidate]:
        return [Candidate(self.ids[int(i)], 0.0, ("bm25",)) for i in order]

    def prepare(self, queries: list[str]) -> None:
        """Candidates of each query, outside the timing of the ``assemble`` stage."""
        for q in queries:
            self.prepared[q] = self.candidates(self.bm25(q))

    def assemble(self, query: str) -> Any:
        return assemble(self.prepared[query], self.snapshot, self.config, self.tok)

    def end_to_end(self, query: str) -> Any:
        return assemble(self.candidates(self.bm25(query)), self.snapshot, self.config, self.tok)


def registry_for(stages: Stages) -> StageRegistry:
    """The two real stages and the composed end-to-end call over one snapshot."""
    reg = StageRegistry()
    reg.register("bm25", stages.bm25, reset=stages.reset)
    reg.register("assemble", stages.assemble, reset=stages.reset)
    reg.register("end_to_end", stages.end_to_end, reset=stages.reset)
    return reg


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("repo_dir")
    ap.add_argument("repo_id")
    ap.add_argument("label")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--log", default="results/latency/latency_log.csv")
    ap.add_argument("--no-append", action="store_true")
    args = ap.parse_args(argv)
    stages = Stages(args.repo_dir, args.repo_id, args.budget)
    qdir = configs_dir() / "bench" / "query_sets"
    qid = f"assembly-{args.label}-b{args.budget}-v1"
    qfile = qdir / f"{qid}.txt"
    if not qfile.exists():
        qfile.write_text((qdir / f"retrieval-{args.label}-v1.txt").read_text(encoding="utf-8"))
    queries = qfile.read_text(encoding="utf-8").splitlines()
    stages.prepare(queries)
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
    sample = stages.assemble(queries[0]).manifest
    summary = {
        "label": args.label,
        "units": len(stages.ids),
        "budget": args.budget,
        "example_tokens": sample.total_tokens,
        "example_units": len(sample.entries),
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
