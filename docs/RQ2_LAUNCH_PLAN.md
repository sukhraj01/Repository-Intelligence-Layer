# RQ2 final experiment: readiness audit and launch plan

Audit of 2026-11-08 (entry E-RQ2-READINESS in `docs/experiments/B.md`). The protocol is `docs/RQ2_PROTOCOL.md`
(section 11 where it differs); this page covers what stands between a finished mining run and the final tables.
**Update 2026-11-09:** the launch rulings (D124 to D134) are recorded and the final cell configurations and run scripts exist;
section 9 holds the placement, cells, costs, job graph, the status of the gaps and the checklist. Sections 1 to 8 are the audit as
written on 2026-11-08 and are not rewritten.

Nothing here is a result of the experiment and nothing was trained: the audit read code, stored logs and the cluster's
accounting, ran every stage that has a plan-only form at minimal scale, and wrote plan-only forms for the stages that had
none. **No design choice is made here**: where one is needed the options are listed with their cost, and a
*recommendation* is marked as such.

Evidence classes: **measured** (a stored run or this audit's dry run), **projected** (linear in a measured rate, no
interval), **reasoned** (arithmetic or argument).

## 1. State in one table

| # | Stage | State |
|---|---|---|
| 1 | Mining report, yield against G2, quarantine summary | report step needs a finished session's summary; **yield from the state log added**; G2 met by projection |
| 2 | Content-overlap audit on the full store | built, run on the pilot and on 20 directories now; **not run at full scale**; location open |
| 3 | Materialise, rank inputs, BM25 teacher, feature table, cache | built and run at pilot scale; **no full-scale job script**; the cache does not fit account A |
| 4 | Arms, cell table, budget, job graph | **plan-only form added**; no final cell configuration files and no run script exist |
| 5 | Evaluation on the dev set, the eight repositories, Verified | stores exist for the first two and for six of twelve Verified folders; **one run script cannot score three sets** |
| 6 | Checkpoint retention and archive | switch built, plan runs; **no GPU run yet**; no alias for the archive account; space on A |
| 7 | Noise audit, label sheets | sheet and scorer built; **no reader has returned a sheet** |
| 8 | RQ3 contexts from trained checkpoints | builder takes another arm; **no way to encode with a retained model** |
| 9 | Analysis: Holm, paired intervals, delta, decision rules | **not written**: only the protocol text |

## 2. The chain, stage by stage

Costs are GPU-hours or CPU-hours as labelled; "plan-only" is the stage's dry-run form; "pilot" means it ran on the
1,391-directory pilot store (store on account A, 20 directories in this audit's dry run, job 64656).

### Stage 1. Mining report, yield and gate G2 (CPU, account C, minutes)

- **Purpose.** Report attempted, mined and quarantined pull requests, yield against G2 (D77: at least 10,000 positives at
  full scale; 100 pilot directories with a positive was the pilot gate), both readings (`non_test` primary, D96;
  `pool_aligned` sensitivity), quarantine by reason (the limitation for the paper, timeout class apart).
- **Code.** `scripts/mine_pilot.py report` (reads `summary.json`, written when a session ends), new
  `scripts/mine_pilot.py yield` (`ril/data_mining/state_yield.py`, reads `state.jsonl` only); readings by `rank-prepare --reading`.
- **Plan-only / pilot.** Both read-only. `report` renders the tracked pilot summary after a one-line fix (it raised `KeyError:
  'per_repo'` on the stored copy, which omits that key; test added). `yield` ran on the running store's state log.
- **Measured now** (state log, 2,835 of 10,000 attempted, linear projection, no interval): mined 62.6% (pilot 69.55%), no
  Python change 25.6%, no positive 10.6%, quarantined 1.2% (34 rows; none a snapshot timeout in this window). Quarantine classes:
  changed file unparseable 17 (Python 2 syntax 7, other syntax 10), patch missing 6, old file missing at base 5, diff
  truncated 4, unit id rejected 3. Projected at 10,000 attempted: about 6,257 mined directories and about 61,000 positives
  **unrestricted** (G2 needs 10,000; the count includes test-file positives, so the `non_test` figure is lower: the pilot kept
  1,286 of 1,391 directories and 7,081 positives under it). Store size now 1.1 GB at 2,985 rows: projected **3.7 GB** at
  10,000 (the plan said 2 GB or less; rows are 0.37 MB each against 0.285 MB in the pilot).
- **Pace** (measured): 771 rows in 67.5 minutes after the relaunch (11.4 rows per minute). Session 1 stops 5,000 attempts after
  its start (about 18:30 IST on 2026-11-08 at this pace), session 2 continues to 10,000 (about 4 hours more after a queue wait).
- **Untested at full scale.** `non_test` and `pool_aligned` counts for the whole store (needs materialised directories);
  `report` on a store with a fault-stopped session (no summary).
- **Depends on.** Session 1 finished.

### Stage 2. Content-overlap audit and drop list (CPU, 2 h projected, D105, Q68)

- **Code.** `scripts/mine_overlap_audit.py index|audit|apply`, `scripts/ada/overlap_audit.sbatch`. Held-out index (27 MB)
  exists on account A only; the store is on C.
- **Pilot / dry run.** Pilot: 1,445 s for 0.44 GB, 3 of 1,391 directories dropped. Dry run: 20 directories audited in 24 s,
  `apply` at floor 20 dropped 0, flagged 0 (job 64656, reproduces the pipeline end to end on current main).
- **Projected.** About 2 h for 3.7 GB (linear), 13 min if the index is rebuilt; peak memory decided by the largest repository
  (4.84 GB on the pilot, 12 GB asked).
- **Untested at full scale.** Everything above 1,391 directories. Coverage limit Q68 stays: 26 of 605 held-out repositories
  are visible to the audit.
- **Where.** On C needs the index and code staged there (a small copy); on A needs the store copied (3.7 GB of 5.1 GB free).
  Option list in section 3.
- **Applying the drop list.** No new code: `materialise --names FILE` takes the names; the list is `ls pr` minus
  `drop_f20_non_test.txt` (one `comm -23`). It is a line in the prep job script, not yet written.

### Stage 3. Materialise, pool-rank inputs, BM25 teacher, feature table, cache (CPU)

- **Code.** `mine_pilot.py materialise | rank-prepare | rank-bm25`, `train.py features | select | cache | filter-size`.
  The only job script is `scripts/ada/mp_prep.sbatch`, **pilot-specific** (fixed pilot run root, `--drop-tests`, a 300-directory
  reproduction check, a 1 GiB space guard on `$HOME`).
- **Dry run** (20 directories, node-local scratch, job 64656): materialise 13 s (921 MB peak), rank-prepare 7 s (18
  `non_test` directories), BM25 ranks 6 s, features 1 s, selection 1 s, cache 4 s, FILTER size 1 s (K = 20 keeps 15 of 18 examples
  and 70 of 110 positives). All eight steps return 0 on current main.
- **Projected at about 5,800 `non_test` directories** (pilot rates times 4.5): materialise 53 min, BM25 ranks 1.4 h, the rest
  under 30 min; **3 hours, CPU, node-local disk** (the plan graph uses 3.0). Peak memory 3.4 GB (materialise) and under 12 GB.
- **Cache size and memory (projected from measured).** The pilot cache is 1.25 GB for 1,286 directories (decoded about 4 GB);
  at 5,800 directories it is about **5.6 GB compressed, 17 GB decoded**. A run-batch process holds the cache plus training 3 GB
  plus evaluation 6 GB: **about 26 GB peak against the 32,000 MB per-user limit** (the pilot job asked 20 GB for about 13 GB).
  The job must ask 30 GB. `$HOME` of account A has 5.1 GB free, so the cache cannot be kept there; node-local disk is lost between
  jobs, so every training job would rebuild it (3 CPU-hours before the GPU is used). **Account C has 27 GB free.**
- **Depends on.** Stage 2.

### Stage 4. Arms, cell table, budget and job graph (plan-only form: `scripts/rq2_plan.py plan`)

Cell table of option E (12 cells x 3 seeds = 36 runs, 100 updates of the 3,000-update schedule, batch 32):

| Cell | Data | Arm | Teacher | Role |
|---|---|---|---|---|
| mined_raw | mined | RAW | none | confirmatory (D69) |
| mined_sub | mined | RAW on a random subsample of FILTER's size | none | confirmatory (D69) |
| mined_filter_bm25 | mined | FILTER, K = 20, positive level | BM25 | confirmatory (D69) |
| mined_filter_srs | mined | FILTER | SweRankEmbed-Small | exploratory |
| mined_weight, mined_curriculum | mined | WEIGHT (power, k 20, floor 0.1); CURRICULUM (4 buckets) | BM25 (assumed, open) | exploratory |
| inj_raw, inj_oracle, inj_sub | pool, noise r = 0.4 | RAW; ORACLE_CLEAN; subsample matched to the clean count | none | controls |
| inj_filter_bm25, inj_filter_srs, inj_weight | pool, noise r = 0.4 | FILTER, FILTER, WEIGHT | BM25, SweRankEmbed-Small, SweRankEmbed-Small | exploratory |

- **Plan-only checks** (`ril/training/rq2_plan.py`, 13 tests): configurations rendered in memory from the pilot templates
  (`mp_raw_s0`, `n1_r40_raw_s0`), the held-identical block checked across arms per data condition, 36 distinct hashes,
  retention on, 3,200 example visits per run, arms accepted by `arm_from_config`, fresh-noise check, distinct-example check,
  budget on two bases, job graph and critical path. The configuration hash is unchanged by moving the loader to a torch-free
  module (six stored runs reproduce their directory hash prefix; test pinned).
- **Seeds and fresh noise (D82).** A run's noise draw is keyed on the run's seed (`noise.inject(..., cfg["seed"])`), so seeds
  0, 1, 2 would reproduce the Wave 7 realisations. The plan uses seeds **100, 101, 102** (three, disjoint from the exploratory
  waves) and refuses injected cells on a wave seed. The count is O7; the values are a tactical choice under D82.
- **Budget against Block 3 (46.7):**

| Basis | Training and dev evaluation | Eight repositories | Verified look | Total | Margin |
|---|---|---|---|---|---|
| Protocol (reasoned unit costs 0.40, 0.48, 0.40) | 14.40 | 17.28 | 7.20 | **38.88** (option E: 38.9) | 7.82 |
| Measured unit costs (0.42 per run, 0.178 per checkpoint for the eight) | 15.12 | 6.41 | 7.20 (placeholder) | **28.73** | 17.97 |

  The eight-repository cost was reasoned as 0.48 and measured as 0.178 (69,961 distinct texts at 109 texts/s; this audit's
  count of distinct texts reproduces 69,961). The Verified look stays a placeholder: 0.292 GPU-hours per checkpoint is the
  projection for the six Verified folders that have stores (114,503 distinct texts at 109 texts/s).
- **Charges on the margin that are not in the table:** a dense teacher over the mined store (stage 4a below); the 1,000-update
  sensitivity (1.06 + 0.178 per run, measured); the M3 mined-set rank measurement (limit 2).
- **Distinct examples (G5, D42).** At 3,200 visits and about 5,800 `non_test` directories, RAW makes 0.55 passes and FILTER
  (59.5% of the pilot's examples kept, about 3,450) 0.93 passes: **each arm reaches the common distinct-example count, barely for
  FILTER**; if the final `non_test` count or the kept share is lower, FILTER and the subsample repeat examples and the table must
  say so. At 1,000 updates (32,000 visits) the store is exhausted in every arm (5.5 and 9.3 passes): the matched unique count
  cannot be reached by mining more.
- **4a. Dense teacher on the mined store (FILTER-SweRankEmbed-Small).** Not measured on the pilot (the SweRankEmbed-Small pass
  covered 300 directories inside a 1.99 GPU-hour stage that also held a second teacher and wasted jobs). **Upper bound from that
  stage, 0.0036 GPU-hours per directory-pass: about 21 GPU-hours for 5,800 directories** (reasoned), more than the protocol's
  margin (7.8) and above the measured-basis margin (18.0) once the other charges are added. A pass over distinct rows per repository
  would cost much less and is not measured. The injected cells need no new pass (stored scores of the 5,000-directory pool).
- **Plan graph** (`job_graph`; each GPU job is six runs of one seed and one data condition, 3.6 GPU-hours measured basis):
  report, overlap audit, prep, FILTER size (CPU, account holding the store) then training jobs, dev analysis, three Verified
  look jobs of 2.4 GPU-hours. Injected-noise jobs do not wait for mining.

### Stage 5. Evaluation (GPU; dev set, eight repositories, Verified)

- **Code.** `ril/evaluation/checkpoint_eval.py` (one `e1_config`, one prep directory, one set of roles per call; the role `test`
  needs `deliberate_test`), `train.py run-batch` (evaluates the dev roles after each run) and `train.py eval --eval-override`
  (label, roles, `deliberate_test`) for a retained model. New plan-only check: `scripts/rq2_plan.py eval --set NAME=E1:PREP:ROLES:E3`
  (`ril/evaluation/eval_plan.py`, 3 tests), run on the account that holds the stores (job 64658):

| Set | Repositories | Distinct unit texts | Queries | Encoding at 109 texts/s | Missing |
|---|---|---|---|---|---|
| dev (e1 dev configuration, includes ansible) | 6 | 212,834 | 680 | 0.54 GPU-h at the build's rate (the pilots' five repositories without ansible: about 0.30 measured) | none |
| the eight (D100, role test) | 8 | 69,961 | 224 | **0.178** (equals the build's measurement) | none |
| Verified with stores | 6 of 12 (astropy, matplotlib, seaborn, flask, requests, xarray) | 114,503 | 734 | 0.292 | **django, sympy, sphinx, pytest, pylint, scikit-learn have no unit records or stores** |

- **What does not exist.** One job script that trains, scores the dev set, scores the eight, and (later, once) scores Verified
  with the right roots and labels. `run-batch` takes one set of roots, so the eight and Verified need `eval --eval-override` on
  retained models; the "Verified look once, after the dev analysis" order is a procedure, not code.
- **Where the stores live.** Dev prep and e3 cache: A (`ril_x2/prep`, `ril_t1/work/e3_cache`) and C (staged for N1). The eight: A only
  (480 MB). Verified-six: with the dev prep (A and C).
- **Per-checkpoint cost** (measured for the eight, projected for the others): dev (five repositories) about 0.30, the eight 0.178,
  Verified-six 0.29: about 0.77 plus 0.075 for the training loop.

### Stage 6. Retention and archive (D76, D98)

- **Code.** `checkpoint.retain_final` and `RETAIN_DIR` (`ril/training/retention.py`), `scripts/archive_checkpoints.py` (read-only
  plan), a numbered copy script kept outside the repository.
- **Dry run.** On a synthetic retained folder with a manifest the plan lists the folder, checks the manifest and prints the copy plan,
  with and without an alias (exit 0 both ways). The switch itself has had **no GPU run**.
- **Gaps.** (a) 274 MB per model: 36 models 9.9 GB, the 18 mined 4.9 GB, the 9 confirmatory 2.5 GB; account A has 5.1 GB free,
  C 27 GB. (b) No SSH alias for account B (the archive); its home is 25 GB, 22 GB free at the last survey, wall limit 6 h, one job.
  (c) The copy script stages through the engineer's machine. (d) `RETAIN_DIR` must be exported by the final job script; with the
  key on and no directory the run refuses to start (by design).

### Stage 7. Noise audit and label sheets (D78, D99, D101)

- **Built.** Sheet builder and scorer (`scripts/label_audit_build.py`, `label_audit_score.py`), 400 stratified pairs from the
  **pilot** mined set (200 kept, 200 dropped at K = 20 under BM25, 100-pair overlap), instructions `docs/LABEL_AUDIT.md`.
- **Back.** No reader's sheet. Readers are two team members who are not the lead (D101); about 5 hours each.
- **The scorer needs** the two returned sheets, the sample's K-rank strata, and no judge (none chosen). What the final tables use
  (the audited findable-noise share) is read from the pilot sample unless a new sample is drawn from the full store, which would
  need full-store BM25 ranks (stage 3) and another round of reading. Decision in section 6.

### Stage 8. RQ3 contexts from trained checkpoints (GPU, Block 4: 6.0 cap, 0.377 used)

- **Plug-in point.** `ril/assembly/rq3_contexts.py`: an `Arm` with a dense key per checkpoint is one more arm of the same builder
  (budget 8,000 primary); contexts for BM25, untrained dense and RRF exist for all 377 executable instances.
- **Missing.** Encoding the 377-instance unit texts with a *retained model directory*: the existing job (`rq3_units_encode.sbatch`)
  encodes registered encoder names only. The pass per checkpoint costs **0.377 GPU-hours (measured, untrained encoder, 214,285
  distinct texts)**: three checkpoints 1.1, nine 3.4, against 5.6 left in Block 4. The same encoding would serve a Verified look
  restricted to the executable subset (section 6, decision 4).

### Stage 9. Analysis (CPU)

- **Protocol.** Holm within families (D72), paired bootstrap intervals (2,000 draws, repository-clustered at L2, query-level at
  dev L3), delta = 1.5 (D73), the decision rules of section 6 of the protocol, seed spread, the injected-noise sanity rules.
- **State.** `ril/analysis/stored_{rows,stats,analysis}.py` and `mp_tables.py` hold the paired bootstrap and the minimum
  detectable difference for the pilots; **no module applies Holm, delta and the verdict rules** to a final run. It can be written
  and tested on the pilot rows now.
- **Tables the report needs** (`docs/REPORT_GAPS.md` rows 1, 2, 4 block the paper): per-contrast table at both levels with
  Holm-adjusted and uncorrected intervals; per-cell seed values; distinct examples seen per cell; dose-response and sanity
  rows; the mined-set K-rank profile; the audit result; the quarantine limitation.

## 3. Where the data and the jobs can run (options; no choice)

Facts (measured unless marked):

| | A | C | B |
|---|---|---|---|
| Free `$HOME` | **5.1 GB** (90% used) | 27 GB | 22 GB (survey of 2026-11-03) |
| Holds | dev prep and cache, the eight (480 MB), the pilot store, held-out index, pool caches under another directory, environment | the running mined store (1.1 GB now, 3.7 GB projected), environment, dev prep, pool caches and noise scores (staged for N1) | nothing staged; no alias |
| Does not hold | the full mined store | the eight repositories (480 MB) | everything (about 12 GB to stage) |
| Queue, GPU, wait (Submit to Start, 2026-10-20 on) | 44 jobs: p50 0.03 h, p90 2.75 h, max 8.25 h | 1 job: 0.01 h | not measured |
| Limits | 10 CPU, 1 GPU job, 32,000 MB, 4 days | same | 1 job, 6 h wall, priority 0 |

The ledger has no queue-wait column; the waits come from the scheduler's accounting (`results/rq2_readiness/queue_wait_summary.csv`).
The 3 to 8 hour waits cited earlier are the tail, not the median.

**What must move.** The mined store (3.7 GB) or the training must meet it. The numbered copy scripts kept outside the repository
stage through the engineer's machine (laptop disk and bandwidth). Sizes: store 3.7 GB, the eight 0.48 GB, held-out index 27 MB,
retained models 2.5 to 9.9 GB, code and configurations under 1 MB.

**Ownership.** Account C belongs to a teammate by the project state page and the engineer's own account by the operating
notes; this audit could not settle which. If it is the teammate's: their consent to GPU jobs and 30 GB of memory requests on their
login, to about 6 GB of staged data and 5 to 10 GB of retained models in their home (27 GB free, their own files present),
and to the mining job's priority being unaffected (job 64594 waits on 64593). Precedent: job 52385 and the N1 runs used C for
GPU work; the D21 ledger already counts C (2.24 GPU-hours).

**Critical path in calendar days** from "mining store finished" (job graph, `ril/training/rq2_plan.py`; wall = GPU-hours per
job on one GPU; CPU stages 0.1 + 2 + 3 + 0.1 h; queue wait added per job; the p90 and max rows are pessimistic because they
apply the wait to every job, while queued jobs of a chain overlap their waits in practice). The 3,000-update schedule is not
changed; the teacher pass of 4a and the sensitivity are excluded.

| Option | Description | Median wait | p90 wait per job | Max wait per job | Blocker |
|---|---|---|---|---|---|
| 1 | everything on A (store copied to A) | 35 h, **1.5 days** | 73 h, 3.0 days | 150 h, 6.2 days | A has 5.1 GB free: store 3.7 GB, cache 5.6 GB and models do not fit; engineer frees space |
| 2 | everything on C | 35 h, 1.5 days | 73 h, 3.0 days | 150 h, 6.2 days | the eight repositories (0.48 GB) copied to C; teammate's consent if C is not the engineer's |
| 3 | mined cells on C, injected cells on A (A has the injected inputs; C the store) | 24 h, **1.0 day** | 54 h, 2.2 days | 114 h, 4.8 days | as 2; Verified look runs on C after the dev analysis |
| 4 | A, B and C | not computed: B could take one of C's three mined jobs, shortening the chain by one job (3.6 h) | | | B has a 6 h wall (a six-run job is 3.6 h), no alias, nothing staged (about 12 GB to stage); use B for the archive only |

Assumptions: GPU-hours equal wall-hours (the six-run job measured 2.4 to 2.7 GPU-hours in the pilots, 3.6 is the measured-basis
figure with the eight repositories); the Verified look is 7.2 hours (placeholder); no job fails (a failed or node-lost job
restarts a run, `docs/COMPUTE.md`); mining ends before the day count starts.

## 4. Job graph (option 3, measured basis)

| Job | Where | After | Wall (h) | GPU-h |
|---|---|---|---|---|
| report, yield | C | session 2 done | 0.1 | 0 |
| overlap audit and drop list | C | report | 2.0 | 0 |
| prep: materialise, ranks, feature table, cache | C | overlap | 3.0 | 0 |
| FILTER size | C | prep | 0.1 | 0 |
| train s100, s101, s102 injected (6 runs each) | A | none, chained on A | 3.6 each | 3.6 each |
| train s100, s101, s102 mined (6 runs each) | C | FILTER size, chained on C | 3.6 each | 3.6 each |
| dev analysis | C | all training | 0.5 | 0 |
| Verified look, seeds 100, 101, 102 (6 retained models each) | C | dev analysis, chained | 2.4 each | 2.4 each |
| Total | | | | **28.7** (measured basis) |

`python3 scripts/rq2_plan.py plan --filter-size N --pool-examples M --accounts A C` prints the 36 runs with hashes and the full graph.

## 5. Preflight checklist for launch day

1. `yield` on the final state log: mined, quarantine by class, G2; `report` once a summary exists.
2. Overlap audit on the full store, `apply`, record dropped directories; the names file for prep is the store minus that list.
3. Prep: `non_test` directories, BM25 ranks, feature table (0 held-out rows), cache; record the example count and the FILTER size.
4. `rq2_plan.py plan --filter-size <kept> --pool-examples <examples>`: the distinct-example check passes or the shortfall is
   written next to the table; fresh-noise check empty; 36 hashes.
5. `rq2_plan.py eval` for the sets in use: `ready` true; Verified decision applied (section 6).
6. Space: `df` on the account for the cache, retained models (`RETAIN_DIR` outside any work tree) and results; memory request 30 GB.
7. CUDA gate passes inside each run (already in the code); one GPU job per account; record every job in the ledger.
8. Leakage tests pass (`make test-all` on the cluster): pool and evaluation repositories disjoint, no gold text in a query, teacher
   is not the model being trained, no evaluation data on a training path.
9. Registration (cell list, decision rules) fixed before the first run; the Verified look is one job, after the dev analysis.
10. Seeds outside {0, 1, 2}; configuration hashes recorded; commit hash in `RIL_COMMIT`.

## 6. Gaps found

Severity: **A** blocks the launch, **B** blocks a stated claim or a cost, **C** hygiene. Size is in work packages (one package is one
task of the sequence in section 8).

| # | Gap | Sev. | Owner | Size | Cheapest fix |
|---|---|---|---|---|---|
| 1 | No final cell configuration files and no run script for the 36 runs (cache path, noise scores, `RETAIN_DIR`, 30 GB, three evaluation sets) | A | lead | 1 | write the files from the plan renderer and one sbatch; plan-only form exists |
| 2 | One run cannot score three sets; the order "dev analysis, then Verified once" is not enforced | A | lead | 1 | `eval --eval-override` jobs on retained models; label and `deliberate_test` in the override |
| 3 | No full-scale prep script (mined store to cache) and no step applying the overlap drop list | A | lead | 1 | generalise the pilot prep script; drop list through `--names` |
| 4 | Mined cache (about 5.6 GB) does not fit account A and node-local disk is lost between jobs | A | engineer | decision | train on C (27 GB free) or free space on A; no code |
| 5 | Memory at full scale about 26 GB peak against a 32,000 MB limit; pilot scripts ask 20 GB | A | lead | in 1 | request 30 GB; check `sacct` MaxRSS on the first job |
| 6 | Final analysis (Holm, delta, verdict rules, seed spread) not written | B | lead | 1 | module and tests on the pilot rows (CPU, can run now) |
| 7 | Dense teacher on the mined store unmeasured; upper bound 21 GPU-hours per teacher | B | engineer | decision plus 0.4 GPU-h measurement | drop the cell or measure a per-repository de-duplicated pass on 100 directories first |
| 8 | Verified look covers 6 of 12 folders; the other six have no units or stores | B | engineer | decision | options in the next list |
| 9 | Retained-model space and the archive: A cannot hold them, no alias for B | B | engineer | 0 | retain on C; add the alias; run the numbered copy script |
| 10 | 1,000-update sensitivity cannot reach the matched unique count (32,000 visits against about 5,800 examples) | B | engineer | decision | skip, or run flagged as repeating |
| 11 | No encoding with a retained model for the 377 executable instances | B | lead | 1 | encode job taking a model directory; cost 0.377 GPU-h per checkpoint |
| 12 | Label audit: no reader has returned a sheet; the sample is from the pilot store | B | team | 10 h of reading | send the sheets; decide pilot sample or new draw |
| 13 | Mined store disk 3.7 GB projected against the plan's 2 GB; yield below the pilot's (62.6 against 69.55%) | C | lead | 0 | note in the report; no action |
| 14 | `report` needs a finished session's summary; failed on the tracked pilot summary | C | lead | done | fixed (`.get`), `yield` added, tests added |
| 15 | Evaluation-set check overstated texts by lines (233,064) against distinct (69,961) | C | lead | done | counts distinct hashes; matches the build's number |
| 16 | Ledger sums to 68.03 GPU-hours (A 65.79, C 2.24) against Block 2's 67.41 of 70: the difference is Block 4 (0.377) and the eight-repository build (0.246) | C | lead | 0 | none; stated so the totals can be traced |
| 17 | Noise draws are keyed on the training seed: seeds 0 to 2 would reuse Wave 7 draws | C | lead | done | plan seeds 100 to 102, plan refuses wave seeds |
| 18 | Mining relaunched three times (fixed in the miner); the timeout class will be reported as a limitation | C | lead | 0 | the yield tool lists it; none so far in the window read |

## 7. Decisions the engineer must make before launch

Each decision lists the options with cost; the **recommendation** is mine, reasoned, and is not a decision.

1. **Where the mined-set cells train.** (a) C (store in place; needs the eight repositories copied, 0.48 GB, and the teammate's
   consent if C is theirs); (b) A (store 3.7 GB, cache 5.6 GB, models: needs 10 to 15 GB freed on A first); (c) split, injected on A,
   mined on C. Cost: 1.5, 1.5 and 1.0 day on the median queue (section 3). *Recommendation:* (c), because it is the shortest, uses
   what is already staged on each account, and keeps A's disk untouched; (a) if C's owner objects to sharing the GPU queue.
2. **FILTER-SweRankEmbed-Small on the mined set.** (a) keep and run the dense pass (upper bound 21 GPU-hours, de-duplicated cost
   unknown); (b) drop the cell (11 cells, 33 runs, 25.7 GPU-hours on the measured basis); (c) measure first on 100 directories with a
   per-repository de-duplicated pass (about 0.4 GPU-hours, one job). *Recommendation:* (c), then (a) or (b) on the number; the
   cell is exploratory under D69, so dropping it costs no confirmatory power.
3. **Teacher of WEIGHT and CURRICULUM on the mined set.** BM25 (CPU, assumed in the plan) or SweRankEmbed-Small (needs the pass of
   decision 2). *Recommendation:* BM25.
4. **Which Verified set the single look uses.** (a) the six folders with stores (83 L2 and 55 L3 queries; 0.29 GPU-hours per
   checkpoint; the protocol's 12-folder claim is not met); (b) the executable subset of 377 (L2 320 labels, L3 224; stores and
   units exist; 0.377 GPU-hours per checkpoint, the same order as the 0.4 placeholder; the same encoding serves RQ3's
   trained-checkpoint contexts; excludes matplotlib and scikit-learn; needs a DEV entry); (c) build units and stores for the other six folders (django and sympy are in the 341
   built instances but as a different instance set; extra CPU and GPU not estimated here). *Recommendation:* (b) as the confirmatory
   set, because its stores exist (no new CPU build), it costs about the placeholder per checkpoint, and one encoding pass per
   checkpoint then serves both the look and RQ3 (a second pass of 0.377 per checkpoint avoided); the population change is
   stated and recorded as a departure.
5. **1,000-update sensitivity.** Skip, or three mined cells at one seed (3.7 GPU-hours, repeats flagged because 32,000 visits exceed
   about 5,800 examples). *Recommendation:* skip; it cannot meet the matching rule on any store this project can mine.
6. **Which models to retain.** 9 confirmatory (2.5 GB), the 18 mined (4.9 GB), all 36 (9.9 GB). *Recommendation:* the 18 mined (the
   Verified look and RQ3 need them), on C, archive to B afterwards.
7. **Label audit sample.** Report the pilot sample's rate as the estimate for the miner's construction, or draw a new 400 from the
   full store (needs stage 3 ranks and about 5 hours per reader again). *Recommendation:* the pilot sample first; a new draw only
   if the full-store K-rank profile differs from the pilot's beyond the intervals.
8. **Dev set with or without ansible.** The pilots excluded ansible (D32); including it adds about 0.33 GPU-hours per checkpoint
   (E-DEV-ANSIBLE) and a third L3 repository. *Recommendation:* keep the pilots' five repositories for comparability and report
   ansible as a sensitivity from the retained models.
9. **Where the overlap audit runs.** On C (stage the held-out index, 27 MB, and the code) or on A (copy the store, 3.7 GB, does
   not fit). *Recommendation:* C.

## 8. Next work packages, in the order they should run

1. **Final configurations and run script.** What: render the 36 configurations from the plan, write the sbatch for one seed and one
   data condition (cache, noise scores, `RETAIN_DIR`, 30 GB), and the evaluation jobs for the eight and for the Verified set. Where:
   local for code, a CPU plan check on the cluster. Needs: decisions 1, 2, 3, 4, 6.
2. **Final analysis module.** What: Holm within families, paired bootstrap, delta, verdict rules, seed spread, sanity rules, tables
   for the report, tested on the pilot rows. Where: CPU, local. Needs: nothing.
3. **Full-store prep and overlap job scripts.** What: generalise the pilot prep script to a store and a names file, add the drop
   list step, a size guard and a memory estimate, run at 200 directories. Where: CPU on the account holding the store. Needs:
   decision 9; the mining jobs may still be running.
4. **Dense teacher measurement (if decision 2 is (c)).** What: per-repository de-duplicated dense pass on 100 directories under
   SweRankEmbed-Small, cost per directory. Where: one GPU job, about 0.4 GPU-hours. Needs: the prep output.
5. **Checkpoint encoding for RQ3.** What: encode the 377 executable instances with a retained model directory and build the
   trained-arm contexts. Where: GPU, Block 4. Needs: one retained model (a pilot checkpoint can test it).
6. **Archive alias and copy.** What: the SSH alias for account B, the copy script run by the engineer. Where: the engineer's
   machine. Needs: retained models.
7. **Launch.** What: the checklist of section 5 and the job graph of section 4. Where: A and C. Needs: 1 to 3, mining finished.

## 9. Final cells and run scripts (2026-11-09; decisions D124 to D134, DEV-038, DEV-039; entry E-RQ2-FINAL-CELLS)

Evidence classes as above. Nothing was trained and no GPU job was submitted; the plan-only checks ran on the CPU of accounts A and C
(`results/rq2_final/plan_only/`). All settings are `provisional` until launch and none is in `configs/frozen/`.

### 9.1 Rulings recorded (section 7 of this plan is settled)

| Section-7 item | Ruling | D |
|---|---|---|
| 1 where the mined cells train | mined set on C, injected-noise family on A, B unused; the eight repositories and the built parts of the executable 377 copied to C (done, verified) | D124 |
| 2 FILTER with SweRankEmbed-Small on the mined set | exploratory and conditional: measure on 100 directories (about 0.4 GPU-hours), run only if the full-store pass costs at most 6.0 GPU-hours | D125 |
| 3 teacher of WEIGHT and CURRICULUM | BM25 | D126 |
| 4 which Verified set | the 377 executable instances; departure recorded as DEV-038 (432 L2 queries become 320, 302 L3 become 224, minimum detectable difference about 16% larger) | D127 |
| 5 1,000-update sensitivity | not run on the mined set; DEV-039; optional on the injected family | D128 |
| 6 models to retain | the 18 mined-set models on C (15 without the dense-teacher cell); injected models not retained; the final sets are scored once, after the dev analysis | D129 |
| 7 label-audit sample | the pilot sample first | D130 |
| 8 dev set | the pilots' five repositories | D131 |
| 9 where the overlap audit runs | C; the held-out index is copied there (done, verified) | D132 |
| gap 10 and G5 pool smaller than the visits | 100 updates for every arm, each arm cycles its own pool in a fresh seeded order per pass, distinct examples seen stored beside every result | D133 |

### 9.2 The 36 runs

Twelve cells x seeds 100, 101, 102 (outside the exploratory waves, D82), 100 updates of the 3,000-update schedule, batch 32, K = 20
positive level, BM25 teacher for the confirmatory cell, configurations in `configs/experiments/rq2_final/<cell>_u100_s<seed>.yaml`,
rendered by `scripts/rq2_plan.py render` and checked against the registered design (`check_protocol`).

| Account | Runs | GPU-hours (0.42 each, measured) | Final sets afterwards |
|---|---|---|---|
| A | 18 injected-noise runs (inj_raw, inj_oracle, inj_sub, inj_filter_bm25, inj_filter_srs, inj_weight) | 7.56 | none (dev only, not retained) |
| C | 15 mined-set runs (mined_raw, mined_sub, mined_filter_bm25, mined_weight, mined_curriculum) | 6.30 | 15 retained models, 12.87 |
| C | 3 mined_filter_srs runs, conditional on D125 | 1.26 | 3 retained models, 2.57 |
| C | dense teacher: measurement (0.4) and pass (at most 6.0), conditional | at most 6.4 | |

Cell table, roles and teachers: `docs/experiments/B.md` E-RQ2-FINAL-CELLS.

### 9.3 Evaluation by set and the sealed order

| Set | Stage | Scored by | Per checkpoint (GPU-hours) |
|---|---|---|---|
| dev, five repositories | training | each run, `train.py run-batch --eval-set dev` | in the 0.42 per run |
| the eight repositories (D100) | final | `scripts/rq2_final_sets.py run`, retained model, role test | 0.178 measured |
| executable 377 of Verified (D127) | final | the same, three stored parts | 0.388 measured (341 built) plus up to 0.292 projected (36 earlier) |

The final-sets script refuses to start without `--follows-dev-analysis ID` and a complete dev-analysis record naming that id and
covering the run (`write_dev_analysis_record`); each score row carries the id and the record's digest; `read_final_sets` returns rows
only for that id. The job graph puts the final sets after the dev analysis.

### 9.4 Job graph (per-run jobs) and critical path

CPU stages on C (report, overlap audit, prep, FILTER size) first; the injected jobs on A wait for nothing and chain on A; the mined
jobs on C wait for the FILTER size and chain on C; the conditional teacher measurement is first on C, the pass after the unconditional
runs and before the three dependent runs; then a manual collection of the injected results to the analysis account (small named
set, byte-verified), the dev analysis, and one final-sets job per retained model on C. Critical path in wall hours, GPU-hours as wall:
26.1 h (1.1 days) at the median queue wait with the conditional cell dropped, 36.4 h (1.5 days) with it; 124 h and 153 h if every
job drew the 90th-percentile wait of account A (a tail applied to each of 48 or 56 jobs: pessimistic). Section 3's option 3 gave 1.0
day with six-run jobs; the difference is the per-job queue wait (see pushback in the entry).

Budget against Block 3 (46.7): **30.56 GPU-hours** on measured costs for the rulings' evaluation scope (margin 16.14; 9.74 after the
conditional teacher), 30.24 on the protocol's reasoned costs for the same scope; the registered design's own scope (eight for all 36
runs) is 28.73 measured and 38.88 protocol (margin 7.82, 1.42 after the conditional teacher).

### 9.5 Gap status (section 6)

| # | Gap | State now |
|---|---|---|
| 1 | final cell configurations and run script | **done** (36 configurations, two run scripts, submit and preflight scripts); memory request 30 GB (mined), 24 GB (injected) |
| 2 | one run cannot score three sets; order not enforced | **done** (set selector, final-sets script, sealed order in code, recorded in each row) |
| 3 | full-scale prep script and drop-list step | open (a later prompt); the preflight reads the prep summary file (JSON, in the run's work directory) that the prep job will write |
| 4 | mined cache does not fit A | **decided** (D124); not yet built |
| 5 | memory about 26 GB against 32,000 MB | request set to 30 GB and checked by the preflight; MaxRSS of the first job still to read |
| 6 | final analysis module | open (another branch) |
| 7 | dense teacher unmeasured | rule fixed (D125); measurement is a later prompt |
| 8 | Verified look covers six of twelve folders | **decided** (D127, DEV-038) |
| 9 | retained-model space and archive | **decided** (D129: retain on C); the alias for B stays open |
| 10 | 1,000-update sensitivity | **decided** (D128, DEV-039) |
| 11 | encoding with a retained model for the 377 | built for the final sets (`final_sets.evaluate_retained`); RQ3's trained-arm contexts still need the same model-directory encoding for the 377 contexts |
| 12 | label audit | open (readers) |

### 9.6 Preflight checklist (section 5), status 2026-11-09

| # | Item | State |
|---|---|---|
| 1 | `yield` on the final state log | **done** (read-only): 10,000 attempted, 6,230 mined, 123 quarantined (1.23%), 0 timeouts, 54,700 positives unrestricted |
| 2 | overlap audit on the full store, drop list applied | open (index copied to C; audit job is a later prompt) |
| 3 | prep: `non_test` directories, ranks, feature table, cache, FILTER size | open (the preflight checks the prep summary file) |
| 4 | plan with the real FILTER size and example count; distinct-example statement | open; the preflight prints it from the prep summary (illustrative at 5,800 and 3,450: RAW 0.55 passes, FILTER 0.93) |
| 5 | evaluation sets ready | **done** on A and C (0 missing for the dev set, the eight and the three parts of the 377) |
| 6 | space, retention directory, memory 30 GB | **checked** (A 5.3 GB free for 3.0 needed; C 26.0 GB for 10.0 needed; request 30,720 MB under 32,000); final space check at launch |
| 7 | CUDA gate inside each run; one GPU job per account | in the code; the submit script refuses a run already queued |
| 8 | leakage tests on the cluster | 41 of 41 torch and leakage tests passed on the final code (job 66005); `scripts/rq2_record.py leakage` writes the record the preflight needs; open until run on the launch commit |
| 9 | registration fixed before the first run | open: the engineer runs `scripts/rq2_record.py registration` |
| 10 | seeds outside the waves, hashes, commit in `RIL_COMMIT` | **done** in the plan and the preflight; the commit is the launch commit |

### 9.7 Next work packages

Full-store prep and overlap job scripts (decision 9 settled: on C); the dense-teacher measurement on 100 directories; the final
analysis module that writes the dev-analysis record; then the launch: `rq2_record.py` (registration, leakage), `rq2_preflight.py` and
`rq2_submit.py --confirm-launch` on C (mined) and A (injected), by the engineer.
