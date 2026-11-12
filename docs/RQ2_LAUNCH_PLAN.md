# RQ2 final experiment: readiness audit and launch plan

Audit of 2026-11-08 (entry E-RQ2-READINESS in `docs/experiments/B.md`). The protocol is `docs/RQ2_PROTOCOL.md`
(section 11 where it differs); this page covers what stands between a finished mining run and the final tables.
**Update 2026-11-09 (second):** the launch rulings (D124 to D134) are recorded and the final cell configurations and run scripts exist;
section 10 holds the placement, cells, costs, job graph, the status of the gaps and the checklist. Sections 1 to 8 are the audit as
written on 2026-11-08 and are not rewritten; section 9 is the reconciliation of the same day.

Section 9 (2026-11-09) supersedes the mining-store size, adds the FILTER-pool rule, retention options, data location and disk. Nothing here is a result of the experiment and nothing was trained: the audit read code, stored logs and the cluster's
accounting, ran every stage that has a plan-only form at minimal scale, and wrote plan-only forms for the stages that had
none. **No design choice is made here**: where one is needed the options are listed with their cost, and a
*recommendation* is marked as such.

Evidence classes: **measured** (a stored run or this audit's dry run), **projected** (linear in a measured rate, no
interval), **reasoned** (arithmetic or argument).

## 1. State in one table

| # | Stage | State |
|---|---|---|
| 1 | Mining report, yield against G2, quarantine summary | **done** (E-RQ2-FULL-PREP): the run finished, 6,230 mined, 123 quarantined, 0 timeouts, G2 met (54,700 positives unrestricted) |
| 2 | Content-overlap audit on the full store | **job script built** (sharded, resumable), run on 200 directories and on a 210-directory probe on C; not run on the whole store (a later prompt) |
| 3 | Materialise, rank inputs, BM25 teacher, feature table, cache | **job script built** (one entry point, explicit stages, `LIMIT`), run end to end on 200 directories; the mined cache is about 2.3 GB and fits C |
| 4 | Arms, cell table, budget, job graph | **plan-only form added**; no final cell configuration files and no run script exist |
| 5 | Evaluation on the dev set, the eight repositories, Verified | stores exist for the first two and for six of twelve Verified folders; **one run script cannot score three sets** |
| 6 | Checkpoint retention and archive | switch built, plan runs; **no GPU run yet**; no alias for the archive account; space on A |
| 7 | Noise audit, label sheets | sheet and scorer built; **no reader has returned a sheet** |
| 8 | RQ3 contexts from trained checkpoints | builder takes another arm; **no way to encode with a retained model** |
| 9 | Analysis: Holm, paired intervals, delta, decision rules | **built and tested on the pilot rows** (`ril/analysis/rq2_final.py`, E-RQ2-ANALYSIS); not run on final rows; one open finding on its error rate |

## 2. The chain, stage by stage

Costs are GPU-hours or CPU-hours as labelled; "plan-only" is the stage's dry-run form; "pilot" means it ran on the
1,391-directory pilot store (store on account A, 20 directories in this audit's dry run, job 64656).

### Stage 1. Mining report, yield and gate G2 (CPU, account C, minutes)

**State 2026-11-09 (E-RQ2-FULL-PREP, measured, read only): the run has finished** (jobs 64593 and 64594 COMPLETED, last summary
2026-11-08 20:54 IST, no `HALT` file); the earlier projections in this stage are superseded by these numbers.

- **Code.** `scripts/mine_pilot.py report` (reads `summary.json`), `scripts/mine_pilot.py yield` (`ril/data_mining/state_yield.py`, reads
  `state.jsonl` only), `scripts/rq2_full_prep.py progress STATE STORE` (the same yield plus the store's growth by quarter of the log);
  readings by `rank-prepare --reading`.
- **Result.** 10,000 attempted: mined 6,230 (62.3%; pilot 69.55%), no Python change 2,607, no positive 1,040, quarantined 123 (1.23%;
  changed file unparseable 48, old file missing at base 26, patch missing 23, diff truncated 14, unit id rejected 8, snapshot unavailable
  3, compare not found 1), **0 snapshot timeouts**. 54,700 positives unrestricted (G2 needs 10,000; 8.78 per mined directory), 1,102
  repositories seen. Mining time 9.55 h in two sessions. `non_test` and `pool_aligned` counts of the whole store are not measured yet
  (projected from the 200-directory trial, stage 3).
- **Store.** `pr` 0.103 GB, `cas` 1.035 GB, `listing` 0.724 GB (1.87 GB). The 3.7 GB projection counted the listing directory, which was
  complete at 2,985 rows, as growing; the distinct-row store grows by quarter of the log by 947, 61, 19 and 9 MB (567, 235, 124, 87 new
  repositories), so it saturates and a linear projection of it overstates. The snapshot size per mined directory is flat across the
  quarters (4,992, 4,455, 4,970, 4,864 functions on average; the first 200 mined directories 3,783).
- **Done 2026-11-10 (E-MINE-FULL-RESULT, measured; report `results/mining/full/report.md`).** Both readings pass G2: unrestricted 54,700
  positives, `non_test` 36,046 (35,804 after the audit's drop list, 5,789 directories), `pool_aligned` 29,473 (4,935 directories). 0 snapshot
  timeouts, so no partial-fetch pass (D146). Store 1.86 GB (299 KB per mined directory); mining 9.55 h; the three failures cost 21.6 h of failed
  wall time and 45.9 h of waiting.
- **Depends on.** Nothing further. `scripts/mine_pilot.py report` still needs a session summary (present).

### Stage 2. Content-overlap audit and drop list (CPU, D105, Q68)

- **Code.** `scripts/mine_overlap_audit.py index|audit|merge|apply`; the audit is now run by the stage `overlap` of
  `scripts/ada/rq2_full_prep.sbatch` in resumable shards (the repository name's hash picks the shard; default 8; a finished shard is
  skipped on a resubmission), merged into the records an unsharded audit writes, then `apply` at floors 10, 20, 50, positives `all`
  and drop-flagged. The held-out index (27 MB) and the pilot's reference files were copied from A to C through the engineer's machine
  with a SHA-256 manifest (5 files, verified on C, nothing overwritten): `$HOME/ril_prep/inputs`.
- **Measured.** 200 directories of the full store: 377 s in 3 shards (peak 1.2 GB), 1 dropped and 2 flagged at floor 20; merged
  records equal an unsharded audit (same SHA-256, summary and lists at every floor). 210 directories of three large repositories:
  184 s (peak 1.2 GB). Pilot: 1,445 s for 0.44 GB, 3 of 1,391 dropped.
- **Projected for the 6,230 directories.** 1,578 s (0.44 h; two-point reading through the trial and the probe, the audit costs 0.9 s per
  MB of distinct rows plus 21 s per million snapshot functions) up to 14,967 s (4.2 h; linear per function, a bound); the largest
  repository (google-cloud-python, 870,248 distinct rows) decides the peak (4.8 GB on the pilot's 946,825-row repository).
- **Done 2026-11-10 (E-MINE-FULL-RESULT, measured, job 66544).** 6,230 directories audited in 8 shards, 4,366.9 s (the two-point projection was
  1,578 s, the linear bound 14,967 s), peak 3.5 GB; 13 dropped at floor 20 (floors 10 and 50: 34 and 9; every flagged directory: 138); drop list
  tracked at `results/mining/overlap_audit/full/drop_f20_non_test.txt`, SHA-256 `36e3a144d2d7154c3abc0df8fc31e8ec11e3777b07cf5ef030401f63881d9f44`,
  applied to the training manifest only (6,217 of 6,230 kept).
- **Coverage.** Q68 stays: the audit sees 26 of 605 held-out repositories.
- **Applying the drop list.** Done by the stage `drop`: the training manifest is the final directories minus `drop_f20_non_test.txt`
  (the store is not touched, `drop_manifest.json` records both hashes); a tracked, hashed list can be supplied instead
  (`DROP_LIST` and `DROP_SHA256`); the launch preflight reads `drop_list_applied` and `held_out_rows` from the prep summary file.

### Stage 3. Materialise, pool-rank inputs, BM25 teacher, feature table, cache (CPU)

- **Code.** One entry point, `scripts/ada/rq2_full_prep.sbatch` over `scripts/rq2_full_prep.py` (`ril/data_mining/full_prep_run.py`),
  with the stages `select, overlap, drop, materialise, inputs, teacher, features, cache, check`, `LIMIT=N` for a trial, `NAMES_FILE`
  for a probe, `READINGS` (default `non_test`; `pool_aligned` is the sensitivity reading), resumable (finished stages are skipped,
  ranks are appended per directory, a resubmission rebuilds the node-local view it needs), 12 GB, 8 h. Outputs under
  `$HOME/ril_prep/runs/<RUN>`; `rq2_full_prep.py link RUN WORK` links the cache, feature table and the prep summary file into a launch work
  directory (refuses a trial and never replaces a path). the prep summary file carries `examples`, `filter_size`, `held_out_rows`,
  `drop_list_applied` and `scope` (`full` or `trial`), the fields `ril/bench/rq2_launch.py` reads.
- **Measured on 200 directories** (`non_test`, 2 CPUs, per stage seconds: materialise and byte check 73, rank inputs 36, BM25 41,
  feature table 0.6, cache and FILTER size 36, check 5; peaks 0.9, 0.3, 0.7, 0.04, 0.6, 0.2 GB): 188 of 199 directories, 1,177
  positives; `pool_aligned` 159 directories, 877 positives; FILTER K = 20 keeps 134 of 188 examples and 356 of 1,177 positives;
  0 held-out rows; second run equal on 65 of 65 files and byte-identical caches; ranks and feature rows equal the pilot's on 119
  shared directories. **Measured on a probe of 210 directories of airflow, openmetadata and azure-cli:** 13 min 9 s, cache 238 MB,
  FILTER size step peak 1.7 GB.
- **Projected for the 6,230 directories** (linear, no interval): materialise and check 0.4 to 0.8 h, rank inputs 0.4 h, BM25 0.45 h,
  cache and FILTER size 0.35 to 0.4 h; **the `non_test` chain 2.0 h (two-point audit) to 6.3 h (everything linear), `pool_aligned` about
  0.7 h more**. About 5,860 `non_test` directories (5,600 to 6,010 on the trial's Wilson interval) and about 4,950 `pool_aligned`.
- **Cache size and memory.** Two caches give 157 to 158 bytes per candidate row compressed and 1.12 to 1.25 KB per row decoded;
  the 5,860 directories carry about 14.7 M candidate rows, so the mined cache is **about 2.3 GB compressed** (this page said 5.6 GB) and
  **17 GB decoded with the earlier reader** (the page's figure, now reproduced from a count). The reader now keeps one copy of each
  distinct text and id (equal values, 3 of 3 real caches compare equal): 1,712 MB against 295 MB on the probe's cache, 476 against
  352 MB on the trial's; projected **3 to 6 GB** for the whole cache (5.28 M distinct rows in the store; not measured at that size). A
  run process then needs about 12 to 15 GB (cache 3 to 6, training 3, evaluation 6) instead of 26 GB. **A 30 GB memory request cannot
  start on this cluster:** the partition grants at most 3,000 MB per CPU, 30 GB is 11 CPUs, the account's limit is 10 (job 66022
  waited on `QOSMaxCpuPerUserLimit` with an empty queue); the most one job can ask is 30,000 MB, holding all 10 CPUs; 12 and 14 GB were
  allocated 6 CPUs. The run scripts of section 10 ask 30G for the mined family (gap 5).
- **Disk on C (24 GB free).** Cache about 2.3 GB (`non_test`) plus about 1.8 GB (`pool_aligned`), node-local view about 4.4 GB and
  archive about 2.5 GB (lost with the node); the store is not copied.
- **Done 2026-11-10 (E-MINE-FULL-RESULT, measured, job 66544; both readings; replaces the "untested at full scale" line below).** 4 h 09 m 57 s
  (12 GB asked, 6 CPUs allocated): audit 4,366.9 s, materialise 1,939.5, rank inputs 2,831.7, BM25 teacher 2,973.9, feature table 2.7, cache and FILTER
  size 2,671.6, check 208.3; projection was 2.7 to 7.0 h. `non_test`: 5,789 examples, 35,804 positives, 991 repositories, cache 2.40 GB (projected
  2.3 GB); `pool_aligned`: 4,935 examples, 29,473 positives, cache 1.73 GB. Largest child peak 5.5 GB (cache read with shared strings 5.4 GB, inside
  the projected 3 to 6 GB); Slurm's `MaxRSS` of the batch step equals the 12 GB request, so a rerun asks 16 GB. Held-out rows 0, drop list applied,
  scope full. FILTER K = 20 (BM25) keeps 3,885 of 5,789 examples (67.11%, clustered 95% 64.0 to 70.0%): F = 3,885 against 3,200 visits, N = 100 (D147).
  200-directory repeat equal on every compared file and equal to the full run; 912 of 912 rank rows identical to the pilot's. Link command and
  `resolve` are the launch step (section 11.4), not done here.
- **Was untested before the full run (now measured, above).** Peak memory and wall time of the audit and the cache read; the shared reader's saving at 5,860 examples;
  `non_test` and `pool_aligned` counts of the whole store.
- **Depends on.** Stage 2 (it is a stage of the same job).

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
  detectable difference for the pilots. **Built 2026-11-09 (E-RQ2-ANALYSIS):** `ril/analysis/rq2_final.py` applies Holm, delta and the
  verdict rules to per-query rows of final runs, refuses the final evaluation sets without the id of the dev-analysis entry (D100),
  carries the distinct-directory diagnostics and writes a hashed machine-readable summary; `rq2_final_tables.py` and
  `scripts/report_tables.py` render the four report tables once a summary built from final rows exists. Tested on the stored pilot
  rows (the noise, mined-set and learning-curve summaries reproduce to their rounding). Open: the repository-clustered percentile
  interval does not hold the family-wise error rate at 8 to 12 repositories (entry, question 1).
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
| 6 | Final analysis (Holm, delta, verdict rules, seed spread): **built 2026-11-09, tested on the pilot rows, not run on final rows** (E-RQ2-ANALYSIS); error-rate finding open | B | lead | 1 | the lead answers the questions of the entry; run on the final rows after the dev analysis |
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
5. **FILTER-pool rule (new, section 9.2).** Options (a) common visit count from the smallest pool, (b) keep 100 and let FILTER repeat, (c) enlarge the pool; recommendation (a), a rule fixed before the first run.
5b. **1,000-update sensitivity.** Skip, or three mined cells at one seed (3.7 GPU-hours, repeats flagged because 32,000 visits exceed
   about 5,800 examples). *Recommendation:* skip; it cannot meet the matching rule on any store this project can mine.
6. **Which models to retain.** (Options (i) to (iii) with disk, archive and the D100 rule: section 9.4.) 9 confirmatory (2.5 GB), the 18 mined (4.9 GB), all 36 (9.9 GB). *Recommendation:* the 18 mined (the
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
2. **Final analysis module (built 2026-11-09, E-RQ2-ANALYSIS).** What: Holm within families, paired bootstrap, delta, verdict rules,
   seed spread, sanity rules, tables for the report, tested on the pilot rows. Where: CPU, local. Needs: the lead's answers to the
   entry's questions before the first final row is read.
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

## 9. Reconciliation of 2026-11-09

Read-only checks made after the mining jobs ended, and additions to sections 3, 4, 7 and 8. Evidence classes as above. Where this
section and an earlier one differ, this section is later. Nothing was run on a GPU and nothing on the mining account was changed.

### 9.1 Mining on C, final state (measured)

Jobs 64593 (6 h 05 min) and 64594 (3 h 43 min) COMPLETED; no `HALT` file; `state.jsonl` has 10,000 rows: mined 6,230 (62.3%), no
Python change 2,607 (26.1%), no positive 1,040 (10.4%), quarantined 123 (1.2%). `pr/` holds 6,230 directories (350 MB); the whole store is
**1.8 GB** (the 3.7 GB of section 2 was a linear projection from 1.1 GB at 2,985 rows and was too high by a factor of two; the plan's own
2 GB figure was close). Yield against G2, quarantine classes and the overlap audit are the job of the next session; not read here.

### 9.2 The FILTER pool against the visits of a run (projected from stored numbers)

An example is a directory: a batch holds 32 distinct directories, each contributing up to `max_positives` positives
(`ril/training/data_loader.py`, read; verified). The protocol's G5 line ("32 x N distinct pairs", 3,232 at N = 100, about 32,000 at
N = 1,000) counts visits, that is directories; read as positive rows it would overstate what is available by about 5.5 (the pilot has 7,081
positives in 1,286 directories). The protocol's wording is ambiguous; the code is not.

| Quantity | Value | Source |
|---|---|---|
| mined directories | 6,230 | state log, 9.1 |
| `non_test` share | 92.45% (1,286 of 1,391) | pilot, `docs/experiments/B.md` E-MINED-PILOT; **not measured at full scale** |
| `non_test` directories | about 5,760 | 6,230 x 0.9245 |
| FILTER K = 20 (BM25) keeps | 59.5% (765 of 1,286) | E-MINED-PILOT; pilot only |
| FILTER pool | about **3,430** | 5,760 x 0.595 |
| visits of a 100-update run | **3,200** | 100 x 32 |
| margin | about 7% (230 directories), before the held-out and overlap drops (pilot: 3 of 1,391, 0.2%) | |
| share of FILTER at which the pool equals the visits | 55.6% | 3,200 / 5,760 |
| binomial interval of the pilot share | 56.8 to 62.2% (n = 1,286, standard error 1.4 points; directories cluster by repository, so wider in fact) | reasoned |
| passes at 100 updates | RAW 0.56, FILTER 0.93 (`rq2_plan.py plan --filter-size 3427 --pool-examples 5760`) | plan tool |
| passes at 1,000 updates | RAW 5.6, FILTER 9.3 | 32,000 / pool |

The 7% margin is smaller than the uncertainty of the kept share carried over from one pilot (200 repositories) to 10,000 attempts; with
a FILTER pool of 3,000 the plan tool reports a shortfall of 200 visits (1.07 passes). The size-matched subsample draws as many directories
as FILTER keeps, so it repeats exactly when FILTER does; RAW, which draws from the whole pool, does not.

**Measured 2026-11-10 (E-MINE-FULL-RESULT, D147).** The keep rate of FILTER K = 20 (BM25) on the full set is 67.11% of the 5,789 `non_test`
examples (clustered 95% interval 64.0 to 70.0%), not the pilot's 59.5%: the pool is 3,885 against 3,200 visits (margin +685, +21.4%; +505 at the
interval's lower end), so rule (a) leaves N = 100; passes RAW 0.55, FILTER 0.82. The `pool_aligned` reading has F = 3,320 (+120).

**The rule the protocol needs.** All arms of the comparison must make the same number of visits, and the handling of repeats must be the
same for every arm; otherwise a difference between FILTER and RAW is a difference in distinct examples seen as much as in supervision
(G5, D42). Options, none chosen:

| Option | What it is | Cost | Effect on the contrasts |
|---|---|---|---|
| (a) **Common visit count from the smallest pool** *(recommended, reasoned)* | rule fixed now: N = min(100, floor(F / 32)) for every arm and cell, F the FILTER pool after drops; nothing changes if F >= 3,200; the schedule is untouched (`budget.stop_after`) | none in GPU (a shorter run, at most 7% fewer updates at F of 3,000); a DEV entry if the rule triggers (O1's 100 changes) | both confirmatory contrasts stay clean: no arm repeats, RAW sees a subset of its pool |
| (b) Keep 100 updates, let FILTER and the subsample repeat | report distinct examples seen per cell; FILTER against the subsample is the clean contrast (same F, same repeats) | none | FILTER against RAW is confounded by distinct count and flagged as such; one of the two confirmatory contrasts weakens |
| (c) Make F large enough | lower K until F >= 3,200 plus a margin, or mine more attempts (listing beyond 10,000: cost not measured) | K is part of the arm definition, so this is a design change; mining time unmeasured | contrasts clean, but the arm differs from the pilots' FILTER K = 20 |

Cheapest check that settles the trigger: the prep job's `filter-size` output on the real store (CPU, minutes, already in the plan graph);
the rule is then applied before the first run. The 1,000-update sensitivity (decision 5) cannot satisfy any option: it needs 9.3 visits per directory.

### 9.3 Data location, disk and calendar days

- **Account C lacks the eight evaluation repositories**: `~/ril_eval` is absent on C and is 480 MB on A (measured today). Everything else
  checked is on C and equal to A: `ril_x2/prep` (616 files, 2,454,199,616 bytes, path-and-size manifests equal), `ril_t1/work/e3_cache`
  (521 files, 74,873,170 bytes, manifests equal), and the injected-noise pool files `pool_A`, `pool_T3x`, the BM25 and SweRankEmbed-Small
  score files for the 5,000 directories and the feature table (sha256 equal for all five; on A two of them are links, hashed through
  the link). No content hash of the original staging was recorded (only its size and duration in `docs/COMPUTE.md`); the comparison above
  was made now, content-hashed for those five files and by size for the two directories. The dev dense encoder outputs (`ril_x2/enc`) are
  on A only and were not compared; training does not need them.
- **Copy time** at the recorded staging rate (about 10 GB in 85 minutes, 7.1 GB per hour, `docs/COMPUTE.md`): the eight repositories
  (480 MB) about 4 minutes; the 1.8 GB mined store about 15 minutes if it were moved (it is not, under the split).
- **Disk.** A: 5.1 GB free (90% used, `df` today). The mined cache is projected at 5.6 GB (1.25 GB for 1,286 directories, scaled by
  5,760 / 1,286), so it cannot live on A. C: 26 GB free (49% used). Under `mined=C injected=A` C holds the store 1.8 GB, the cache
  5.6 GB and the 18 mined models 4.9 GB: 12.3 GB, leaving about 14 GB. A could hold at most one retained model group of 4.9 GB (the 18
  injected-cell models) with 0.2 GB spare: effectively none.
- **Calendar days** (`rq2_plan.py plan ... --queue-wait-hours H [--accounts X | --family-accounts mined=C injected=A]`; wait applied to each
  job on the critical path, from "mining finished", copy time not included, the dense-teacher pass and the sensitivity excluded):

| Layout | p50 wait (0.03 h) | p90 wait (2.75 h) |
|---|---|---|
| all on A, or all on C | 34.9 h, 1.5 days | 72.9 h, 3.0 days |
| mined on C, injected on A (`mined=C injected=A`) | 24.0 h, 1.0 day | 53.9 h, 2.2 days |

  GPU use on the measured basis 28.7 hours (36 runs) against the Block 3 cap of 46.7; on the protocol's costs 38.9. The queue figures are
  account A's GPU waits (44 jobs); C has one GPU job on record, so its p90 is not known.

### 9.4 Retention against the test role of the eight repositories (decision, options only)

D100 gives the eight repositories the test role: no tuning, no look at their results to choose or replace them, evaluated once after the
dev analysis (as stated in the brief of this work and in the build entry E-EVAL-REPOS-BUILD; the decision's own text was not located
beyond those). The protocol says the same of Verified ("looked at exactly once", after the dev analysis). All 36 models are therefore needed after the dev analysis unless the
eight, and for the 18 mined models Verified, are scored inside each training job. A model is about 274 MB (137M parameters at two bytes).

| Option | Disk | Archive | Keeps D100's rule | Risk |
|---|---|---|---|---|
| (i) retain all 36 and evaluate after the dev analysis | 9.9 GB; **does not fit on A (5.1 GB free)**, so the 18 injected-cell models must be written on C or moved | needed (C to B, no alias for B; or through the engineer's machine) | yes, by construction: the numbers do not exist before the dev analysis | disk and moves; a technical fault is repaired by re-scoring a retained model |
| (ii) score the eight and Verified inside each job, seal the results unread until the dev analysis is finished; retain only what feeds RQ3 and the report | 2.5 to 4.9 GB (9 confirmatory or the 18 mined) | small | by discipline only: the numbers exist from the first job; the seal is procedural (result files written and not opened, their hashes entered in the ledger) | a fault in an in-job evaluation of a model not retained needs a retrain (0.38 GPU-hours plus evaluation); the eight must be on every account that trains |
| (iii) retain a subset: the 18 mined models on C; score the 18 injected-cell controls inside their jobs, sealed *(recommended, reasoned)* | 4.9 GB on C | small | yes for the confirmatory (mined) cells; procedural seal for the controls | as (ii) for the controls only; the controls are not the confirmatory contrasts |

GPU hours are the same in all three (the encoding is done once per model either way). The recommendation keeps the earlier one (retain the
18 mined models, on C) and says what happens to the other 18.

### 9.5 Not in the repository

- **Final analysis module (gap 6, severity B).** `grep` finds no Holm, delta or verdict code outside documents; the one hit in the code is a
  label string in `ril/training/rq2_plan.py` (the name of a planned job). Scope: one module under `ril/analysis/` reading the per-query
  rows of the run directories (the format `stored_rows.py` reads), producing per contrast and per level (L2 repository-clustered, L3 query
  level) the paired bootstrap interval (2,000 draws), Holm step-down within the primary family of 8 and the secondary family of 8 with
  uncorrected intervals beside, the verdict of section 6 (positive, negative with a bound, inconclusive at delta = 1.5), seed mean and SD
  (three seeds), the injected-noise sanity rules and the dose-response reading, and the tables listed under stage 9; tests on the pilot rows
  (t5, mp) and on constructed cases for each verdict; CPU only. About one work package.
- **Account B has no SSH alias** (`~/.ssh/config` defines `ada` and `adac` only), so the archive script cannot run. The engineer must add an
  alias for B (key-based, `BatchMode`) before the first copy; or choose to archive to the engineer's machine instead; the numbered copy script
  refuses to run without an alias.

### 9.6 What was and was not run before launch

Earlier dry runs on account A, jobs 64656 and 64658, passed all 11 steps and the evaluation-set check (section 2). The retention plan was
checked against an empty directory and the archive script's syntax; there has been no GPU run of the retention switch. `--family-accounts` was
already in the plan tool and its tests (14 tests pass locally).

## 10. Final cells and run scripts (2026-11-09; decisions D124 to D134, DEV-038, DEV-039; entry E-RQ2-FINAL-CELLS)

Evidence classes as above. Nothing was trained and no GPU job was submitted; the plan-only checks ran on the CPU of accounts A and C
(`results/rq2_final/plan_only/`). All settings are `provisional` until launch and none is in `configs/frozen/`.

> **Superseded in places by section 11 (2026-11-09, later):** 45 runs (three cells added), one GPU job per account and seed, the mined
> family's update count computed from the prepared store, the interval rule of the decisions. Where a number in this section differs
> from section 11, section 11 is current. Section 10.2 to 10.4 and 10.6 are kept as the record of the first cell table.

### 10.1 Rulings recorded (section 7 of this plan is settled; the options of 9.2 and 9.4 are settled by D133 and D129)

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

### 10.2 The 36 runs

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

### 10.3 Evaluation by set and the sealed order

| Set | Stage | Scored by | Per checkpoint (GPU-hours) |
|---|---|---|---|
| dev, five repositories | training | each run, `train.py run-batch --eval-set dev` | in the 0.42 per run |
| the eight repositories (D100) | final | `scripts/rq2_final_sets.py run`, retained model, role test | 0.178 measured |
| executable 377 of Verified (D127) | final | the same, three stored parts | 0.388 measured (341 built) plus up to 0.292 projected (36 earlier) |

The final-sets script refuses to start without `--follows-dev-analysis ID` and a complete dev-analysis record naming that id and
covering the run (`write_dev_analysis_record`); each score row carries the id and the record's digest; `read_final_sets` returns rows
only for that id. The job graph puts the final sets after the dev analysis.

**Retained scores of the executable 377 (2026-11-12, D152, DEV-042, `E-RQ3-SCORE-RETENTION`).** The final-sets job encodes the same 377
instances for the same retained models that the agent study later needs, and used to delete the per-instance unit scores with its
node-local work directory. It now copies them, for the executable 377 only, to `<RETAIN_DIR>/exec377_scores/<run id>/dense_scores/`
(`--no-retain-scores` turns it off, `--scores-root` moves it): the byte copies of the score files of the 377, a record with the
checkpoint hash of the model, the configuration hash, the dev-analysis id, one SHA-256 per file and a digest of the whole set, and one
file per stored part. The scoring row of each part carries the digest of the part and the hash of the record file. The copy runs after
the metrics are computed and written and touches none of them (a test compares the result file and the two metric tables of
all three parts byte for byte with and without retention); the sealed order is unchanged (the guard still demands the dev-analysis
record before any scoring, and no score is read before it); the eight repositories are not retained. The agent study's context pass
reads these scores in place of its own encode stage (section 11 and `docs/RQ3_PILOT.md`, "Trained arms"). Space: 377 files of a few
hundred kilobytes each per model (estimate to be replaced by the first measured size).

### 10.4 Job graph (per-run jobs) and critical path

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

### 10.5 Gap status (section 6)

| # | Gap | State now |
|---|---|---|
| 1 | final cell configurations and run script | **done** (36 configurations, two run scripts, submit and preflight scripts); memory request 30 GB (mined), 24 GB (injected) |
| 2 | one run cannot score three sets; order not enforced | **done** (set selector, final-sets script, sealed order in code, recorded in each row) |
| 3 | full-scale prep script and drop-list step | **done** (E-RQ2-FULL-PREP): `scripts/ada/rq2_full_prep.sbatch`, run on 200 directories; it writes the the prep summary file the preflight reads; the run on the whole store is a later prompt |
| 4 | mined cache does not fit A | **decided** (D124); not yet built |
| 5 | memory about 26 GB against 32,000 MB | **blocker found**: a 30 GB request is 11 CPUs (3,000 MB per CPU) against the limit of 10 and never starts (job 66022); the 26 GB is the cache read whole by training (17 GB decoded), reduced to a projected 3 to 6 GB by the shared-string reader (run about 12 to 15 GB). The mined run script and `MEM_REQUEST_MB` still say 30G: set `--mem=30000M` or about 16G and move the preflight constant with it; MaxRSS of the first job still to read |
| 6 | final analysis module | open (another branch) |
| 7 | dense teacher unmeasured | rule fixed (D125); measurement is a later prompt |
| 8 | Verified look covers six of twelve folders | **decided** (D127, DEV-038) |
| 9 | retained-model space and archive | **decided** (D129: retain on C); the alias for B stays open |
| 10 | 1,000-update sensitivity | **decided** (D128, DEV-039) |
| 11 | encoding with a retained model for the 377 | built for the final sets (`final_sets.evaluate_retained`); RQ3's trained-arm contexts still need the same model-directory encoding for the 377 contexts |
| 12 | label audit | open (readers) |

### 10.6 Preflight checklist (section 5), status 2026-11-09

| # | Item | State |
|---|---|---|
| 1 | `yield` on the final state log | **done** (read-only): 10,000 attempted, 6,230 mined, 123 quarantined (1.23%), 0 timeouts, 54,700 positives unrestricted |
| 2 | overlap audit on the full store, drop list applied | **done 2026-11-10** (job 66544): 13 of 6,230 dropped, list tracked with its SHA-256 |
| 3 | prep: `non_test` directories, ranks, feature table, cache, FILTER size | **done 2026-11-10** (same job): 5,789 examples, FILTER size 3,885, held-out rows 0; the link into a launch work directory is the launch step |
| 4 | plan with the real FILTER size and example count; distinct-example statement | open; the preflight prints it from the prep summary (illustrative at 5,800 and 3,450: RAW 0.55 passes, FILTER 0.93) |
| 5 | evaluation sets ready | **done** on A and C (0 missing for the dev set, the eight and the three parts of the 377) |
| 6 | space, retention directory, memory (30 GB cannot start, see gap 5) | **checked** (A 5.3 GB free for 3.0 needed; C 26.0 GB for 10.0 needed; request 30,720 MB under 32,000); final space check at launch |
| 7 | CUDA gate inside each run; one GPU job per account | in the code; the submit script refuses a run already queued |
| 8 | leakage tests on the cluster | 41 of 41 torch and leakage tests passed on the final code (job 66037; first on the earlier code 66005); `scripts/rq2_record.py leakage` writes the record the preflight needs; open until run on the launch commit |
| 9 | registration fixed before the first run | open: the engineer runs `scripts/rq2_record.py registration` |
| 10 | seeds outside the waves, hashes, commit in `RIL_COMMIT` | **done** in the plan and the preflight; the commit is the launch commit |

### 10.7 Next work packages

The plan tool no longer takes `--accounts` (section 9.3 quotes the old call): placement is by family (`FAMILY_ACCOUNTS`, D124), `--family-accounts` overrides it, and `--drop-conditional` plans without the dense-teacher cell.

Full-store prep and overlap job scripts (decision 9 settled: on C); the dense-teacher measurement on 100 directories; the final
analysis module that writes the dev-analysis record; then the launch: `rq2_record.py` (registration, leakage), `rq2_preflight.py` and
`rq2_submit.py --confirm-launch` on C (mined) and A (injected), by the engineer.

### 10.8 Command sequence for the whole-store prep (account C, after E-RQ2-FULL-PREP)

From the repository root at the launch commit, then on C from `$HOME` (the held-out index and pilot files are already in `$HOME/ril_prep/inputs`):

    rsync -a --exclude __pycache__ ril scripts configs <C>:ril_prep/code/
    sbatch --export=ALL,STORE=$HOME/ril_mine/store/full,RUN=full_v1,READINGS=non_test,RIL_COMMIT=<hash> ril_prep/code/scripts/ada/rq2_full_prep.sbatch
    # read $HOME/ril_prep/runs/full_v1/check.json and non_test/prep summary file: scope full, held_out_rows 0, drop_list_applied true
    # copy overlap/drop_f20_non_test.txt into the repository with its SHA-256 (tracked, hashed list)
    python3 -I ril_prep/code/scripts/rq2_full_prep.py link $HOME/ril_prep/runs/full_v1 $HOME/ril_rq2f/work --reading non_test
    # then rq2_plan.py plan --filter-size <summary.filter_size> --pool-examples <summary.examples>, registration, preflight

Add `READINGS=non_test:pool_aligned` for the sensitivity reading. Check `sacct` MaxRSS and elapsed afterwards; a failed job is resubmitted with the same `RUN`.

## 11. Rulings applied before any final run (2026-11-09; decisions D136 to D143, DEV-040, DEV-041; entries E-RQ2-ANALYSIS and E-RQ2-FINAL-CELLS, addenda)

Nothing was trained and no GPU job was submitted. Plan-only checks ran on the CPU of accounts A and C (`results/rq2_final/plan_only/`, jobs 66505 and 66506); the torch and leakage tests ran on account A (job 66507, 41 of 41). All settings stay `provisional` until launch.

### 11.1 Rulings recorded

| # | Ruling | D | Record |
|---|---|---|---|
| 1 | contrasts are decided on the cluster-robust t interval with R - 1 degrees of freedom (clustering over repositories), same Holm procedure; the percentile bootstrap beside it in every table | D136 | DEV-040 |
| 2, 3, 4, 5, 8 | Holm family = one family on one evaluation set (never pooling the eight with the 377); family grouping of section 4 with D69; only the confirmatory FILTER-BM25 against RAW decides the RQ3 contrast; the final L3 claim needs the executable 377 at both levels; "indistinguishable" = absolute difference below the pooled seed SD, the leave-out check compares the sign of the point estimate, a dev sign that disagrees makes the claim inconclusive with the reason written. All accepted as coded | D139 | none (as coded) |
| 6 | clean RAW cell on the injected pool (`inj_clean_raw`, rate 0), three seeds, account A | D137 | |
| 7 | second noise rate: `inj_raw_r01` and `inj_filter_bm25_r01` at r = 0.1 (fresh draws, seeds 100 to 102), three seeds each, account A; dose-response has three points (0, 0.1, 0.4), secondary and exploratory (D69) | D138 | |
| 9 | pool rule replaced (supersedes D133's cycling rule): N = min(100, floor(F / 32)) for every arm of the mined family, F the FILTER pool after the held-out and overlap drops; computed by the launch step from the prepared store, written into the configurations and their hashes before submission; the submit script refuses otherwise | D140 | DEV-041 (conditional) |
| 10 | one GPU job per account and per seed, all arms of the seed in a fixed interleaved order, resumable, skipping finished runs | D141 | |
| 11 | retention as ruled: 18 mined models retained on C; injected-noise models scored on dev inside their jobs and not retained; the eight and the 377 scored once from the retained models after the dev analysis; account B unused | D142 | |

### 11.2 The cell table and the budget (45 runs)

| Account | Cell | Arm | Role | Runs | GPU-h at 0.42 |
|---|---|---|---|---|---|
| C | mined_raw, mined_filter_bm25, mined_sub | RAW; FILTER-BM25; RAW on a FILTER-sized subsample | confirmatory | 9 | 3.78 |
| C | mined_weight, mined_curriculum | WEIGHT; CURRICULUM (BM25 teacher) | exploratory | 6 | 2.52 |
| C | mined_filter_srs | FILTER with SweRankEmbed-Small | exploratory, conditional (D125) | 3 | 1.26 |
| A | inj_raw, inj_oracle, inj_sub | r = 0.4 controls | controls | 9 | 3.78 |
| A | inj_filter_bm25, inj_filter_srs, inj_weight | r = 0.4 | exploratory | 9 | 3.78 |
| A | inj_clean_raw | RAW, rate 0 | control (D137) | 3 | 1.26 |
| A | inj_raw_r01, inj_filter_bm25_r01 | RAW; FILTER-BM25 at r = 0.1 | exploratory (D138) | 6 | 2.52 |

Account A: 27 runs, 11.34 GPU-hours (the 9 added runs are 3.78 of it). Account C: 18 runs, 7.56, plus the final sets of the 18 retained models (15.44) and the conditional dense teacher (at most 6.4). Budget against Block 3 (46.7), measured costs, rulings scope (D127, D129): **34.34 GPU-hours** (training and dev 18.90, the eight 3.20, the executable 377 12.24), margin 12.36; with the conditional teacher 40.74, margin 5.96 (expected about 34.3 and about 40.7). On the protocol's reasoned costs the same scope is 33.84 (margin 12.86; 6.46 with the teacher). The registered design's own scope (the eight for every one of the 45 runs) would be 34.11 measured and 46.80 on the protocol basis, 0.10 over the cap: that scope is not what runs, and the cap holds with the rulings' scope.

### 11.3 Job graph (one job per account and seed) and calendar days

CPU stages on C (report, overlap audit, prep, the launch step that computes F and N and renders the run configurations) first. Training: three jobs on C (mined, seeds 100 to 102; five arms each, six with the conditional cell, which then waits for the dense-teacher pass) and three on A (injected, nine arms each, nothing to wait for), one GPU job at a time per account. Arm order inside a seed job: mined RAW, FILTER-BM25, subsample, WEIGHT, CURRICULUM, (FILTER-SweRankEmbed-Small); injected RAW, FILTER-BM25, ORACLE-CLEAN, subsample, clean RAW, FILTER-SweRankEmbed-Small, WEIGHT, RAW at 0.1, FILTER-BM25 at 0.1: the confirmatory pair first, paired references adjacent, so a job that dies part-way leaves complete pairs for the earlier seeds and the pairs that matter first for the current one. Then the manual collection of the injected results, the dev analysis, and three final-sets jobs on C (one per seed, six retained models each). Per-run records, hashes, result directories and ledger rows stay per run. Wall request: two hours per arm (12 and 18 hours per job).

Critical path in wall hours (GPU-hours as wall), measured waits of account A's GPU jobs (p50 0.03 h, p90 2.75 h, max 8.25 h, section 3), one wait per job on the path:

| Conditional cell | Jobs on the graph | p50 | p90 | max |
|---|---|---|---|---|
| dropped | 15 (6 training, 3 final sets) | 25.3 h (1.1 days) | 58.0 h (2.4 days) | 124.0 h (5.2 days) |
| included | 17 | 35.5 h (1.5 days) | 70.9 h (3.0 days) | 142.4 h (5.9 days) |

Training waits are drawn six times (not 36); the final-sets jobs add three more (the final sets were per-model jobs before: batching them per seed is the same rule and is one change in the graph). Against the per-run graph of section 10.4 the p90 estimate falls from 124 h and 153 h to 58 h and 71 h.

### 11.4 The update count (D140)

The launch step is `python3 -I scripts/rq2_plan.py resolve --work DIR`: it reads the prep summary, takes F = `filter_size`, writes the updates record (F, N, visits per arm, the SHA-256 of the summary it read) and renders all configurations with N and the resolved subsample size into `DIR/configs_resolved`, each hashed. N = 100 if F is at least 3,200 (nothing changes, the projected F is about 3,430), otherwise floor(F / 32) for every arm alike. The preflight checks `updates_computed` and that the resolved configurations match the plan; the submit script refuses to build a mined job graph without a valid updates record (missing, edited, or computed from a summary that has changed since), and the preflight file records N and must match it. The injected family keeps 100.

### 11.5 Checklist (section 10.6 as amended)

| # | Item | State |
|---|---|---|
| 1 | `yield` on the final state log | done |
| 2 | overlap audit on the full store, drop list applied | **done 2026-11-10** (E-MINE-FULL-RESULT: 13 of 6,230 dropped; tracked list, SHA-256 `36e3a144…d9f44`) |
| 3 | prep: `non_test` directories, ranks, feature table, cache, FILTER size | **done 2026-11-10** (F = 3,885, 5,789 examples, held-out rows 0); `resolve` (F, N, resolved configurations) is the launch step, open |
| 4 | plan with the real FILTER size and example count; distinct-example statement | open; the preflight prints it from the prep summary and N (illustrative at 5,800 and 3,450: RAW 0.55 passes, FILTER 0.93) |
| 5 | evaluation sets ready | done on A and C |
| 6 | space, retention directory, memory | checked on both accounts in the rehearsal; final check at launch |
| 7 | CUDA gate in each job; one GPU job per account; no seed job submitted twice | in the code |
| 8 | leakage tests on the cluster | 41 of 41 torch and leakage tests passed on the code of this section (job 66507); open until run on the launch commit |
| 9 | registration fixed before the first run | open (the cell table changed: the digest is new); the engineer runs `scripts/rq2_record.py registration` |
| 10 | seeds outside the waves, hashes, commit in `RIL_COMMIT` | done in the plan and the preflight |
| 11 | converter from the dev results and the final-sets results to the analysis rows | **done** (`scripts/rq2_rows.py`, `ril/evaluation/final_rows.py`; refuses without the dev-analysis id; tested on a synthetic final-sets result and on the stored pilot rows) |
| 12 | the dev-analysis record writer (`write_dev_analysis_record`) is called by the analysis step | open: the analysis module reads rows; writing the record is the engineer's step after the dev analysis |
| 13 | an SSH alias for B (optional copy of the 18 retained models) | open, optional, a later step |

### 11.6 What the rehearsal found

Both rehearsals passed on a synthetic work directory (every check true, N = 100 on C), and the real directories fail exactly the items that wait for the prep job and the records (registration, leakage record, prep summary, inputs, `updates_computed`). The submit script refused three ways: no preflight file (exit 2), no confirmation (exit 2), N not computed from a prepared store (exit 2); nothing was submitted. Findings: (a) the registered design's scope on the protocol basis is 0.10 GPU-hours over the cap with 45 runs (section 11.2): no action, that scope does not run; (b) a panel with fewer than two queries has no interval; the analysis refuses it with an error; (c) the per-seed job loads the mined cache once for its arms, so the memory estimate of section 10 (26 GB projected) is unchanged only if the evaluation stores are released between arms (`--drop-eval-stores` is set): the MaxRSS of the first seed job is the check; (c2) **the 30 GB request of section 10 cannot start** (found by the full-store prep trial, job 66022: partition u22 grants 3,000 MB per CPU, so 30,720 MB is allocated 11 CPUs against the account's 10): the mined request is now 30,000 MB (10 CPUs, the largest that can start; D143, tactical), the injected request stays 24,576 MB (9 CPUs), and the preflight checks the allocated CPUs against the limit; (d) the FILTER-SweRankEmbed-Small cell can have a different pool size from FILTER-BM25's; N follows the BM25 pool (the confirmatory one) and the distinct-examples diagnostic reports the other if it repeats.
