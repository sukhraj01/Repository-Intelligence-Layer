# Roadmap

Live plan. Tick boxes as work lands. Source: `10_timeline_and_fallback.md` and
`12_open_decisions.md` (master doc rev 16). Owners are Person A / B / C — mapping is Open question Q1
in `PROJECT_STATE.md`.

Dependency structure matters more than dates: **RQ2 cannot start until the training pipeline works;
RQ3 cannot start until RQ2 has produced at least two distinguishable checkpoints.**

## Weeks 1–2 — foundations (All)

Week-1 deliverables, in order (contracts in `specs/`):

- [x] Repo bootstrap: package skeleton, tooling, git, commit-hook stub
- [ ] Freeze the CodeUnit schema and write it down (`specs/code_unit.md`) (draft v0 implemented and tested; awaiting answers to the eight questions)
- [x] Reach the data sources and read their formats: access probes, CORE-Bench listing and samples, metadata of Verified / Loc-Bench, SweLoc search (`knowledge/datasets/`)
- [x] Build the held-out repository list from CORE-Bench L2/L3 and SWE-bench Verified (`specs/held_out_repos.md`) (605 repositories)
- [x] Filter any candidate training pool against it; record how many instances survive (`specs/held_out_repos.md`) (CodeSearchNet python and the unconfirmed `gangiswag/train_data` candidate; CoRNStack cannot be filtered)
- [ ] Stand up the per-commit latency harness (`specs/latency_harness.md`)
- [ ] Parse one real repository end to end; print ten CodeUnits and the edge-recovery % (`specs/parse_one_repo.md`)
- [ ] Gather evidence for decisions 1–10 (`decisions/`)
- [ ] **Close ADR-001 … ADR-010 by end of week 2** (team decision)

## Weeks 1–4 — Person A: parsing, call graph, BM25

- [ ] Repository parser + CodeUnit emission
- [ ] Call / import / inherit graph with edge-recovery coverage
- [ ] BM25 index (identifier splitting, field weights, tune b)

## Weeks 3–8 — Person B: dense encoder, baseline training, data pipeline

- [ ] Dense encoder + flat exact index
- [ ] Baseline training (multi-positive InfoNCE, repo-local hard negatives)
- [ ] Training data pipeline: SweLoc + own PR-mined set, filtered by held-out list

## Weeks 3–6 — Person C: evaluation harness

- [ ] CORE-Bench loaders (L2, L3, REWRITE splits)
- [ ] Metrics at chunk granularity; reproduces a published CORE-Bench number as a sanity check

## Weeks 5–8 — Person A: RQ1

- [ ] Ablation: dense / dense+BM25 / dense+structural / all three — with latency columns
- [ ] Latency distribution measured; rerank decision informed (ADR-009)

## Before week 6 — freeze

- [ ] All latency optimisation landed
- [ ] Retrieval stack frozen; `configs/frozen/` written, hashed, benchmark snapshot recorded

## Weeks 6–12 — Person B: RQ2

- [ ] Four arms × three seeds at matched optimizer updates
- [ ] Budget-accounting table (compute cost, unique examples seen, effective epochs)
- [ ] Subsampled-RAW control; positive-vs-negative and quantity-quality only if core completes

## Weeks 7–10 — Person A: graph extension

- [ ] Test and configuration node types, `tests` / `configures` edges
- [ ] CORE-Bench L3 evaluation

## Week 12 — go / no-go

One question: do we have **at least two trained retrievers with a measurable retrieval difference**?
Yes → RQ3 proceeds. No → RQ3 is cut; the project ships as RQ1 + RQ2 + the latency analysis, which is
still complete and defensible.

- [ ] Go / no-go recorded as an ADR

## Weeks 10–14 — Person C: RQ3

- [ ] Agent integration (fixed scaffold, model, temperature, seed)
- [ ] Paired per-instance runs; retrieval-vs-reasoning failure log (gold-patch file in context?)

## Weeks 13–16 — All

- [ ] Analysis, error breakdown, report, presentation

## Milestones to show the professor

| Week | Artifact | Done |
|---|---|---|
| 3 | Parser running on a real repository; ten CodeUnits and the edge-recovery percentage | [ ] |
| 6 | Baseline encoder trained; a natural-language query returning the right function | [ ] |
| 9 | RQ1 ablation table with the latency column | [ ] |
| 12 | Four RQ2 arms, three seeds each, with the budget-accounting table | [ ] |
| 14 | RQ3 resolved rates with CIs and the retrieval-vs-reasoning failure breakdown | [ ] |
