# Project State

> **Current truth only.** Not a history. History lives in `RESULTS.md` and the git log.
> **Hard cap: 200 lines.** If this file exceeds it, the fix is to *delete resolved content*,
> not to add a summary. See the maintenance rule at the bottom.

**Last updated:** 2026-11-01 (review tooling added) · earlier: 2026-10-31 (documentation and tree consolidation after Waves 1 to 6 and the merge of a/rq1: incremental graph updates and the BM25 identifier-splitting pilot; end of Wave 6: teacher ranks for the 5,000-directory pool and the matched-pool arms pilot E-PILOT-ARMS2, evidence only, nothing decided by the sessions) · no supervision cell beats RAW or the size-matched subsample beyond seed noise; NOISE (Wave 5) stays at the untrained encoder · Block 2 at 45.15 of 46 GPU-hours (all on account A) · earlier: RAW curve, graph role, twelve supervision-quality papers, contamination, encoder numbers, power table, D25-D39 · **Milestone:** M0 (parser, first graph, BM25, loader and metrics) plus the RQ2 apparatus.

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
| Parser and graph | **built** (first build 2026-10-17) | `ril/parsing/` (`repository_parser.py`, `call_graph.py`, `repo_graph.py`, `exploratory_edges.py`, `git_history.py`, `build.py`, `incremental.py` = per-commit updater equal to the full rebuild on 100 of 100 commits, Q58); `scripts/parse_repo.py PATH --repo-id owner/name --seed N`; own `ast` resolver `own-ast-resolver/v0` (`provisional: ADR-011`); class unit `source` = `full` by default, `header` and `header_sigs` selectable (`ParseOptions.class_source`, `provisional: ADR-013`, Q28); ambiguous invoke sites read through a policy (`ril/parsing/ambiguity_policy.py`: keep, drop, rebucket, max3; stored graph unchanged; Q35); byte-identical rebuilds; flask 974 units, requests 678, django 35,860 |
| Edge recovery, exploratory edges, storage options | **measured**, nothing chosen | ADR-012 (four recovery definitions with trade-offs), ADR-011 addendum (storage table), `results/tables/p_*.csv`, `RESULTS.md` rows `p-*`; tracer and comparators in `ril/evaluation/`, storage in `ril/bench/graph_storage.py`, `graph_measure.py` |
| BM25 | **built** (reference form), latency rows exist | `ril/retrieval/bm25_index.py`: reference tokenisation (stemmed, 33-word stop list) and Lucene-variant scoring, k1 1.5 / b 0.75 `provisional: ADR-004`, `top_k`; identifier splitting and field weights exist as options (workstream A, local pilot only; the reference form is the default); `bm25` p50 0.04 ms on 974 units, 0.20 ms on 35,860 (local) |
| Graph expansion, recency prior (pilot code) | **piloted** (exploratory) | `ril/retrieval/graph_expansion.py` (hop decay, edited list and RRF-fused list, chance controls), `recency.py`; `ril/evaluation/e3_prepare.py` (instance cache), `e3_eval.py` (grids; refuses to sweep on test instances), `e6_dense.py` (dense scores, never run); `ril/analysis/e3_tables.py`, `fitted_weights.py`; `docs/EXPERIMENTS.md` E-GRAPH-SIGNAL, E-GRAPH-WEIGHTS, E-RECENCY, `RESULTS.md` rows `e3-*`, `e4-*`, `e5-*`; structure variants on the same cache: `ril/evaluation/{x1_prepare,x1_eval,policy_readers}.py`, `ril/analysis/{x1_tables,l3_census}.py` (E-CLASS-SOURCE, E-AMBIG-POLICY, E-L3-CENSUS, rows `x1-*`; clustered bootstrap added to `e3_tables.Boot`); none of it is a design choice (Q30) |
| Dense encoder, flat exact index | **built**, measured zero-shot | `ril/retrieval/dense_encoder.py` (CodeRankEmbed, Qwen3-Embedding-0.6B, revisions pinned, `provisional: ADR-006`); cluster pipeline `ril/evaluation/{x2_dense,x2_jobs}.py`, evaluation `x2_eval.py`, tables `ril/analysis/x2_tables.py`; latency `ril/bench/dense_measure.py` (stages `query_encode`, `dense_search`, throughput `dense_encode`); `docs/EXPERIMENTS.md` E-DENSE-FUSION, rows `x2-*`, ADR-006/ADR-003 addenda; 2.84 GPU-hours of block 1 |
| Pool ranks (K-rank teachers) | **measured** (exploratory) | `ril/training/{pool_ranks,pool_rank_jobs}.py`, `ril/analysis/x3_tables.py`, `scripts/pool_ranks.py`, jobs `scripts/ada/x3_*.sbatch`; SweRankEmbed-Small registered as a teacher (`dense_encoder.py`); 160 stratified directories, 1,522 positives, plus the never-filtered Verified export (457); per-positive rank table `results/tables/x3_pool_ranks_features.csv`; full-pool job resumable, about 4.9 GPU-hours per dense teacher (not run); 1.25 GPU-hours of block 1 |
| Fusion, assemble | fusion measured (RRF, score level), not a stage; assembly not started | |
| Training stack (RQ2 apparatus) | **built** (2026-10-25), nothing trained for a result | `ril/training/` (`pool_reader`, `negatives`, `supervision`, `data_loader`, `contrastive_loss`, `encoders`, `training`, `train_jobs`), `ril/evaluation/checkpoint_eval.py`, `scripts/train.py`, jobs `scripts/ada/t1_validate.sbatch`, `t1_train.sbatch` (GPU template, CUDA gate); arms enter only through filter / weights / ordering (identity test bit-exact; DEV-012: negative policy held identical); K-rank from the X3 feature table; every training value `provisional: ADR-001, ADR-002, ADR-006`; validated on 24 real pool directories on the cluster CPU (rows `t1-*`) |
| Wave 4 block 1 (evidence, exploratory) | **run** (2026-10-29) | graph role `ril/evaluation/s1_graph_role.py`, `ril/analysis/s1_tables.py` (E-GRAPH-ROLE); twelve paper notes in `knowledge/papers/`; `ril/evaluation/contamination_edited.py`, `ril/analysis/x5_tables.py` (E-CONTAM-EDITED), dev config `configs/experiments/e1_bm25_dev3.yaml` (E-DEV-ANSIBLE); `ril/evaluation/e7_encoders.py`, `ril/analysis/e7_tables.py` (E-ENCODER-NUMBERS); `ril/analysis/rq3_power.py` (E-POWER update); 0.07 GPU-hours |
| Arms pilot (RQ2 evidence) | **run** (2026-10-31, exploratory) | `configs/experiments/t4/` (24 stage-1 and 6 stage-2 configurations), `budget.stop_after` (complete at N on a longer schedule), NOISE control and reversed-order CURRICULUM in `ril/training/supervision.py`, tables `ril/analysis/t4_tables.py` / `scripts/t4_tables.py`, job `scripts/ada/t4_runs.sbatch`; `docs/EXPERIMENTS.md` E-PILOT-ARMS; 11.4 GPU-hours |
| Matched-pool arms pilot (RQ2 evidence) | **run** (2026-10-31, exploratory) | pool ranks for 5,000 directories (a K-rank feature table kept on the cluster, 62,238 positives, 0 held-out; 3.16 GPU-hours), `RAW_SUBSAMPLE` arm in `ril/training/supervision.py`, configs `configs/experiments/t5/` (stage 1: 2 seeds x 7 cells; stage 2: seed 0 x 3 cells), tables `ril/analysis/t5_tables.py` / `scripts/t5_tables.py`, job `scripts/ada/t5_runs.sbatch`; `docs/EXPERIMENTS.md` E-PILOT-ARMS2, RESULTS rows `p0-pool-ranks`, `t5-arms2`; 11.5 GPU-hours; DEV-014 |
| Smoke pilots (RQ2 evidence) | **run** (2026-10-29, exploratory) | `configs/experiments/t2/` (36 configurations), `configs/experiments/t2_pilots.yaml`, teacher pass and run batches (`scripts/train.py teacher|features|run-batch`, `scripts/ada/t2_*.sbatch`), tables `ril/analysis/t2_tables.py` / `scripts/t2_tables.py`; `docs/EXPERIMENTS.md` E-PILOT-K/NEG/LEAK, rows `t2-*`, ADR-001/ADR-002 addenda of 2026-10-29 |
| Evaluation: chunk-to-unit mapping, graph-reach pilot | **piloted** (exploratory) | `ril/evaluation/chunk_mapping.py`, `graph_reach.py`, `chunk_unit_pilot.py`, `ril/analysis/reach_tables.py`; 160 of 160 positives of flask, requests, seaborn found by exact text (D7 stands), residual share 16 of 160 (D6 stands); `docs/EXPERIMENTS.md` E-GRAPH-REACH, `RESULTS.md` rows `m-*`; job `scripts/ada/m_chunk_unit_reach.sbatch` (about 35 s) |
| Evaluation: CORE-Bench loader, metrics, unit-level BM25, label-noise readings | **built, piloted** (exploratory) | `ril/evaluation/{core_bench,metrics,unit_retrieval,label_noise,e1_run}.py`; reproduces Verified L2 11.94 / 46.74, L3 22.19 / 33.89 and all-L2 13.00 / 38.82 (mean over folders; paper 11.9 / 46.7, 22.2 / 33.9, 13.0 / 38.8); `docs/EXPERIMENTS.md` E-BM25-REPRO, E-LABEL-NOISE, `RESULTS.md` rows `e1-*`, `e2-*`; jobs in `scripts/ada/README.md` |
| Review tooling | **built** (2026-11-01) | `scripts/review_flags.py` (`ril/util/review_flags.py`): blocking and warning flags on a branch's added lines plus a trace of ledger and "Result" numbers to files under `results/`; `make review-flags BASE=main`, `make review`; standard in `docs/REVIEW.md`; `.github/pull_request_template.md`, `.github/workflows/ci.yml` (minimum, not a verdict). Over `foundation-v0..main`: 47 blocking (34 login-name paths in tracked run logs, 10 suppressions without a reason, 3 unsourced numbers), 0 false positives after one narrowing |
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

Order: (1) what the engineer decides, (2) Person A, (3) Person C, (4) what the engineer does outside the repository. `origin/main` equals local `main`; workstream A must merge `main` into `a/rq1` before its next block.

**1. The engineer decides (nothing below is decided by a session; ADR-001 to ADR-010 are all `Proposed`).** Evidence is in each ADR's addenda; the registry entry is in `docs/EXPERIMENTS.md`; open Q numbers are in the table below.

| ADR | Evidence now (where) | Open Q |
|---|---|---|
| 001 pool | filter state under three teachers, leak pilot, 5,000-directory ranks with 0 held-out (ADR-001 addenda 2026-10-25, 2026-10-29; E-POOL-RANKS) | Q7 |
| 002 quality signal | RAW +9.6 / +11.1 over the untrained encoder at 100 updates; NOISE stays at the untrained encoder; no supervision cell above RAW or the size-matched subsample beyond seed noise (ADR-002 addenda 2026-10-30, 2026-10-31; E-PILOT-ARMS, E-PILOT-ARMS2) | spend or keep the last 0.85 GPU-hours of Block 2 (cap 46; one 100-update run costs 0.38); raise the cap for a third seed, the other two subsample draws, stage 2 seed 1, ansible (about 10 to 12 GPU-hours together); make the T5b trigger one-sided (WEIGHT 0.3 below RAW fired it); run the self-teacher cell D40 only if a static teacher separates (has not happened) |
| 003 graph role | same-file expansion level with the stored graph on the fused first stage (ADR-003 addenda 2026-10-25, 2026-10-29; E-GRAPH-ROLE); training-time and agent-tool roles unmeasured | Q30, Q31 (schema, ADR-011) |
| 004 granularity | unit-level primary under D18; BM25 rows reproduced; chunk mapping 160 of 160 (ADR-004 addenda) | Q11, Q59 |
| 005 benchmark | Verified final test, dev repositories, contamination 13.7% / 8.9% edited (ADR-005 addenda; E-CONTAM-EDITED) | Q12 |
| 006 encoder | zero-shot numbers, cost, training memory (ADR-006 addenda; E-ENCODER-NUMBERS); base CodeRankEmbed is the working default (D30) | none |
| 007 scaffold, 008 LLM | RQ3 power table only (E-POWER); no agent pilot | Q45 |
| 009 rerank, 010 usable by others | none; rerank unmeasured | none |

Also yours: Q3 and Q33 (latency hook setting, thresholds) before the freeze; Q57 and Q58 below.

**2. Person A (workstream A, merged 2026-10-31; status page `docs/status/person_a.md`; A's requests are Q57 to Q59, the engineer settles them).** Next for A: the A1 development-set runs on the cluster once an account login exists, then A2 (b) and (c). Needs from C: none yet. Not re-verifiable from stored output: the "2 of 4,163 edges" resolver-fix figure (no stored edge diff).

**3. Person C.** No status page and no merged branch from C exists in the repository. Roadmap items waiting on C: Rewrite-split loaders, the own PR-mined training set, agent integration and the paired RQ3 runs (`docs/ROADMAP.md`). Ask C for a status page in the format of `docs/status/person_a.md` and for the PR set's provenance record.

**4. The engineer outside the repository.** (a) Set `GITHUB_TOKEN` (read-only) on Ada, decision D2: unblocks the rename cache and E-POOL-DATES. (b) Give the second-reader spot-check sheet to the second reader (`data/review/`, untracked; built by `scripts/build_spot_check.py`, scored by `scripts/spot_check_agree.py`; context in ADR-012). (c) Apply the master-document corrections listed in DEV-011 and the derived-copy rule in DEV-010. (d) The run logs under `results/logs/t5*` and `results/rq2/t5*` hold a cluster home path with the account's login name (34 lines); remove or replace it before the first push (`make review-flags` lists them). (e) Add the SSH aliases for accounts B and C so jobs can use them (Block 2 is at 45.15 of 46 on account A).

**What the two arms pilots together support** (exploratory, measured, dev repositories only, one encoder; detail in ADR-002 and `docs/EXPERIMENTS.md`). Correct supervision matters: the gain needs correct positives (NOISE control). Quality beyond quantity has no evidence here: FILTER, WEIGHT and CURRICULUM are within about 1 point of RAW, and FILTER cells are 0.7 to 1.1 below the size-matched subsample at L3. The minimum detectable difference at three seeds is 1.4 (L2) and 1.7 (L3), above every observed gap. Unresolved: the subsample is +1.31 above RAW at stage 1 but -1.70 below at stage 2 (seed 0). Weak points: two seeds, two to five clusters, one subsample draw, ansible not evaluated. A null stays a null: if it holds, RQ2 is reported with the retrieval-versus-reasoning breakdown at RQ3.

**Local machine: editing, `make lint`, `make test` (one worker) and git only**; torch tests run on Ada (`scripts/ada/t1_tests.sbatch`).

## Blockers

Accounts: only account A has an SSH alias locally; B and C are not configured, so all jobs ran on A (the engineer adds the aliases). Queue waits of 3 to 8 hours per job (per-user CPU and GPU limits) dominate wall time. The `tests/leakage` check (d) failure found after T3 was fixed in cfedf49 (19 of 19 leakage tests pass). Data: `GITHUB_TOKEN` is **not set on Ada** (decision D2): E-POOL-DATES (D29 flip experiment) was skipped, the rename cache holds 108 repositories and every post-rename count is a lower bound until the token exists. Compute: Block 2 at 45.15 of 46 GPU-hours; `$HOME` on A had 8.3 GB available by `df` and 3.1 GB to the soft quota by `quota -s` at the last check (2026-10-31, files 832 of 3,000 by `quota -s`; rechecked after Wave 6: 21,831 of 25,000 MB, 8.3 GB by `df`); checkpoints use node-local `/tmp` and a resubmission on another node restarts the run (`docs/COMPUTE.md`); no card above 11 GB is reachable from A. Q7: the intended pool is not confirmed (the directories hold 307,996 positive rows, not the table's 49,973 instances; the pool stays `provisional: ADR-001`). CORE-Bench corpora are streamed, not stored. No code blocker.

## Open questions

| # | Question | Blocks | Resolve by |
|---|---|---|---|
| Q3 | Does a docs-only commit need a fresh latency row, or may it reference the previous row? Harness implements both behind `RIL_LATENCY_HOOK` (strict default); the hook is not installed until the engineer runs `make hooks` | hook setting | stays strict (D20); engineer |
| Q33 | Regression thresholds in `configs/bench/latency.yaml` (p50 or p95 up by more than 50% and 0.5 ms vs the previous comparable row) are conservative placeholders, `provisional: Q33`; also whether a failing run is logged (now: not, unless `--append-on-fail`) | `make bench-check`, hook | stays provisional until real stages have rows (D20); engineer, before the freeze |
| Q5 | ADR-001...ADR-010 (training pool, quality signal, graph role, granularity, benchmark, encoder, scaffold, LLM, rerank, usable-by-others) | frozen config, RQ2 start | team, end of week 2 |
| Q7 | Is the candidate pool intended, or is the pool built with the published scripts? Read in full: `gangiswag/train_data` python = SweLocMulti's Python part (SweRank+ Table 1: 2,448 repositories, 24,285 PRs, 49,973 instances), not the original SweLoc (3,387 repositories); SweRank+ states no benchmark-repository exclusion; 89 held-out repositories (3,431 PRs, 14.13%) occur in it (DEV-004). Loc-Bench: 560 rows (V1) vs 660 (V0.2) | ADR-001, pool filter | engineer (D22: provisional pool meanwhile); X3 evidence in the ADR-001 addendum of 2026-10-25 |
| Q11 | CORE-Bench evaluation is whole-snapshot retrieval: each query's candidate list is the repository snapshot at the base commit (paper Sec. 4.1; 12,153 of 12,153 list chunks located in 11 base-commit checkouts; DEV-003), and chunk ids carry no path or line span. D7 and D12 fix the mapping and the primary set; pilot M located 160 of 160 positives by exact text (three repositories); still open: the reported-metric granularity and whether chunk-level numbers are also reported (ADR-004) | ADR-004, evaluation | engineer |
| Q12 | CORE-Bench L3 labels are LLM-judged; the paper does not say how the three votes combine into the kept score (R1); released qrels are binary; L2 positives include import blocks (3 of 53 sampled) | RQ3 interpretation | note in report |
| Q30 | Graph role(s) in the frozen configuration. Measured 2026-10-29 (E-GRAPH-ROLE, ADR-003): on the fused first stage, same-file expansion ordered by first-stage score is level with or above the stored graph at L3 (Verified-six, graph minus it -2.7 [-6.0, 0.8] and -2.0 [-5.2, 0.8] for the two encoders); contain-only equals the stored graph (contain edges never leave a file); non-contain-only is 6 to 7 points below; non-contain edges reach about 8% of missed L3 gold units from the top 5 in two hops. So no evidence that typed edges add to file-level expansion; training-time structure and agent-tool roles are unmeasured. Cheapest further test: stacked expansion (same-file by score, lowest 10 and 25 replaced by the best non-contain neighbours, same budget) | ADR-003, frozen config | engineer; evidence in ADR-003 |
| Q31 | ADR-011 schema choices still open (`specs/repo_graph.md` Q-G3 to Q-G11, Q-G13; storage read structure D16, first families D19, projections D20 and recovery reporting D15 are decided): `test` as flag or kind; which files are config/document; optional edge fields (`site`, `target_text`, `count`); `external` vs `unresolved` boundary; one graph per commit vs validity ranges; resolver per family; which families are in the first stored graph; storage option (measured in the first graph build) | ADR-011, first graph build | engineer, after the build |
| Q45 | RQ3 design and sample size: hypothesis test or effect estimate with an interval? Minimum detectable effect (exact McNemar, power 0.8) is 4.5 / 5.5 / 6.25 / 7.75 points at n = 432 for discordance 10 / 15 / 20 / 30%, 3.25 to 5.25 at n = 900; the one published fixed-agent retrieval swap read in full differs by -0.6 to +1.2 points (`paper_reported`, one run, derived discordance about 14%), below every cell. Deciding number: the smallest resolved-rate difference worth reporting (5 to 6 points or more: a test is feasible at Verified sizes; 3 points or less: only an estimate, interval about +/- 3.7 at n = 432). Discordance and run-to-run SD need one agent pilot | RQ3 design, run count | engineer (`docs/EXPERIMENTS.md` E-POWER, ADR-007 note) |
| Q57 | (from RA-1) The resolver cache fix changes resolver output (2 of 4,163 edges on requests, 0 on flask and django). Bump `RESOLVER_VERSION`? Options: (a) bump to v0.1 at the next cache rebuild; (b) keep v0; (c) revert the fix and drop incremental updates. Evidence: measured (A2a), the 2-edge figure has no stored diff. Cheapest flip: none needed. Workstream A recommends (a): caches keyed on the resolver string rebuild once. | cache keys, frozen graph | engineer |
| Q58 | (from RA-2) Adopt the incremental updater as the per-commit graph build (agent setting, freshness)? Options: adopt / keep full rebuilds only. Evidence: measured (A2a: 100 of 100 updates equal to the full rebuild, speedup p50 1.3x to 9.6x, minimum 1.05x). Cheapest flip: none. Workstream A recommends adopt; the full build stays the default of `build_repository` meanwhile. | RQ3 agent setting | engineer |
| Q59 | (from RA-3) Which BM25 variants go into the A1 development sweep? Options: the four of A1-PILOT plus k1/b, or fewer. Evidence: measured locally, exploratory (identifier splitting +8.9 MRR [+6.9, +10.5], name weight +13.1 [+10.3, +15.9]; an upper bound, docstrings share the function's vocabulary). Cheapest flip: the A1 dev runs. Workstream A recommends running all four; reference form kept meanwhile (`provisional: ADR-004`). | tuned index, ADR-004 | engineer |

Resolved: Q1 (owners named in `docs/ROADMAP.md`), Q4 (remote supplied; the engineer pushes). Resolved as engineer defaults in Wave 5 (D34 Q54, D35 Q55, D37 Q56 in ADR-006 / ADR-002 addenda; D36 RQ3 form, D38 NOISE, D39 seeds before updates). Resolved earlier (as engineer defaults, evidence class in the owning ADR): Q28 (D25), Q35, Q36 (D26, D27), Q46 primary and Q51, Q52, Q53 (D28, D30, D31), Q50 (D29, with the limitation stated), Q47 (D32), Q48 (D33); Q49 answered by E-GRAPH-ROLE (evidence only; Q30 stays open). Earlier: Q24, Q25, Q27, Q29, Q32, Q34, Q37, Q38, Q40, Q42 (D14-D21); Q39, Q41 provisionally (D18); Q43 (D22); Q44 (D23, edited-function check done: flip condition not met); Q8, Q9, Q13-Q23, Q26, Q10, Q2, Q6.

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
