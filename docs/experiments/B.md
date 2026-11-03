# Experiments: data mining and stored-output analysis

Append-only log, entries by this workstream only. Rules, interpretation rules and the index of all entries are in
`docs/EXPERIMENTS.md`; the same rules apply here. Entry ids are unique across all experiment logs.

## Registry

| ID | RQ | What varies | Held fixed | Seeds | Primary outputs | Status |
|---|---|---|---|---|---|---|
| E-MINE-PILOT | RQ2 (data) | nothing varies: the unfiltered PR-mined set is built and measured against the published pool | seed 0, the 5,000-directory population, held-out list v2 with the Loc-Bench tier | 0 | `results/mining/` tables from `<run root>/summary.json` of a run root | M0 to M4 done (live, 2026-11-02/03; the full run is not started) |
| E-MINED-PILOT | RQ2 (data, evidence) | training data: the PR-mined pilot set (pool-like reading) against the published pool; supervision on the mined set: RAW, FILTER K = 20 (BM25 teacher), RAW on a random subset of FILTER's size | model, schedule (100 updates of the 3,000-update schedule), batch, negatives, loss, optimizer, evaluation (five dev repositories, DEV-028) | 0, 1 | per-query rows of 6 runs under `results/rq2/mp_*`; tables in the results tables folder with the prefix mp_ | done 2026-11-03/04 (exploratory; six runs) |
| E-STORED-ANALYSIS | RQ2 (evidence) | nothing is trained or re-run: four readings of per-query rows already stored under `results/rq2/` | every stored run, query set, gold reading and metric as in E-PILOT-ARMS2 | none (no randomness except the bootstrap, seed 0) | variance components and minimum detectable differences; per-query gain by slice; per-query winner and best-of-arms oracle; per-query loss under injected noise | done 2026-11-02 (exploratory; Part A tables and checkpoint inventory) |

## E-MINE-PILOT: an unfiltered PR-mined training set, built from scratch, and what the published pool's selection removed. Exploratory, stated 2026-11-02 (before any run)

Status: exploratory, outside the pre-registered RQ tables. Code: `ril/data_mining/` (package), `scripts/mine_pilot.py`, `scripts/ada/mine_pilot.sbatch`, `configs/mining/pilot.yaml` and `validation.yaml`, tests `tests/unit/test_mining_*.py` and `tests/reproducibility/test_mining_repro.py`. Implementation choices that go beyond the stated design are in DEV-015 to DEV-018. Evidence class of every table below, once filled: measured, exploratory. **Nothing in this entry is a measurement yet:** stage M0 (code and offline tests) is done; stages M1 to M4 need the live API and are blocked (see "Blocker").

**Why.** The published pool looks selected per pull request by one teacher (E-POOL-RANKS, Q50), so RAW in RQ2 is not raw. A set whose positives are never filtered by any retriever makes the selection measurable and gives RAW a definition. The system part (index, fusion) is not touched.

**Design, fixed before any run (engineer, 2026-11-02; D60 to D66 of the brief).**
- D60 Population: the repositories of the 5,000-directory pool (D41; first 5,000 directories after the held-out filter by `sha256("0:<directory>")`, the rule of `ril.training.train_jobs`). Pilot: the first 200 repositories in the seeded order `sha256("0:<repository>")`.
- D61 Link: GraphQL `closingIssuesReferences` of the merged pull request. A body regex ("fixes #n") selects nothing; its extra recall is counted. The unit is the (issue, PR) pair; multiplicity is reported.
- D62 Query: the issue title, a blank line, the issue body. `issue_edited_after_pr_created` is recorded (`lastEditedAt` against the PR's `createdAt`) and its share reported; history is not reconstructed.
- D63 Diff: compare `baseRefOid...headRefOid`, base = the response's merge base, so merge style does not matter. Positives: units of the base commit that own a removed or rewritten old-side line or a pure insertion (innermost unit; DEV-015). Added functions are not positives and are counted (`added_function_defs`, DEV-018). Test and module-level units are kept with flags. Per positive: path, kind, name, `is_test`, removed and inserted lines, unit lines and `loc`. Nothing retriever-dependent is computed.
- D64 Quarantine: a pull request that cannot be fetched or parsed completely is kept in the state log with its reason and counted in every yield table. Reasons: `compare_not_found`, `compare_failed:*`, `diff_truncated` (300-file cap), `patch_missing`, `snapshot_unavailable`, `changed_file_unparseable:<cause>`, `old_file_missing_at_base`, `missing_commit_id`. Parse-failure causes are a heuristic reading of the error text (`classify_parse_failure`), reported with their remainder `syntax-other`.
- D65 Held-out: exact names plus current-name resolution plus the content-overlap audit, Loc-Bench tier on; the loss is reported at repository and directory level (`population.counts`); a repository whose current GitHub name is held out is dropped and counted (`renamed_into_held_out`). The content-overlap audit of the mined corpora is **not built** in this stage (it needs the held-out corpus hash index, streamed from the benchmark archive on the cluster).
- D66 Output: `pr/<owner>__<name>-<PR>/{corpus.jsonl, queries.jsonl, qrels/test.tsv}` plus `<instance>/pr_meta.json`; `pool_reader` reads it unchanged through the zip and listing written by `pack` (tested). `<run root>/provenance.json`, resumable `<run root>/state.jsonl`, `<run root>/budget.json`, `<run root>/api_events.jsonl` (every call and every sleep).

**Questions and reading rules (committed before M2).**
1. *Agreement with the published pool (M1).* For pull requests in both sets (same repository and number): exact-match share of the positive sets, mean Jaccard, extra and missing positives, in two readings: all positives, and positives outside test files. Expected before the run, from the dataset card (no positive lies in a test file): extras that lie in test files; and function-level corpora, so class and module positives sit in the side table only. A disagreement that is not one of these is listed as an open question with examples; none is hidden. A low agreement is a statement about the two constructions, not about which is right; hand-checking 20 pull requests (`results/mining/handcheck_<N>.md`) reports what it shows and claims no correctness.
2. *Yield (M2).* Descriptive: repositories, merged PRs, PRs with a closing issue, pairs, attempted, mined, quarantined by reason, PRs with at least one positive, positives per PR (median, mean, p90), API calls, wall time, parse-failure share by cause. No hypothesis.
3. *Selection (M2).* For each repository, the share of its linked merged pull requests that the published pool kept (also pool PRs with no closing reference found, reported separately). Kept versus dropped mined PRs: positives per PR, changed Python files, hunk lines, corpus size, as medians with repository-clustered bootstrap intervals of the difference. The pool "selected for" a property only if the interval of the difference excludes 0; otherwise "not distinguishable at this sample size". The sample is a seeded draw of the linked PRs, so the kept and dropped groups are subsamples, not the full populations.
4. *Rank comparison (M3).* Share of directories with no positive in the top 10 under BM25, CodeRankEmbed and SweRankEmbed-Small (published definition, `rank` column), directory-level Wilson interval and repository-clustered bootstrap beside it, next to the published pool and the never-filtered Verified export, read from `results/tables/x3_pool_ranks_topk.csv` and `x3_pool_ranks_reference.csv` (E-POOL-RANKS): published pool estimate, top 10, no positive: CodeRankEmbed 15.3%, BM25 23.2%, SweRankEmbed-Small 1.7%; never-filtered Verified export, top 10: SweRankEmbed-Small (stored text) 19.3%, CodeRankEmbed 35.7%; BM25 has no Verified row (measured there only if the same job is run). The brief of this stage names 15.3% and 23.2% as BM25 and CodeRankEmbed and 19.3% as Verified without a teacher; the tables assign 15.3% to CodeRankEmbed and 23.2% to BM25, and 19.3% to SweRankEmbed-Small, so the table values are used and the correction is recorded here. **The comparison counts only with at least 100 pilot directories that have a positive** (`results/mining/README.md`); with fewer it is reported as "too small to compare" together with the pull requests needed at the measured yield (`rank_compare.reading_rule`). A difference of shares is called real only if the intervals of both sets exclude each other's point estimate; otherwise indistinguishable at this size. The mined set is function-level with the same teacher text form as the pool, so the numbers are comparable in construction; they are not comparable in repository mix, which is stated beside the table.
5. *Scale cost (M4).* Linear extrapolation from the measured per-PR API calls, wall time and bytes to 2,000 repositories and to 20,000 and 100,000 pull requests; the binding constraint is the one whose extrapolated requirement is largest against its limit (REST 5,000 requests per hour, GraphQL 5,000 points per hour, wall time per job, disk quota). The full run is not started.

**Blocker check at the start of the live stages (measured 2026-11-02, account A; presence only, no value printed).** `GITHUB_TOKEN` is non-empty in a non-interactive `ssh` command and in a submitted job (job 53623, one second, `u22`, gnode002); an unauthenticated `GET https://api.github.com/` from that compute node answers 200. No token or egress blocker. (The earlier blocker text, written when the token was absent, is superseded.) `quota -s` on the login node reports the mount the file server mount named share1 (21,831 of 25,000 MB, 832 of 3,000 files), not `$HOME` (`ada5:/home2`, 50 GB with 7.6 GB available by `df`); `$HOME` holds 320,183 files, so the file figure is not a limit on it. The binding disk figure for the runs is `df`.

**Result of M0 (offline; synthetic and hand-built inputs, not a measurement).** 83 tests (`pytest tests/unit/test_mining_*.py --collect-only -q`) in `tests/unit/test_mining_*.py` and 2 in `tests/reproducibility/test_mining_repro.py` (85 collected together): patch parsing and the mapping against hand-built fixtures (function, method, nested function, class body, decorator change and addition, file rename, pure rename, file deleted, file added, module-level edit, new function, new method, generated file, binary file, a diff touching thousands of lines of one function, the compare endpoint's file cap, three-page pagination); the API client against scripted responses (conditional request, retries, retry-after, primary and secondary limits, reserve, token never in `repr` or logs); the per-PR pipeline and its quarantine reasons; the reader contract (`pool_reader` over the packed zip); a crash between the directory and its state row is adopted on resume; a second run makes no call and leaves the same bytes; two fresh runs give the same bytes and the same zip. The API responses are hand-built from the documented shapes and are **synthetic**: they show the code against these shapes, not against the live service. Shapes to verify at M1 against the live API, each a place the synthetic fixture could be wrong: `baseRefOid` of a merged pull request is the commit the compare endpoint should start from (the merge base of the response is what is used); `closingIssuesReferences` for a merged PR; the compare `files` limit and `patch` omission rule; a fetch of an unreferenced commit by SHA from the git endpoint.

**Result of M1 (measured, exploratory; live API; `results/mining/m1_agreement.md`, `results/mining/m1_agreement.json`, `results/mining/derived_figures.md`).** 42 pull requests are in both the published pool and the mined set (five seeded repositories; DEV-024 and DEV-025 describe the sample). Exact agreement of the positive sets: 9 of 42 (21.4%) over all positives and 20 of 42 (47.6%) outside test files; mean Jaccard 0.690 and 0.823. No pool positive is missing from the mined set (0 of 708). The disagreement is in the mined extras (320; 172 in test files), which are explained in part and not entirely: pure insertions (42 of the 148 extras outside tests), whole-function removals (53), functions absent from the pool's corpus because they are `async def` (43), 10 unexplained; dropping pure insertions raises the exact share to 64.3% without losing a pool positive. The pool's corpus differs from the mined one as well (corpus-id Jaccard median 0.62; the pool has no test-file functions, which are 165,847 of the mined-only functions). By the pre-stated reading rule these are two constructions, not a verdict on which is right; the construction rule of the pool is an **open question** (Q61). Dataset-card statement "no pool positive lies in a test file": holds on these 42 pull requests (0 of 708); the mined set has 18.2% of its positives in test files (194 of 1,065, published-first sample), reported as the M1 disagreement of D85 with and without test positives in the table. The hand-check file (untracked, third-party text) is handcheck_20.md in the results folder for mining.

**Dead ends and corrections of the live stages (recorded so they are not retried).** (1) `git archive` honours `export-ignore`; the first snapshot reader dropped test directories of some repositories (DEV-026 (1)); the first two runs were discarded. (2) Sequential base-commit fetches of large repositories took 100 to 300 s each; background fetches ahead solved it. (3) Writes of a 33 MB corpus to the home file system stalled for 20 minutes; the corpus is stored compressed (DEV-026). (4) The listing of one repository with a very large number of merged pull requests stopped on the 400-page bound; raised to 2,000. (5) `python3` on the login node is 3.9 and cannot import the package (it needs 3.10); all runs go through jobs.

**Result of M2 (measured, exploratory; live API; `results/mining/derived_figures.md`, `results/mining/m2_report.md`, `results/mining/m2_summary.json`, run log `results/logs/mine_pilot_2026-11-03.json`).** Pilot of D60/D61: the first 200 repositories of the seeded order (190,197 merged pull requests, 23,670 with a closing reference, 25,422 (issue, pull request) pairs), 2,000 linked pull requests mined by the seeded order of `sha256("0:<repo>#<number>")`. Sessions: three listing jobs (66, 67 and 66 repositories; the slowest took 9,248.5 s), one mining session of 6 hours 1 minute (code at commit `2b9bf1d`; see DEV-026 for the speed settings). Outcome of the 2,000 attempts: 1,391 mined (69.6%), 206 with no positive (10.3%), 386 with no Python change (19.3%), 17 quarantined (0.85%): `diff_truncated` 3 (the compare endpoint's 300-file list), `patch_missing` 3, `changed_file_unparseable` 7 (Python 2 `except` 3, long literals 2, mixed tabs 1, other 1), and `old_file_missing_at_base` 4: in these four the changed files lie in a directory the parser skips by rule (`third_party` vendored directory in three, a `build` directory in one; checked on all four with job 54896), so the reason name is a misnomer for "changed file in a skipped directory" (the pull request stays quarantined). Positives: 11,047 function and method positives in the corpus (median 2, mean 7.9, p90 17, max 324 per pull request), more in the side table (class and module units, DEV-016), 8,695 added functions counted from the patches. Of the corpus positives 3,966 (35.9%) lie in test files; 656 of 1,391 pull requests have a test positive and 105 have only test positives (D85: the dataset card's "no pool positive in a test file" does not hold for the mined set; the pool-like reading in M3 removes them). Parse failures by language-version cause: 7 of 2,000 attempted (0.35%) were quarantined for an unparseable changed file; 133 of the 1,391 mined pull requests have at least one unparsed file in their corpus (files by cause: `print` statement 893, other syntax 363, `except` form 208, octal 29, long literal 6, exec 2, tabs 1; the cause is a reading of the error text, `classify_parse_failure`). Links: 519 issues have several pull requests, 1,163 pull requests several issues; 5,518 merged pull requests name an issue in the body that the closing list lacks (counted, not used); 63 of 1,497 mined pairs (4.2%) have the issue edited after the pull request was created. API: 4,122 GraphQL calls and 2,014 compare calls, 37 HTTP 502 responses retried, 250.8 seconds slept in all, 0 secondary-limit stops.

**Selection by the published pool (question 3).** 1,844 of the 23,670 linked pull requests of the 200 repositories are in the published pool (7.8%); 661 more pool pull requests of these repositories have no closing reference found. The share is very uneven across repositories: median 14.7% (quartiles 8.0% and 23.1%), 11 of 199 repositories with a linked pull request have none in the pool, 4 have all of theirs; the two largest repositories (5,545 and 2,001 linked pull requests) have 8 and 0 in the pool. Kept against dropped mined pull requests (158 against 1,233), median and repository-clustered 95% interval of the difference: positives per pull request 6 against 2 (difference 4, [3, 7]); changed Python files 4 against 2 (2, [1, 3]); hunk lines touched 39 against 15 (24, [16, 38.5]); corpus size 800 against 3,182 functions (-2,381.5, [-15,849, -466.5]). All four intervals exclude 0, so by the stated rule the pool is **selected for** larger edits (more positives, more files, more lines) and from smaller repositories; the repository mix is partly the explanation for the last one (the pool takes little from the largest repositories), and the intervals are clustered over the 156 repositories that have a mined pull request. This is the measured counterpart of Q50 (the published pool is not unfiltered at the pull-request level); it does not say by which rule the pool chose.

**Result of M4 (extrapolation, `results/mining/m4_scale.md`).** Binding constraint: **disk**, then the miner's wall time, not the API. At the measured 1.84 MB per mined directory the 20,000-pull-request target needs 25.6 GB and the 100,000 target 128 GB against 5.5 GB free on the shared home file system; the REST limit needs 20 hours for 100,000 pull requests against 285 hours of mining at 10.3 s per attempted pull request in one process; the pilot's mining session peaked at 10.0 GB of 10 GB requested (listings held in memory), which a run over the 1,473 repositories of the population would exceed. The full-run command is in `m4_scale.md` with the two changes it needs first (an output location, streamed listings); it was not started.

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

**Result of M3 (measured, exploratory; `results/mining/m3_ranks.md`, run log `results/logs/mine_ranks_2026-11-03.json`).** Pool-like reading, first 300 directories of the seeded order (89 repositories), reading rule met (at least 100 directories with a positive). Share of directories with no positive in the top 10: BM25 53.3% [47.7, 58.9], CodeRankEmbed 40.2% [34.3, 46.3] (254 directories, 72 repositories), SweRankEmbed-Small 31.3% [26.4, 36.8], against the published pool's 23.2%, 15.3% and 1.7%: different under all three by the stated rule; under CodeRankEmbed the mined set and the never-filtered Verified export (35.7% [31.3, 40.3]) are indistinguishable at this size. The two teacher labels of the brief are as corrected in D84 (15.3% is CodeRankEmbed, 23.2% BM25; 19.3% is SweRankEmbed-Small on Verified stored text, a form not measured here). This is consistent with the earlier finding that the pool's directories look selected with respect to SweRankEmbed-Small (E-POOL-RANKS) and does not establish the rule. 1.99 GPU-hours (stage limit 2.0); not measured: the stored-text pass and the dense teachers in the as-mined reading (DEV-027).

## E-MINED-PILOT: can the mined set be read, ranked, filtered and trained on, and does raw mined supervision gain as the published pool's does? Exploratory, readings stated 2026-11-03 (before any run)

Status: exploratory, integration pilot, **not the confirmatory experiment** (that is decided by `docs/RQ2_PROTOCOL.md`); outside the pre-registered RQ tables; every number below it carries the label `exploratory`. Decisions of the engineer, 2026-11-03: D88 (Block 2 cap 66 to 70 GPU-hours for this pilot), D89 (data), D90 (teacher ranks), D91 (cells), D92 (reading rules, below). Deviations: DEV-028 (evaluation on five dev repositories, not six), DEV-029 (the pool-like reading keeps `async def`, as in M3). Evidence class of every table, once filled: measured, exploratory.

**Data (D89).** The mined pilot run of E-MINE-PILOT (1,391 directories) in the pool-like reading used in M3 (no test-file function in the corpora, no test positive, directories left with no positive dropped), after the held-out filter of `ril.training.train_jobs.select_job` (core list plus Loc-Bench tier, rename cache). The numbers of directories and positives that remain are reported. Positives are used as mined (D83 to D87); the only retriever-dependent addition is the teacher rank below.

**Teacher ranks (D90).** BM25 for every directory (CPU; `ril.training.pool_ranks` definition, code text, 1,024-token cut). Check before anything is trained: the rank rows of the first 300 directories of the seeded order must equal the rows of M3 (`rank-reproduce`: same functions, same `rank`, same `rank_all` for every positive); if one differs, the stage stops and the difference is reported. No dense-teacher ranks (SweRankEmbed-Small on the stored text is a separate item).

**Cells (D91).** N = 100 updates of the 3,000-update schedule (T3), D31 shape, D28 negatives, CodeRankEmbed base, seeds 0 and 1: RAW on the mined set; FILTER K = 20 (positive level, BM25 teacher); RAW on a random subset of FILTER's size (D43, one draw per seed, `draw: 0`; the size is the number of examples FILTER K = 20 leaves, counted by `train.py filter-size` on the cache). Six runs, about 2.7 GPU-hours at 0.45 per run; the stage is aborted if the first run's cost would take it above 3.2. Evaluation as in E-PILOT-ARMS2 (DEV-028). Configurations `configs/experiments/mp/`. Cluster: account A, `~/ril_mp`.

**Reading rules (D92), fixed before the first run.**
1. *Examples seen.* Per cell: unique examples seen, examples seen and passes over the set (`effective_epochs`), from the run log (matched-pool rule D42). RAW on the mined set and the cells on the published pool see different numbers of unique examples; this is stated next to every comparison.
2. *Primary reading.* RAW on the mined set against RAW on the published pool of Wave 6 (`results/rq2/t5a_raw`, seeds 0 and 1: same code, same schedule, same evaluation; only the training pool differs): the mean difference (mined minus pool) at L2 (nDCG@10) and L3 (Recall@100), unit level, reading `units_all_nomod`, dense column, with the repository-clustered (L2) and query-level (L3) intervals of the earlier tables and the seed-level differences beside it. Both pools are different in repository mix, size and construction (M1, M3); the difference is a difference of pools and not of one property.
3. *FILTER.* FILTER-BM25 on the mined set against RAW on the mined set, and against the size-matched subsample on the mined set, with repository-clustered intervals at L2 and query-level intervals at L3 (the L3 set has two repositories, so a clustered interval would not be informative), and the same contrasts per seed. Two shapes of a result are called out in advance: a difference whose interval includes 0 is "indistinguishable at this sample size"; a difference of arms with an interval that excludes 0 is reported with the minimum detectable difference beside it.
4. *Minimum detectable difference at two seeds, both ways* (as in E-STORED-ANALYSIS): the query-level value (no repository term) and the value with the repository term, from the variance components of the per-query rows of the mined cells (`ril.analysis.stored_stats.components`, `minimum_detectable`), 5% two-sided, 80% power; stated for FILTER against RAW and for FILTER against the subsample.
5. *Several passes.* With about a thousand directories, 100 updates of 32 examples are 3,200 examples seen, i.e. several passes over the data (the exact number is in the run log); the published pool (about 5,000 directories) is seen less than once. This is said next to every number, because a difference between pools can be a difference in repeated exposure.
6. *Scope.* One teacher (BM25), one base encoder, five dev repositories, two seeds, 100 updates. No claim about SweRankEmbed-Small (not run), about longer schedules, or about the final design; nothing here replaces `docs/RQ2_PROTOCOL.md`. A null stays a null.

**Stop rules.** BM25 reproduction not exact: stop and report. First run's measured cost such that six runs would exceed 3.2 GPU-hours: stop the stage. A CUDA gate (a real matmul) that fails: the job stops at once.

**Result of E-MINED-PILOT (measured, exploratory; two seeds; dev only; 2026-11-03 and 2026-11-04).** Run log `results/logs/mp_pilot_2026-11-03.json`; tables `results/tables/mp/mp_{effects,seeds,unique,mdd}.csv` (log `results/logs/mp_tables.json`); runs `results/rq2/mp_{raw,filter_bm25,sub}/` (config hashes in the log and `mp_unique.csv`). Code: `ril/analysis/mp_tables.py`, `scripts/mp_tables.py`; jobs `scripts/ada/mp_prep.sbatch`, `mp_runs.sbatch`; commands below. Account A, RTX 2080 Ti, CUDA gate passed in every run.

*Data and ranks (D89, D90).* The pool-like reading has 1,286 of the 1,391 mined directories (105 have only test positives); the held-out filter dropped 0 (the population was filtered at repository level before mining, D65), so 1,286 directories and 7,081 positive rows remain. BM25 ranks for all 1,286 directories (1,036.5 s CPU); the rows of the first 300 directories equal the M3 rows exactly (`rank-reproduce`: 300 of 300 identical, none missing). FILTER K = 20 (BM25, positive level) keeps 765 of 1,286 examples (59.5%) and 1,858 of 7,081 positives (26.2%); the subsample draws 765. The cache is 1.25 GB (`written` 1,286 examples).

*Examples seen (D92 (i), (v)).* 100 updates of 32 examples are 3,232 examples seen in every cell. RAW on the mined set: 1,286 unique examples, 2.51 passes; FILTER and the subsample: 765 unique, 4.23 passes; RAW on the published pool (Wave 6): 3,232 unique of 5,000, 0.65 passes (`mp_unique.csv`). So the mined cells repeat examples and the pool cell does not; a difference between the pools is not separable from this. Small repositories also left 2 to 4 visits per run with fewer negatives than asked (`negative_shortfall_visits`; the pool cell has 0).

*Primary reading (D92 (ii)): RAW on the mined set against RAW on the published pool (Wave 6, seeds 0 and 1), dense column, `units_all_nomod`, percentage points, mined minus pool.* L2 nDCG@10 (351 queries, 5 repositories): the untrained encoder to RAW is +7.93 on the mined set and +9.59 on the pool; difference -1.66, repository-clustered interval [-3.10, -0.22], query-level [-2.55, -0.70]; per seed -2.07 and -1.25. L3 Recall@100 (155 queries, 2 repositories): +12.18 and +11.13 over the untrained encoder; difference +1.05, query-level [-0.23, 2.28] (a clustered interval over two repositories is [-0.86, 3.13] and not informative); per seed -0.37 and +2.46. Reading: at L2 RAW on the mined set gains about 83% of what RAW on the pool gains (7.93 of 9.59), and the clustered interval excludes 0; at L3 the two are indistinguishable at this size. Mined set and pool differ in repository mix, size, construction (M1, M3) and in repeated exposure (above); no property of the labels is isolated by this contrast. Inference, not measured here: the mined subsample (765 unique, 4.2 passes) is not detectably different from the full mined set (1,286 unique, 2.5 passes) at L2 (-0.17 [-0.74, 0.44]), so the L2 gap to the pool is not evidently produced by the number of unique examples within the range the mined set spans.

*FILTER (D92 (iii)), mined set, FILTER-BM25 K = 20 minus the comparison, points.* L2 (clustered interval; query-level in brackets): against RAW +0.93 [0.52, 1.28] ([0.20, 1.64]), seeds +1.42 [0.91, 2.45] and +0.44 [-0.88, 1.24]; against the size-matched subsample +1.10 [0.38, 1.60] ([0.31, 1.91]), seeds +0.67 [0.26, 1.13] and +1.53 [0.23, 2.49]. L3 (query-level): against RAW -0.02 [-0.86, 0.82], seeds +0.76 and -0.79; against the subsample +0.21 [-0.59, 1.05], seeds -0.13 and +0.54. The subsample against RAW on the mined set: L2 -0.17 [-0.74, 0.44], L3 -0.22 [-0.89, 0.49]. Seed spread of the cell means at L2: RAW 25.11 and 25.09, FILTER 26.52 and 25.52, subsample 25.85 and 23.99.

*Minimum detectable difference at two seeds (D92 (iv); 5% two-sided, 80% power; `mp_mdd.csv`; interval from 300 repository resamples).* L2, FILTER against RAW: 1.44 [0.92, 4.39] with and without the repository term (the estimated repository component is 0 in this contrast); against the subsample 1.46 [1.08, 3.22] with the repository term, 1.46 [1.02, 2.73] query-level. L3 (two repositories, so the repository term is nearly unestimable): against RAW 2.36 [1.18, 4.44] both ways; against the subsample 1.57 [1.37, 3.17] with the repository term, 1.16 [1.16, 3.17] query-level. Every observed FILTER difference (+0.93 and +1.10 at L2, 0.02 and 0.21 at L3) is below the minimum detectable difference of its contrast. The L2 intervals above exclude 0 because they cover the draw of repositories (and queries) only; they do not cover seed variation, and one of the two seeds of FILTER against RAW includes 0. So the L2 FILTER difference is a lead, not a finding, and the L3 result is a null at this size.

*What this shows, and what it does not (D92 (vi)).* End to end: the mined pilot set was read through the existing pool reader, ranked (BM25 reproduces M3 exactly), filtered and trained on, in six runs of the unchanged training code. Not shown: any statement about SweRankEmbed-Small or CodeRankEmbed as teachers (not run), about ansible (not evaluated, DEV-028), about longer schedules, or about the final design. This pilot does not decide the confirmatory experiment. The only comparison with the pool's FILTER cells is qualitative (on the pool no FILTER cell separated from RAW or the subsample beyond seed noise, E-PILOT-ARMS2; here FILTER-BM25 is +0.9 to +1.1 at L2 on the mined set, below the minimum detectable difference); a null at L3 stays a null.

*Cost and operations.* 2.60 GPU-hours (stage limit 3.2; Block 2 ledger 67.41 of the cap 70, D88): 1.30 and 1.24 for the two seeds' three runs each (0.43 and 0.41 per run), plus 0.06 for two jobs that stopped within two minutes (an unquoted colon in the pool description made the configuration files unreadable, job 56056; the CUDA gate stopped a node without CUDA, job 56565). The first run's cost (0.42) was checked before the stage continued. `$HOME` of account A was at 2.9 GB free before the preparation and at 288 MB afterwards (cache 1.25 GB; other jobs of the account also write there); nothing was deleted. Commands (from the work directory `~/ril_mp`, code at the commit named in the log):

    sbatch --export=ALL,RIL_COMMIT=<hash> scripts/ada/mp_prep.sbatch
    sbatch --export=ALL,SEED=<0|1>,RIL_COMMIT=<hash>,CELLS="raw filter_bm25 sub" scripts/ada/mp_runs.sbatch
    python3 -I scripts/mp_tables.py results results/rq2/t3_curve_raw/<run>/step_00000/query_rows.csv results/tables/mp results/logs/mp_tables.json --draws 300

Skipped (named in the brief or the design): dense-teacher ranks, SweRankEmbed-Small on the stored text, ansible, a third seed, a second subsample draw, WEIGHT and CURRICULUM on the mined set.
