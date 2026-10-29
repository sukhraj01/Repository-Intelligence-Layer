# Project State

> **Current truth only.** Not a history. History lives in `RESULTS.md` and the git log.
> **Hard cap: 200 lines.** If this file exceeds it, the fix is to *delete resolved content*,
> not to add a summary. See the maintenance rule at the bottom.

**Last updated:** 2026-10-29 (end of Wave 4 block 1; evidence only, nothing decided by the sessions) · graph role: no evidence that typed edges add to score-ordered same-file expansion (E-GRAPH-ROLE, ADR-003) · twelve supervision-quality papers read in full (ADR-002 addendum) · edited functions are less often contamination hits (8.9% vs 13.7%; E-CONTAM-EDITED); Pro ansible added as third dev L3 repository (E-DEV-ANSIBLE) · encoder numbers (E-ENCODER-NUMBERS): Qwen3-Embedding-0.6B cannot take a float32 AdamW step on an 11 GB card · RQ3 power table extended (E-POWER update) · engineer defaults D25-D33 recorded in the owning ADRs · earlier: smoke pilots at 63 updates (E-PILOT-K/NEG/LEAK), training stack, pool ranks, dense numbers, contamination scan (see `RESULTS.md`) · **Milestone:** M0 (parser, first graph, BM25, loader and metrics) plus the RQ2 apparatus.

---

## One-line status

Research design is locked (Master Project Document rev 16, 2026-10-11). The repository is a working
Python 3.11 project: `make setup`, `make test`, `make test-all`, `make lint` pass. **Built so far:** the CodeUnit and its
helpers, the held-out filter, the repository parser, the typed graph builder (contain, import, invoke, inherit, override, plus
exploratory tests and configures), the edge-recovery measurements, the graph storage measurement and the
chunk-to-unit mapping with the graph-reach pilot, the BM25 index and the CORE-Bench loader and metrics (reproduce the published BM25 rows). BM25 and a **dense encoder with a flat exact index** (`provisional: ADR-006`) exist as retrieval signals; fusion,
graph expansion and a recency prior exist as measurement code only; no assembly. The RQ2 training stack exists (validated, nothing trained for a result). Latency harness: **built**; `parse`, `graph_build`, the graph
storage stages and now `bm25`, `graph_expand_1hop/2hop` and `graph_expansion` with a real index have rows (query-set ids `graph-<repo>-<backend>-v1`, `retrieval-<repo>-v1`).

## What is built

| Layer | State | Notes |
|---|---|---|
| Repo scaffold: folders, docs split from master, ADR stubs, specs, folder layout | done | |
| Package `ril/`, `pyproject.toml`, `Makefile`, tests, ruff, `mypy --strict` | done | Python 3.11 pinned; Poetry venv in `.venv`; Ada path (`uv`) in the Makefile header |
| `ril/config`, `ril/util` | done | no experiment parameters yet |
| Commit hook | done, opt-in | `make hooks` installs `scripts/hooks/latency_check.sh` as `10-latency` (runs `make bench-check`, stages the two CSVs; `RIL_LATENCY_HOOK=strict\|relaxed\|off`, strict default); **not installed yet** |
| CodeUnit schema | **FROZEN v1** (ADR-013) | `ril/parsing/code_unit.py`, `unit_id.py`, `repo_id.py`, `path_rules.py` per `specs/code_unit.md` (decision log D4-D11); `unit_type` has `module`; canonical bytes pinned by a golden test; class-unit `source` open (Q28; three forms measured, ADR-013 addendum of 2026-10-23) |
| Data access, formats, statistics | done | every card statistic re-measured; `knowledge/datasets/*.md`; `scripts/ada/README.md`; Ada reachable non-interactively |
| Held-out list, filter, leakage tests | done, list schema 2 | 605 core repositories + 169-repository Loc-Bench tier (switchable) + current-name aliases; `rule_counts`, `rename_resolution`, `content_overlap` in `ril/training/`; rebuild `python -I scripts/build_held_out.py`; resolution is partial without a token (see Blockers) |
| Paper notes and literature scan | done for the reading plan; fourth pass 2026-10-23 | `knowledge/papers/`, checked quote tables (`scripts/check_paper_note.py`); `LANDSCAPE.md` (per-RQ taken / open / contradicted, scan refreshed 2026-10-23 with queries and dates; RQ2 and graph leads still unread are listed there) |
| RepoGraph design | DRAFT v0, options only | `specs/repo_graph.md` (own version constant `REPO_GRAPH_SCHEMA_VERSION`), `docs/GRAPH_DESIGN.md`, ADR-011 Proposed; no choice made, no code |
| Latency harness | **built** | `ril/bench/` (`latency_harness.py`, `profile_stages.py`, `stub_stages.py`); `make bench` / `make bench-check`; logs `results/latency/{latency,throughput}_log.csv`; stages `query_encode`, `bm25`, `dense_search`, `graph_expansion`, `graph_expand_1hop`, `graph_expand_2hop`, `rrf_fusion`, `cross_encoder_rerank`, `assemble`, `end_to_end` (latency) and `parse`, `graph_build` (throughput); thresholds provisional (Q33); a real stage replaces a stub with one `REGISTRY.register` line and a new `query_set_id` |
| Parser and graph | **built** (first build 2026-10-17) | `ril/parsing/` (`repository_parser.py`, `call_graph.py`, `repo_graph.py`, `exploratory_edges.py`, `git_history.py`, `build.py`); `scripts/parse_repo.py PATH --repo-id owner/name --seed N`; own `ast` resolver `own-ast-resolver/v0` (`provisional: ADR-011`); class unit `source` = `full` by default, `header` and `header_sigs` selectable (`ParseOptions.class_source`, `provisional: ADR-013`, Q28); ambiguous invoke sites read through a policy (`ril/parsing/ambiguity_policy.py`: keep, drop, rebucket, max3; stored graph unchanged; Q35); byte-identical rebuilds; flask 974 units, requests 678, django 35,860 |
| Edge recovery, exploratory edges, storage options | **measured**, nothing chosen | ADR-012 (four recovery definitions with trade-offs), ADR-011 addendum (storage table), `results/tables/p_*.csv`, `RESULTS.md` rows `p-*`; tracer and comparators in `ril/evaluation/`, storage in `ril/bench/graph_storage.py`, `graph_measure.py` |
| BM25 | **built** (reference form), latency rows exist | `ril/retrieval/bm25_index.py`: reference tokenisation (stemmed, 33-word stop list) and Lucene-variant scoring, k1 1.5 / b 0.75 `provisional: ADR-004`, `top_k`; no identifier splitting or fields yet; `bm25` p50 0.04 ms on 974 units, 0.20 ms on 35,860 (local) |
| Graph expansion, recency prior (pilot code) | **piloted** (exploratory) | `ril/retrieval/graph_expansion.py` (hop decay, edited list and RRF-fused list, chance controls), `recency.py`; `ril/evaluation/e3_prepare.py` (instance cache), `e3_eval.py` (grids; refuses to sweep on test instances), `e6_dense.py` (dense scores, never run); `ril/analysis/e3_tables.py`, `fitted_weights.py`; `docs/EXPERIMENTS.md` E-GRAPH-SIGNAL, E-GRAPH-WEIGHTS, E-RECENCY, `RESULTS.md` rows `e3-*`, `e4-*`, `e5-*`; structure variants on the same cache: `ril/evaluation/{x1_prepare,x1_eval,policy_readers}.py`, `ril/analysis/{x1_tables,l3_census}.py` (E-CLASS-SOURCE, E-AMBIG-POLICY, E-L3-CENSUS, rows `x1-*`; clustered bootstrap added to `e3_tables.Boot`); none of it is a design choice (Q30) |
| Dense encoder, flat exact index | **built**, measured zero-shot | `ril/retrieval/dense_encoder.py` (CodeRankEmbed, Qwen3-Embedding-0.6B, revisions pinned, `provisional: ADR-006`); cluster pipeline `ril/evaluation/{x2_dense,x2_jobs}.py`, evaluation `x2_eval.py`, tables `ril/analysis/x2_tables.py`; latency `ril/bench/dense_measure.py` (stages `query_encode`, `dense_search`, throughput `dense_encode`); `docs/EXPERIMENTS.md` E-DENSE-FUSION, rows `x2-*`, ADR-006/ADR-003 addenda; 2.84 GPU-hours of block 1 |
| Pool ranks (K-rank teachers) | **measured** (exploratory) | `ril/training/{pool_ranks,pool_rank_jobs}.py`, `ril/analysis/x3_tables.py`, `scripts/pool_ranks.py`, jobs `scripts/ada/x3_*.sbatch`; SweRankEmbed-Small registered as a teacher (`dense_encoder.py`); 160 stratified directories, 1,522 positives, plus the never-filtered Verified export (457); per-positive rank table `results/tables/x3_pool_ranks_features.csv`; full-pool job resumable, about 4.9 GPU-hours per dense teacher (not run); 1.25 GPU-hours of block 1 |
| Fusion, assemble | fusion measured (RRF, score level), not a stage; assembly not started | |
| Training stack (RQ2 apparatus) | **built** (2026-10-25), nothing trained for a result | `ril/training/` (`pool_reader`, `negatives`, `supervision`, `data_loader`, `contrastive_loss`, `encoders`, `training`, `train_jobs`), `ril/evaluation/checkpoint_eval.py`, `scripts/train.py`, jobs `scripts/ada/t1_validate.sbatch`, `t1_train.sbatch` (GPU template, CUDA gate); arms enter only through filter / weights / ordering (identity test bit-exact; DEV-012: negative policy held identical); K-rank from the X3 feature table; every training value `provisional: ADR-001, ADR-002, ADR-006`; validated on 24 real pool directories on the cluster CPU (rows `t1-*`) |
| Wave 4 block 1 (evidence, exploratory) | **run** (2026-10-29) | graph role `ril/evaluation/s1_graph_role.py`, `ril/analysis/s1_tables.py` (E-GRAPH-ROLE); twelve paper notes in `knowledge/papers/`; `ril/training/contamination_edited.py`, `ril/analysis/x5_tables.py` (E-CONTAM-EDITED), dev config `configs/experiments/e1_bm25_dev3.yaml` (E-DEV-ANSIBLE); `ril/evaluation/e7_encoders.py`, `ril/analysis/e7_tables.py` (E-ENCODER-NUMBERS); `ril/analysis/rq3_power.py` (E-POWER update); 0.07 GPU-hours |
| Smoke pilots (RQ2 evidence) | **run** (2026-10-29, exploratory) | `configs/experiments/t2/` (36 configurations), `configs/experiments/t2_pilots.yaml`, teacher pass and run batches (`scripts/train.py teacher|features|run-batch`, `scripts/ada/t2_*.sbatch`), tables `ril/analysis/t2_tables.py` / `scripts/t2_tables.py`; `docs/EXPERIMENTS.md` E-PILOT-K/NEG/LEAK, rows `t2-*`, ADR-001/ADR-002 addenda of 2026-10-29 |
| Evaluation: chunk-to-unit mapping, graph-reach pilot | **piloted** (exploratory) | `ril/evaluation/chunk_mapping.py`, `graph_reach.py`, `chunk_unit_pilot.py`, `ril/analysis/reach_tables.py`; 160 of 160 positives of flask, requests, seaborn found by exact text (D7 stands), residual share 16 of 160 (D6 stands); `docs/EXPERIMENTS.md` E-GRAPH-REACH, `RESULTS.md` rows `m-*`; job `scripts/ada/m_chunk_unit_reach.sbatch` (about 35 s) |
| Evaluation: CORE-Bench loader, metrics, unit-level BM25, label-noise readings | **built, piloted** (exploratory) | `ril/evaluation/{core_bench,metrics,unit_retrieval,label_noise,e1_run}.py`; reproduces Verified L2 11.94 / 46.74, L3 22.19 / 33.89 and all-L2 13.00 / 38.82 (mean over folders; paper 11.9 / 46.7, 22.2 / 33.9, 13.0 / 38.8); `docs/EXPERIMENTS.md` E-BM25-REPRO, E-LABEL-NOISE, `RESULTS.md` rows `e1-*`, `e2-*`; jobs in `scripts/ada/README.md` |
| Agent integration | not started | |
| Dev / test repositories | **set** (2026-10-18) | dev: Pro openlibrary and qutebrowser, Live conan, haystack, streamlink (355 instances; base commits from the datasets' metadata); test: Verified (12 folders, six with units); `configs/experiments/e1_bm25_reproduction.yaml`; sweeps on role `dev` only |

## Decisions log (closed 2026-10-17 and 2026-10-18 by the engineer; reasoning, evidence class and flip experiments in the owning document; index in `decisions/README.md`)

| D (was) | Decision in one line | Owner |
|---|---|---|
| D1 (Q8) | held-out matching = exact names + current-name resolution; fork network = sensitivity only; content-overlap audit reported | `specs/held_out_repos.md`, ADR-001 |
| D2 (Q22) | read-only `GITHUB_TOKEN` on Ada, never printed or stored | same |
| D3 (Q9) | Loc-Bench held out as a separate switchable tier | `specs/held_out_repos.md`, ADR-005 |
| D4 (Q13) | relations in a separate edge store; CodeUnit lists hold resolved ids only | `specs/code_unit.md`, ADR-013 |
| D5 (Q14) | `repo_id` = `owner/name` case-folded; commit in the container; aliases for renames | same |
| D6 (Q15) | top-level functions, methods, classes + one residual `module` unit per file | same, ADR-004 |
| D7 (Q16) | chunk-to-unit link is a derived mapping built by the evaluation loader | same, ADR-004 |
| D8 (Q17) | `last_modified` = last commit time <= snapshot, or `""` | same |
| D9 (Q18) | `is_test` = file-level path rule (agrees with pytest on 3 repositories) | same |
| D10 (Q19) | `tests` filled by the graph build; `[]` = not computed | same |
| D11 (Q20) | id `path::Qual.name`, `#2` ordinal on collisions, converter to the pool form | same |
| D12 (Q21) | unit-level evaluation primary on Verified (432 L2, 302 L3); other sub-datasets chunk-level | ADR-004, ADR-005 |
| D13 (Q23) | Rewrite runs scored against the original qrels; 158 folders reported as a packaging defect | ADR-005, DEV-008 |
| D14 (Q24, Q25) | "covered by nobody" reworded to "no ablation shows the value of test and configuration links"; derived copies corrected in place with "(corrected, see DEV-0nn)" | DEV-010, DEV-011, ADR-003 |
| D15 (Q27) | edge recovery reported as dynamic-oracle recall (with and without implicit callees, n stated) beside the call-site breakdown with denominators named; "70-85%" not repeated | ADR-012 |
| D16 (Q38) | first stored graph read into an in-memory adjacency from a typed edge-list file; no graph database | ADR-011, `specs/repo_graph.md` |
| D17 (Q40) | primary averaging = mean over queries with repository-clustered bootstrap intervals; folder means only in the reproduction table | ADR-005 |
| D18 (Q39, Q41) | a chunk's positive counts for every unit it overlaps; gold without module residuals primary for graph decisions, CORE-Bench-faithful reading beside it; **provisional**; checked 2026-10-23: class-source and policy orderings do not flip, some edge-subset orderings do (among overlapping intervals, ADR-004 addendum); X2 (2026-10-25): the stated selections and every Verified ordering are the same under both readings; on dev, CodeRankEmbed alone is 3.5 below BM25 at L3 under the primary reading and level with it under `units_all` (one flip larger than 2.5 points; ADR-006 addendum) | ADR-004 |
| D19 (Q37) | first stored graph: contain, invoke, import, inherit/override; tests, configures, co_change built but off by default | ADR-011 |
| D20 (Q29, Q32, Q34) | readings in code accepted (module unit fields, timestamp form; `tests(u)`/`configs(u)` projections; offline stages in the throughput log); Q3 strict, Q33 provisional | `specs/code_unit.md`, `specs/repo_graph.md`, `specs/latency_harness.md`, ADR-013 |
| D21 (Q42) | GPU use authorised: block 1 <= 8 GPU-hours, block 2 <= 24, logged per job | ADR-006, `docs/COMPUTE.md` |
| D22 (Q43) | pool filter-state experiment (X3) runs; the pool is `gangiswag/train_data` python minus the held-out list, `provisional: ADR-001`; X3 reported 2026-10-25 (ADR-001, ADR-002 addenda): qrels unfiltered per positive (RAW available), directories selected w.r.t. SweRankEmbed-Small (PR-level filter or teacher fit, open: Q50) | ADR-001 |
| D23 (Q44) | full documents-only contamination scan in the background (X4), base-commit functions above a size floor; not part of the frozen evaluation; X4 done 2026-10-29: 13.7% of base-commit functions (floor 20 nodes) occur in the corpus, edited-function check done 2026-10-29 (8.9% of 783 edited functions vs 13.7%; flip condition not met) | ADR-005, `docs/EXPERIMENTS.md` |
| D24 | not decided in advance, settled by this wave's measurements: Q28, Q35/Q36, Q30, ADR-006 encoder, ADR-001 pool (after X3); Q45 waits for ADR-007; Q1, Q4 the engineer's | owning ADRs |
| D25 (Q28) | class unit `source` stays `full` (+2.3 nDCG@10 under D18 gold, +55% tokens); dense check: `header` is below `full` in every cell | ADR-013 addendum |
| D26, D27 (Q35, Q36) | ambiguous call sites dropped in the stored graph; `external`/`unresolved` boundary accepted as built | ADR-011 addendum |
| D28, D30, D31 (Q51, Q52, Q53; Q46 primary) | one negative policy for all arms (primary random repository-local, secondary teacher top-M with the cut, exploratory); teacher cells run not chosen; base CodeRankEmbed; batch 32 x (1+1), fp16, checkpointing, 512 tokens (DEV-012, DEV-013) | ADR-002 addendum |
| D29 (Q50) | pool accepted with its limitation: directories selected w.r.t. SweRankEmbed-Small, positives inside not filtered; E-POOL-DATES skipped (no token) | ADR-001 addendum |
| D32 (Q47) | Pro ansible (83 instances) is a third dev L3 repository; Verified stays final test | ADR-005 addendum |
| D33 (Q48) | no Qwen3 instruction variants unless Qwen3 would win the choice | ADR-006 addendum |

## Next task

**Block 2 of the supervision pilots (T3, then T4).** Budget: 24 GPU-hours in total for Block 2 (Wave 3 spent 17.00 of its 24; this wave's Block 1 used 0.07 of its 2, so the cap is the full 24, which includes the 7.0 unspent). Account A only.
T3 (about 5 GPU-hours): RAW only, CodeRankEmbed base, D28 primary negatives, D31 shape, 3,000 updates per seed, 2 seeds, checkpoints at 0, 100, 300, 1000, 2000, 3000, each evaluated on dev L2 and on L3 over three repositories. Pass for the dev evaluation: `--e1-config configs/experiments/e1_bm25_dev3.yaml --prep ~/ril_x2/prep --e3-cache ~/ril_t1/work/e3_cache --data-root ~/ril_x2/raw`. Record the curve as E-PILOT-CURVE and the update count N (smallest at or past the knee, at most 2,000); if there is no movement at 3,000 updates, stop after T3 and report.
T4 (about 15 GPU-hours, only if T3 found movement): RAW; FILTER with teachers BM25, SweRankEmbed-Small, CodeRankEmbed at K = 20; RAW and the best FILTER cell again under the secondary negative policy; 2 seeds; dev only, exploratory, outside the RQ tables, repository-clustered intervals; WEIGHT and CURRICULUM only if budget remains.
**Local machine: editing, `make lint`, `make test` (one worker) and git only**; torch tests run as `scripts/ada/t1_tests.sbatch`; checkpoints go to node-local `/tmp`.
For the engineer: ADR-001..010 are open and now have the evidence of Waves 3 and 4 behind them (ADR-002 reading addendum, ADR-003 graph role, ADR-006 encoder numbers); answer Q54 (how to train Qwen3 or stay retrieval-only), Q55 (query-latency budget), Q56 (reversed-order CURRICULUM control and a self-teacher warm-up cell) and the RQ3 question under Q45 (hypothesis test or effect estimate; the deciding number is the smallest resolved-rate difference worth reporting); answer `data/review/spot_check.md` and run `python -I scripts/spot_check_agree.py ANSWERS.csv`; correct the master document per DEV-011 and DEV-005 to DEV-007.

## Blockers

Accounts: only account A has an SSH alias locally; B and C are not configured, so all jobs run on A (the engineer adds the aliases). Data: `GITHUB_TOKEN` is **not set on Ada** (decision D2): E-POOL-DATES (D29 flip experiment) was skipped, the rename cache holds 108 repositories and every post-rename count is a lower bound until the token exists. Compute: `$HOME` on A has about 0.5 GB free (`~/ril_x1/work_census_*`, 1.4 GB regenerable, could be deleted by the engineer), so checkpoints use node-local `/tmp` and a resubmission on another node restarts the run (`docs/COMPUTE.md`); no card above 11 GB is reachable from A. Q7: the intended pool is not confirmed (the directories hold 307,996 positive rows, not the table's 49,973 instances; the pool stays `provisional: ADR-001`). CORE-Bench corpora are streamed, not stored. No code blocker.

## Open questions

| # | Question | Blocks | Resolve by |
|---|---|---|---|
| Q1 | Which team member is Person A / B / C (owners in `docs/ROADMAP.md`)? | ownership columns | engineer, week 1 |
| Q3 | Does a docs-only commit need a fresh latency row, or may it reference the previous row? Harness implements both behind `RIL_LATENCY_HOOK` (strict default); the hook is not installed until the engineer runs `make hooks` | hook setting | stays strict (D20); engineer |
| Q33 | Regression thresholds in `configs/bench/latency.yaml` (p50 or p95 up by more than 50% and 0.5 ms vs the previous comparable row) are conservative placeholders, `provisional: Q33`; also whether a failing run is logged (now: not, unless `--append-on-fail`) | `make bench-check`, hook | stays provisional until real stages have rows (D20); engineer, before the freeze |
| Q4 | GitHub remote(s) for the team repo; the engineer performs every push | publishing only | engineer |
| Q5 | ADR-001...ADR-010 (training pool, quality signal, graph role, granularity, benchmark, encoder, scaffold, LLM, rerank, usable-by-others) | frozen config, RQ2 start | team, end of week 2 |
| Q7 | Is the candidate pool intended, or is the pool built with the published scripts? Read in full: `gangiswag/train_data` python = SweLocMulti's Python part (SweRank+ Table 1: 2,448 repositories, 24,285 PRs, 49,973 instances), not the original SweLoc (3,387 repositories); SweRank+ states no benchmark-repository exclusion; 89 held-out repositories (3,431 PRs, 14.13%) occur in it (DEV-004). Loc-Bench: 560 rows (V1) vs 660 (V0.2) | ADR-001, pool filter | engineer (D22: provisional pool meanwhile); X3 evidence in the ADR-001 addendum of 2026-10-25 |
| Q11 | CORE-Bench evaluation is whole-snapshot retrieval: each query's candidate list is the repository snapshot at the base commit (paper Sec. 4.1; 12,153 of 12,153 list chunks located in 11 base-commit checkouts; DEV-003), and chunk ids carry no path or line span. D7 and D12 fix the mapping and the primary set; pilot M located 160 of 160 positives by exact text (three repositories); still open: the reported-metric granularity and whether chunk-level numbers are also reported (ADR-004) | ADR-004, evaluation | engineer |
| Q12 | CORE-Bench L3 labels are LLM-judged; the paper does not say how the three votes combine into the kept score (R1); released qrels are binary; L2 positives include import blocks (3 of 53 sampled) | RQ3 interpretation | note in report |
| Q30 | Graph role(s) in the frozen configuration. Measured 2026-10-29 (E-GRAPH-ROLE, ADR-003): on the fused first stage, same-file expansion ordered by first-stage score is level with or above the stored graph at L3 (Verified-six, graph minus it -2.7 [-6.0, 0.8] and -2.0 [-5.2, 0.8] for the two encoders); contain-only equals the stored graph (contain edges never leave a file); non-contain-only is 6 to 7 points below; non-contain edges reach about 8% of missed L3 gold units from the top 5 in two hops. So no evidence that typed edges add to file-level expansion; training-time structure and agent-tool roles are unmeasured. Cheapest further test: stacked expansion (same-file by score, lowest 10 and 25 replaced by the best non-contain neighbours, same budget) | ADR-003, frozen config | engineer; evidence in ADR-003 |
| Q31 | ADR-011 schema choices still open (`specs/repo_graph.md` Q-G3 to Q-G11, Q-G13; storage read structure D16, first families D19, projections D20 and recovery reporting D15 are decided): `test` as flag or kind; which files are config/document; optional edge fields (`site`, `target_text`, `count`); `external` vs `unresolved` boundary; one graph per commit vs validity ranges; resolver per family; which families are in the first stored graph; storage option (measured in the first graph build) | ADR-011, first graph build | engineer, after the build |
| Q45 | RQ3 design and sample size: hypothesis test or effect estimate with an interval? Minimum detectable effect (exact McNemar, power 0.8) is 4.5 / 5.5 / 6.25 / 7.75 points at n = 432 for discordance 10 / 15 / 20 / 30%, 3.25 to 5.25 at n = 900; the one published fixed-agent retrieval swap read in full differs by -0.6 to +1.2 points (`paper_reported`, one run, derived discordance about 14%), below every cell. Deciding number: the smallest resolved-rate difference worth reporting (5 to 6 points or more: a test is feasible at Verified sizes; 3 points or less: only an estimate, interval about +/- 3.7 at n = 432). Discordance and run-to-run SD need one agent pilot | RQ3 design, run count | engineer (`docs/EXPERIMENTS.md` E-POWER, ADR-007 note) |

| Q54 | Qwen3-Embedding-0.6B does not take one float32 AdamW step on an 11 GB card at any batch (peak 10.6 GiB; about 24 GiB reasoned for a fitting step). Options: train only CodeRankEmbed (Qwen3 stays zero-shot, retrieval-only); a recipe change (8-bit optimizer states, half-precision master weights, adapters, gradient caching; a changed held-identical recipe); a 24 GB-class card on a partition the account can use. Measured: OOM; reasoned: the rest | ADR-006, RQ2 base | engineer (ADR-006) |
| Q55 | Query-latency budget for the encoder choice: warm p50 GPU 18.1 ms (CodeRankEmbed) vs 45.2 ms (Qwen3), CPU 411 ms vs 1,533 ms; the paired fused gain is +1.85 (Verified-six L2, interval includes 0) and +3.43 (L3, clustered interval includes 0) | ADR-006 | engineer |
| Q56 | R5 shows two cheap controls the arms lack: a reversed-order CURRICULUM cell (pacing and a reversal control are what make a curriculum claim interpretable) and a warm-up before the self-teacher cell (every learner-as-judge paper adds one). Not added to the arms; about 0.5 GPU-hours per cell at pilot size | ADR-002, T4 | engineer |
Resolved this block (as engineer defaults, evidence class in the owning ADR): Q28 (D25), Q35, Q36 (D26, D27), Q46 primary and Q51, Q52, Q53 (D28, D30, D31), Q50 (D29, with the limitation stated), Q47 (D32), Q48 (D33); Q49 answered by E-GRAPH-ROLE (evidence only; Q30 stays open). Earlier: Q24, Q25, Q27, Q29, Q32, Q34, Q37, Q38, Q40, Q42 (D14-D21); Q39, Q41 provisionally (D18); Q43 (D22); Q44 (D23, edited-function check done: flip condition not met); Q8, Q9, Q13-Q23, Q26, Q10, Q2, Q6.

## Pre-push checklist (before the engineer's first push)

- Remove real Ada login names, the course code and key file names from tracked files (accounts as A, B, C only; the mapping
  stays in an untracked local note). Do it then, not now (engineer, 2026-10-25).

## Carried debt

None.

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Retrieval stack not frozen before RQ2 starts | RQ2 arms differ in more than supervision | latency optimisation and config freeze land before week 6; `configs/frozen/` is immutable after freeze |
| Repository leakage between training pool and L2/L3/Verified | invalidates RQ2 and RQ3 | repo-level disjointness test in `tests/leakage/`; held-out list built first |
| CORE-Bench ships no train split (SFT set unreleased) | "train on CORE-Bench" has no referent | SweLoc + own PR-mined set (ADR-001) |
| Week-12 go/no-go: fewer than two distinguishable retrievers | RQ3 cut | fallback declared in the proposal; ships as RQ1 + RQ2 + latency analysis |
| Ada: throttled downloads, quota, QOS changes, bad GPU nodes | slow or failed jobs | `docs/COMPUTE.md` lessons; resumable downloads; GPU-capability gate |
| Schedule slip on parser/graph (Person A critical path) | RQ1 and graph extension late | week-3 milestone check; CodeUnit frozen in week 1 so others are unblocked |

---

## Maintenance rule

This file is **replaced, not appended.** At the end of each working block:

1. Rewrite the tables above so they describe reality *now*.
2. Delete anything resolved. A closed question leaves this file entirely — its reasoning lives in
   the ADR, `RESULTS.md` row or commit message that closed it.
3. Do not paste benchmark output here. One aggregate number max; details go to `RESULTS.md`.
4. Do not paste narrative here.
5. If you are about to add a fifth row to a table that already has ten, something is being tracked
   at the wrong granularity — move it to `docs/ROADMAP.md`.

**Why the cap exists:** this file is read at the start of every working block. A 200-line file
costs seconds. Left to grow it becomes thousands of lines of resolved history, gets skimmed instead
of read, and stops working precisely when the project is complex enough to need it. Pruning it is
part of the task, not cleanup after the task.

## Boundaries with other docs

| File | Holds | Volatility |
|---|---|---|
| `PROJECT_STATE.md` | what is true right now | rewritten at the end of each block of work |
| `docs/ROADMAP.md` | the plan, weeks 1–16, checkboxes | ticked, rarely restructured |
| `RESULTS.md` | every benchmark ever run, one line each | append-only |
| `decisions/` | why each significant choice was made | ADR per decision, addenda not overwrites |
| `docs/DEVIATIONS.md` | departures from the master doc | append-only |
| `docs/EXPERIMENTS.md` | experiment registry: IDs, protocol, status | updated as experiments are planned/run |
| `docs/0*–12*` | design, split from the master doc by topic | stable; master wins on conflict |

If a fact could go in two of these, it goes in exactly one — the leftmost row that fits.
