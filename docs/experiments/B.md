# Experiments: stored-output analysis

Append-only log, entries by this workstream only. Rules, interpretation rules and the index of all entries are in
`docs/EXPERIMENTS.md`; the same rules apply here. Entry ids are unique across all experiment logs.

## Registry

| ID | RQ | What varies | Held fixed | Seeds | Primary outputs | Status |
|---|---|---|---|---|---|---|
| E-STORED-ANALYSIS | RQ2 (evidence) | nothing is trained or re-run: four readings of per-query rows already stored under `results/rq2/` | every stored run, query set, gold reading and metric as in E-PILOT-ARMS2 | none (no randomness except the bootstrap, seed 0) | variance components and minimum detectable differences; per-query gain by slice; per-query winner and best-of-arms oracle; per-query loss under injected noise | done 2026-11-02 (exploratory; Part A tables and checkpoint inventory) |

## E-STORED-ANALYSIS: what do the stored per-query rows say that the cell means do not? Exploratory, readings stated 2026-11-02 (before any table)

Status: exploratory, outside the pre-registered RQ tables. CPU only, local; no run, no GPU-hours. Code `ril/analysis/stored_*.py`,
wrapper `scripts/stored_analysis.py`, tests with a synthetic fixture; tables under `results/tables/stored/`. All rows are
`exploratory`.

**Inputs.** `query_rows.csv` of the runs under `results/rq2/`, dense column of each run (column `name` starting `dense:`), reading
`units_all_nomod` (the primary reading of E-PILOT-ARMS2), metric nDCG@10 at L2 and Recall@100 at L3, role `dev`, the five dev
repositories without ansible (the evaluation set of Waves 5 to 8: 351 L2 and 155 L3 queries). Runs used:

- untrained encoder: the step-0 rows of the learning curve (`t3_curve_raw`); the dir that has a complete set is used and its
  queries are intersected with the Wave 6 queries;
- Wave 6 (E-PILOT-ARMS2 stage 1): `t5a_*`, seeds 0 and 1: RAW, subsample (draw 0), FILTER with BM25, CodeRankEmbed and
  SweRankEmbed-Small, WEIGHT, CURRICULUM;
- Wave 7 (E-PILOT-NOISE): `n1_r20_*`, `n1_r40_*`; Wave 8 (E-PILOT-NOISE-SIB): `n8_r40_*`; seeds 0 and 1;
- Wave 5 (E-PILOT-ARMS stage 1, `t4a_*`): per-query rows are not under `results/rq2/` (only the tables are tracked); it is
  skipped and listed in the report.

A run's seed is the `seed` key of its `config.yaml`; runs of one cell are matched across arms by that seed. Per-query values are
in the metric's own 0 to 1 scale; tables print points (x100).

**1. Seed noise decomposition.** Per level, for RAW alone (levels of the metric) and for each Wave 6 cell minus RAW
(paired differences, `d = cell - RAW`, same seed index), method-of-moments variance components of a nested layout
(repository, query within repository, seed crossed with query): `s2_repo`, `s2_query`, `s2_seedquery` (within-query,
between-seed variance), `s2_seed` (variance of the run means across seeds, with `s2_seedquery / n` removed; negative values are
reported as 0 and flagged). Contribution to the variance of a run mean: `s2_repo / R + s2_query / n + s2_seedquery / n + s2_seed`
(R repositories, n queries). Interval: percentile bootstrap over repositories (2,000 draws, seed 0; at L3, R = 2, so repository
components are descriptive only and say so). Minimum detectable difference at k seeds per arm, 5% two-sided, 80% power:
`2.8016 * sqrt(s2_repo_d / R + s2_query_d / n + (s2_seedquery_d / n + s2_seed_d) / k)` on the paired differences
(the term `s2_repo_d / R` is dropped in the second, "query-level" variant, which is what the L3 intervals of the earlier tables
used). Computed at k = 2 and 3 by pooling the six cells' components. Compared with the values already in the docs:
E-PILOT-ARMS2 (3 seeds: L2 1.4, L3 1.7) and E-PILOT-NOISE (2 seeds: r = 0.2 1.56 and 2.77, r = 0.4 2.15 and 1.86). **Reading
rule:** a "disagreement" is a stored value outside the interval of the recomputed one, or a ratio above 1.25 or below 0.8 where
there is no interval; the old values are not edited.

**2. Who gains from training.** Per query, `gain = mean over seeds (RAW at 100 updates, Wave 6) - untrained`. Slices:
(a) repository; (b) number of positives = size of the gold set of the query at that level under `units_all_nomod` (union of the
`units_all` lists of the level's positives without `<module>` ids; read from `data/processed/e1/out/units/`), in bins by quartile
of the evaluated queries of the level (cut points merged where equal); (d) positive unit type, from the `kind` of the query's
positives: a query is counted under every kind it has (function, method, class, test unit; module residuals and non-Python
positives have no unit in this reading), and separately as "single kind" or "mixed". Mean gain per slice with a bootstrap over
repositories (2,000 draws, seed 0; for slice (a) the repository is the stratum, so the bootstrap is over queries inside it).
**(c) lexical overlap of the query with its positives is not computed:** the issue text and unit texts of the dev repositories
are not on this machine (only metadata and patches are), and Part A is CPU-and-local by the brief; recorded as skipped, with
what it needs (the issue statements of the 507 dev queries and the parsed text of their gold units). **Reading rule:** a slice
"gains more" only if its interval excludes the all-query gain's interval or the difference between slices has an interval
excluding 0; with five repositories at L2 and two at L3, slice intervals are wide and a gain concentrated in one repository
is reported as that, not as a property of the slice.

**3. Complementarity.** Per query and level, each Wave 6 arm's metric is the mean of its two seeds. Winner = the arm with the
largest value; a tie (difference below 1e-9) is counted as a tie, not assigned. Reported: win counts per arm; the share of
queries where the best non-RAW arm beats RAW by more than a threshold, at thresholds 0 (any), 0.01, 0.05 and 0.10 in metric
units (no single threshold is the primary; "one rank-metric step" is not defined by the brief, so all four are shown; for
Recall@100 one step is one more positive, 1/n_positives); the mean of the per-query best-of-arms oracle (maximum over arms,
including RAW). **The oracle is an upper bound that no deployable method reaches** and carries that label in every table.
**Seed-noise control (required):** the same statistics for a "best of two RAW seeds" oracle against the mean of the two RAW
seeds, and the share of queries where RAW seed 1 beats RAW seed 0 by more than each threshold; an arm-level complementarity is
only claimed if it exceeds this control. The best-of-seven-arms oracle is also compared with a best-of-seven oracle drawn from
the two RAW seeds plus the subsample's two seeds (arms that differ only in data subset) to separate arm differences from the
number of draws.

**4. Which queries does noise hurt.** The item 2 split applied to `loss = RAW at r = 0 (Wave 6 `t5a_raw`) - RAW at r
(Wave 7: r = 0.2 and 0.4 `n1_*_raw`; Wave 8: sibling r = 0.4 `n8_r40_raw`)`, seeds averaged, with slices (a), (b), (d) as above.
Concentration: the share of the total loss carried by the worst 10% and 25% of queries (sorted by loss), against the same
statistic for the seed-to-seed difference of RAW at r = 0 (a no-noise reference of the same kind). The share of queries with no
change at all (absolute difference below 1e-9 between the seed-mean at r = 0 and at r), reported with the number of queries in
which the metric cannot change (metric already 0 at both, or 1 at both). **Reading rule:** damage is "concentrated" only if the
worst-10% share exceeds the no-noise reference's by more than the bootstrap interval of the reference.

**Does not show** anything about a trained-to-convergence encoder, other encoders, or the public pool's noise; slices are
descriptive, two seeds, five (L2) and two (L3) repositories, dev only. The oracle in item 3 is not a method. Nothing here is a
decision.

## Results (produced 2026-11-02; CPU, local; 2,000 bootstrap draws, seed 0)

Command: `python -I scripts/stored_analysis.py results/rq2 data/processed/e1/out/units results/tables/stored results/logs/stored_analysis.json --draws 2000 --seed 0`
(22 s). Tables `results/tables/stored/s1_components.csv`, `s1_mdd.csv`, `s2_gain_by_slice.csv`, `s3_complementarity.csv`,
`s3_oracles_and_controls.csv`, `s4_loss_by_slice.csv`, `s4_loss_concentration.csv`, `s4_no_change.csv`; log
`results/logs/stored_analysis.json` (input hash, hardware). Code `ril/analysis/stored_{rows,stats,analysis}.py`, tests
`tests/unit/test_stored_analysis.py`. Percentage points unless stated; 351 L2 and 155 L3 dev queries (two L2 queries have no gold
unit under the reading and are dropped, as in the earlier tables). **All rows exploratory.**

**Deviations from the readings stated above (recorded, nothing else changed).** (1) At L3 there are two repositories, so a
repository-cluster bootstrap has three distinct resamples; the L3 intervals in every table are query-level (queries resampled
with replacement, within repository for the components), the convention of the earlier tables. L2 intervals are
repository-cluster as stated. (2) The "share of the total loss" of item 4 has a denominator that is about zero for the no-noise
reference (a seed difference sums to about 0), so it is unstable (reference shares above 1); the table carries both that form and
the share of the *positive* loss mass, and the reading uses the second. (3) Slice (c) was skipped as stated. (4) Wave 5
(`t4a_*`) per-query rows are not in `results/rq2/`; skipped.

**Data check.** The pooled seed SD (SD of run means across seeds, pooled over cells) recomputed from the stored rows is 0.52 /
0.73 (Wave 6, L2 / L3), 0.51 / 0.99 and 0.77 / 0.66 (Wave 7, r = 0.2 and 0.4), 0.42 / 0.69 (Wave 8), the values quoted in the
earlier entries to the second decimal (`s1_mdd.csv`, rows `pooled_seed_sd_all_cells`): the loaders read the same numbers.

**1. Seed noise decomposition.** Variance of a RAW run's mean at 100 updates (Wave 6, two seeds): at L2 85% repository (5
repositories), 12% query within repository, 1% seed-by-query, 2% seed (total 12.3 points squared; direct seed variance of the run
mean 0.35); at L3 (2 repositories, repository component 0 after flooring, not estimable) 75% query, 3% seed-by-query, 22% seed
(total 4.2; direct seed variance 1.05). Seed noise is a small part of the variance of a level at L2 and the largest identifiable
part after the query term at L3; the repository term dominates absolute levels but cancels in a paired difference on the same
queries. Minimum detectable difference (paired, 5% two-sided, 80% power, cells pooled, interval from the bootstrap in
brackets), Wave 6, six cells against RAW:

| seeds per arm | L2, with repository term | L2, query level | L3, with repository term | L3, query level |
|---|---|---|---|---|
| 2 | 1.99 [1.14, 2.99] | 1.32 [0.95, 2.71] | 3.15 [2.21, 4.73] | 1.23 [0.90, 2.39] |
| 3 | 1.85 [1.01, 2.56] | 1.10 [0.81, 2.23] | 3.08 [2.12, 4.59] | 1.02 [0.75, 1.96] |

Against the values already in the docs (E-PILOT-ARMS2, three seeds: L2 1.4, L3 1.7): the stored value lies inside the interval of
the query-level variant at both levels (ratios 0.78 and 0.60; the query-level variant is the closer analogue of the earlier
"larger of seed bound and query bound"), inside the with-repository interval at L2 (ratio 1.32) and **outside it at L3** (1.7 against
[2.12, 4.59]; the repository term there rests on two repositories). Noise pilots at two seeds, stored value against the
query-level variant: E-PILOT-NOISE r = 0.2: L2 1.56 against 1.66 [0.87, 3.60], L3 2.77 against 3.59 [2.42, 5.11]; r = 0.4: L2 2.15 against 1.89
[1.45, 2.62], L3 1.86 against 1.83 [1.34, 3.09]; E-PILOT-NOISE-SIB: L2 2.00 against 1.19 [1.00, 2.68], L3 1.93 against 1.69
[1.06, 2.77]; all inside. Against the with-repository variant the stored value is outside at L3 for r = 0.2 (2.77 against
[4.03, 7.76]) and r = 0.4 (1.86 against [3.15, 7.26]), inside in the other cases. **Disagreements by the stated rule: three, all L3
with the repository term (Wave 6 at three seeds, noise r = 0.2 and r = 0.4 at two seeds); none for the query-level variant.** The
old values stand unedited. What the disagreement means: if the question is whether a difference would hold on repositories other
than these two, the L3 minimum detectable difference is two to three times the earlier figure; if the question is the
difference on these queries, the earlier figure holds. The seed component rests on 1 degree of freedom per cell pair and moves
between 0 and 2.3 points squared across the Wave 7 sets (`s1_components.csv`, flags `s2_seed<0` where it was floored to 0).

**2. Who gains from training** (RAW at 100 updates, Wave 6 seed mean, minus the untrained encoder; all-query gain +9.59 [6.89,
11.63] L2, +11.13 [9.08, 13.24] L3, the values of E-PILOT-ARMS2). By repository the gain ranges from +4.90 [1.19, 9.55]
(streamlink, 37 queries) and +5.65 [1.67, 9.56] (haystack) to +12.56 [8.67, 15.91] (openlibrary); at L3 openlibrary +11.34, qutebrowser +10.90. By
number of positives (quartiles of the level's queries) L2: at most 4 positives +12.62 [10.52, 14.21], 5 to 8 +6.73 [1.32,
10.15], 9 to 14 +9.01 [4.05, 13.45], more than 14 +9.29 [4.63, 12.10]; L3: at most 16 +16.74 [11.05, 22.70], then +7.20, +10.69, +9.23.
By unit type, L2: queries with a function positive +11.55 [8.20, 13.60], method +8.56 [5.34, 11.10], class +11.27 [5.84, 13.96]; L3: function
+11.40, method +9.52, class +9.27, test unit +9.40 (intervals overlapping). **By the stated rule no slice gains more than the
all-query gain except L3 queries with a single kind of positive (+28.17 [14.39, 42.20], 10 queries), which is too few to read.**
The gain is positive in 61% (L2) and 79% (L3) of queries and negative in 15% and 13% (`share_positive`, `share_negative`);
it is wide, and not concentrated in a slice that this evidence can name. The slice with the smallest gain is the repositories
with the fewest queries and the "5 to 8 positives" bin, both inside the all-query interval. Slice (c) not computed.

**3. Complementarity** (Wave 6, seed-averaged arms). Queries on which one arm is strictly best (ties not assigned; 132 of 351 at L2 and 80 of 155
at L3 are ties): L2 RAW 21, subsample 37, FILTER-BM25 50, FILTER-SweRankEmbed-Small 27, FILTER-CodeRankEmbed 42, WEIGHT 14,
CURRICULUM 28; L3 RAW 2, subsample 22, FILTER-BM25 13, FILTER-SRS 8, FILTER-CRE 11, WEIGHT 2, CURRICULUM 17. Share of queries
where the best of the six other arms beats RAW by more than 0 / 0.01 / 0.05 / 0.10: L2 0.62 [0.50, 0.74], 0.55 [0.44, 0.66], 0.33
[0.23, 0.41], 0.13 [0.09, 0.18]; L3 0.68, 0.66, 0.25 [0.18, 0.32], 0.08 [0.04, 0.12]. **Seed-noise control:** the best of two RAW seeds
beats the mean of the same two seeds by more than 0 / 0.01 / 0.05 / 0.10 on 0.58 / 0.44 / 0.20 / 0.07 (L2) and 0.60 / 0.55 / 0.12 / 0.01
(L3) of queries; the margin shares of the six-arm maximum are above this control at 0.05 and 0.10 but it also takes a maximum
over three times as many draws. Oracle (an upper bound, not a method) in points, L2 / L3: RAW 26.76 / 45.10; best of the two RAW
seeds 29.36 / 46.98 (+2.60 / +1.88); best of RAW and subsample, two seeds each, 31.20 / 49.14 (+4.45 / +4.05); best of the seven
seed-averaged arms 30.70 / 48.69 (+3.94 / +3.60); best of all 14 runs 33.65 / 50.88 (+6.89 / +5.78). The seven-arm oracle is not
above the four-run oracle drawn from RAW and its size-matched subsample (arms that differ only in a data subset; the seven-arm
oracle uses seed-averaged arms, which are less noisy than single runs, so the comparison favours the four-run oracle), so the data show
no complementarity between arms beyond what selecting among noisy draws gives; with two seeds this cannot rule out a small one.
Interpretation: a per-query switch between arms is not supported as an idea by these rows.

**4. Which queries does noise hurt** (RAW at 100 updates; loss = r = 0 minus noised, seed means). Mean loss at r = 0.4: uniform noise
3.67 [2.04, 4.85] L2, 2.32 [1.42, 3.21] L3; sibling noise 1.01 [-0.06, 1.84], 0.52 [-0.12, 1.14] (the values of the earlier entries). Uniform r = 0.4 by repository, L2: qutebrowser 5.20, haystack 4.70, conan 4.49, streamlink 2.42,
openlibrary 0.99 [-0.13, 2.18]; at L3 qutebrowser 3.94 against openlibrary 0.83, so the loss is concentrated in repositories (the
repository with the largest gain from training is the one hurt least). By number of positives at L2: at most 4 positives 5.10 [3.27, 6.27],
5 to 8 2.41; no unit-type slice differs. **Share of queries with no change at all** (|difference| < 1e-9 between the seed means): r = 0.2 0.35 L2,
0.41 L3; r = 0.4 0.32 [0.24, 0.41] L2, 0.28 [0.21, 0.36] L3; sibling 0.35 and 0.36; of the L2 share about 0.23 of all queries are
queries on which the metric cannot move (0 or 1 under both). The same statistic for two seeds of RAW with no noise is 0.43 [0.34, 0.52] L2
and 0.40 [0.33, 0.48] L3, so noise at r = 0.4 turns few queries from unchanged to changed (L2 0.43 to 0.32). Queries made worse / better at r = 0.4: 52% / 15% (L2), 54% / 18% (L3);
sibling 38% / 27% and 40% / 25%. **Concentration:** the worst 10% of queries carry 47% (L2) and 49% (L3) of the positive loss mass at r =
0.4 uniform (worst 25%: 81%, 80%), against 67% to 79% (L2) and 52% to 76% (L3) for the seed difference of RAW with no noise (the
reference is a single-seed contrast and noisier than a two-seed mean, which makes it conservative). The damage is therefore not
concentrated in a few queries beyond what seed noise already concentrates; the pre-registered total-loss form cannot be read
(deviation 2). It is spread over about half of the queries and unevenly across repositories.

**Limits.** Two seeds (the seed component of every decomposition has one degree of freedom per pair); five L2 and two L3
repositories; dev only; one encoder; the untrained rows come from the learning-curve job (same code and queries, ansible
dropped by intersection); intervals are bootstrap intervals with the deviations above. Nothing here is a decision.

## Checkpoint inventory (read-only on the cluster, 2026-11-02)

Account A only (the one alias on this machine; B and C answer by full login and were not inspected, so whatever the last N1
stage left on C is not covered: it ran the same job script). Read commands only (`ls`, `find` with name predicates and
`-printf`, `du`, `df`, `quota -s`); nothing was written, moved, deleted or loaded. Listing record (home path replaced by
`<home>`): `results/logs/checkpoint_listing_a.json`; table `results/tables/checkpoint_inventory.csv` (100 rows: 89 training
runs, 10 learning-curve steps, the untrained step 0); summary `results/logs/checkpoint_inventory.json`; code
`ril/analysis/checkpoint_inventory.py`, wrapper `scripts/checkpoint_inventory.py`, tests `tests/unit/test_checkpoint_inventory.py`.

- **Retained on shared storage: one run, and it is not a result run.** `<home>/ril_t1/work/ckpt/t1_validate_tiny/74d02bf3/`
  (config hash 74d02bf3, training-stack validation with a 530 KB toy encoder on the CPU): `final/` plus `step_000000019/` and
  `step_000000029/`, 3,728,245 bytes in all. Its evaluation outputs are in the repository (`results/rq2/t1_validate_tiny/`).
- **Node-local and gone: every other run.** 88 training runs (the CPU validation on real pool directories, the 36 smoke runs `t2_*`, the
  17 Wave 6 runs `t5a_*` and `t5b_*`, the 24 Wave 7 runs and the 10 Wave 8 runs) wrote their checkpoints, half-precision final model and encoded stores under node-local `/tmp/ril_<exp>_<job>/`
  (the recorded `checkpoint_root` of each run); each job script removes that directory at exit (`rm -rf "$CK"` in
  `t1_validate`, `t2_runs`, `t3_curve`, `t4_runs`, `t5_runs`, `n1_runs`, `n8_runs`), and node-local storage is not shared. The same
  holds for the 10 learning-curve steps (steps 100 to 2,000 of two seeds). Step 0 of the full-set curve job is the untrained encoder
  (no checkpoint written). The 30 Wave 5 runs (`t4a_*`, `t4b_*`) are not in `results/rq2/` (their per-query rows are
  not tracked; their tables are), so they have no inventory rows; `t4_runs.sbatch` removes its work directory too.
- **Evaluation outputs in the repository:** 99 of the 100 rows (per-query rows and `results.json`); the exception is
  `t1_validate_cre` (a CPU validation run with no evaluation).
- **Other weights on the shared storage are not trained here:** the downloaded base encoders under `<home>/ril_e/hf_cache`
  (CodeRankEmbed 547 MB, Qwen3-Embedding-0.6B 1,192 MB, SweRankEmbed-Small 273 MB), and encoded stores of base encoders
  under `<home>/ril_x2/enc` (the `ril_x2` tree is 8.47 GB, of which none is a trained model).
- **Disk, account A:** `df` 8.54 GB available of 52.4 GB (84% used); `quota -s` 21,831 MB used, soft 25,000, hard 27,000 (3,169 MB
  below the soft limit), files 832 of 3,000 (soft) and 3,200 (hard). The whole retained checkpoint tree is 3.2 MB.

**What could be evaluated cheaply from retained checkpoints: nothing.** No retained checkpoint belongs to a run that produced a
reported number, so there is no encode-only evaluation to add, and none was run. For the lead's decision, the stored costs
(`docs/COMPUTE.md`, E-PILOT-ARMS2): one 100-update run costs 0.38 GPU-hours, of which the training loop is 4.5 min (0.075) and the
encode-only evaluation of the five dev repositories (316k unit texts at about 290 texts/s) 18 min (0.30); the third dev
repository's ansible (274k unit texts) about 20 min (0.33) per checkpoint. So keeping the final model of each run would have saved
0.075 GPU-hours of 0.38 per later re-evaluation; the cost of any new evaluation (another dev set, another reading, ansible) is
dominated by encoding, not by training, and without a retained model it needs the retrain (0.38 + the new evaluation). A final
half-precision model is about 274 MB (E-TRAIN-STACK), so 14 retained models would be about 3.8 GB against 3.2 GB to the quota's
soft limit on account A: a retention policy for later waves is the lead's decision.
