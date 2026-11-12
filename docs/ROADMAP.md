# Roadmap

Live plan. Tick boxes as work lands. Source: `10_timeline_and_fallback.md` and
`12_open_decisions.md` (master doc rev 16).

**Owners.** Person A = Neill Rawani (retrieval stack, RQ1; status page `status/person_a.md`).
Person B = Sukhraj Singh (decisions, RQ2, integration). Person C = Chaitanya Shah (evaluation, raw
PR set, RQ3). An item is ticked only once its work is merged into `main` and has a commit and
evidence (a `RESULTS.md` row, a ledger row or a registry entry in `EXPERIMENTS.md`).

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
- [ ] **Close ADR-001 … ADR-010 by end of week 2** (team decision) — 2026-11-03: ADR-001 to ADR-006 and ADR-010 accepted; ADR-007 (needs the agent pilot and ADR-008), ADR-008 (needs the engineer's dollar budget) and ADR-009 (needs a real rerank stage) stay open

## Weeks 1–4 — Person A: parsing, call graph, BM25

- [x] Repository parser + CodeUnit emission (`ril/parsing/repository_parser.py`; first build of 2026-10-17)
- [x] Call / import / inherit graph with edge-recovery coverage (`ril/parsing/call_graph.py`; the coverage is reported under several definitions, ADR-012)
- [ ] BM25 index (identifier splitting, field weights, tune b) — reference form built (`ril/retrieval/bm25_index.py`, `RESULTS.md` rows `e1-*`); identifier splitting and field weights added as options and piloted locally (A1-PILOT, `results/ledger_a.md`, merged 2026-10-31); tokenizer and k1/b selected on dev at chunk level (A1-DEV, reproduced 2026-11-08, E-A1-TAKEOVER); the gain is +4.6 to +5.1 alone at L2 and not distinguishable from 0 inside RRF(BM25, dense) at L2; field weights and unit-level granularity are open, so the item stays unticked

## Weeks 3–8 — Person B: dense encoder, baseline training, data pipeline

- [x] Dense encoder + flat exact index (`ril/retrieval/dense_encoder.py`, `provisional: ADR-006`; CodeRankEmbed and Qwen3-Embedding-0.6B measured zero-shot, E-DENSE-FUSION, 2026-10-25)
- [x] Smoke pilots E-PILOT-K, E-PILOT-NEG, E-PILOT-LEAK at 63 updates, 2 seeds (exploratory, 2026-10-29; evidence for ADR-001/ADR-002, nothing decided)
- [x] Block 1 of the supervision pilots (2026-10-29, evidence only): graph-role measurement against score-ordered same-file expansion (E-GRAPH-ROLE, ADR-003); twelve supervision-quality papers read in full (ADR-002 addendum); edited-function contamination follow-up and Pro ansible as a third dev L3 repository (E-CONTAM-EDITED, E-DEV-ANSIBLE); paired encoder numbers and Qwen3 training-memory check (E-ENCODER-NUMBERS, ADR-006); RQ3 power table (E-POWER update)
- [x] Block 2, T3: learning curve of RAW (E-PILOT-CURVE, 2026-10-29; reduced design, 5.14 GPU-hours; Block 2 at 22.14 of 24)
- [x] Block 2, Wave 6: teacher ranks for the 5,000-directory pool (3.16 GPU-hours) and the matched-pool arms pilot E-PILOT-ARMS2 (2026-10-31, exploratory; stage 1 two seeds, stage 2 one seed on three cells; Block 2 at 45.15 of 46)
- [x] Arms pilot E-PILOT-ARMS, stage 1 (24 runs at 100 updates) and stage 2 (6 runs at 1,000 updates), exploratory (2026-10-31; 11.4 GPU-hours; Block 2 at 33.53 of 36)
- [x] Training stack (pool reader, multi-positive InfoNCE, pluggable negative policy, the three arm hooks with the identity test, budget accounting, checkpoints, evaluation hook; `ril/training/`, E-TRAIN-STACK, 2026-10-25; every training value `provisional: ADR-001, ADR-002, ADR-006`)
- [x] Baseline training (multi-positive InfoNCE, repo-local hard negatives): implemented and run at pilot scale as the RAW arm (E-TRAIN-STACK, E-PILOT-CURVE; provisional, not the frozen run)
- [ ] Training data pipeline: SweLoc + own PR-mined set, filtered by held-out list — the SweLoc part is read, filtered and cached (`ril/training/pool_reader.py`, E-POOL-RANKS); the own PR-mined set: rebuilt by the lead (`ril/data_mining/`, E-MINE-PILOT); pilot built and measured on the live API (E-MINE-PILOT M1 to M4); the full run finished 2026-11-08 and is reported, audited and prepared (E-MINE-FULL-RESULT: 6,230 mined, 5,789 `non_test` examples after the audit, 2026-11-10); this item closes when RQ2 trains on it; integration pilot done (E-MINED-PILOT: the pilot set is read, ranked, filtered and trained on; exploratory); de-duplicated store, materialise step and the pool-aligned reading built and checked on the pilot (E-MINE-STORE, byte-identical 1,391 of 1,391); the full 10,000-attempt run waits for the token on account C

## Weeks 3–6 — Person C: evaluation harness

- [x] CORE-Bench loaders (L2, L3, REWRITE splits) — L2 and L3 folders load (`ril/evaluation/core_bench.py`); Rewrite pairing and staging code merged after review (E-C1-EVAL); the dev BM25 run reported from Colab (E-C1-COLAB-DEV) was re-run natively on account A with stored query-level rows and equals it in 12 of 12 cells (E-C-CATCHUP, D144)
- [x] Metrics at chunk granularity; reproduces a published CORE-Bench number as a sanity check (BM25 rows reproduced to the printed decimal, pilot E1)

## Weeks 5–8 — Person A: RQ1

- [x] Ablation on the development set with latency columns from stored rows (2026-11-09, E-RQ1-LADDER, D145: dense, plus BM25 by RRF, plus same-file expansion, plus typed expansion against the same-file and chance controls, plus recency prior; rerank not built, the three stages without a latency row measured 2026-11-10, E-FREEZE-AND-LATENCY: rank fusion 5.04 ms, same-file expansion 0.41 ms, recency prior 2.04 ms p50 at django size)
- [ ] Ablation: dense / dense+BM25 / dense+structural / all three — with latency columns (graph-signal and recency pilots on BM25 seeds done, exploratory: E3 to E5; dense, dense+BM25 and the graph on a fused first stage measured zero-shot with latency rows, E-DENSE-FUSION 2026-10-25; the frozen-configuration ablation still to run; the freeze proposal is in E-RQ1-LADDER)
- [ ] Latency distribution measured; rerank decision informed (ADR-009)

## Before week 6 — freeze

- [x] Retrieval settings recorded per consumer in `configs/frozen/` (RQ2 evaluation k 60, RQ3 contexts and dev selection k 100; hashed, manifest, latency snapshot from stored rows; 2026-11-10, E-FREEZE-AND-LATENCY, D148); not unified; ruled 2026-11-12 (D149, E-FREEZE-RULING-REPORT-3): RQ2 evaluation frozen at launch, RQ3 contexts frozen, the dev selection is a provenance record in `configs/records/`
- [ ] All latency optimisation landed (rank fusion sorts two whole rankings: 5.04 ms at django size, a selection-based fusion is a candidate; the query encoder dominates on both nodes)

## RQ2 final-experiment tasks (added 2026-11-03; decisions O1 to O15 in `docs/RQ2_PROTOCOL.md` section 11)

Design of record: option E, 12 cells x 3 seeds, 8 extra evaluation repositories, 38.9 GPU-hours; Block 3 cap 46.7 (`docs/COMPUTE.md`). Primary update count 100, with a 1,000-update sensitivity check on a subset of cells. Confirmatory: FILTER (BM25 teacher) against RAW and against the size-matched subsample, on the unfiltered mined set; everything else exploratory.

- [ ] Enlarge the evaluation set (O8, D75, D100): the eight repositories are fixed by rule (`configs/experiments/eval_repos_v1.json`, `scripts/select_eval_repos.py`); unit records and dense stores are built for them (E-EVAL-REPOS-BUILD, build only, no retrieval result read); evaluation happens once, after the dev analysis
- [x] Retention switch in the training job scripts (O9, D76; built and tested 2026-11-05, `ril/training/retention.py`, `scripts/archive_checkpoints.py`; no GPU run yet): keep the half-precision final model of runs that feed RQ3 and the report (about 274 MB each). Still open: the archive copy to account B's storage (needs an alias for account B; numbered script written, not run)
- [x] Label sheet for pull-request labels (O11): relevance of each edited function to its issue, three-way verdict and reason, for the noise audit (400 stratified pairs, two readers on a 100-pair overlap); the call-edge sheet stays separate — sheets and scorer built 2026-11-05 (E-LABEL-AUDIT-SHEET, `docs/LABEL_AUDIT.md`); **nobody has read any pair yet**; reading the sheets and scoring them is a separate, open item below
- [ ] Read the pilot label sheets (reader 1 and reader 2 are two team members who are not the lead; the lead reads no pair, D101; two readers, about 5 hours each) and score them with `scripts/label_audit_score.py` (E-LABEL-AUDIT-SHEET); then decide whether the full mined set needs a second, larger audit
- [x] Mined-set gates: token on the cluster (D2), M1 to M4, G2 at 100 pilot directories with a positive and 10,000 positives at full scale (O10), content-overlap audit of the mined corpora (built 2026-11-06, D105, E-OVERLAP-AUDIT; pilot store audited; full store audited 2026-11-10, 13 of 6,230 directories dropped, E-MINE-FULL-RESULT; G2 passes at all readings)
- [ ] Draw fresh noise realisations for the confirmatory and calibration cells (O15); the Wave 7 and 8 realisations are not reused
- [ ] Register the cell list, Holm families (O5) and delta = 1.5 points (O6) before any final run
- [ ] **Declared fallback (O13), stated before any final run:** if the arms do not separate by the rule of protocol section 6, RQ3 contrasts RAW with the untrained encoder. This measures "does training help", not "does supervision quality help", and is labelled so (DEV-022)

## Weeks 6–12 — Person B: RQ2

- [ ] Four arms × three seeds at matched optimizer updates
- [ ] Budget-accounting table (compute cost, unique examples seen, effective epochs)
- [ ] Subsampled-RAW control; positive-vs-negative and quantity-quality only if core completes

## Weeks 7–10 — Person A: graph extension

- [x] Test and configuration node types, `tests` / `configures` edges (built and off by default; precision sampled, `ril/parsing/exploratory_edges.py`, `RESULTS.md` rows `p-*`; census of 2026-10-23 over 540 Python L3 instances: test units are 20.5% of L3 positives and 44% of those outside the L2 files; non-Python positives 1.7%)
- [x] Edge sets on L3 and stacked expansion against the same-file control, dev only (2026-11-09, E-A-OWNER-ITEMS, exploratory: no edge set beats same-file; ansible lacks dense scores; Verified-six not read)
- [ ] CORE-Bench L3 evaluation

## Week 12 — go / no-go

One question: do we have **at least two trained retrievers with a measurable retrieval difference**?
Yes → RQ3 proceeds. No → RQ3 is cut; the project ships as RQ1 + RQ2 + the latency analysis, which is
still complete and defensible.

- [ ] Go / no-go recorded as an ADR

## Weeks 10–14 — Person C: RQ3

- [x] Context assembly stage (2026-11-06, D102, ADR-014 Proposed; `ril/assembly/`, `assemble` and BM25-only `end_to_end` latency rows, gold-in-context by budget and first stage, E-ASSEMBLY exploratory); the agent-model tokenizer and the budget for the agent are not done
- [x] Unit-cap re-run of the assembly stage (2026-11-06, D103, E-ASSEMBLY-CAP, dev only): cap 1,000 kept; RRF above BM25 on dev, intervals exclude 0
- [x] RQ3 pilot preparation (2026-11-06, D104, E-RQ3-PILOT-PREP; `docs/RQ3_PILOT.md`): what the cluster can execute (no container runtime usable; 263 of 500 Verified environments buildable without root; gold patch passes on three repositories), a provider adapter with a persistent limiter and tests (`ril/agent/providers/`, `scripts/rq3_pilot.py`), prompts for 100 dev instances, a three-call smoke test; the pilot itself is not run
- [x] Executable evaluation for RQ3 (2026-11-07, D106, E-RQ3-EXEC; `ril/evaluation/executor/`, `results/rq3_exec/`): 377 of 500 Verified instances qualify (gold patch passes all FAIL_TO_PASS and PASS_TO_PASS tests twice, no root, no container); cost of one model patch is one run (p50 17 s); 111 of 140 older-Python instances recovered with micromamba; retrieval contexts for the subset need unit records for django, sympy, pytest, sphinx, pylint (estimate in `results/rq3_exec/unit_build_estimate.csv`); nothing evaluated with a model patch
- [x] Unit records, BM25 scores and encoding for the executable subset (2026-11-07, D107, E-RQ3-UNITS; `ril/evaluation/rq3_units.py`, `results/rq3_units/`): 341 instances built with 0 failures plus the 36 already stored, so all 377 have units and BM25 scores; 220,974 distinct unit texts encoded with the untrained base encoder at 0.377 GPU-hours (rule: at most 6.0 at 109 texts/s); nothing evaluated; trained-checkpoint encodings and retrieval contexts remain open
- [x] Retrieved contexts for the executable subset (2026-11-07, D108, E-RQ3-CONTEXTS; `ril/assembly/rq3_contexts.py`, `results/rq3_contexts/`): 377 instances x BM25, untrained dense, RRF x budgets 8,000 and 16,000, 0 failures, 30 of 30 rebuilt files byte-identical; all 377 already had query vectors (no GPU time); 8,000-token archive on the engineer's machine; trained-checkpoint arms and the agent runs remain open
- [x] RQ3 pilot run (2026-11-06 to 2026-11-07: 400 of 400 units, 565 calls) and its analysis from stored data (D109, E-RQ3-PILOT-RESULT; `ril/analysis/rq3_pilot_analysis.py`, `results/rq3_pilot/analysis/`): all three flip criteria pass, free tier workable (3 to 8 days for 2 to 8 arm-runs), BM25 17.0% against RRF 8.5% unusable after follow-ups mostly through gold absence, run-to-run same edits 63%; no resolved rate (nothing graded); scaffold, model and Q45 decisions remain the engineer's
- [x] Edit blocks to the executor's patch (2026-11-08, D110, E-RQ3-PATCHAPPLY; `ril/agent/providers/patch_convert.py`, `results/rq3_patch/`): exact primary, tolerant sensitivity; pilot edits apply in 276 of 400 units (tolerant rescues 0); 20 of 20 gold-derived edits resolve through the executor; no model call
- [x] RQ3 driver and plan (2026-11-08, D111 to D114, E-RQ3-DRIVER; `ril/agent/providers/driver.py`, `results/rq3_driver/`): held-out slice of 50 frozen (N = 327), prompts of the 377 built (887 of 1,131 pass the screen; Q70), driver replay-tested on the real executor (30 of 30), analysis plan with run-noise power, cost model, spend guard; no model call; graded model check waits for the engineer (billing, cap, key, limits)
- [x] Read the five agent-scaffold papers in full (Agentless, SWE-agent, OpenHands new notes; LocAgent, CoSIL re-verified), ADR-007 addendum (D116, E-LIT-SCAFFOLD)
- [x] Rulings on that reading applied (2026-11-08, D121, E-LIT-SCAFFOLD addendum): qualified header for a partly read note (check and test), scaffold renamed retrieval-supplied one-shot repair, any-of-k secondary reading in `ril/analysis/rq3_results.py`, report paragraphs on scaffolds and two threats
- [x] RQ3 prompt pseudonymisation (2026-11-08, D120, E-RQ3-PSEUDONYMISE; Q70 answered): 1,131 of 1,131 prompts pass the screen, restore in the driver, round trips and replay checked, no model call
- [x] Workstream C catch-up (2026-11-09, D144, E-C-CATCHUP): scaffold table of the evaluation API brought to the five-paper reading; Colab C1 dev BM25 comparison re-run natively on account A (12 of 12 cells equal, query-level rows stored, Q64 answered)
- [x] RQ3 trained-arm pipeline (2026-11-12, D150, D151, E-RQ3-TRAINED-ARMS; `scripts/rq3_trained_arm.py`, `scripts/ada/rq3_trained_*.sbatch`): plan with cost against Block 4 (eight of 18 retained models fit), encode stage under the sealed order, contexts and prompts through the untrained path (byte equality and determinism tested), analysis plan for the trained arms; CPU only, nothing encoded, no model call; encoding and the graded runs wait for the RQ2 models and the lead
- [x] RQ3 score retention and fused trained arms (2026-11-12, D152, DEV-042, E-RQ3-SCORE-RETENTION; `ril/evaluation/score_retention.py`, `scripts/rq2_final_sets.py`, `scripts/rq3_trained_arm.py`): the final-sets job keeps the executable-377 scores (metrics byte-identical, sealed order unchanged), the trained arm is RRF of BM25 and the model's scores, the plan costs retained models 0 and orders the fallback encode stage by Q73 (eight models fit); CPU only, nothing encoded, no model call; the first sealed scoring job and the cluster run of the new context path wait for the lead
- [x] RQ3 model check across providers, apparatus (2026-11-12, D155, E-RQ3-MODEL-CHECK-PLAN; `ril/agent/providers/{messages_api,model_check}.py`, limits-file template): four candidates of two providers, rule fixed in code before any call, tested without network; the check itself (billing, keys, prices, four runs of 50) waits for the lead
- [x] RQ3 model check amended (2026-11-12, D158, E-RQ3-MODEL-CHECK-AMEND; `ril/agent/providers/cache_probe.py`, `model_check.py`, `scripts/rq3_driver.py`): one provider and one candidate by written key, whole-study cost with a measured cache-hit fraction (probe of 10 prompts sent twice), adjacent repeats, the previous-generation model refused; code and tests only, no call
- [ ] Agent integration (fixed scaffold, model, temperature, seed)
- [ ] Paired per-instance runs; retrieval-vs-reasoning failure log (gold-patch file in context?)

## Weeks 13–16 — All

- [x] Report pass 4 (2026-11-12, E-REPORT-DRAFT-4, D156, D157): power slot (run-noise table rerun, reproduced byte for byte; power of 4 points), the benchmark-subset citation, related-work refresh (three papers read in full, nine existing notes cited), launch status, two mismatches fixed, source-file check; 16 open slots, all waiting for runs or readers
- [ ] Analysis, error breakdown, report, presentation
- [x] Final report skeleton (`reports/final/final_report.tex`: every section, generated tables from stored results by `scripts/report_tables.py`, every empty slot a `\todo` naming its experiment entry) and the evidence-gap map (`docs/REPORT_GAPS.md`); the slots fill as the confirmatory contrasts and the agent runs finish

## Milestones to show the professor

| Week | Artifact | Done |
|---|---|---|
| 3 | Parser running on a real repository; ten CodeUnits and the edge-recovery percentage | [x] (reported under four definitions; ADR-012) |
| 6 | Baseline encoder trained; a natural-language query returning the right function | [ ] |
| 9 | RQ1 ablation table with the latency column | [ ] |
| 12 | Four RQ2 arms, three seeds each, with the budget-accounting table | [ ] |
| 14 | RQ3 resolved rates with CIs and the retrieval-vs-reasoning failure breakdown | [ ] |

> Cost statement for the RQ2 runs (rewritten 2026-10-31): the 20,000-update plan is no longer the working assumption (it was reasoned, not measured). Measured: the RAW encoder reaches its gain by 100 updates and stays flat to 2,000 (E-PILOT-CURVE); a run of 100 updates with its dev-subset evaluation costs about 0.25 GPU-hours and one of 1,000 updates about 0.9 (E-PILOT-ARMS). The working assumption for the arms is 100 to 1,000 updates with at least 3 seeds per arm, about 0.25 to 0.9 GPU-hours per run; whether a larger pool is needed first is the engineer's question (ADR-002 addendum 2026-10-31).

## RQ2 final launch (audit of 2026-11-08, `docs/RQ2_LAUNCH_PLAN.md`)

- [x] Readiness audit of the chain from the mined store to the final tables; plan-only launcher, evaluation-set check, yield from the state log; dry run at minimal scale (E-RQ2-READINESS, D115)
- [x] Rulings on the analysis rule, the cell table, the pool rule and the job batching applied (2026-11-09, D136 to D143, DEV-040, DEV-041, addenda to E-RQ2-ANALYSIS and E-RQ2-FINAL-CELLS, `docs/RQ2_LAUNCH_PLAN.md` section 11): decisions read from the cluster-robust t interval (family-wise error 0.03 to 0.05 at 8 to 20 repositories, 1,000 simulations per cell; the old rate pinned beside), 45 runs (clean cell and a second noise rate added), N = min(100, floor(F / 32)) computed from the prepared store, one GPU job per account and seed, converter from the scoring results to the analysis rows, one shared sealed-order guard; plan-only rehearsal on A and C; budget 34.34 GPU-hours against 46.7
- [x] Launch step after the prep job (2026-11-12, E-RQ2-LAUNCH, D153, D154): dense-teacher measurement (2.48 GPU-hours projected, SweRank cell on, run later), `resolve` (F = 3,885, N = 100), GPU smoke and retention check, registration and preflight on the launch commit c2a8db6, six jobs submitted (C 73578 to 73580, A 73581 to 73583); seed 100 training
- [ ] RQ2 monitoring: seed jobs finish, then SweRank single-arm jobs (own authorization), dev analysis and its record, sealed final-sets scoring
- [x] Final cell configurations and run scripts for the 36 runs (2026-11-09, E-RQ2-FINAL-CELLS, D124 to D134; extended to 45 by D137 and D138): committed configurations, per-run job scripts per account family, submit and preflight scripts, evaluation by set, sealed order of the final sets; plan-only validated on accounts A and C, nothing submitted
- [x] Full-store prep job (materialise with a names file, `non_test` reading, BM25 ranks, feature table, cache, FILTER size) with the overlap drop list applied; run at 200 directories first (E-RQ2-FULL-PREP, D135; run on the whole store 2026-11-10, E-MINE-FULL-RESULT)
- [x] Overlap audit on the full store and its drop list (2026-11-10, E-MINE-FULL-RESULT, job 66544: 6,230 directories, 4,366.9 s, 13 dropped, list tracked with its SHA-256)
- [x] Final analysis module (built 2026-11-09, E-RQ2-ANALYSIS, `ril/analysis/rq2_final.py`; scope in `docs/RQ2_LAUNCH_PLAN.md` 9.5; reproduces the stored pilot summaries, not yet run on final rows; its test of the family-wise error rate failed, see the entry): `ril/analysis/` module reading per-query run rows; paired bootstrap per contrast and level, Holm within the two families of 8, delta 1.5 verdicts, seed mean and SD, sanity and dose-response rules, report tables; tested on the pilot rows and constructed cases; CPU
- [ ] Dense teacher cost on the mined store: per-repository de-duplicated pass on 100 directories (about 0.4 GPU-hours); rule fixed by D125: run the cell only if the full-store pass costs at most 6.0 GPU-hours
- [x] Verified look set decided: the 377 executable instances (D127, DEV-038)
- [ ] Trained-arm contexts for the 377 executable instances from a retained model directory (the final-sets scoring already encodes the 377 for RQ2's look; RQ3's contexts need the model-directory encoding and the context build, Block 4)
- [ ] Alias for the archive account and the copy of retained models; retention directory on the account with space (account A has 5.1 GB free); account B has no SSH alias (`ada` and `adac` only), so the archive script cannot run until the engineer adds one
- [x] FILTER-pool rule decided (D133): 100 updates for every arm, each arm cycles its own pool in a fresh seeded order per pass, distinct examples seen stored beside every result, no change of the visits; the prep job's `filter-size` output states whether FILTER repeats
- [x] Retention against the test role of the eight and where the mined cells train decided (D124, D129): the 18 mined models retained on C, the eight and the executable 377 scored once from them after the dev analysis, mined cells on C and injected cells on A (eight repositories and built parts of the 377 copied to C, verified)
- [ ] Return of the pilot label sheets from two readers who are not the lead; decide pilot sample or new draw
