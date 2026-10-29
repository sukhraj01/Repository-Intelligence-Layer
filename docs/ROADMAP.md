# Roadmap

Live plan. Tick boxes as work lands. Source: `10_timeline_and_fallback.md` and
`12_open_decisions.md` (master doc rev 16). Owners are Person A / B / C — mapping is Open question Q1
in `PROJECT_STATE.md`.

Dependency structure matters more than dates: **RQ2 cannot start until the training pipeline works;
RQ3 cannot start until RQ2 has produced at least two distinguishable checkpoints.**

## Weeks 1–2 — foundations (All)

Week-1 deliverables, in order (contracts in `specs/`):

- [x] Repo bootstrap: package skeleton, tooling, git, commit-hook stub
- [x] Freeze the CodeUnit schema and write it down (`specs/code_unit.md`) (FROZEN v1, ADR-013; id builder, repo_id normalizer and is_test rule implemented and tested; class-unit `source` still open, Q28)
- [x] Reach the data sources and read their formats: access probes, CORE-Bench listing and samples, metadata of Verified / Loc-Bench, SweLoc search (`knowledge/datasets/`)
- [x] Build the held-out repository list from CORE-Bench L2/L3 and SWE-bench Verified (`specs/held_out_repos.md`) (605 repositories; list schema 2 adds current-name resolution and a Loc-Bench tier of 169 more)
- [x] Filter any candidate training pool against it; record how many instances survive (`specs/held_out_repos.md`) (CodeSearchNet python and the unconfirmed `gangiswag/train_data` candidate; CoRNStack cannot be filtered)
- [x] Stand up the per-commit latency harness (`specs/latency_harness.md`) (synthetic stub stages; graph stage names registered; thresholds provisional, Q33)
- [x] Parse one real repository end to end; print ten CodeUnits and the edge-recovery % (`specs/parse_one_repo.md`): flask, requests and django at Verified base commits; recovery reported under four definitions, none chosen (ADR-012); storage options measured (ADR-011 addendum)
- [x] Read the data and training papers in full and record notes with a checked quote table (`knowledge/papers/`: CORE-Bench, SweRank, SweRank+, CoRNStack, SWE-bench; `scripts/check_paper_note.py`)
- [x] Read the graph papers in full and record notes (`knowledge/papers/`: LocAgent, KGCompass, LARGER, SpIDER, GREPO, ARISE, CoSIL)
- [x] Read the call-graph accuracy papers, the supervision papers and Agent Retrieval Bench in full; log a literature scan with a per-RQ summary (`knowledge/papers/`: PyCG, Jarvis, Sun et al., Rethinking Negative Pairs, CodeR, Agent Retrieval Bench, `LANDSCAPE.md`)
- [x] Read the candidate encoder's report, the remaining negative-policy and graph scan entries in full, refresh the literature scan and update the per-RQ summary (`knowledge/papers/`: Qwen3 Embedding, NV-Retriever, MAP4CS, hard-negative transfer, LogicLoc, RepoNavigator, NoCFG; `LANDSCAPE.md`, scan of 2026-10-23)
- [x] Design the knowledge graph as a separately versioned artifact: node kinds, edge families, edge record with status, three roles, storage options (`specs/repo_graph.md` DRAFT v0, `docs/GRAPH_DESIGN.md`, ADR-011 Proposed; no choice made)
- [ ] Gather evidence for decisions 1–10 (`decisions/`) — pool check, power table and contamination slice measured 2026-10-18 the full documents-only scan and its edited-function follow-up 2026-10-29 (`docs/EXPERIMENTS.md`); engineer decisions D14-D24 of 2026-10-18 recorded in the owning ADRs and specs, references audited (DEV-011), second-reader spot-check sheet prepared; class-unit source forms, ambiguous-site policies and the L3 positive census measured 2026-10-23 (Q28, Q35, Q36; ADR-013, ADR-011 addenda); dense and fusion numbers 2026-10-25 (ADR-006, ADR-003 addenda); pool filter state and K-rank under three teachers 2026-10-25 (E-POOL-RANKS; ADR-001, ADR-002 addenda); ADR-001 to ADR-010 still open
- [ ] **Close ADR-001 … ADR-010 by end of week 2** (team decision)

## Weeks 1–4 — Person A: parsing, call graph, BM25

- [x] Repository parser + CodeUnit emission (`ril/parsing/repository_parser.py`; first build of 2026-10-17)
- [x] Call / import / inherit graph with edge-recovery coverage (`ril/parsing/call_graph.py`; the coverage is reported under several definitions, ADR-012)
- [ ] BM25 index (identifier splitting, field weights, tune b) — reference-tokenisation index built (`ril/retrieval/bm25_index.py`); identifier splitting, fields and b tuning open

## Weeks 3–8 — Person B: dense encoder, baseline training, data pipeline

- [x] Dense encoder + flat exact index (`ril/retrieval/dense_encoder.py`, `provisional: ADR-006`; CodeRankEmbed and Qwen3-Embedding-0.6B measured zero-shot, E-DENSE-FUSION, 2026-10-25)
- [x] Smoke pilots E-PILOT-K, E-PILOT-NEG, E-PILOT-LEAK at 63 updates, 2 seeds (exploratory, 2026-10-29; evidence for ADR-001/ADR-002, nothing decided)
- [x] Block 1 of the supervision pilots (2026-10-29, evidence only): graph-role measurement against score-ordered same-file expansion (E-GRAPH-ROLE, ADR-003); twelve supervision-quality papers read in full (ADR-002 addendum); edited-function contamination follow-up and Pro ansible as a third dev L3 repository (E-CONTAM-EDITED, E-DEV-ANSIBLE); paired encoder numbers and Qwen3 training-memory check (E-ENCODER-NUMBERS, ADR-006); RQ3 power table (E-POWER update)
- [x] Block 2, T3: learning curve of RAW (E-PILOT-CURVE, 2026-10-29; reduced design, 5.14 GPU-hours; Block 2 at 22.14 of 24)
- [ ] Block 2, T4: arms pilot (not run; update count and budget are for the engineer to decide)
- [x] Training stack (pool reader, multi-positive InfoNCE, pluggable negative policy, the three arm hooks with the identity test, budget accounting, checkpoints, evaluation hook; `ril/training/`, E-TRAIN-STACK, 2026-10-25; every training value `provisional: ADR-001, ADR-002, ADR-006`)
- [ ] Baseline training (multi-positive InfoNCE, repo-local hard negatives)
- [ ] Training data pipeline: SweLoc + own PR-mined set, filtered by held-out list

## Weeks 3–6 — Person C: evaluation harness

- [ ] CORE-Bench loaders (L2, L3, REWRITE splits) — L2 and L3 folders load (`ril/evaluation/core_bench.py`); Rewrite splits not yet run
- [x] Metrics at chunk granularity; reproduces a published CORE-Bench number as a sanity check (BM25 rows reproduced to the printed decimal, pilot E1)

## Weeks 5–8 — Person A: RQ1

- [ ] Ablation: dense / dense+BM25 / dense+structural / all three — with latency columns (graph-signal and recency pilots on BM25 seeds done, exploratory: E3 to E5; dense, dense+BM25 and the graph on a fused first stage measured zero-shot with latency rows, E-DENSE-FUSION 2026-10-25; the frozen-configuration ablation still to run)
- [ ] Latency distribution measured; rerank decision informed (ADR-009)

## Before week 6 — freeze

- [ ] All latency optimisation landed
- [ ] Retrieval stack frozen; `configs/frozen/` written, hashed, benchmark snapshot recorded

## Weeks 6–12 — Person B: RQ2

- [ ] Four arms × three seeds at matched optimizer updates
- [ ] Budget-accounting table (compute cost, unique examples seen, effective epochs)
- [ ] Subsampled-RAW control; positive-vs-negative and quantity-quality only if core completes

## Weeks 7–10 — Person A: graph extension

- [ ] Test and configuration node types, `tests` / `configures` edges (census of 2026-10-23 over 540 Python L3 instances: test units are 20.5% of L3 positives and 44% of those outside the L2 files; non-Python positives 1.7%)
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
| 3 | Parser running on a real repository; ten CodeUnits and the edge-recovery percentage | [x] (reported under four definitions; ADR-012) |
| 6 | Baseline encoder trained; a natural-language query returning the right function | [ ] |
| 9 | RQ1 ablation table with the latency column | [ ] |
| 12 | Four RQ2 arms, three seeds each, with the budget-accounting table | [ ] |
| 14 | RQ3 resolved rates with CIs and the retrieval-vs-reasoning failure breakdown | [ ] |
