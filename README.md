# Repository Intelligence Layer (RIL)

A repository-level code retrieval layer for LLM coding agents, **plus** a controlled study of
whether the retriever's *training supervision* affects whether the agent actually resolves the
issue.

Lead: Sukhraj Singh (IIIT Hyderabad) · Team of 3 · NLP semester project · 16 weeks · Python only.

> **Status: design locked, implementation not started.** Nothing in this repository runs yet.
> See `PROJECT_STATE.md` for the current truth.

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
docs/             design docs + live documents     decisions/        ADRs (10 open decisions)
specs/            week-1 acceptance contracts      knowledge/        papers, datasets
configs/          frozen / demo / experiments      data/             raw, processed, index, held_out
results/          latency, rq1, rq2, rq3, logs     scripts/          thin CLIs; scripts/ada/ = Slurm jobs
ril/              the package                      tests/            unit, integration, leakage, repro
reports/          proposal + final (LaTeX)
```

## Where to start

- **Current state and next task:** `PROJECT_STATE.md`, then `docs/ROADMAP.md`.
- **Understanding the research:** `docs/README.md` has the reading order. The full design lives in
  `docs/source/MASTER_PROJECT_DOCUMENT.md`.
- **Deciding things:** `decisions/README.md` — ten decisions must close by end of week 2.

## Quick start

*Not available yet.* `make setup`, `make test`, `make bench` are created in the week-1 bootstrap.

## Compute

Local machine: 8 GB RAM, no GPU — parsing, tests, small subsamples only. Indexing at CORE-Bench
scale, training and the RQ2 arms run on IIIT-H's **Ada** cluster, and datasets are acquired there,
never downloaded by hand. See `docs/COMPUTE.md`.

## Provenance

Design derived from the team's Master Project Document (rev 16, 2026-10-11). Key sources:
CORE-Bench (Zhang et al. 2026), SweRank (Gangi Reddy et al. 2025), LocAgent (Chen et al. 2025),
CoRNStack (Suresh et al. 2024), SWE-bench (Jimenez et al. 2024). Full list: `docs/11_references.md`.
