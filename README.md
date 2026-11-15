# Repository Intelligence Layer (RIL)

A repository-level code retrieval layer for LLM coding agents, **plus** a controlled study of
whether the retriever's *training supervision* affects whether the agent actually resolves the
issue.


## Status

The design is fixed (Master Project Document rev 16, 2026-10-11), the apparatus is built and the
experiments have been run. Current state and open items are in `PROJECT_STATE.md`; every measured
number is a row of `RESULTS.md` (or `results/ledger_a.md`) with its run log in `results/logs/`. The
full report is `reports/final/final_report.tex`; a two-page version is `reports/short/short_report.tex`.
To see the retrieval layer run on one real issue, use `make demo` (`docs/DEMO.md`).

**What exists**

- Repository parser and typed graph (contain, import, invoke, inherit, override; tests and
  configures built but off by default), with an incremental updater (`ril/parsing/`).
- BM25, a dense encoder over a flat exact index, rank fusion, same-file and graph expansion, and a
  recency prior (`ril/retrieval/`); context assembly under a token budget (`ril/assembly/`).
- CORE-Bench loaders and metrics that reproduce the published BM25 rows, the RQ2 training stack
  (pool reader, negative policies, the three arm hooks, budget accounting), the agent driver and
  the executable evaluation of the 377-instance subset (`ril/evaluation/`, `ril/training/`,
  `ril/agent/`).
- A latency and throughput harness with a row for every stage (`ril/bench/`, `results/latency/`).
- Frozen records for the evaluation and the contexts (`configs/frozen/`), guarded by a test.

**What was measured** (Python only; absolute resolved rates are not claims about agent capability)

- **RQ1** (development repositories, exploratory): on a dense baseline, adding BM25 by rank fusion
  raises Recall@100 by 8.9 points at Level 2 and 9.0 at Level 3; same-file expansion adds more at
  Level 3 (+12.2, two repositories); the typed graph does not beat the same-file control (Recall@100
  -5.6 at Level 3). Median cost per added stage: fusion 5.04 ms, same-file expansion 0.41 ms,
  against 18.34 ms for the dense path (different machines; not an end-to-end percentile).
- **RQ2** (matched optimization budgets, three seeds, one fixed stack): filtering mined pairs with a
  BM25 teacher did not separate from raw pairs or from a size-matched random subsample, on the eight
  evaluation repositories or on the 377 executable instances; no confirmatory contrast is rejected.
  A null result, reported as one.
- **RQ3** (327 confirmatory instances, one hosted model and one-shot repair held fixed, three
  adjacent repeats): raw-pair training 42.41% resolved against 39.96% for the untrained retriever;
  +2.45 points (-0.82 to +5.91), not distinguishable from zero. The filtered-pair and subsample arms
  are not distinguishable either; each trained arm is one training seed and the design detects about
  7 to 9 points, so this is a null with that bound, not evidence of no effect.
- **Calibration arms** (exploratory, outside the registered analysis): gold-file contexts resolved
  45.11% (+5.15 points over untrained, unadjusted, below the detectable difference and probably
  inflated); an empty context resolved 16.91% of the 272 instances it reached, not near zero, so
  part of every rate may be prior knowledge of the repositories.

**Ownership.** Person A / B / C are named in `docs/ROADMAP.md`.

---

## The idea in four lines

1. Coding agents cannot read a whole repository, so something must choose what they see — RIL is
   that selector: function-level indexing, lexical + dense + structural signals, rank fusion,
   context assembly under a token budget.
2. The retriever is trained, and its training-data decisions are usually made by convention.
3. **The experiment:** four retrievers that differ *only* in training supervision (RAW, FILTER,
   WEIGHT, CURRICULUM), trained for the same number of optimizer updates; then each is plugged into
   the same fixed agent and scored on resolved rate (RQ2 → RQ3). RQ1 fixes the architecture the
   others hold constant.
4. **The claim, stated narrowly:** our literature audit did not identify a study that
   systematically evaluates the controlled pipeline from retriever supervision quality, through
   retrieval performance, to repository-level coding-agent success. A null result is a publishable
   outcome, because the retrieval-vs-reasoning failure breakdown says why.

Two further threads the project owns: **latency/throughput analysis** (profiled per component,
recorded before every commit — a standing requirement from the professor) and a **structural
signal** over a code graph extended with test and configuration edges, evaluated on CORE-Bench L3.

---

## Layout

```
PROJECT_STATE.md  what is true right now           RESULTS.md        every benchmark, append-only
docs/             design docs + live documents     decisions/        ADRs (ADR-001..013)
docs/status/      one status page per workstream   specs/            acceptance contracts
knowledge/        paper notes, dataset cards       configs/          frozen / demo / experiments / bench
data/             held_out (tracked); the rest     results/          latency, rq1, rq2, rq3, logs, tables,
                  is rebuilt on the cluster                          figures, ledger_* (per-workstream rows)
scripts/          thin CLIs; scripts/ada/ = Slurm  tests/            unit, integration, leakage, reproducibility
reports/          proposal + final (LaTeX)

ril/
  config/ util/   parameters, paths; seed, logger, checks      parsing/    CodeUnit, parser, typed graph, updater
  retrieval/      BM25, dense encoder, graph expansion, recency   training/   pool, negatives, arm hooks, loss, runs
  assembly/       context assembly under a token budget            agent/      driver and providers for the agent runs
  evaluation/     loaders, metrics, chunk mapping, power          bench/      latency and throughput harness
  analysis/       tables from results/ (reads results/ only)
```

## Where to start

- **Current state and next task:** `PROJECT_STATE.md`, then `docs/ROADMAP.md`.
- **Seeing it run:** `make demo` and `docs/DEMO.md` (one real issue, every stage printed).
- **Understanding the research:** `docs/README.md` has the reading order. The full design lives in
  `docs/source/MASTER_PROJECT_DOCUMENT.md`.
- **Deciding things:** `decisions/README.md` — ADR-001 to ADR-010 are the open decisions and are all `Proposed`; the evidence gathered so far is in their addenda.

## Getting started

Requirements: Python 3.11 (pinned in `pyproject.toml` as `>=3.11,<3.12`) and [Poetry](https://python-poetry.org/).

```
make setup    # create the virtual environment and install dependencies
make lint     # ruff and mypy --strict
make test     # fast unit tests: one worker, no torch
```

Anything that imports PyTorch, trains or encodes runs on the Ada cluster, not on a laptop (see
`docs/COMPUTE.md`). The optional `train` dependency group is installed only there, with
`make setup-train`. For the repository layout and the reading order, start at `docs/README.md`.

### Contributing

- One branch per workstream, named `<initial>/<topic>` (for example `a/parser-callgraph`).
- No direct commits to `main`; the maintainer merges.
- Run `make lint` and `make test` before opening a merge request.

## Compute

Local machine: 8 GB RAM, no GPU — parsing, tests, small subsamples only. Indexing at CORE-Bench
scale, training and the RQ2 arms run on IIIT-H's **Ada** cluster, and datasets are acquired there,
never downloaded by hand. See `docs/COMPUTE.md`.

## Provenance

Design derived from the team's Master Project Document (rev 16, 2026-10-11). Key sources:
CORE-Bench (Zhang et al. 2026), SweRank (Gangi Reddy et al. 2025), LocAgent (Chen et al. 2025),
CoRNStack (Suresh et al. 2024), SWE-bench (Jimenez et al. 2024). Full list: `docs/11_references.md`.
