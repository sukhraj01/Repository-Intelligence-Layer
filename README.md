# Repository Intelligence Layer (RIL)

A repository-level code retrieval layer for LLM coding agents, **plus** a controlled study of
whether the retriever's *training supervision* affects whether the agent actually resolves the
issue.


## Status

The design is fixed (Master Project Document rev 16, 2026-10-11) and the apparatus runs. Current
state, blockers and the next task are in `PROJECT_STATE.md`; every measured number is a row of
`RESULTS.md` or `results/ledger_a.md` with its run log in `results/logs/`.

**Exists and runs** (all of it exploratory or measured on development repositories; nothing is frozen):

- Repository parser and a typed graph (contain, import, invoke, inherit, override; tests and
  configures built but off by default) with a per-edge status, plus an incremental updater that
  matches the full rebuild on 100 of 100 commits tested (`ril/parsing/`, `docs/ARCHITECTURE.md`).
- BM25 (reference form, with identifier splitting and field weights as options) and a dense
  encoder with a flat exact index; graph expansion, rank fusion and a recency prior as measurement
  code (`ril/retrieval/`).
- CORE-Bench loaders and metrics that reproduce the published BM25 rows (`ril/evaluation/`,
  `RESULTS.md` rows `e1-*`).
- The RQ2 training stack: pool reader, negative policies, the three arm hooks, budget accounting,
  checkpoint evaluation (`ril/training/`).
- Measured pilots, each registered in `docs/EXPERIMENTS.md`: graph signal and graph role, pool
  filter state, contamination scan, encoder numbers, RQ3 power, and two arms pilots
  (E-PILOT-ARMS, E-PILOT-ARMS2).
- A latency and throughput harness with per-stage rows (`ril/bench/`, `results/latency/`).

**Does not exist yet:** the frozen configuration (`configs/frozen/`), the four-arm RQ2 runs at
three seeds, context assembly, and the agent runs for RQ3.

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
  evaluation/     loaders, metrics, chunk mapping, power          bench/      latency and throughput harness
  analysis/       tables from results/ (reads results/ only)
```

## Where to start

- **Current state and next task:** `PROJECT_STATE.md`, then `docs/ROADMAP.md`.
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
