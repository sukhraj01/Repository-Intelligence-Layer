# Experiments: data mining and stored-output analysis

Append-only log, entries by this workstream only. Rules, interpretation rules and the index of all entries are in
`docs/EXPERIMENTS.md`; the same rules apply here. Entry ids are unique across all experiment logs.

## Registry

| ID | RQ | What varies | Held fixed | Seeds | Primary outputs | Status |
|---|---|---|---|---|---|---|
| E-MINE-PILOT | RQ2 (data) | nothing varies: the unfiltered PR-mined set is built and measured against the published pool | seed 0, the 5,000-directory population, held-out list v2 with the Loc-Bench tier | 0 | `results/mining/` tables from `<run root>/summary.json` of a run root | M0 to M4 done (live, 2026-11-02/03; the full run is not started) |
| E-MINED-PILOT | RQ2 (data, evidence) | training data: the PR-mined pilot set (pool-like reading) against the published pool; supervision on the mined set: RAW, FILTER K = 20 (BM25 teacher), RAW on a random subset of FILTER's size | model, schedule (100 updates of the 3,000-update schedule), batch, negatives, loss, optimizer, evaluation (five dev repositories, DEV-029) | 0, 1 | per-query rows of 6 runs under `results/rq2/mp_*`; tables in the results tables folder with the prefix mp_ | done 2026-11-03/04 (exploratory; six runs) |
| E-MINE-STORE | RQ2 (data, infrastructure) | the storage form of the mined set (rows once per repository plus a manifest per pull request, rebuilt on demand) and the reading of the data (unrestricted, non_test, pool_aligned); nothing is trained | the finished pilot run root (1,391 directories), the M3 selection of 300 directories, BM25 ranks under the published definition | none (no randomness) | `results/mining/m5_reading_shares.json`, `results/mining/full_run_plan.md`, `results/logs/mine_store_2026-11-05.json` | done (pilot; the full run is not started) |
| E-MINE-FULL | RQ2 (data) | nothing varies: the PR-mined set at the target scale (10,000 attempted pull requests of the 1,473 repositories of the population), mined in two bounded sessions of 5,000 | `configs/mining/full.yaml` (seed 0, version pr-mining/v1), the sampling and mining order of the pilot, held-out list v2 | 0 | the de-duplicated store on account C, `report.md` of the run, then the pool-like and pool-aligned counts | running (launched 2026-11-05; relaunched 2026-11-06 after a listing fault, DEV-034; 2026-11-07, DEV-035; 2026-11-08 after a fetch timeout, DEV-036) |
| E-RETAIN-FINAL | RQ2 (infrastructure) | nothing varies: a storage switch that keeps the finished model in half precision with a manifest | tiny CPU configuration; code before and after the switch | 3 (tiny run) | `ril/training/retention.py`, tests, Ada jobs 60205 and 60207 | done 2026-11-05 (switch built and tested; no GPU run yet) |
| E-EVAL-REPOS | RQ2/RQ3 (evaluation set, inventory) | nothing varies: a table of every CORE-Bench repository as a candidate evaluation repository; no repository is chosen | held-out list v2, the stored unit records and dense stores, the pool listing and the mining population (seed 0, 5,000 directories) | none (no randomness) | `results/tables/eval_repo_inventory.csv`, `results/logs/eval_repo_inventory_2026-11-05.json` | done 2026-11-05 (counts measured; sizes and costs of unbuilt repositories estimated; language class is a screen) |
| E-EVAL-REPOS-BUILD | RQ2/RQ3 (evaluation set, build) | nothing varies: unit records, instance caches and dense stores of the eight repositories fixed by D100; no retrieval result is computed or read | the dev build pipeline (e1 units, e3 prepare, x2 prepare, base encoder at 512 tokens, float16), BM25 parameters of the dev configuration | none (no randomness; seed 0 recorded) | `configs/experiments/eval_repos_v1_build.yaml`, `results/tables/eval_repo_build_measured.csv`, `results/logs/eval_repos_build_2026-11-06.json` | done 2026-11-06 (build measured; no evaluation) |
| E-ASSEMBLY | RQ3 (apparatus, evidence) | the token budget B (4,000 / 8,000 / 16,000 / 32,000) and the first stage (BM25; the stored RRF(BM25, CodeRankEmbed t1024, k 100)) | the assembly policy of ADR-014 (unit cap 1,000 tokens, 200 candidates, class units in header form, approximate tokenizer), the E3 cache and D18 readings, the stored dense scores, dev and Verified-six instances; nothing is trained | none (no randomness except the bootstrap, seed 0) | per-query rows of the run, summary tables, latency rows of `assemble` and `end_to_end` (`results/rq3/assembly_gold_2026-11-06/`, `results/tables/assembly/`, `results/latency/latency_log.csv`) | measured, exploratory 2026-11-06 |
| E-ASSEMBLY-CAP | RQ3 (apparatus, evidence) | the cap on the text of one unit (500 / 1,000 / 2,000 approximate tokens) | the assembly policy of ADR-014 otherwise, the E3 cache and D18 readings, the stored dense scores, budgets 4,000 to 32,000, both first stages, dev instances only (Verified-six not read) | none (bootstrap seed 0) | per-query rows, selection and paired tables (`results/rq3/assembly_cap_2026-11-06/`, `results/tables/assembly_cap/`) | measured, exploratory 2026-11-06 |
| E-RQ3-EXEC | RQ3 (apparatus, measurement) | nothing varies in the measurement: which Verified instances can be evaluated by execution on the cluster (gold patch, two runs, no container, no root) | the benchmark's install specifications (4.1.0), the executor `executor/v1` and its recorded departures, two runs per instance, environment policies `latest` then `era` | none (no randomness; seed field 0) | `results/rq3_exec/executable_instances_v1.json`, `repo_table.csv`, `subset_vs_500.csv`, `cost_per_instance.json`, `coverage_table.csv`, `power_at_n.csv`, `unit_build_estimate.csv`, `older_python_recovery.csv`, `docs/RQ3_PILOT.md` | done 2026-11-07 (subset frozen: 377 of 500) |
| E-RQ3-UNITS | RQ3 (apparatus, measurement) | nothing varies: unit records, BM25 scores and unit-text vectors (untrained base encoder) of the executable subset of Verified; no retrieval result is read | the dev pipeline (parser, class form full, BM25 k1 1.5 / b 0.75, CodeRankEmbed at 512 tokens, float16), the frozen subset of E-RQ3-EXEC, the encoding rule of D107 (6.0 GPU-hours at 109 texts/s) | none (no randomness; seed field 0) | `results/rq3_units/` (instances, counts, checks, encode logs, manifest), `configs/experiments/rq3_units_v1.yaml`, `docs/RQ3_PILOT.md` | done 2026-11-07 (341 built, 0 failures; 220,974 distinct texts; 0.377 GPU-hours) |
| E-RQ3-PILOT-PREP | RQ3 (apparatus, evidence) | nothing varies in the measurement: what the cluster can execute (part A), a provider adapter with a persistent limiter, the prompts of the pilot, a three-call smoke test | the assembly of ADR-014 (budget 8,000 model tokens, cap 1,000), BM25 and RRF(BM25, dense) first stages, 100 dev instances drawn with seed 0, template `rq3-pilot-prompt/v1` | 0 (draw and seed field) | `results/rq3_pilot/part_a/`, `results/rq3_pilot/smoke_2026-11-06/`, `docs/RQ3_PILOT.md` | part A and adapter done; pilot run started 2026-11-06 (see update below), not complete |
| E-RQ3-PILOT-RESULT | RQ3 (apparatus, evidence) | nothing varies: stored data of the finished pilot (400 units, 565 calls, 100 dev instances, BM25 and RRF first stages, two runs, B 8,000) is analysed; no call, no cluster job | the pilot's prompts, replies and log; the unusable definition of `ril/agent/providers/`; D106 subset and D108 budgets unchanged | bootstrap seed 0 | `results/rq3_pilot/analysis/` | done (D109) |
| E-RQ3-PATCHAPPLY | RQ3 (apparatus, evidence) | nothing varies in a measurement: the rule that turns SEARCH/REPLACE blocks into the executor's patch (exact primary, whitespace-tolerant sensitivity), applied to the pilot's stored edits (apply rates) and to gold-derived edits of 20 executable instances (end to end) | the pilot's stored replies and prompts (D109); the executable subset and executor (D106); seed 0 for the draw | 0 | `results/rq3_patch/` | done (D110) |
| E-RQ3-DRIVER | RQ3 (apparatus, plan) | nothing varies in a measurement: a held-out slice of 50 executable instances is drawn and frozen, prompts of the 377 are built and screened, the path from reply to graded row is one tested driver (replay-tested on the real executor), the analysis plan is fixed, power with run noise and a cost model are computed | the executable subset (D106), contexts (D108), pilot figures (D109), edit rule (D110); seed 0 for the draw, the bootstrap and the simulation | 0 | `results/rq3_driver/` | done (D111 to D114); no model call |
| E-LABEL-AUDIT-SHEET | RQ2 (data, noise audit) | nothing varies: a stratified sample of the pilot mined set is drawn and put on a sheet for human readers; nothing is trained | the pilot mined set (`non_test` reading, 1,286 directories, 7,081 positives), BM25 ranks of E-MINED-PILOT, K = 20 at positive level (O3), the sheet columns and truncation rules of `docs/LABEL_AUDIT.md` | 0 (draw and shuffles) | `results/audit/pilot_v1/sample_meta.json`; sheets and key untracked under `data/review/label_audit_pilot_v1/` | built 2026-11-05; nobody has read any pair |
| E-OVERLAP-AUDIT | RQ2 (data, contamination) | floor (10 / 20 / 50 syntax-tree nodes) and corpus-share threshold sensitivity; positives reading (non_test, all); drop of flagged directories as a sensitivity cell | the matching key (E-CONTAM-PROBE syntax-tree hash), primary floor 20, flag share 5%, held-out index, the pilot store (1,391 directories), `non_test` reading | none (no randomness; seed orders the hand-reading sample) | `results/mining/overlap_audit/` records, summary, drop and flag lists | pilot store audited (job 61808, measured); full set not run |
| E-RQ2-READINESS | RQ2 (apparatus, audit) | nothing varies in a measurement: every stage between a finished mining store and the final RQ2 tables is read, dry-run at minimal scale where a plan-only form exists, and costed | the protocol of section 11, the pilot store (20 directories), the stored evaluation sets, the state log of the running mining job (read only) | none (the plan's seeds are 100 to 102 for fresh noise draws, D82) | `docs/RQ2_LAUNCH_PLAN.md`, `results/rq2_readiness/`, `ril/training/rq2_plan.py`, `ril/evaluation/eval_plan.py`, `ril/data_mining/state_yield.py` | done 2026-11-08 (no GPU job, no model call) |
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

**Scale-up preparation (2026-11-03; `results/mining/storage_survey.md`, `dedup_measure.md`, `full_run_plan.md`, `docs/POOL_CONSTRUCTION.md`; run log `results/logs/mine_scale_prep_2026-11-03.json`).** (1) *Storage.* No area writable by account A can hold the 25.6 GB of 20,000 attempted pull requests (2.9 GB free on the home file system; the other shared mounts are root-owned or absent on compute nodes); account C's home has 28 GB free but no token; recommendation and commands in the survey. (2) *De-duplication.* A content-addressed store (each distinct corpus row once per repository) would take 0.34 GB for the pilot's directories against 2.55 GB stored now (86.5% saving, measured at 12 directories per repository); the readers cannot read it unchanged, a materialising build step could (not built); options in `dedup_measure.md`. (3) *Memory.* The peak came from building the corpus file in memory, not from the listings (DEV-028); streamed writing lowers the largest snapshot from 7.8 to 3.8 GB, a repeat of 462 pilot pull requests is byte-identical with a 3.16 GB peak. (4) *Q61.* `docs/POOL_CONSTRUCTION.md`: the released scripts (not the papers) define the corpus (no `async def`, no path containing `test`, nested functions kept, vendored code kept), the positives (functions with a removed line; added-only functions are not positives) and a CodeRankEmbed consistency step per row; the papers and the code disagree on teacher, cut and the test requirement; how rows became the per-PR directories, and whether the released code made `train.zip`, are not stated. The publisher provides no dataset card. (5) *Plan.* Targets of 5,000, 10,000 and 20,000 attempted pull requests: 6.4, 12.8 and 25.6 GB as stored now, 14.3, 28.5 and 57.1 hours of mining in one process, 3,215, 6,430 and 12,860 pool-like directories expected.

## E-MINED-PILOT: can the mined set be read, ranked, filtered and trained on, and does raw mined supervision gain as the published pool's does? Exploratory, readings stated 2026-11-03 (before any run)

Status: exploratory, integration pilot, **not the confirmatory experiment** (that is decided by `docs/RQ2_PROTOCOL.md`); outside the pre-registered RQ tables; every number below it carries the label `exploratory`. Decisions of the engineer, 2026-11-03: D88 (Block 2 cap 66 to 70 GPU-hours for this pilot), D89 (data), D90 (teacher ranks), D91 (cells), D92 (reading rules, below). Deviations: DEV-029 (evaluation on five dev repositories, not six), DEV-030 (the pool-like reading keeps `async def`, as in M3). Evidence class of every table, once filled: measured, exploratory.

**Data (D89).** The mined pilot run of E-MINE-PILOT (1,391 directories) in the pool-like reading used in M3 (no test-file function in the corpora, no test positive, directories left with no positive dropped), after the held-out filter of `ril.training.train_jobs.select_job` (core list plus Loc-Bench tier, rename cache). The numbers of directories and positives that remain are reported. Positives are used as mined (D83 to D87); the only retriever-dependent addition is the teacher rank below.

**Teacher ranks (D90).** BM25 for every directory (CPU; `ril.training.pool_ranks` definition, code text, 1,024-token cut). Check before anything is trained: the rank rows of the first 300 directories of the seeded order must equal the rows of M3 (`rank-reproduce`: same functions, same `rank`, same `rank_all` for every positive); if one differs, the stage stops and the difference is reported. No dense-teacher ranks (SweRankEmbed-Small on the stored text is a separate item).

**Cells (D91).** N = 100 updates of the 3,000-update schedule (T3), D31 shape, D28 negatives, CodeRankEmbed base, seeds 0 and 1: RAW on the mined set; FILTER K = 20 (positive level, BM25 teacher); RAW on a random subset of FILTER's size (D43, one draw per seed, `draw: 0`; the size is the number of examples FILTER K = 20 leaves, counted by `train.py filter-size` on the cache). Six runs, about 2.7 GPU-hours at 0.45 per run; the stage is aborted if the first run's cost would take it above 3.2. Evaluation as in E-PILOT-ARMS2 (DEV-029). Configurations `configs/experiments/mp/`. Cluster: account A, `~/ril_mp`.

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

*What this shows, and what it does not (D92 (vi)).* End to end: the mined pilot set was read through the existing pool reader, ranked (BM25 reproduces M3 exactly), filtered and trained on, in six runs of the unchanged training code. Not shown: any statement about SweRankEmbed-Small or CodeRankEmbed as teachers (not run), about ansible (not evaluated, DEV-029), about longer schedules, or about the final design. This pilot does not decide the confirmatory experiment. The only comparison with the pool's FILTER cells is qualitative (on the pool no FILTER cell separated from RAW or the subsample beyond seed noise, E-PILOT-ARMS2; here FILTER-BM25 is +0.9 to +1.1 at L2 on the mined set, below the minimum detectable difference); a null at L3 stays a null.

*Cost and operations.* 2.60 GPU-hours (stage limit 3.2; Block 2 ledger 67.41 of the cap 70, D88): 1.30 and 1.24 for the two seeds' three runs each (0.43 and 0.41 per run), plus 0.06 for two jobs that stopped within two minutes (an unquoted colon in the pool description made the configuration files unreadable, job 56056; the CUDA gate stopped a node without CUDA, job 56565). The first run's cost (0.42) was checked before the stage continued. `$HOME` of account A was at 2.9 GB free before the preparation and at 288 MB afterwards (cache 1.25 GB; other jobs of the account also write there); nothing was deleted. Commands (from the work directory `~/ril_mp`, code at the commit named in the log):

    sbatch --export=ALL,RIL_COMMIT=<hash> scripts/ada/mp_prep.sbatch
    sbatch --export=ALL,SEED=<0|1>,RIL_COMMIT=<hash>,CELLS="raw filter_bm25 sub" scripts/ada/mp_runs.sbatch
    python3 -I scripts/mp_tables.py results results/rq2/t3_curve_raw/<run>/step_00000/query_rows.csv results/tables/mp results/logs/mp_tables.json --draws 300

Skipped (named in the brief or the design): dense-teacher ranks, SweRankEmbed-Small on the stored text, ansible, a third seed, a second subsample draw, WEIGHT and CURRICULUM on the mined set.

## E-MINE-STORE: can the mined set be kept de-duplicated and rebuilt byte for byte, and how does the pool-aligned reading change the BM25 shares? Exploratory, stated 2026-11-05 (after the engineer's decisions D93, D94, D95)

Status: exploratory, infrastructure; no model is trained and no GPU is used. Decisions of the engineer, 2026-11-05: D93 (build the de-duplicated store and a materialise step; readers unchanged; byte-identity on the pilot directories is the requirement), D94 (10,000 attempted pull requests, mining on node-local disk, store and state on account C's home, no work lost on a resumption on another node), D95 (Q61: a labelled "pool-aligned" reading as a view (named the default for comparisons with the published pool; amended by D96 of 2026-11-05: `non_test` stays primary, `pool_aligned` is a sensitivity reading); its BM25 share re-measured on the same 300 directories against M3; a short question to the pool's authors drafted). Deviations: DEV-031, DEV-032. Code: `ril/data_mining/{cas,durable,readings}.py`, `--store-layout`, `--durable`, `store-convert`, `materialise`, `compare-roots`, `--reading` in `scripts/mine_pilot.py`; jobs `scripts/ada/mine_store_proof.sbatch`, `scripts/ada/mine_reading_bm25.sbatch`; code commit 3622e71.

**Store.** Per repository `cas/<repo>/rows.gz` (distinct corpus rows in slot order, one gzip member per append), `digests.bin` (SHA-1 per row) and `segments.jsonl` (the commit record of an append); per pull request `pr/<dir>/corpus.manifest` (row slots, little-endian uint32, deflated) beside the three small files. An unfinished append is cut back to the commit record when the repository is opened. `materialise` rebuilds `pr/<dir>/{corpus.jsonl.gz, queries.jsonl, qrels/test.tsv, pr_meta.json}` with the same writer as before the store existed. A run root records its layout in its run record and refuses the other one. `durable.py` copies a run root between node-local disk and a shared area in a fixed order (rows, directories, listings, logs with `state.jsonl` last), extends append-only files only after checking the destination's last bytes, refuses a diverged destination, and never deletes.

**Result 1, byte identity (measured).** Pilot run root (1,391 directories, 156 repositories) converted to a store, rebuilt on the node-local disk of the same node and compared with the original by SHA-256 over the relative paths and bytes of every file of each directory: **1,391 of 1,391 identical** (none different, none missing on either side; job 58615 at commit 3622e71; the first run, job 58605, gave the same result and the same store bytes). Run log `results/logs/mine_store_2026-11-05.json`.

| | value |
|---|---|
| store, total | 396,746,195 bytes (rows 312,192,836; digests 39,714,000; commit records 40,563; per-directory files and manifests 44,798,796) |
| corpora of the pilot as stored before | 2,547,895,175 bytes (the small files of each directory, about 45 MB, were stored before as well) |
| conversion of the pilot | 527.4 s (first run 575.4 s), process peak 2,161 MB |
| `materialise` of all 1,391 directories on node-local disk | **695.5 s** (first run 726.2 s; 0.50 s per directory), process peak 3,435 MB, largest repository 946,825 distinct rows |
| byte comparison | peak 78 MB; `sacct` MaxRSS of the whole job 4.3 GB (first run 6.7 GB; the difference was not investigated), 12 GB requested |

The store is 84.4% smaller than the corpora alone (2,547,895,175 bytes); the store total includes the small files of every directory, which that figure leaves out, so the saving is a little larger than 84.4%. The earlier row-model measurement gave 86.5% (`dedup_measure.md`); the store adds the digests. Nothing about the saving at 10,000 attempted is measured; `full_run_plan.md` scales the pilot's bytes per directory and labels the result an upper estimate. Tests: `tests/unit/test_mining_dedup_store.py` (19: byte identity through the miner and through `run_pilot`, a crash between the three writes, a store shorter than its commit record, a slot beyond the rows, mixed layouts, copies in every order, a diverged or longer destination, restore on an empty node, and a run continued from the durable copy). No reader was changed; `pool_reader`, the rank tooling and `pack` read a materialised root as they read a plain one, and read a manifest directory only to refuse it with a message.

**Result 2, the pool-aligned reading on the same 300 directories (measured, exploratory; BM25, code text, 1,024-token cut; job 58616, table `results/mining/m5_reading_shares.json`).** The 300 directories are M3's (first 300 of the seeded order under the `non_test` reading, selection file sha256 153b1bc8…). Each reading is prepared for exactly those directories; a reading that drops one is counted, not replaced. The `non_test` row reproduces the M3 numbers (160, 136 and 109 of 300 at K = 10, 20 and 40); two runs of the job give ranks files that differ only in a timing field.

| reading | directories kept of 300 | repositories | no positive in top 10 | top 20 | top 40 |
|---|---|---|---|---|---|
| `non_test` (the M3 reading, keeps `async def`) | 300 | 89 | **53.3%** [47.7, 58.9] (160 of 300; clustered [40.9, 60.6]) | 45.3% (136) | 36.3% (109) |
| `pool_aligned` | **240** | 80 | **53.3%** [47.0, 59.5] (128 of 240; clustered [42.2, 59.9]) | 43.3% [37.2, 49.7] (104) | 33.8% [28.1, 40.0] (81) |
| `unrestricted` (as mined) | 300 | 89 | 53.0% [47.4, 58.6] (159 of 300) | 44.7% (134) | 38.3% (115) |

Change against M3 (the `non_test` row): 0.0 points at K = 10 (53.3% in both; 128 of 240 against 160 of 300), -2.0 at K = 20, -2.6 at K = 40, all far inside the intervals, so **the pool-aligned reading does not change the BM25 share at this sample size**; the published pool's BM25 value at K = 10 is 23.2% [16.4, 31.0] (E-POOL-RANKS), so the gap to the pool that M3 reported stays. The reading drops 60 of the 300 directories (20%), which is the figure that matters for the size of the training set: about 5,100 pool-aligned directories are expected from 6,430 pool-like ones at the 10,000 target (an estimate from 300 directories). Caveats: one teacher (BM25), 240 to 300 directories of one pilot, the same directories compared across readings (so the three rows are not independent), and the dense teachers were not re-run (GPU, outside this stage). The reading rules (compared only with at least 100 directories that have a positive) are met.

**Not done / stopped.** The full run and its token on account C (absent: presence tested 2026-11-05) are not started; the space on account A, the copy of the pilot and the removal commands were handed to the engineer (nothing was deleted or copied between accounts); the question to the pool's authors is drafted in `results/mining/pool_authors_question.md` and not sent. Anything trained on the pool-aligned reading needs new ranks and cells.

Commands (from `~/ril_mine`, code at commit 3622e71):

    sbatch --export=ALL,RUN=pilot scripts/ada/mine_store_proof.sbatch
    sbatch --export=ALL,RUN=pilot,SAMPLE=ranks/pilot/non_test/limit300/sample.json scripts/ada/mine_reading_bm25.sbatch

## E-MINE-FULL: the PR-mined set at the target scale. Exploratory (data), launched 2026-11-05

Status: **running** (launched 2026-11-05 on account C). Plan: `results/mining/full_run_plan.md` (steps 1, 3, 4), decisions D93 and D94 of the engineer. Code commit `0c0200a`, mining configuration `configs/mining/full.yaml`, configuration hash `33b7336093995d0722cd41fed36f3f90c561a01b07639fe8dcbf2bc10ff9def4`, `CREATED=2026-11-05`, CPU only (no GPU).

**Decision D96 (2026-11-05, recorded with this launch; supersedes the default in D95/DEV-031).** The primary reading of the mined set for RQ2 stays the reading of the M3 measurement (`non_test`); `pool_aligned` is a sensitivity reading, reported on the pilot and not recomputed for the full set unless a later result needs it. Evidence class: **measured, exploratory** (300 directories, BM25 only; E-MINE-STORE result 2). Reasons: the share of directories with no positive in the BM25 top 10 is 53.3% under both readings (M3: 160 of 300; pool-aligned: 128 of 240, interval [47.0, 59.5]) and moves by 2 to 3 points at K = 20 and K = 40, inside the intervals; the pool-aligned reading drops 20% of the directories (less data and power) and needs new ranks and cells; it also drops positives that received only inserted lines, which DEV-015 keeps. Cheapest experiment that could flip it: BM25-only ranks are already measured; dense-teacher ranks (CodeRankEmbed, SweRankEmbed-Small) of the pool-aligned reading on the same 300 directories, about one GPU-hour, run if the final analysis needs the sensitivity row. The choice does not affect the mining run: readings are applied afterwards by `rank-prepare`.

**Decision D97 (2026-11-05, engineer; recorded at the merge of the evaluation branch).** `ril/data_mining/c_miner.py`, `github.py`, `recording.py`, `ranks.py`, `scripts/c_mine_prs.py` and their tests stay in the tree as a synthetic-only harness, superseded by the miner in `ril/data_mining/miner.py`, the store and the readings. The only mined set that may feed RQ2 or any scientific claim is the one produced by that pipeline. Evidence class: reasoned only for the decision; the dependency fact is measured (`git grep`: nothing on main imports `c_miner`; only `scripts/c_mine_prs.py` and two C test files do). Reasons: the harness cannot affect the mined set; dropping it would cost another review round over about 1,500 lines the pipeline has already replaced. Its policies differ from the pipeline's and are not adopted for any mined set: D60 (it selects repositories by stars, not the pool's seeded set), D63 (it quarantines squash and rebase merges), DEV-016 (it drops class and module positives), D62, D66 and DEV-017, D93 to D96, D94 (200 repositories, 2,000 pull requests cap). Its overlap audit and recorded-response replay may be ported into `ril/data_mining` later as a separate change (not planned). Removal later is a decision of the lead and needs no other approval. Cheapest experiment that could flip it: none needed; the cost is reading and maintenance only.

**Pre-flight (read-only, 2026-11-05).** Token on account C: `token_nonempty` (value not printed). Home: 28 GB free of 50 GB. No job running. The pilot store on C matches the copy on A in size (396,761,049 bytes) and file count (6,032). The pilot store holds `cas/` and `pr/` only, with no `listing/*.json`, so the store was **not seeded** with the pilot's listings; the three listing jobs list all 1,473 repositories.

**Staged on C.** Code, scripts and configs by `rsync`; the held-out files; the population listing (38,246,591 bytes) copied from A through this machine, SHA-256 `d6b5e0a47f32517b09aa49bd2af93f86b2e8f5c4b0a56256a8da6064b1bfacf3` equal on both accounts.

**Jobs (account C, CPU).**

| Job | What | Dependency |
|---|---|---|
| 60032, 60041, 60034 | listing shards 0, 1, 2 of 3 (1 CPU, 3 GB, 12 h) | none |
| 60042 | mining session 1, `STOP_AFTER=5000`, 12 GB, 4 days | `afterok` on 60032, 60041, 60034 |
| 60043 | mining session 2, `STOP_AFTER=5000` | `afterany` on 60042 |

Deviation from the plan, tactical: (1) the first mining session carries `--dependency=afterok` on the three listing jobs, because the miner needs complete listings (an addition to the plan, not a configuration change). (2) Job 60033 (shard 1 of the first submission) failed in 6 s: the three listing jobs started together on one node and all tried to create the shared virtual environment, so shard 1 found it half built. It was resubmitted unchanged as 60041, and the mining jobs 60035 and 60036 (which depended on 60033) were cancelled and resubmitted as 60042 and 60043; no configuration value and no sampling order changed. Lesson for the next first submission to a new account: create the environment once before submitting parallel jobs.

**Expected finish (linear estimate from the pilot, no interval).** Listing about 12 h (11.8 h over three jobs); mining about 28.5 h in all (14.3 h per session of 5,000), so about 40 h after the listing jobs start, plus queue time (waits of 3 to 8 hours per job have been seen on these accounts). Expected output: about 6,955 mined and 6,430 pool-like directories, about 2 GB in the store.

**What the report step will measure.** `mine_pilot.py report ril_mine/store/full ril_mine/store/full/report.md` after each session: attempted, mined and quarantined pull requests with reasons, positives per mined pull request, share of positives in test files, directories with a positive outside test files (pool-like), store size and rows per repository, per-repository counts (largest first), against the pilot's yield (69.55% mined, 64.3% pool-like of attempted). The yield and bytes per directory are expected to differ from the pilot's (1,473 repositories against 200); the report states the difference. Pool-like rank measurement (M3 at scale) is a separate GPU stage, not part of this entry.

**Resumption.** If a session ends before the log shows `done`, resubmit the same `sbatch` command (plan, step 4) with `DURABLE` unchanged, after `squeue -u $USER` shows no mining job; never two mining jobs on one durable directory.

**Incident and relaunch (2026-11-06, appended).** At 2026-11-06 17:03 the queue showed mining session 1 (60042) pending with `DependencyNeverSatisfied` and session 2 (60043) pending on `Dependency`, with no listing job left and no `state.jsonl`. State recorded before cancelling: 60042 `afterok:60034(failed),afterok:60041(unfulfilled),afterok:60032(unfulfilled)`; 60043 `afterany:60042(unfulfilled)`. `sacct`: 60032, 60034, 60041 all FAILED with exit code 1:0 after 02:57:36, 02:35:52 and 02:53:13 on one node, MaxRSS 268 to 360 MB (memory and wall time were not the cause). Cause (stderr of each job, same traceback): `http.client.IncompleteRead` raised while reading a GraphQL response body in `UrllibTransport.send`; the exception is not a `URLError`, so the client's retry did not apply and the job died. The listings those jobs had finished lived only on node-local disk (pushed at job end), so nothing reached `ril_mine/store/full` (empty). Time lost: about 3 hours of listing per shard, and about one day of the schedule including queue time. The earlier `60033` log (missing numpy) is the already recorded environment race, not this fault. Evidence class: measured (logs, `sacct`). Fix (DEV-034, commit `a80e529`, tests in `test_mining_api.py` and `test_mining_dedup_store.py`; mining tests, `ruff` and `mypy --strict` clean): the transport maps `http.client.HTTPException` to the retried `TransportError`; listing-only jobs push finished listings every `SYNC_SECONDS` and in a `finally`. No configuration value, sampling order, seed, target or reading changed; no listing shard had finished, so all three were resubmitted with the same shard arguments. The stuck 60042 and 60043 were cancelled.

| Job | What | Dependency |
|---|---|---|
| 61677, 61678, 61679 | listing shards 0, 1, 2 of 3 (1 CPU, 3 GB, 12 h), `RIL_COMMIT=a80e529` | none |
| 61680 | mining session 1, `STOP_AFTER=5000`, 12 GB, 4 days | `afterok` on 61677, 61678, 61679, `--kill-on-invalid-dep=yes` |
| 61681 | mining session 2, `STOP_AFTER=5000` | `afterany:61680`, `--kill-on-invalid-dep=yes` |

Ten-minute watch: the three listing jobs were running after 13 minutes, and the first push had put 16 listing files into the store directory (the new periodic push works). Expected finish (linear estimates): listing about 12 h, then mining about 28.5 h plus queue wait. A failed listing now cancels the mining jobs instead of leaving them pending.

**Second failure and relaunch (2026-11-07, appended; DEV-035).** Jobs 61677 to 61679 (listing) FAILED after 6 h 33 min on one node, all within the same second (2026-11-06 23:40:48): `Temporary failure in name resolution`, beyond the client's five retries (62 s of backoff); memory (about 0.7 GB) and wall time were not the cause. 61680 (session 1) was cancelled by `--kill-on-invalid-dep`, as designed. 61681 (session 2, `afterany:61680`) was released by the cancelled job, listed the remaining third (about 7 h 50 min), mined 150 pull requests (93 mined, 38 no Python change, 15 no positive, 4 quarantined) and FAILED after 7 h 58 min on `ValueError` from the unit-id grammar (a Kannada identifier) inside `parse_repository`. Not the cause: rate limit (remaining never below 2,828 of 5,000, no 403 or 429) and token. One repository, `googleapis/google-api-python-client`, had no listing: its failure was skipped silently by the listing stage. Time lost since the relaunch: about 24 hours; effective mining before the stop: 7 minutes. Changes: DEV-035 (commit 893703f: network retries 12, server-error retries 8; mining refuses an incomplete listing; quarantine of a rejected unit id; new dependency layout). The 150 existing state rows are kept (resumable; the final set is the first 10,000 of the complete seeded order, finished pull requests are skipped). New jobs on account C: listing completion 63964 (list-only, reuses 1,472 stored listings), session 1 63965 (`afterok:63964`), session 2 63966 (`afterok:63964,afterany:63965`), all with `--kill-on-invalid-dep=yes`, `RIL_COMMIT=893703f`.

Watch result: the listing completion job 63964 listed the one missing repository in 730 s (1,473 of 1,473 listings now stored, 0 failed) and finished COMPLETED; session 1 (63965) started on gnode006 and after 9 minutes had 225 state rows (150 kept, 75 new), past the identifier that stopped the earlier session. Session 2 (63966) waits on it.

**Third failure and relaunch (2026-11-08, appended; DEV-036).** Session 1 (63965, started 2026-11-07 21:38 on one node) FAILED after 2 h 58 min and session 2 (63966, started 2026-11-08 00:37, on the same node) after 54 min, both exit code 1:0; the listing completion job 63964 had COMPLETED in 13 min. Both ended on the same traceback: `subprocess.TimeoutExpired` from `git fetch --depth 1` of one base commit of `open-metadata/openmetadata` past the 900 s limit (two different commits); the miner handled `SnapshotError` only, so the timeout was fatal. Session 2 ran, so it did not die of its dependency. A fetch of the first commit run locally (outside the cluster) was still running after more than 15 minutes with a pack of about 500 MB, so the commit is heavy; this was not tested on C. Not the cause: memory (MaxRSS 7.4 GB and 4.4 GB of 12 GB asked), disk (24 of 50 GB used on the home), quota, name resolution, token or rate limit (no such line in either log). State at failure: 2,214 rows (225 at the end of the last watch): 1,378 mined, 571 no_python_change, 234 no_positive, 31 quarantined (syntax-other 9, patch_missing 5, old_file_missing_at_base 5, diff_truncated 4, corpus_unit_id_rejected 3, python2-except 2, python2-print 2, python2-long-literal 1): a quarantine rate of 1.4% of attempted, at most 6 in any 200 consecutive rows (3%). Time lost: about 13 hours from the relaunch to the diagnosis, of which about 4 h of mining ran (1,989 new rows in 3 h 52 min of job time).

Change (DEV-036, commit 1b61213, tests `tests/unit/test_mining_failure.py`, 29): a content exception quarantines the pull request as `corpus_error:<Class>`; a git step past its limit is `snapshot_timeout` and is not retried; infrastructure errors (by type, `ril/data_mining/failure.py`) still end the process; the session stops with exit code 5 above 5% quarantined of the last 200 attempted; the job script relaunches the miner up to 5 times from `state.jsonl` and writes a `HALT` file on exit codes 3 to 5 that a following job refuses to pass; git aborts a stalled transfer after 120 s; a failed session pushes its recorded rows. Measured on the stored rows: the guard would not have stopped any of the first 2,214 rows. No configuration value, seed, order or target changed.

New jobs on account C (commit 1b61213, memory 12 GB, 4 days, nodes gnode004 and gnode044 excluded as before): session 1 **64593** (no dependency, no listing job remains), session 2 **64594** (`afterany:64593`, `--kill-on-invalid-dep=yes`). The 2,214 state rows are kept. Twenty-minute watch (started 11:05 IST): session 1 RUNNING on gnode033, no traceback; the durable state grew from 2,214 to 2,310 rows (96 new: 66 mined, 20 no_python_change, 10 no_positive, 0 quarantined); the first push came after 10 minutes and the first rows after about 12 minutes, which is consistent with a heavy fetch at the head of the queue (not verified). Expected finish: mining about 28.5 h in all, 2,310 of 10,000 done, linear (no interval), plus queue wait for session 2.

## E-RETAIN-FINAL: can the finished model be kept in half precision without changing the run? Stated and done 2026-11-05 (D98)

Status: infrastructure, no experiment arm. Implements the retention task of `docs/RQ2_PROTOCOL.md` O9 (D76); nothing departs from D76, so there is no deviation entry.

**What was built.** `checkpoint.retain_final` (default off) in the training configuration; target directory `RETAIN_DIR` of the job environment (absolute, outside any git work tree; the run raises before the first update if the key is on and the variable is unset). `ril/training/retention.py` (manifest, verification, inventory, archiving plan; no torch), the copy of the encoder in half precision made in `ril/training/training.py` from a deep copy (the in-memory model and the `final` folder are untouched), the `RETAIN_DIR` line in `t1_train.sbatch` and the six batch runners, `scripts/archive_checkpoints.py`. The manifest holds the configuration hash, the commit (`RIL_COMMIT`), seed, arm, cell (`exp_id`), update count, evaluation set ids (`evaluation.set_ids`, else `evaluation.roles`), the SHA-256 of the model folder (hash over the sorted path and file-hash lines), its byte size and the per-file hashes.

**D98 (implementation choice, reversible).** The key is left out of the configuration hash and of the held-identical view. Reason: it changes where a file is written and nothing that is computed; a hash that moved with it would put the same run in two result directories and make an arm that retains differ "outside the arm" from one that does not. Evidence class: reasoned, then tested (below). Cheapest flip: put the key back into the hash (one line in `config_hash`); the cost is that old run hashes stay valid only for configurations without the key.

**Evidence (measured).** Tiny CPU configuration (512 buckets, 16 dimensions, 6 updates, seed 3), Ada CPU job 60205 (account A, `gnode` CPU node, one process each): the code of `main` (d9c62c5), the branch with the switch off and the branch with it on give the same configuration hash (`8dbdf0be...`), the same batch-plan hash (`ebe0a8b4...`) and the same SHA-256 of both model files (model weights `d6264b5d...`, encoder description `579b03cc...`); with the switch on the record gains one key, `retained`. The half-precision file reloaded as a model differs from the in-memory model by at most 1.3e-4 in any component of a unit-length query embedding (mean 3.9e-5, 8 queries); the test allows 1e-3. Tests `tests/unit/test_retention.py` (7, local) and `tests/unit/test_retention_training.py` (5, torch; the whole job-60207 test list, 41 tests including the leakage tests, passed). Not checked: the real 137M-parameter encoder (reload tolerance and the 274 MB size are arithmetic: 137M x 2 bytes), a run on a GPU, and the copy to account B (no alias for B exists; the script was not run).

## E-EVAL-REPOS: which CORE-Bench repositories could serve as evaluation repositories, and what would each cost to build? Inventory only, stated and done 2026-11-05

Status: exploratory inventory, outside the pre-registered RQ tables. **Nothing is chosen.** CPU only; no GPU-hours. Implements the table that `docs/RQ2_PROTOCOL.md` O8 (D75: at least eight repositories at L2 and as many with L3 labels as obtainable) needs before the choice.

**Inputs (hashes in the run log).** Per-folder instance ids and qrels counts (the per-folder id export, 1,458 folders; only the 632 L2 and 97 L3 originals are used, Rewrite folders skipped), corpus row counts per L2 folder (the corpus statistics export), the held-out list v2 and rename cache (`data/held_out`), the dev configuration (`configs/experiments/e1_bm25_dev3.yaml`: roles and which folders have unit records), and one cluster survey (`scripts/ada/eval_repo_survey.py`, `results/logs/eval_repo_survey_2026-11-05.json`, CPU job 60260 on a CPU node, 478 s, plus job 60214 of the first classifier, discarded): the stored unit records (521 files) and per-instance dense stores of the dense encoder at 512 tokens under the X2 working directory, line counts of the unit-text shards (953,927 distinct unit texts in all), file counts of the 12 bare clones, the listing of the published pool (24,285 directories, 2,448 repositories) with the mining population (the 5,000-directory selection of D41, seed 0: 1,473 repositories), and a language sample of every L2 corpus by six range requests of 48 KiB (about 180 MB; 46 failed requests in 14 folders after five tries, those folders are classed on fewer chunks).

**Commands.** `sbatch --export=ALL,IN=...,OUT=... scripts/ada/eval_repo_survey.sbatch` on the cluster, then `python -I scripts/eval_repo_inventory.py --survey <survey.json>` locally. Configuration hash `856c99ff00b55a67260493341bf777d44960257f2644f6eb68744b1ed0e198c7` (survey version, thresholds, encoding rates, input hashes), output SHA-256 `4b69835eea2e5336c0e7674765143059e8c723d6779c2f8f398df6356e2c39a4`; two runs give the same bytes. Hardware of the survey: CPU node, 40 CPUs, 128.6 GB; peak memory of the first survey job 2.08 GB (my estimate before the run said under 1.5 GB: the pool listing is the larger part; 6 GB were asked).

**Columns that matter.** One row per repository (605, case-folded `owner/name`). `l2_queries` and `l3_queries` are distinct instance ids over all folders that hold the repository (matplotlib has 123 L2 queries, 32 of them in the Verified folder; `*_by_folder` gives the split). `unit_records_instances` and `dense_store_instances` count stored snapshots, not queries. `units_basis` says `measured` (stored records; distinct unit texts = the texts one checkpoint must encode) or `estimated`. `held_out_listed`, `in_published_pool_listing`, `in_training_population`, `in_mining_population` and `leaks_if_evaluated` are described below.

### Facts (measured unless marked)

1. **Repositories.** 605 distinct (L2) of which 92 have L3 labels. By set: 6 dev (ansible, conan, haystack, openlibrary, qutebrowser, streamlink), 12 Verified, 587 other. Distinct instance ids: L2 5,035, L3 2,567 (E-L3-CENSUS and `core_bench.md`).
2. **Language screen (a line-marker heuristic on six slices of each corpus; Python needs a `def`/`class` line ending in a colon, `elif`, `except`, `from x import y` and the like). Not a language detector.** Of 605: python 286, mixed 21, non_python 297, unknown 1 (too few code-like chunks). By dataset the screen reproduces what the dataset names say: the two multi-language sets are non_python in 74 of 80 repositories (Multi-SWE-bench 37 of 39, Multilingual 37 of 41; the rest `mixed`, one `python`), Pro has 3 python and 7 non_python repositories, SWE-bench-Live 208 python and 5 mixed, SWE-bench++ 93 python, 13 mixed, 231 non_python. Known misses in the sample: astropy (Python with bundled C) is `mixed`; astral-sh/ruff (Rust) is `python` (its test fixtures are Python files). A first classifier (job 60214) labelled Ruby, C and C++ repositories `python` through `def` lines without a colon and decorators; it was replaced before any table was built (dead end, kept so it is not retried). Every `mixed` and every non-dev non-Verified `python` repository with L3 labels needs a look at its file list before use.
3. **Python-class repositories outside dev and Verified: 269 python, 20 mixed; none has unit records.** Their L2 queries (python): at least 1 query 269, 3: 100, 5: 67, 8: 47, 10: 39, 20: 15 repositories; 1,441 queries in all; 20 of the 269 sit in a folder shared with another repository, 26 in more than one folder. Source datasets of the 269: SWE-bench-Live 197, SWE-bench++ 90, SWE-bench+ 5, Multilingual 1 (a repository can belong to several).
4. **L3 labels.** 92 repositories: 15 `python`, 4 `mixed`, 73 non_python. The credible Python ones are the 3 Pro repositories (ansible 83 queries, openlibrary 81, qutebrowser 74; all dev) and the 12 Verified ones (django 136, sympy 51, sphinx 26, scikit-learn 21, xarray 13, ..., astropy `mixed` through its C code): 15 in all. The other flagged ones are ruff (`python`, a Rust repository whose test fixtures are Python) and jq, micropython and nlohmann/json (`mixed`), all from the multi-language sets and probably not Python. **No further Python repository with L3 labels exists outside dev and Verified**: "as many with L3 labels as obtainable" is 15 at most, 12 of them the final test.
5. **What is already built.** Unit records for 12 repositories (the 6 dev and the Verified-six: astropy, matplotlib, seaborn, flask, requests, xarray), 521 snapshots; dense stores for 11 of them (ansible has records but no dense store in that directory: it was left out of the dense waves by cost). django, sympy, sphinx, scikit-learn, pytest and pylint have none.
6. **Overlap.** `held_out_listed` is 605 of 605, as it must be: the list is built from these folders. **In the published pool's listing: 92 repositories** (89 by exact name, 3 by current name: faststream, django-dbbackup, authlib), 87 python-class, 4 mixed, 1 non_python; the filter removes exactly these 92 repositories (3,485 of 24,285 directories, 92 of 2,448 repositories; three of them under another spelling than the CORE-Bench one). **In the training population actually used (pool after the filter, and the 1,473-repository mining population): 0 of 605.** So no CORE-Bench repository leaks into the final training sets under the rules in force; the check is exactly as strong as the exact-name-plus-resolved-name filter and the rename cache (108 repositories looked up; unresolved renames are not checked here).
7. **Cost of building one (`distinct_unit_texts` x rate; the stored per-repository figure is 0.06).** Measured on the 12 repositories with records: distinct unit texts 1,091 (flask) to 274,336 (ansible); the five dev repositories hold 315,585 together (63,117 each). At 229 texts/s (the dev evaluation rate on record: 590k texts in 43 minutes, `docs/COMPUTE.md`) that is 0.0766 GPU-hours per repository, 0.383 for the five; at 178 texts/s (the rate in the task brief; **no log in the repository contains 178**) 0.0985 and 0.492; the stored 0.06 corresponds to about 290 texts/s (E-PILOT-ARMS2: 316k texts, 18 minutes). The three rates differ by 1.6 times; the cost column is given at 178 and 229 and the choice of rate is the lead's. Dev plus Verified together: 2.42 GPU-hours per checkpoint at 229/s (django 0.31, sympy 0.43, ansible 0.33). **Estimated** for the 269 other python-class repositories (distinct unit texts = median measured texts-per-L2-corpus-chunk ratio of the 12, 2.9, times the repository's chunks; low/high columns use the smallest and largest ratio, 1.1 to 5.5): median 0.0093 GPU-hours per checkpoint at 229/s, 90th percentile 0.039, sum for all 269 6.6; among those with at least 5 L2 queries (67): median 0.020, 90th percentile 0.053, largest 0.115; at 178/s multiply by 1.29. **Check of the estimate:** leave-one-out over the 12 gives a median absolute relative error of 30% and a maximum of 184% (flask, one snapshot); the ratio varies 5-fold across repositories, so an estimate is a screen, not a budget. Parse: measured prep seconds per snapshot (checkout plus parse) sum to 2,442 s for ansible (83 snapshots), 8,912 s for django's estimate; estimated median 40 s and 90th percentile 152 s for repositories with at least 5 L2 queries (snapshots x estimated units x the median measured seconds per unit); a rate from one machine class, estimate only. Files: Python files at HEAD from the bare clones (measured at HEAD, not at base commits) for 11 repositories, the rest estimated from units per file (median 11.7 units per Python file at HEAD in the 11 measured ones, range 6.6 to 22.6).
8. **Not checked.** Language of the `mixed` and unknown repositories beyond the sample; whether the corpus of a folder is the repository snapshot at one commit for every query (it is a union of per-query candidate lists, so folder chunks overstate one snapshot); the parser on any repository not in the 12; snapshots that cannot be checked out (an instance whose base commit is gone); dense encoding of an estimated repository; the mining population beyond the repository names in the listing; renamed repositories outside the rename cache.

### Options for the choice (the lead decides; no recommendation)

Each rule is stated so that a later session can apply it from `results/tables/eval_repo_inventory.csv` with a seeded key `sha256("0:<repository>")` where a seed is needed.

| Rule | Pool it draws from | What it implies |
|---|---|---|
| A. Seeded draw of 8 | the 269 python-class repositories outside dev and Verified, ordered by the seeded key | L2 only; repositories with 1 query possible; cost median 0.009 GPU-hours each (estimated); no L3 added |
| B. A with a floor on L2 queries (the floor is the lead's) | 100 / 67 / 47 / 39 / 15 repositories at floors 3 / 5 / 8 / 10 / 20 | fewer repositories, more queries each; the floor trades eligible count against interval width |
| C. A or B including the 20 `mixed` repositories after a manual file-list check | 289 | more choice; every `mixed` needs a human look |
| D. By source dataset, round robin of the seeded order | SWE-bench-Live 197, SWE-bench++ 90, SWE-bench+ 5, Multilingual 1 | spreads the draw over datasets whose label procedures may differ; the second to fourth groups are small |
| E. Existing material only | dev 6 and Verified 12 (11 have unit records and dense stores) | no new building; L2 count is 6 dev + 12 final test, L3 is 3 dev + 12 final test; the "at least eight" holds if the eight may include the dev repositories, but choices were made on dev |
| F. Cost cap | any of the above, taken in the seeded order until the summed estimated cost reaches a stated number of GPU-hours per checkpoint | makes the budget explicit; uses the estimate (error 30% median) |

Questions that decide between them: (1) may dev repositories count among the eight, or only repositories not used for choices (the protocol says all choices are made on dev); (2) do the new repositories play the role of dev (choices) or test; (3) which encoding rate is used for budgeting (178, 229 or 290 texts/s); (4) is a `mixed` repository acceptable after a manual check; (5) L3 cannot be enlarged beyond the 15 Python-class repositories, so is the L3 claim stated on those?

## E-LABEL-AUDIT-SHEET: sheet and scorer for the pull-request noise audit (O11, D78). Exploratory (data), built 2026-11-05

Status: built; **nobody has read any pair**, so no noise rate, agreement or findability figure exists. Decision D99 (2026-11-05, recorded here; reasoned only, cheapest flip: a pilot read of 20 rows by one person, about 25 minutes): the sample is stratified by the BM25 cell at K = 20 only, 200 pairs per cell, because dense-teacher ranks do not exist for enough of the population (below). No GPU was used. Code: `ril/evaluation/{label_audit,label_audit_jobs,label_audit_score}.py`, `ril/data_mining/audit_pairs.py`, `scripts/label_audit_build.py`, `scripts/label_audit_score.py`, job `scripts/ada/label_audit.sbatch`; tests `tests/unit/test_label_audit*.py` (32); instructions `docs/LABEL_AUDIT.md`; the call-edge sheet and scorer are unchanged. Account A, jobs 60209 (stopped at 140 of 247 pull requests by an uncaught git timeout; 244 pairs kept) and 60308 (resumed, 37.5 min, peak RSS 0.41 GB).

**Population and draw (measured).** The pair is one positive of one mined pull request (the unit of the positive-level filter). Population: the 1,286 `non_test` directories, 7,081 positives, from the BM25 rank file of E-MINED-PILOT (sha256 da16350a...f9f7c). K = 20 keeps 1,858 positives and drops 5,223, which reproduces the filter-size record of that experiment (1,858 kept of 7,081). Draw, seed 0, uniform without replacement within each cell: **200 pairs from the kept cell, 200 from the dropped cell** (at least 100 per cell met). 247 directories, 91 repositories; pairs of one pull request are not independent. Overlap: 100 pairs (50 per cell), read by both readers; the other 300 are split 75 + 75 per cell, so each reader has 100 + 150 = 250 rows with the same cell mix. Row order is shuffled per sheet from the seed. Pair ids are hashes of seed, directory and positive.

**What does not exist (stated, not computed).** SweRankEmbed-Small ranks exist for the first 300 directories only (1,830 of the 7,081 positives); 111 of the 400 sampled pairs have one (57 in the BM25-kept cell, 54 in the dropped cell). No dense cell can reach 100 pairs, so the sample is not stratified by the dense teacher; the dense rank is carried in the key and the scorer prints the wrong-positive counts by dense cell as a descriptive table only. No GPU ranks were computed.

**Text on the sheets.** Issue text and the function text before the change come from the store (the miner's own stored query and corpus row). The pull request title and the diff are not stored, so the job fetched the compare response and title of the 247 pull requests again (215 API calls), fetched each base commit, parsed it with the project parser and mapped hunks to units with the miner's `map_change`. A hunk is shown only if it removes or rewrites a line of the function or inserts lines the function owns. **399 of 400 pairs reproduce the stored removed and inserted line counts**; one pair (a base-commit fetch that timed out twice) says on its row that the diff is unavailable. Truncation (written in `docs/LABEL_AUDIT.md` and recorded in `sample_meta.json`): issue body 3,000 characters, function text 4,000, hunks 4,000, pull request title 300, at most 30 other edited functions. Cells that a spreadsheet would read as a formula get a leading space.

**Files and hashes.** reader_1 1,246,935 bytes (sha256 4757c564...d4a5), reader_2 1,248,103 (1e3e95b3...fd0d8), reader_overlap 496,239 (6bc40b87...c9d8c71b), key 57,219 (c4719189...e31b); sizes and hashes verified after the copy from the cluster; full values in `sample_meta.json`. About 3.0 MB in all, but the sheets are **kept local, not tracked**: they quote public issues and tracebacks verbatim, which the provenance check rejects (home paths of third parties and other strings the pattern list rejects); the check was not loosened. They sit in `data/review/label_audit_pilot_v1/sheets/`, the key and the raw extraction beside them; `sample_meta.json` (tracked) records what was drawn. The key is never in a reader's file.

**Scorer.** Agreement on the overlap (percent with Wilson interval, Cohen's kappa with a seeded bootstrap interval, three-way and without "cannot tell"); wrong-positive share per cell with Wilson intervals, pooled, and population-weighted with a stratified bootstrap; precision of the K = 20 drops (wrong-positive share in the dropped cell) and the share of noisy pairs dropped; the missing-positive share from the second question. "Cannot tell" and two-reader disagreements are unresolved; every rate is printed excluded / lower / upper (rule in `docs/LABEL_AUDIT.md` and the scorer's docstring). Every number is labelled as measured on a sample of readers' judgements, with n. Tested on synthetic filled sheets only.

**Not done.** Nobody has read a pair; no kappa, rate or findability exists. No model judge was chosen or run (ADR-008 note of 2026-11-05). The full mined set (E-MINE-FULL) is not sampled. Hours: by the protocol's rate (about 1 hour per 50 positives, reasoned) each reader needs about 5 hours for 250 rows.

Commands (code at the commit named in the job log):

    sbatch --export=ALL,SEED=0,RIL_COMMIT=<hash> scripts/ada/label_audit.sbatch      # from ~, files under ~/ril_audit
    python -I scripts/label_audit_score.py --key <key.csv> --sheet <reader_1_filled.csv> --sheet <reader_2_filled.csv> --json <report.json>   # after reading

## E-EVAL-REPOS-BUILD: unit records and dense stores of the eight evaluation repositories (D100). Build only, stated and done 2026-11-06

Status: **build, not an evaluation.** No retrieval result was computed or read on these repositories; the eight take the test role (D100), so nothing here is tuned. Evidence class: measured (counts, seconds, GPU time). Implements the build half of D100 and the O8 task of `docs/RQ2_PROTOCOL.md` section 11.

**The eight, fixed by rule (`configs/experiments/eval_repos_v1.json`, `scripts/select_eval_repos.py`, test `tests/unit/test_eval_repo_selection.py`; inventory SHA-256 `4b69835e...2c39a4`).** Pool: Python-class repositories outside dev and Verified with at least 5 L2 queries (67); order `sha256("0:<repository>")`. Evaluation set with L2 queries: pdm-project/pdm 33, psf/black 5, python-control/python-control 12, jupyterlab/jupyter-ai 11, aws-cloudformation/cfn-lint 82, ibm/mcp-context-forge 9, jlowin/fastmcp 22, pyomo/pyomo 5 (179 queries). Reserve, unused: sissbruecker/linkding, quantumlib/cirq, pvlib/pvlib-python, python-telegram-bot/python-telegram-bot, dynaconf/dynaconf, spesmilo/electrum, delgan/loguru, projectmesa/mesa. **No reserve repository was needed**: no repository failed (parse, base commit, checkout) at any stage. pvlib's 55 SWE-bench+ queries would have had no readable base commits (E-BM25-REPRO coverage table), a fact recorded here before any reserve is considered.

**Inputs.** Base commits from the datasets' own metadata (SWE-bench-Live and SWE-Bench++ tables, `scripts/build_eval_inputs.py`; 179 of 179 found). Raw L2 folders fetched on the cluster; folders shared with other repositories (`SWE-bench-Live/python`: 56 queries of which 12 python-control and 14 python-telegram-bot; `SWE-bench-Live/aws`: 83 of which 82 cfn-lint) are cut to the repository's own instances by the new `instances_of_repo` key of the folder spec (`ril/evaluation/e1_run.py`; existing configurations do not carry it, so earlier hashes are unchanged). Role `test`, level L2 only (L3 labels do not exist outside dev and Verified, D100 (6)).

**Jobs and code.** Account A. Code commit `b4aa33f` (CPU job; one later commit adds a free-disk guard to the script) and `bcb57ef` (GPU job). Build configuration SHA-256 `2fb77306...1243b4`; unit-record configuration hash `238055a9...b7ba5`, instance-cache hash `70b48163...daa682`.
- Job 60670 (CPU): failed in 0 s on gnode012, node-local `/tmp` full. Tactical: free-space guard in the script, `--exclude=gnode012`.
- Job 60671 (CPU, gnode025, 4 CPUs, 23 min 42 s, peak RSS 3.49 GB of 12 GB asked; my estimate before the run was under 8 GB for four processes): raw folders, eight bare clones on node-local disk (413 s), unit records 179 of 179, instance caches 179 of 179, unit-text stores 179 of 179, 0 failures at every stage. The job state is FAILED because the last step, `prep-queries`, stopped at the development-only latency statistic (no development role in this configuration) after writing all query stores; nothing else depends on it.
- Job 60677 (GPU, gnode052, RTX 2080 Ti, 14 min 45 s = 0.246 GPU-hours): CUDA gate passed (matrix product maximum error 1.2e-4), CodeRankEmbed revision `3c4b6080...`, 512 tokens, float16 (agreement with float32: minimum cosine 0.999996), batch 64, peak GPU memory 1.43 GB. Store check (jobs 60692, 60693, CPU): every unit text of every instance has a stored vector (0 missing); the stores also hold the texts of the two other class-source forms the preparation always produces (69,961 texts encoded, 59,417 needed for the `full` form).
- Jobs 60678, 60692, 60693 (CPU, seconds): cache statistics and the store check.

**Measured against estimated (`results/tables/eval_repo_build_measured.csv`; the inventory is not edited so that the hash recorded by the selection stays valid; the estimate columns are copied beside the measured ones).**

| Quantity | Estimated (inventory) | Measured |
|---|---|---|
| Distinct unit texts, `full` form (eight repositories) | 255,756 | 59,417 (estimate 4.3 times too high) |
| Parse stage seconds, summed over 179 snapshots | 1,621 (includes checkout) | 296 (the whole instance-cache pass, which parses, builds the graph and the BM25 index, took 1,174) |
| Units per snapshot, pyomo | 6,964 | 24,026 median (3.4 times higher; the other seven repositories are within 0.5 to 1.5 times) |
| Encoding seconds, units | 1,117 at 229 texts/s (0.310 GPU-hours); 1,437 at 178 (0.399) | 640 s = 0.178 GPU-hours for 69,961 texts |
| Encoding rate | 229 (dev pipeline), 178 (brief) | 109 texts/s overall; 165 without cfn-lint |

Reading (evidence: measured, one run on one card). The per-checkpoint cost of encoding the eight repositories is 0.178 GPU-hours at the measured rate, below the 0.310 estimated at 229 texts/s, because the estimate of distinct texts was 4.3 times too high, not because the encoder was faster: the measured rate is lower than both budgeting rates (D100 (5)). The 20% margin of D79 holds on the measured total; the rate on a different text mix (cfn-lint's templates, pyomo's long modules) is the open number, and the first evaluation job should log its own rate. The inventory's per-repository estimate has errors of 0.2 to 3.4 times in units and 4.3 times in distinct texts for these eight: it is a screening estimate, not a budget.

**Flaky or unexplained.** (1) cfn-lint encoded at 29 texts/s (264 s for 7,754 texts, 7.9k tokens/s) against 100 to 200 texts/s (20 to 40k tokens/s) for the other stores; the store ran first after model load. I did not investigate (warm-up, a shared card or node noise are all possible); the total GPU time includes it. (2) Node gnode012 had a full local disk (job 60670). (3) The shared-folder filter depends on instance ids starting with `owner__name-`; it holds for these eight (179 of 179 instances found in the metadata).

**What this does not show.** Nothing about retrieval quality, nothing about the arms, nothing about whether the eight differ from dev. The first look at results on these repositories is the single confirmatory evaluation after the dev analysis (D100 (2)).

## E-ASSEMBLY: how much of the gold lands in the assembled context, by token budget and first stage? Exploratory, stated 2026-11-06 (before any number was computed)

Status: exploratory, outside the pre-registered RQ tables. CPU only; no GPU-hours. Evidence class: measured (counts on stored first-stage scores; the assembly policy itself is reasoned, ADR-014, decision D102). Code: `ril/assembly/` (policy, tokenizer, manifest, `gold_in_context`, measurement `measure.py`), `ril/analysis/assembly_tables.py`, `scripts/assembly_run.py`, job `scripts/ada/assembly_gold.sbatch`, configuration `configs/experiments/assembly_gold.yaml`, tests `tests/unit/test_assembly*.py`. Spec: `specs/assembly.md`.

**Why.** RQ3 varies the retriever only; what an agent reads is the assembled context, so the share of gold that reaches it bounds what any retriever can give the agent (the retrieval-versus-reasoning breakdown starts here). It also gives the budget grid a first description before any budget is chosen for an agent.

**What varies.** The budget B (4,000, 8,000, 16,000, 32,000 approximate tokens) and the first stage (BM25; RRF(BM25, CodeRankEmbed at 1,024 tokens), k 100, the setting E-GRAPH-ROLE stated for that encoder, from the stored dense scores). **What is fixed.** The policy of ADR-014: the 200 best units, unit cap 1,000 tokens, class units in header form, the approximate tokenizer (`approx-words-v1`); the E3 cache with the D18 readings (primary `units_all_nomod`, `units_all` beside it); no graph expansion. No dense score is computed (no GPU); an instance without stored dense scores has BM25 rows only.

**Instances.** Role `dev` (openlibrary, qutebrowser, conan, haystack, streamlink at L2; openlibrary and qutebrowser at L3) and role `test` (Verified, the six repositories with unit records). The test role is read once, with the values stated in the configuration; no sweep, nothing selected from it. The eight evaluation repositories of D100 are not touched.

**Measures per query (one instance and level).** Share of gold files in the context (a file counts when at least one included unit lies in it); share of gold units included; share of gold units included intact (not cut by the unit cap); whether no gold file is in the context ("absent"); tokens used; units included. Mean over queries with a query-level and a repository-clustered 95% interval (2,000 draws, seed 0; D17). Dev L3 has two repositories, so its clustered interval is not informative (Q47).

**Reading rules (before the run).** (1) The number to read for "does retrieval limit the agent" is the share of queries with no gold file in the context, per budget and first stage, on Verified-six with its clustered interval; the shares of gold files and units are descriptive. (2) A difference between the two first stages is stated only on the queries that have both, with the interval of the difference not computed here (the two intervals are reported side by side; overlap means indistinguishable at this sample size). (3) Nothing here sets a budget or a unit cap for the agent.

Results (measured, exploratory; run `assembly_gold_2026-11-06`, ril commit 562da39, configuration hash e418b3aa, CPU job on account A, 1 h 38 min, peak memory 4.1 GB, no GPU). 521 instances measured, 0 failed. Stored dense scores exist for 354 of the 437 dev instances and for all 83 Verified-six instances; the 83 dev instances without them (no stored dense scores) are in the BM25 rows of the "all" scope only, and every row below is on the matched queries (those that have both first stages). Primary reading `units_all_nomod`; `units_all` is in the table file. Tokens are approximate (`approx-words-v1`); on 200 sampled units the approximation counts 1.22 times a real tokenizer's count in total (median 1.26, 5th to 95th percentile 1.05 to 1.59, a 0.6B embedding model's tokenizer, not the agent's), so a budget of B approximate tokens is about B/1.2 real tokens of that tokenizer. Files: `results/tables/assembly/`, `results/rq3/assembly_gold_2026-11-06/` (per-query rows, hashes, environment, token ratio).

Share of queries with no gold file in the context, Verified-six (the number of reading rule 1), % [repository-clustered 95% interval; 6 repositories]:

| level | first stage | B 4,000 | B 8,000 | B 16,000 | B 32,000 |
|---|---|---|---|---|---|
| L2 (83 queries) | BM25 | 45.8 [28.6, 56.3] | 31.3 [12.2, 39.7] | 26.5 [10.3, 33.8] | 16.9 [4.1, 26.7] |
| L2 | RRF | 31.3 [16.7, 43.4] | 21.7 [6.1, 32.5] | 14.5 [2.0, 22.4] | 8.4 [0.0, 14.0] |
| L3 (55 queries) | BM25 | 21.8 [3.3, 33.9] | 9.1 [0.0, 14.3] | 5.5 [0.0, 7.9] | 3.6 [0.0, 7.1] |
| L3 | RRF | 14.5 [0.0, 25.0] | 3.6 [0.0, 7.1] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] |

Share of gold files and gold units in the context, Verified-six, % (clustered intervals in the table file):

| level | first stage | files 4k | files 8k | files 16k | files 32k | units 4k | units 8k | units 16k | units 32k |
|---|---|---|---|---|---|---|---|---|---|
| L2 | BM25 | 51.2 | 64.3 | 69.7 | 81.5 | 22.8 | 30.7 | 38.0 | 43.8 |
| L2 | RRF | 64.3 | 74.5 | 82.1 | 90.0 | 25.9 | 33.1 | 46.5 | 53.4 |
| L3 | BM25 | 46.4 | 59.7 | 65.8 | 76.2 | 13.4 | 17.4 | 22.8 | 29.4 |
| L3 | RRF | 57.7 | 70.0 | 76.9 | 84.4 | 15.3 | 19.9 | 27.1 | 36.1 |

Dev (L2, 351 matched queries, 5 repositories), files / units / no gold file, %: BM25 57.0 / 19.6 / 29.3 at 4k, 66.3 / 26.0 / 21.1 at 8k, 73.4 / 33.2 / 15.7 at 16k, 82.6 / 38.4 / 8.8 at 32k; RRF 65.3 / 22.5 / 19.4, 73.8 / 29.6 / 13.7, 82.2 / 36.9 / 8.6, 87.4 / 44.0 / 5.4. Dev L3 (155 queries, 2 repositories) follows the same pattern (files 58.4 to 85.9 under BM25, 64.6 to 90.6 under RRF). Mean tokens used is within about 25 of B at every budget (the first-fit walk fills the budget), so mean tokens carry no information beyond "the budget is used". Mean units included at B 8,000 on dev L2 is about 25.

Reading (inference from the measured counts). (1) Every number rises with B and the clustered intervals are wide (6 repositories on Verified-six, 5 on dev L2, 2 on dev L3): the direction is consistent across levels, readings and both role groups, the sizes are not pinned down. (2) At B 8,000 about a fifth to a third of L2 Verified-six queries have no gold file in the context under either first stage; this is a retrieval bound that the agent cannot repair with reasoning, and it falls to about 8 to 17% at 32,000. At L3 the file is almost always present from 16,000 up. (3) Gold units are reached far less often than gold files (Verified-six at 8,000 to 32,000: units 17 to 53% against files 60 to 90%): the context often holds the right file but not the gold function, so file-level and unit-level measures must not be mixed in the failure breakdown. (4) RRF is above BM25 in every cell of the point estimates; the difference is not tested (no paired interval for the stage difference was computed here) and the interval overlap is large, so no difference between the first stages is claimed. (5) On Verified-six part of the included gold is cut by the unit cap (L2, B 8,000: 30.7% of gold units included and 23.2% intact under BM25; 33.1% and 24.2% under RRF; about 2 points on dev), so the cap matters there; the cap was not varied. (6) No budget is chosen for the agent.

What this does not show: nothing about agent behaviour, nothing about the agent's own tokenizer (budget is in approximate tokens), nothing about expansion (off), nothing about the eight evaluation repositories, nothing about the retrievers of the RQ2 arms. The Verified-six values are the single stated setting, read once.

## E-ASSEMBLY-CAP: which per-unit cap keeps the most gold units intact in the assembled context? Exploratory, rule stated 2026-11-06 (decision D103, before any number of the re-run was computed)

Status: exploratory, outside the pre-registered RQ tables. CPU only; no GPU-hours. Evidence class: measured (counts on stored first-stage scores); the rule is reasoned and is recorded in the ADR-014 addendum of 2026-11-06, committed before the job was submitted. Code: `ril/assembly/measure.py` (cap grid), `ril/analysis/assembly_tables.py` (`cap_selection_rows`, `select_cap`, `paired_rows`), `scripts/assembly_run.py cap_tables`, job `scripts/ada/assembly_cap.sbatch`, configuration `configs/experiments/assembly_cap.yaml`, tests `tests/unit/test_assembly_measure.py`.

**Why.** In E-ASSEMBLY part of the gold that reached the context was cut by the 1,000-token unit cap (Verified-six, L2, B 8,000, BM25: 30.7% of gold units included, 23.2% intact). ADR-014 named a re-run at 500 and 2,000 as the cheapest flip experiment.

**What varies.** The unit cap: 500, 1,000 (the default), 2,000 approximate tokens. **What is fixed.** Everything else of E-ASSEMBLY: 200 candidates in rank order, class units in header form, the approximate tokenizer, the E3 cache with the D18 readings, stored dense scores (CodeRankEmbed t1024, RRF k 100), budgets 4,000 / 8,000 / 16,000 / 32,000, first stages BM25 and RRF. **Instances.** Role `dev` only (437 instances; 354 have both first stages; matched queries 351 at L2 and 155 at L3 under the primary reading). The test role is not in the configuration: Verified-six was read once in E-ASSEMBLY and is not read again.

**Rule (fixed before the run).** Selection metric: share of gold units included intact (`units_all_nomod`), mean over the matched dev queries, averaged without weights over the eight cells {L2, L3} x B {8,000, 16,000} x {BM25, RRF}. Highest value wins; caps within 1.0 point of the best tie and the smaller cap wins. The share of gold files in the context is reported beside it and does not enter the choice; B 4,000 and 32,000 are reported and do not enter.

Results (measured, exploratory; run `assembly_cap_2026-11-06`, ril commit c406c4d, configuration hash 71ecf03b, CPU job 61413 on account A, 1 h 25 min, peak memory 2.6 GB, 438 instances measured, 0 failed; stored dense scores for 354 of the 437 dev instances with rows, so every row below is on matched queries). Files: `results/tables/assembly_cap/` (`selection`, `paired`, `summary`, `coverage`), `results/rq3/assembly_cap_2026-11-06/` (per-query rows, hash, environment).

Selection metric by cap (intact share of gold units, %, mean of the eight cells) and the gold-file share beside it:

| cap | intact share (metric) | gold files in context (beside, not used) |
|---|---|---|
| 500 | 25.61 | 76.60 |
| 1,000 (default) | 28.70 | 74.95 |
| 2,000 | 29.35 | 74.12 |

The best value is 2,000 (29.35); 1,000 is 0.65 points below it, within the 1.0-point tie, and 500 is 3.74 below. **The rule selects the smaller of the tied caps: 1,000, the current default.** `specs/assembly.md` and the assembly version string are unchanged. Cells (intact %, L2 / L3, B 8,000 and 16,000; BM25 then RRF) are in the selection table; the ordering 500 < 1,000 < 2,000 holds in every one of the eight cells.

Reading (inference from the measured counts). (1) A larger cap raises the intact share and lowers the share of gold files in the context, because longer units use the budget: the first-fit walk includes fewer units (mean units included at B 32,000, L2, BM25: 113 at cap 500, 97 at 1,000, 92 at 2,000). The two measures move in opposite directions, so the choice depends on which one matters for the agent; the rule used only the first. (2) The gain from 1,000 to 2,000 (0.65 points) is smaller than the gain from 500 to 1,000 (3.09 points) and no interval of the difference between caps is computed, so no ordering of 1,000 and 2,000 is claimed beyond the point estimates. (3) The cap stays `provisional: D102`; no agent was run.

Paired difference, RRF minus BM25, dev, at the selected cap 1,000, primary reading, points [query-level 95% interval; repository-clustered 95% interval] (all caps are in the paired table; intervals only, no multiplicity claim; dev L2 has 5 repositories, dev L3 has 2 so its clustered interval is not informative):

| level | B | gold file in context | gold unit intact |
|---|---|---|---|
| L2 (351 queries) | 4,000 | +8.29 [4.4, 12.1]; [3.2, 15.9] | +2.98 [1.2, 4.8]; [0.3, 5.5] |
| L2 | 8,000 | +7.51 [4.0, 11.0]; [3.5, 13.0] | +3.48 [1.8, 5.2]; [2.4, 4.9] |
| L2 | 16,000 | +8.73 [5.7, 12.0]; [4.6, 12.9] | +3.42 [1.5, 5.4]; [0.6, 6.3] |
| L2 | 32,000 | +4.80 [2.6, 7.3]; [2.7, 7.3] | +5.29 [3.6, 7.3]; [2.5, 8.0] |
| L3 (155 queries) | 4,000 | +6.19 [2.0, 10.4]; [1.3, 10.7] | +2.56 [0.9, 4.2]; [0.8, 4.2] |
| L3 | 8,000 | +6.40 [2.5, 10.2]; [0.8, 11.5] | +3.68 [2.0, 5.4]; [2.1, 5.1] |
| L3 | 16,000 | +7.95 [4.8, 11.0]; [2.5, 12.9] | +4.72 [3.2, 6.4]; [2.7, 6.6] |
| L3 | 32,000 | +4.74 [2.5, 7.1]; [1.7, 7.5] | +4.83 [3.2, 6.5]; [4.0, 5.6] |

At cap 1,000 all 16 cells exclude 0 under both intervals. Across the 48 cells of the paired table (three caps), 46 exclude 0 under both intervals; the two that do not are gold-file differences at L3 whose clustered interval includes 0 (cap 500, B 4,000: +5.93 [-0.4, 11.7]; cap 2,000, B 8,000: +4.93 [-0.2, 9.6]), both with only two repositories. The sign is positive (RRF above BM25) in every cell. This is a dev result on 5 repositories (L2) and 2 (L3); it is not a Verified result and says nothing about the agent.

What is not done: Verified-six is not read again (the cap was chosen on dev only; its Verified numbers stay those of E-ASSEMBLY at cap 1,000); no agent-model tokenizer (budgets are approximate tokens); no agent run; no expansion option; no cap other than the three; no per-repository slice of the cap effect.

## E-OVERLAP-AUDIT: do mined positives or corpora contain held-out functions? Stated 2026-11-06 (before any result), decision D105

Status: built; pilot store (1,391 directories) audited on account A, job 61808, 2026-11-06. Evidence class: measured (counts); the rule is reasoned. Implements the audit D65 left unbuilt and the precondition of O10 (`docs/RQ2_PROTOCOL.md` section 11). Code: `ril/data_mining/overlap_audit.py`, `scripts/mine_overlap_audit.py` (`index`, `audit`, `apply`), `scripts/ada/overlap_audit.sbatch`, `tests/unit/test_mining_overlap_audit.py`.

**D105 (rule fixed before the full set is audited; evidence class of the rule: reasoned).**
1. Key: the syntax-tree hash of E-CONTAM-PROBE (docstring, decorators, comments, layout ignored; names and statements kept), floor 20 nodes primary. (a) positives: a mined positive whose hash matches a held-out function at or above the floor. (b) corpus: matched distinct functions over distinct functions at the floor (test-file functions excluded, D96 reading). The line-hash coverage of `content_overlap.py` is computed as a second reading.
2. A directory is **dropped** when at least one non-test positive matches by (a); **flagged, not dropped** when only (b) reaches 5%. Reason: a positive match is the answer leaking; corpus overlap alone is shared boilerplate or vendored code, so it is reported and the drop is a sensitivity cell. 5% is a stated working threshold, not derived. Loss is reported at directory and repository level.
3. Reads the de-duplicated store (rows hashed once per repository); the store is never written.
**Flip experiment:** the numbers at floors 10 and 50 beside 20, positives `all`, and drop-flagged, all from the same records.

**Held-out side and its limit.** Hashes come from stored material only: the Verified probe set (12 repositories, 499 base commits), unit-text stores of the six dev repositories and the eight D100 repositories. That is 26 of the 605 held-out repositories; the other 579 have no unit records (corpora are streamed, not stored), so a leak into one of them is not detectable by this audit. Line-hash coverage covers 20 repositories (no text store for django, sympy, sphinx, scikit-learn, pytest, pylint). Recorded as an open question, not substituted.

**Not done:** the full store (mining in progress); coverage of the other 579 held-out repositories; near-duplicate (renamed or edited) copies.

**Run (job 61808, account A, CPU, gnode006, Python 3.10.12; commit `4420114`; configuration hash `588effda460d...f5938c`).** Index build 790.5 s (381,971 syntax-tree hashes of 26 repositories, 337,390 at the floor; 1,513,138 line hashes of 20 repositories), audit 1,445.5 s for 1,391 directories, 156 repositories, peak 4.84 GB by `sacct` (my estimate was 3 to 6 GB). The 1,286 pool-like directories and 7,081 positives of E-MINED-PILOT are reproduced from the records, and 0 positives lack a corpus row. Outputs: `results/mining/overlap_audit/pilot/` (`records.jsonl`, `summary.json`, `run.json`, `index_manifest.json`, drop and flag lists, `match_sample.tsv`).

| Rule | Dropped (a) | Flagged (b only) | Repositories with a dropped directory | Pool-like directories after | Positives after (of 7,081) |
|---|---|---|---|---|---|
| floor 20, non-test positives (primary) | 3 | 33 | 3 (none lost entirely) | 1,283 of 1,286 | 6,996 |
| floor 10 | 8 | 29 | 6 | 1,278 | 6,630 |
| floor 50 | 3 | 30 | 3 | 1,283 | 6,996 |
| floor 20, all positives (test included) | 3 | 33 | 3 | 1,283 | 6,996 |
| floor 20, flagged also dropped | 36 | 0 | 8 (2 lost entirely) | 1,263 | 6,921 |

**Matches by size (positives, non-test; all sizes shown as in E-CONTAM-PROBE):** under 20 nodes 10, 20 to 49: 0, 50 and up 5 (15 matches in 11 directories; 16 in 12 with test positives). Corpus level (distinct matched functions, 23,000): under 20: 18,496, 20 to 49: 1,958, 50 and up: 2,546. Held-out repositories matched most: by corpus (a hash shared by several repositories counts for each), django 6,361, sympy 6,140, ansible 5,457, astropy 4,628, pyomo 4,367; by large positive matches, scikit-learn (all five). Line-hash reading: 26 directories at or above 5% coverage, 23 of them also flagged by the syntax-tree share.

**Hand reading (all 5 matches at the floor; no judgement was applied by the code).** Each is a function in a repository that is not a fork of scikit-learn and sits in code copied from or adapted from scikit-learn: `sktime/skbase` `BaseMetaEstimator._get_params`, `_set_params`, `_replace_estimator` (96, 114, 66 nodes), `autogluon` `OneHotMergeRaresHandleUnknownEncoder.inverse_transform` (488), `rasbt/mlxtend` `externals/signature_py27.py` `Parameter.__init__` (174). The under-20 matches are generic (`__enter__`, `__exit__`, `name` properties, `log_message`). Provenance beyond path and name was not checked. So all dropped directories are vendored-copy cases, which name matching cannot see; a hash match shows equal code, not that the copy was evaluated on.

**What this shows and does not.** On the pilot store the audit removes 3 of 1,286 pool-like directories (0.2%) and 85 of 7,081 positives (1.2%) at the primary floor. It shows nothing about the 579 held-out repositories without unit records, near-duplicate copies, or the full store. The 33 flagged directories come from 6 repositories (pynwb 11, msgspec 9, mlxtend 6, billiard 4, cloudpickle 2, tensorly 2), concentrated as expected for shared or vendored code; dropping them is a sensitivity cell only.

**G2 (D77, 10,000 positives at full scale).** Pilot positives after the audit: 6,996 (98.8% retained). Estimate, not measured: 6,430 pool-like directories at the 10,000-attempted target times the pilot's 5.5 positives per directory is about 35,000, about 34,500 after the audit, against 10,000. The audit does not threaten G2 on this estimate; the full store decides.

**Full set (not run).** Plan in `results/mining/full_run_plan.md` step 8.
## E-RQ3-PILOT-PREP: can resolved rate be measured on the cluster; provider adapter, prompts and smoke test for the RQ3 pilot. Exploratory, 2026-11-06 (decision D104)

**Question.** Before RQ3 is run: (A) can the cluster apply a patch, run the tests and decide resolved; (B) what does a
hosted-model call cost under the free-tier limits, and can the calls be sent resumably and safely; what do the
prompts of a 100-instance pilot look like. Nothing here is the RQ3 result.

**Part A, measured (account A, CPU jobs, node-local disk, nothing deleted; commands, scripts and outputs in
`scripts/ada/rq3_feasibility/` and `results/rq3_pilot/part_a/`, with a README that maps job ids to outputs).**
Jobs 61759, 61768, 61790, 61882, 61885 carry the evidence; 61762 and 61776 are dead ends (a truncated `uv` download;
`swebench` 5.x without the install specifications) and are recorded as such.
- Dataset and instances: SWE-bench Verified, 500 instances, all with a base commit, a test patch, FAIL_TO_PASS and an
  install specification in `swebench` 4.1.0; 432 have L2 labels, 302 L3. Dev instances not checked.
- Container runtime: none usable. No runtime on the PATH (login node, gnode004); the module `u22/singularity-ce/4.2.2`
  points at a directory that is absent from both; its tarball, extracted node-locally, builds an image but cannot run
  it (`max_user_namespaces` 0, starter not setuid root).
- Environment without root: partly. 263 of 500 buildable (Python 3.8 or newer, no pre-install), 59 with a non-`apt`
  pre-install (untested), 35 need `apt-get`, 143 need Python 3.5 to 3.7 (not downloadable with `uv`); 80 distinct
  environments. Reachable hosts and statuses in `docs/RQ3_PILOT.md`.
- Gold patch: requests-6028, seaborn-3187, xarray-7393 pass FAIL_TO_PASS after the patch and fail before it; environment
  19 / 100 / 138 s, tests 0.7 / 84 / 0.9 s, under 0.3 GB. flask-5014 failed first on an unpinned pytest, and ended with 60
  passed after the patch (exit 0) and 1 failed before it with `pytest<8` (the script's FAIL_TO_PASS id match was lost to
  output truncation in that retry, so the evidence is the exit status and counts). PASS_TO_PASS not checked.

**Part B.** `ril/agent/providers/` (new files only; nothing of workstream C edited): `gemini.py` (client, key handling
from `~/.ril_llm_env` or the environment, masked key object, retries with backoff, 429 and 5xx counted),
`limiter.py` (requests per minute, tokens per minute, requests per day on the Pacific day, state in a JSON-lines
file, clean stop at the cap, resume), `calllog.py` (per-call rows, prompts and replies as files by hash),
`patch_format.py` (prompt and edit format, `rq3-pilot-prompt/v1`), `pilot_run.py` (prepare, run with re-asks and
resume), `report.py`, `contexts.py` (assembled contexts for both first stages); `scripts/rq3_pilot.py`;
`configs/agent/gemini_limits.yaml` (limits with their date). Tests (no network, a recorded fake transport and a
manual clock): limiter arithmetic, resume after a stop, the key absent from logs, files and error messages,
malformed and blocked replies, prompt determinism, run resume, report. Limits used: 90% of the console values (13 a
minute, 225,000 tokens a minute, 450 a day).

**Prepare.** Job 61792 and 61884 built the first draw (budget 9,760 approximate tokens; 100 instances of the five dev
repositories, 200 prompts, median about 36,000 characters); the smoke test showed the model's input token count equal
to the approximate count (ratio 1.00 on three prompts, not the 1.22 of E-ASSEMBLY), so the budget was restated and the
prompts rebuilt as `prepared_dev100_b8000` (job 61889, config `configs/experiments/rq3_pilot_prepare.yaml`, config hash a8ec4fc94cc9 (SHA-256 prefix of the file), seed 0): 100 instances of five dev repositories (conan 46, deepset 50, qutebrowser 50, openlibrary 40, streamlink 14 across the two arms), 200 prompts of 24,877 to 38,428 characters (median 30,115), the two arms' contexts differ for every instance. The prompt files stay on the cluster (`~/ril_rq3/prepared_dev100_b8000`).

**Smoke test.** Three calls (the key file existed at run time): model string accepted, three usable replies on the
first attempt, input 10,001 to 10,099 tokens, latency 1.7 to 3.7 s. `results/rq3_pilot/smoke_2026-11-06/`.

**Dry-run plan.** 400 units, 400 to 1,200 calls, 1 to 3 days at 450 requests a day (the 13-a-minute limit alone gives
about 35 minutes for 450 calls).

**What is not done.** The pilot is not run. Resolved rate is not measured (no model edits, no grader). PASS_TO_PASS was
not checked. The model's own tokenizer is not used (the ratio is read from logged counts). Free-tier terms on the use
of submitted content were not read. Dev instances were not checked for execution. The decision, flip experiment and
open points are in `docs/RQ3_PILOT.md` (D104).

## E-RQ3-EXEC: the executable subset of SWE-bench Verified for RQ3. Measured, stated 2026-11-06, frozen 2026-11-07 (decision D106)

Status: measurement of the apparatus, not an RQ3 result; no retriever's patch was evaluated. Evidence class: measured. Code:
`ril/evaluation/executor/` (new, lead-owned; tests `tests/unit/test_executor.py`), `scripts/rq3_exec.py`,
`scripts/ada/rq3_exec/`. Outputs: `results/rq3_exec/` (README there). Rule and reading: `docs/RQ3_PILOT.md`, "Executable evaluation (D106)".

**Procedure, fixed before any retriever's patch was evaluated.** An instance is in the subset when, on the cluster
without root and without a container, (1) its environment builds from the benchmark's specification (version 4.1.0 of the
install specifications, read from the unpacked sources, parquet SHA-256 `a45b1fe4...`; no `apt-get` step), (2) the gold
patch applied to the base commit makes every FAIL_TO_PASS test pass and every PASS_TO_PASS test pass, and (3) two
repeated runs (independent environments from the shared package cache) agree on every named test. Instances needing an
older Python were tried with `uv` and then with a node-local interpreter from conda-forge (micromamba).

**Result.** 500 instances, 429 built in both runs, **377 executable** (75.4%): 375 under the `latest` policy and 2 under
the `era` policy. By repository (instances, built, executable): astropy 22, 16, 15; django 231, 229, 228; matplotlib 34,
0, 0; seaborn 2, 2, 2; flask 1, 1, 1; requests 8, 8, 4; xarray 22, 22, 18; pylint 10, 9, 4; pytest 19, 19, 19;
scikit-learn 32, 6, 0; sphinx 44, 42, 11; sympy 75, 75, 75. Exclusions (123): 38 need `apt-get` (matplotlib 34,
django 2, sphinx 2); 28 failed to build the environment on a compiled install (scikit-learn 25, astropy 2, pylint 1);
11 package installs failed (scikit-learn 7, astropy 4: pins without a wheel for the interpreter under pip); 28 sphinx
instances produced no test output (the test runner could not import its plugin; not resolved, see "Not done"); 18 gold
runs failed a test (7 FAIL_TO_PASS, 11 PASS_TO_PASS: pylint 5, requests 4, xarray 4, sphinx 3, astropy 1, django 1);
no instance was excluded for disagreeing runs. Tests that touch the network (requests) fail as PASS_TO_PASS.
Table by repository: `results/rq3_exec/repo_table.csv`.

**Older Python (a request of the engineer after the first full run).** `conda.anaconda.org` is reachable from a compute
node (recorded in `docs/COMPUTE.md`); micromamba (2.10.0) installs Python 3.6 in 51 s and 3.7 in 14 s, node-local, without
root. Of the 140 instances that needed Python older than 3.8, **111 are now executable** (django 111 of 111; astropy 0 of 4,
scikit-learn 0 of 25: compiled builds fail), 29 stay excluded with their reasons (`older_python_recovery.csv`).

**Environment departures, recorded per instance in the subset file.** pytest pinned below 8 where unpinned (6 members);
a build constraint `setuptools<=70.0.0` on every install (current setuptools has no `pkg_resources`); conda package
strings and conda environment files read as pip requirements (79 and 18 members), conda-only packages dropped when not on PyPI
(for example `matplotlib-base`, `dask-core`); `tox`, `tox-current-env` and, for sphinx, `roman` installed where the
specification's environment supplied them another way (10 members); a retry of an editable install without PEP 517 when the
pinned build backend lacks the hook; Python 3.6 from conda-forge (111 members). The era policy (unpinned packages as of the
instance's creation date, `uv --exclude-newer`, `pip --uploaded-prior-to`; specification pins undated) was run on the 95
instances that still failed after the supplements: 2 qualified (sphinx-8120, sphinx-8269), 93 did not. It is recorded as
a measured lever with small yield.

**Cost.** One instance, one run, one worker, shared nodes (three workers per job), warm shared package cache from the
second environment onward: run 1 p50 17.8 s, p95 197.6 s, p99 250.8 s (sum 4.04 h for 377); run 2 p50 17.1 s, p95 142.2 s,
p99 357.0 s (sum 3.66 h); peak resident size of any step p50 124.5 MB, p95 299.3 MB, p99 443.5 MB
(`cost_per_instance.json`). **Estimated cost of evaluating one model patch: one run**, so about 17 s at the median and 140
to 200 s at p95, and 3.7 to 4.0 CPU-hours for one pass over all 377 (a model patch skips nothing the gold run does:
environment, patch, re-install, tests). The first instance of each environment on a node pays the package download.
Time by phase over all runs (seconds): install 8,514, tests 7,907, re-install 7,113, packages 1,484, checkout 1,106.

**Subset against the 500** (`subset_vs_500.csv`). Django is 60.5% of the subset against 46.2% of the 500; sympy 19.9%
against 15.0%; matplotlib and scikit-learn are absent; sphinx 2.9% against 8.8%; requests 1.1% against 1.6%. Difficulty
(the dataset's field): under 15 min 36.9% (38.8% of the 500), 15 min to 1 hour 52.8% (52.2%), 1 to 4 hours 9.8% (8.4%),
over 4 hours 0.5% (0.6%). L2 labels: 320 of 377 (84.9%; 86.4% of the 500); L3 labels: 224 of 377 (59.4%; 60.4%). A result
on the subset does not carry to the excluded instances, and two repositories are absent.

**Part 4, reported without choosing.** Executable instances with L2 labels 320, with L3 labels 224; with stored unit
records 36 (L2 and units 36, L3 and units 22): astropy 15, xarray 14, requests 4, seaborn 2, flask 1. **Repositories with
executable instances and no stored unit records: django 228, sympy 75, pytest 19, sphinx 11, pylint 4.** Building them at
the measured rates of the eight-repository build (E-EVAL-REPOS-BUILD: CPU seconds per snapshot per 1,000 units, distinct
text share, 109 texts/s overall), with units per snapshot measured at one base commit each (django 33,531, sympy 38,280,
pylint 8,965, sphinx 7,120, pytest 4,452; job 62850): CPU 3.8 to 9.1 hours (median 6.4), GPU 0.5 to 10.3 hours per
checkpoint (median 5.0), django and sympy making up nearly all of it (`unit_build_estimate.csv`). The range is wide
because the eight repositories' distinct-text share spans 0.02 to 0.38 and the Verified instances of a repository are
spread over years; one snapshot per repository is the unit count. Estimate, not measurement: no unit record was built.
Power at N = 377 (`power_at_n.csv`, `ril/analysis/rq3_power.py`, exact McNemar, power 0.8, alpha 0.05): minimum
detectable difference 4.75 / 5.75 / 6.75 / 8.25 points at discordance 10 / 15 / 20 / 30%. The discordance values are the
module's placeholders (no agent pilot has measured one) and run-to-run noise of the agent is not in the model; N is the
number of instances, not instance-runs.

**Jobs and dead ends** (ledger rows in `results/logs/ada_jobs.csv`, session RQ3X; account A; no GPU). Pilot jobs 61964,
61978, 61989 (25 instances over all 12 repositories, then two re-checks; the first three submissions 61941, 61944, 61949
were cancelled or failed on my script errors: a log path, an ids path, no failure logs). Full run 61997 (8 shards of 62 or
63 instances, 4 array tasks, 2 runs each; the first submission 61991 was cancelled because a 12 GB request occupied 6 of
the 10 CPUs). Supplements: 62365 (xarray name fix and conda-forge interpreters, 162 instances), 62696 and 62763 (sphinx),
era pass 62777 (62599 and 62600 were cancelled: a missing policy flag in the job script, then the tox plugin). Dead ends kept
as rows but not used: run directories `full_y` (sphinx clone failures), `era3` (stopped: `roman` missing); `full_z` is
superseded by `full_s` for the same instances. Bugs found by the pilot and fixed in the executor (each recorded as a
departure when it changes the environment): inline comments in requirements (`uv` rejects them), `pkg_resources` missing,
conda `iris` is a placeholder package on PyPI, `build_editable` hook missing, `tox-current-env` missing, `roman` missing,
GitHub clone resets (retries over HTTP/1.1). A cancelled job leaves its node-local directory behind: the list is in a numbered
cleanup script handed to the engineer (not run: deletions on the cluster stay with the engineer). `ssh ada` (gateway 1) refused, then rejected the key,
during the era pass; the second gateway with the same account worked (`-o HostName=ada-gw2.iiit.ac.in`), nothing was changed.

**Not done / limits.** The code version of the runs is the base commit of this branch plus the uncommitted worktree (the
meta file of each run says so); the final commit is the merge. The three configuration hashes in the subset file are the
three executor states of the run directories (`latest` runs before and after the supplements, `era`). Sphinx: 28 instances
fail at test start and are excluded rather than chased (time-box set by the engineer). The test-output readers follow the
benchmark's formats and were exercised only on these runs. The two runs of an instance share the shared package cache and
the repository mirror, so they are not independent of an upstream change between them. Instances evaluated under the `era`
policy must be evaluated under it for any model patch (the policy is a field of each member). Nothing here says whether
an agent's patch will behave like the gold patch.
**Update 2026-11-06 (second session): merge, terms of use, egress, start of the pilot run.**
- *Merge.* `b/rq3-pilot` merged into `main` with a merge commit (no conflicts); `make lint`, `make test` (1,166 passed
  before the new tests), `check_docs`, `trace_check --all` and `audit_history` clean.
- *Terms of use* (read on the provider's terms page 2026-11-06): submitted content may be used by the provider and read
  by reviewers; decision: public repository text only, enforced by `ril/agent/providers/screen.py` at `prepare` and `run`
  (`tests/unit/test_providers_screen.py`). The 200 prompts hold no home path and no credential-shaped string; they hold 16
  distinct e-mail addresses (project contacts, author lines, placeholders), reviewed and kept as SHA-256 digests in
  `configs/agent/prompt_email_digests.txt`. Departure from the literal brief (reject any address): rejecting all would
  refuse every prompt of two repositories, and stripping addresses would change the prompt bytes against the assembly
  hash; the reviewed list is the tactical reading.
- *Egress.* The model API host answers from a compute node (403 without a key, job 61929); the pilot still runs on the
  engineer's machine because the key is not copied.
- *Run.* Prepared prompts copied to `~/ril_rq3_pilot/` (202 files, checksums equal); real run started 14:31 UTC, detached.
  First ten minutes: 133 calls, no 429 or 5xx, first-reply unusable share 24 to 35%; details and the resume line in
  `docs/RQ3_PILOT.md` ("Run in progress"). The run is not complete; no result is claimed.

## E-RQ3-UNITS: unit records, BM25 scores and encoding cost for the executable subset of Verified. Build only, stated 2026-11-07 (decision D107), done 2026-11-07

Status: **build, not an evaluation.** No retrieval result was computed or read and no agent was called. Evidence class: measured (counts, seconds, GPU time); the rule below is reasoned and was fixed before the count existed. Outputs: `results/rq3_units/` (README there). Code: `ril/evaluation/rq3_units.py`, `scripts/rq3_units.py`, `scripts/ada/rq3_units_{cpu,encode,score}.sbatch`, `configs/experiments/rq3_units_v1.yaml` and `rq3_units_v1_xarray.yaml`, test `tests/unit/test_rq3_units.py`; one backwards-compatible option in `e3_prepare.prepare_instance` (`score_without_gold`, default off, so earlier caches and hashes are unchanged).

**Decision D107** (reasoned; flip experiment: the measured counts below, which were run before the encoding). (1) Scope: all 377 members of `executable_instances_v1.json`, subset unchanged; the 36 with stored unit records and dense scores are re-used, the other 341 are built (django, sympy, pytest, sphinx, pylint: 337; four xarray instances without L2 labels that no earlier build covered: 4). (2) Same parser, unit definition (class form `full`), BM25 settings (k1 1.5, b 0.75), graph build and ambiguity policy as E-GRAPH-SIGNAL and E-EVAL-REPOS-BUILD; no new option. (3) Encoding de-duplicated by text hash within a repository, once per encoder at one cut; the cost is read from the distinct count and the measured rate. (4) Rule fixed before the run: encode with the untrained base encoder (CodeRankEmbed, 512 tokens, float16) only if the distinct-text count implies at most 6.0 GPU-hours at 109 texts per second (the eight-repository build's measured rate; at 178 or 229 the figure would be lower); otherwise report the count and the options and choose nothing. The 6.0 is Block 4 of the project ledger (`docs/COMPUTE.md`), not a cluster limit. (5) No retrieval result is evaluated; gold readings are built only through the existing chunk-to-unit mapping, unchanged, and are not used for any selection.

**What was built (account A; jobs in `results/logs/ada_jobs.csv`, session RQ3U).** 341 instance caches in the layout of `e3_prepare` (units in sorted-id order, typed graph, BM25 scores of the issue text), unit records of the existing unit stage for the 284 instances with an L2 positive (202 of them also with L3), unit-text hashes per instance, de-duplicated text stores, issue-text stores (one per repository, level L2), vectors of every distinct text, and dense scores `dense_L2` per instance. Parsed: **341 of 341 instances, 0 failures** (clones, checkouts, parse, build). With the 36 re-used instances all 377 members now have unit records and BM25 scores; L2 labels 320 (284 built + 36), L3 labels 224 (202 + 22). Gold readings for the 284 and 202 were built with the existing mapping unchanged: 14,469 positive ranks re-computed inside the cache build agree with the unit-stage record (0 disagreements; this compares two computations on the same parse, not an independent check) and 0 gold ids fall outside the units. Issue text: for the 284 labelled instances the folder's L2 text equals the table's `problem_statement` (284 of 284 equal); the 57 unlabelled use the table's text (`l2_query_source` in each cache's meta).

**Counts (`distinct_counts_five.json`, `distinct_counts_xarray.json`).**

| Repository | Instances | Unit slots (all snapshots) | Distinct texts | Distinct share |
|---|---|---|---|---|
| django | 228 | 7,684,203 | 82,625 | 0.0108 |
| sympy | 75 | 2,522,569 | 92,406 | 0.0366 |
| pytest | 19 | 84,630 | 15,983 | 0.1889 |
| sphinx | 11 | 74,442 | 7,514 | 0.1009 |
| pylint | 4 | 30,928 | 15,757 | 0.5095 |
| xarray (second pass) | 4 | 19,096 | 6,689 | 0.3503 |
| All | 341 | 10,415,868 | 220,974 (sum of per-repository stores) | 0.0212 |

Over all snapshots of the five repositories, 10,396,772 unit slots hold 214,216 distinct texts (48.5 times fewer; the per-repository figures sum to 214,285 because 69 texts occur in two repositories and each repository has its own store). De-duplication is what makes the cost small: 228 django snapshots share almost all of their code. The screening estimate of `E-RQ3-EXEC` assumed distinct shares of 0.02 to 0.38 taken from the eight repositories; django and sympy are below that range.

**Rule applied.** Distinct texts to encode 214,285 (five repositories) imply 0.546 GPU-hours at 109 texts per second (0.334 at 178, 0.260 at 229) against the limit 6.0: **allowed**; the four xarray instances 6,689 texts, 0.017 GPU-hours: allowed. Both encodings ran.

**Measured against estimated.**

| Quantity | Estimated (`E-RQ3-EXEC`, `unit_build_estimate.csv`) | Measured |
|---|---|---|
| CPU hours, unit stage plus cache build, summed over instances (in-process seconds) | 3.8 to 9.1 (median 6.4) | 8.79 (django 4.92, sympy 3.73, the other four repositories under 0.15 together); the second parse for the text hashes, the clones (520 s) and idle time of four workers are not in the sum; job 62880 took 2 h 49 min wall on 4 workers |
| GPU hours per checkpoint | 0.5 to 10.3 (median 5.0) | 0.377 (job 63012, 21 min 47 s, 0.363; job 63024, 50 s, 0.014) |
| Encoding rate | 109 texts/s (rule), 178 or 229 elsewhere | 171 texts/s over the five unit stores (django 175, sympy 145, pytest 228, sphinx 232, pylint 369; xarray 182) at 512 tokens, float16, one RTX 2080 Ti, batch 64; peak GPU memory 1.43 GB; float16 against float32 minimum cosine 0.999998 |
| Peak resident size of one instance | about 1.4 GB per worker (extrapolated at 37 KB per unit) | at most 998 MB (sympy, 38k units); django at most 604 MB |

Reading (evidence: measured, one run each). The GPU figure is below the low end of the estimate because the distinct share was lower than assumed, not because the encoder was faster than budgeted (it was faster than 109 texts/s on this text mix, and the rate depends on the mix, as cfn-lint's 29 texts/s showed in E-EVAL-REPOS-BUILD). The CPU figure is at the top of the estimate's range. Unit counts per snapshot (median) were django 33,550, sympy 33,343, pytest 4,452, sphinx 6,805, pylint 6,719, against the probe's one-commit counts (33,531, 38,280, 4,452, 7,120, 8,965).

**Stored outputs.** Small tables and logs are under `results/rq3_units/` (`instances.csv` one row per built instance with seconds, peak resident size and label readings, the count files, the vector checks, the two encode logs, `manifest.csv` with path, size and SHA-256 of 1,352 cluster files). Caches, unit records, hashes, text stores (gzip), vectors and dense scores stay on account A under `~/ril_rq3u` (five repositories) and `~/ril_rq3u_x` (xarray), about 1.1 GB together (`$HOME` free 6.4 GB before, 5.3 GB after). The 36 re-used instances are in `~/ril_t1/work/e3_cache` (caches) and `~/ril_x2/dense/coderankembed__t512` (dense scores, three class-source forms, from E-DENSE-FUSION); their vectors were produced by the same encoder revision and cut.

**Jobs and dead ends.** Smoke 62874 (pylint, 4 instances, 1 min 12 s) before the full run; 62880 (337 instances); 63012 (GPU); 63022 (check and score); 63023 to 63025 (xarray). The first count of "36 re-used" left four executable xarray instances with no unit record (instances without an L2 label were never built by the earlier pipeline); I found them by listing the caches against the subset after the first pass and built them in a second pass with a separate configuration file (the first pass's configuration hash is unchanged). The `RIL_COMMIT` label of job 63023 reads `5d0ac2d`, a typing error: the code was commit `f690225`. Jobs 62874, 62880, 63012 and 63022 are labelled `e2b4b01`; later commits changed only job-script defaults (a work-directory variable and an instance filter). No node had a full disk; nothing was deleted on the cluster.

**Not done / limits.** No retrieval is evaluated, no context assembled, no agent called. Vectors exist for the untrained encoder at 512 tokens only (the dev pipeline also used 1024 for the 36 re-used instances); trained checkpoints need their own encoding pass and their cost is not in the 0.377. `dense_L3` does not exist (queries are encoded for level L2 only; L3 BM25 scores exist for the 202 instances with L3 labels). The RRF fusion and graph expansion are not run on these caches. The 36 re-used caches were built by the earlier pipeline version and were not rebuilt, so their per-instance cost is not in the figures above. A result on these instances does not carry to the 123 excluded ones (D106).

## E-RQ3-CONTEXTS: retrieved contexts of the 377 executable instances, by arm and budget. Build only, stated 2026-11-07 (decision D108), done 2026-11-07

Status: **build, not an evaluation.** No agent was called and nothing was selected from the coverage figures, which are descriptive. Evidence class: measured (counts, shares, hashes); the arm and budget choices are reasoned and were fixed before the run. Outputs: `results/rq3_contexts/`. Code: `ril/assembly/rq3_contexts.py`, `ril/analysis/rq3_contexts_tables.py`, `scripts/rq3_contexts.py`, `scripts/ada/rq3_contexts.sbatch`, `configs/experiments/rq3_contexts_v1.yaml`, test `tests/unit/test_rq3_contexts.py`.

**Decision D108** (reasoned; flip experiment: the coverage table below, which is read, not used to choose). (1) Arms that need no trained checkpoint: BM25; the untrained base encoder alone; RRF over both (k 100, 200 candidates, as in the dev measurement where RRF was above BM25 in all 16 cells). The builder takes each arm as a scorer plus the key of the dense scores it reads, so an arm for a trained checkpoint is one more entry, with no change to the assembly or the builder. (2) Budgets 8,000 (primary, as in the pilot of D104) and 16,000 (secondary), unit cap 1,000, assembly exactly as in `specs/assembly.md`; no new option. (3) All 377 instances get a context, labelled or not (the 57 without L2 labels included); coverage is computed on labelled instances only. (4) Token counts use the tokenizer of the pilot's prompts: the approximate tokenizer `approx-words-v1` with a ratio of 1.0 (D104; three smoke prompts, thin evidence; the model's own count is not available offline). (5) Contexts are deterministic and checked by a second build.

**Step 0.** (a) Mining on account C: jobs 61677, 61678, 61679 and 61681 FAILED, 61680 CANCELLED; no mining work was started here. (b) Query vectors: all 377 members have `dense_L2` (337 + 4 built in E-RQ3-UNITS, 36 from E-DENSE-FUSION), so a vector exists for every query; nothing was encoded and no GPU time was added to Block 4 (0.377 of 6.0 stays). The L2 text equals the table's `problem_statement` for 320 of 320 labelled instances, and the L3 text equals the L2 text for 224 of 224, so L3 reuses the same vectors: BM25 scores at L3 equal those at L2 for 223 of 223 instances that have both; stored `dense_L3` equals `dense_L2` for 20 of 21 (seaborn-3069 differs by at most 3.4e-4 on scores of scale 0.64, a half-precision effect of the earlier build; its top 200 hold the same units, the top 10 in the same order). Contexts use `dense_L2` throughout.

**Run (account A, job 63792, 1 h 50 min on 4 workers, CPU only).** 377 of 377 instances built, 0 failures: 377 x 3 arms x 2 budgets = 2,262 contexts. Dense scores are CodeRankEmbed at 512 tokens (the dev cells of E-ASSEMBLY used 1,024 for the 36 earlier instances). Summed in-process time 6.0 h (checkout, parse, 6 assemblies per arm set). Per-instance files (canonical JSON, gzip with a fixed header) stay on the cluster (`~/ril_rq3c/out/ctx`, 39 MB); the manifest of paths, sizes and SHA-256 is `results/rq3_contexts/rq3_contexts_manifest.csv`, the hash of every context is in `rq3_contexts_contexts.csv`.

**Coverage (descriptive; shares of instances, no interval).** File level uses reading `units_all` (the file of every found positive); denominators 320 (L2) and 224 (L3). Unit level uses `units_all_nomod` (D18 primary); denominators 316 (L2) and 224 (L3): the 284 and 202 of D107 are only the instances built there, the 36 earlier instances add their own readings (4 of the 320 have no unit-level gold without module units). "File" is the share with at least one gold file in the context, "unit" the share with at least one gold unit (file-level denominator).

| level | arm | file 8k | unit 8k | file 16k | unit 16k |
|---|---|---|---|---|---|
| L2 (320) | BM25 | 69.4 | 51.9 | 75.3 | 61.6 |
| L2 | dense | 73.4 | 59.7 | 79.7 | 65.9 |
| L2 | RRF | 80.3 | 64.1 | 85.3 | 70.3 |
| L3 (224) | BM25 | 92.0 | 87.9 | 96.0 | 92.9 |
| L3 | dense | 97.3 | 95.1 | 98.7 | 97.8 |
| L3 | RRF | 97.3 | 96.0 | 98.2 | 97.3 |

Share with no gold file in the context at L2 (320): BM25 30.6 / 24.7, dense 26.6 / 20.3, RRF 19.7 / 14.7 (8k / 16k). The unit-level view (316) with the dev definitions (mean share of gold files / of gold units / no gold file) is in `rq3_contexts_coverage.csv`. **Against dev (BM25, L2, 8k, E-ASSEMBLY):** dev 66.3 / 26.0 / 21.1 against 65.0 / 26.4 / 31.3 here; mean shares are level with dev, the share with no gold file is higher than dev's and equal to Verified-six's 31.3, so the subset looks no easier than dev on BM25 (one line, nothing inferred).

**Size (all 377).** Every context of every arm and budget is full: the walk left a candidate out for lack of room in 377 of 377 (100%), so the budget binds everywhere. Tokens p50 7,984 to 7,987 at 8,000 and 15,985 to 15,986 at 16,000 (min 7,931 and 15,917). Units p50 / p95 at 8,000: BM25 29 / 46, dense 40 / 64, RRF 33 / 53; at 16,000: 57 / 87, 81 / 123, 65 / 100. Files p50 / p95 at 8,000: 15 / 29, 18 / 40, 15 / 31; at 16,000: 26 / 53, 32 / 69, 27 / 58. Units cut by the cap: BM25 4.5%, dense 1.5%, RRF 2.8% (8,000; 16,000 within 0.3). Full table: `rq3_contexts_size.csv`.

**Determinism.** 30 instances (seeded draw, seed 0) were built a second time from the same inputs: 30 of 30 files byte-identical by SHA-256 (`determinism.json`). The test suite also checks equal bytes for equal inputs and an equal archive for equal records.

**Mac side.** The 8,000-token contexts of the three arms as one archive, `~/ril_rq3_contexts/rq3_contexts_b8000.tar.gz` (12.2 MB, 2,262 entries: `<arm>/<instance>.txt` and `.manifest.json`; SHA-256 beside it, checked after the copy). The pilot's directory was not touched.

**Not done / limits.** No trained-checkpoint arm (no encoding pass; its cost is its own and not in Block 4's 0.377); no 16,000-token archive on the Mac; tokens are approximate, so the budgets are not in the agent model's tokens (ratio 1.0 from three prompts); the dense scores of the 36 earlier instances were encoded in an earlier pipeline version at the same revision and cut (the stored arrays are the evidence); RRF k 100 was the dev setting for a 1,024-token encoder and is not re-tuned here; coverage shows what reaches the agent, not what the agent does with it; a result on these instances does not carry to the 123 excluded (D106).

## E-RQ3-PILOT-RESULT: what the finished RQ3 pilot says about cost, usable replies, the two first stages and run-to-run noise. Exploratory, analysis of stored data, 2026-11-07 (decision D109)

Status: **exploratory, outside the pre-registered RQ tables.** Evidence class: measured on 100 development instances, pilot only. Nothing was called and no cluster job was run; the inputs are the pilot's call log (565 rows), its hashed replies and its 200 prepared prompts, and the stored per-query assembly rows, joined to the prompts by the SHA-256 of the context (200 of 200 matched). No resolved rate exists for these instances (they have no executable environment; the executable subset of D106 is Verified). Outputs, inputs' hashes, command and seed: `results/rq3_pilot/analysis/` (README there). Code: `ril/analysis/rq3_pilot_analysis.py`, `scripts/rq3_pilot_analysis.py`, `tests/unit/test_rq3_pilot_analysis.py`. Intervals: Wilson for shares; paired percentile bootstrap over the 100 instances for differences, 10,000 resamples, seed 0 (both runs of an instance move together). A unit is (instance, first stage, run).

**Decision D109** (made before looking; `unusable` is exactly what `ril/agent/providers/patch_format.py` returns as a fault, plus the log's `blocked`; this analysis only refines it).
1. The flip criteria of D104 are read as written, with no reinterpretation after the data.
2. No selection on the pilot: D106's subset, D108's contexts and the budget stay as they are; any prompt or format change is a proposal tested later on a fresh draw of dev instances.
3. Fault classes come from the stored replies, the log's fault code, `finish_reason`, and a check of every stored SEARCH text against the excerpts of the stored prompt (no checkout). Where stored data cannot decide a class, it is said so.

**What ran.** 400 of 400 units final, 565 calls (449 on 2026-11-06, 116 on 2026-11-07, Pacific days), one model string (`gemini-3.5-flash-lite`), temperature 0, B = 8,000 approximate tokens, template `rq3-pilot-prompt/v1`; finish reasons STOP 559, MAX_TOKENS 5, MALFORMED_FUNCTION_CALL 1.

### 1. Cost per unit (analysis 1; `rq3_pilot_cost.csv`)

| first stage | units | calls / unit [interval over instances] | input tokens / unit | output tokens / unit | latency p50 / p95 / p99 (s) | 429 / 5xx / retries |
|---|---|---|---|---|---|---|
| BM25 | 200 | 1.52 [1.36, 1.69] | 13,598 | 896 | 2.41 / 6.77 / 10.86 | 0 / 3 / 3 |
| RRF | 200 | 1.31 [1.19, 1.44] | 11,660 | 969 | 2.76 / 8.26 / 11.49 | 0 / 0 / 0 |
| both | 400 | 1.41 [1.29, 1.54] (max 3) | 12,629 | 933 | 2.58 / 7.81 / 11.22 | 0 / 3 / 3 |

Per call: input 8,941 tokens, output 660. Per instance (its four units): 5.65 calls [5.17, 6.16]. Thought tokens: 0 in all 565 rows (the adapter counts thought tokens inside the output count; the field is recorded as 0, so crowding-out by thinking did not occur; five replies ran to the 4,096-token output limit in visible prose). Three 5xx answers (all BM25) were retried and succeeded; no non-200 final status. First-message input tokens: BM25 8,540 (min 7,838, max 13,422), RRF 8,529 (7,694, 13,548).

### Flip criteria of D104, as written

| criterion | number | verdict |
|---|---|---|
| calls per instance above 3 (read as per unit, as in the design text: 400 units, 400 to 1,200 calls) | 1.41 per unit, interval upper end 1.54; max 3 | **pass** |
| unusable-reply rate above one third (first reply) | 90 of 400 = 22.5% [18.7, 26.8] (BM25 26.5% [20.9, 33.0], RRF 18.5% [13.7, 24.5]); after follow-ups 51 of 400 = 12.8% [9.8, 16.4] (BM25 17.0%, RRF 8.5%) | **pass** |
| day cap hit before 100 units finished | the cap (450 of 500, margin 0.9) was hit on day one after 449 calls with 311 units final | **pass as written**; the wording is ambiguous: if "100 units" meant "all units", day one finished 311 of 400 and the criterion would fire (the dry run had planned 1 to 3 days, and 89 units needed day two) |

### 2. Format faults (analysis 2)

Unusable by first stage and run (units, first reply / after follow-ups): BM25 run 0: 26 / 16 of 100; run 1: 27 / 18 of 100. RRF run 0: 19 / 9; run 1: 18 / 8. Follow-ups: 90 first replies were unusable; the first re-ask gave a usable reply in 15 of 90 calls (16.7% [10.4, 25.7]), the second in 24 of 75 (32.0% [22.5, 43.2]). Rescued units: 39 of 90 (43.3% [33.6, 53.6]); not rescued: 51. The two re-asks cost 165 of the 565 calls (29%).

Fault classes of the 90 unusable first replies (classes in order of the rules in the code; `decline_prose` is a keyword reading, not a determination): reply is prose that says no edit can be given (e.g. "I cannot provide a valid SEARCH/REPLACE block from the provided excerpts.") 46; names a file that is not among the excerpts 15; other prose 9; edit-marker text inside prose with no `FILE:` line 5; empty SEARCH section 5; truncated at the output limit 4; unterminated block 2; empty text 2; malformed function call 1; path with a prefix variant of a shown path 1. **Prose or unseen-file replies are 70 of 90 first replies; strict format faults (empty search, unterminated, marker without file line, truncation, malformed call, empty text, prefix variant) are 20 of 400 units (5.0%).** After follow-ups, of the 51 unusable units: prose or unseen file 40 (BM25 28, RRF 12), empty text after a re-ask 8 (4 and 4), other format fault 3 (empty search 2, prefix variant 1): 3 of 400 units (0.75%). Rescue by class of the first reply (n small): truncated 4 of 4, empty search 4 of 5, prose declines 15 of 46 (32.6%), unseen file 6 of 15 (40.0%), markers without file line 1 of 5; rescue when a gold unit is in the context 22 of 30 (73.3%) against 17 of 60 (28.3%) when it is not. Not determinable from stored data: whether the `other_prose` replies are declines (keyword rule), and why a model returns an empty string after a re-ask (8 units, 19 follow-up calls).

**Edit text against the excerpts shown** (349 units with a usable final reply, 493 blocks): the SEARCH text is an exact substring of the excerpts in 415 blocks (84.2%) and of the named file's excerpts in 410; 28 more match only after collapsing whitespace; 64 of 349 units (18.3%; BM25 20.5%, RRF 16.4%) have at least one block whose SEARCH text is not in the excerpts. Units rescued by a follow-up: 91.3% of blocks exact against 83.5% on first-try units. This is the "edit refers to code not shown" class; it is a usable reply by the definition of the code, and whether such a block applies is the grader's decision (Q69).

### 3. Why BM25 is below RRF on usability (analysis 3, tested)

- **Size of the gap.** Unusable, BM25 minus RRF, paired by instance: first reply +8.0 points [-0.5, +16.5]; after follow-ups +8.5 [+1.0, +16.5].
- **(b) Discordance** on the same instance and run (200 pairs): first reply 29 BM25-only unusable, 13 RRF-only, 24 both, 134 neither; after follow-ups 26, 9, 8, 157. Exact McNemar p 0.020 and 0.006 treating the 200 pairs as independent (they are two runs of 100 instances, so these p-values are optimistic; the instance-clustered intervals above are the ones to use). 16 BM25 instances have no usable run against 7 for RRF; 4 instances have none of their four units usable.
- **(a) Strata** (gold in the unit's own context; unusable first / after follow-ups):

| stratum | BM25 | RRF |
|---|---|---|
| gold file in context | 16.7% / 8.0% (n 162) | 13.7% / 5.5% (n 182) |
| gold file not in context | 68.4% / 55.3% (n 38) | 66.7% / 38.9% (n 18) |
| gold unit in context | 10.3% / 3.7% (n 136) | 9.6% / 1.8% (n 166) |
| gold unit not in context | 60.9% / 45.3% (n 64) | 61.8% / 41.2% (n 34) |

 Gold absence is more frequent under BM25 (no gold file in the context: 19 of 100 instances against 9; no gold unit: 32 against 17). Standardising BM25's within-stratum rates to RRF's mix of strata shrinks the first-reply gap from 8.0 to 2.8 points (file strata; 65% of the gap) or 0.4 (unit strata; 95%), and the after-follow-up gap from 8.5 to 3.8 (56%) or 2.3 (73%); every interval of the standardised gap includes 0 (about ±7). Restricted to instances whose two contexts both hold a gold file (80 instances), the after-follow-up difference is +1.9 points [-4.4, +8.1]; both hold a gold unit (67): +2.2 [-3.0, +7.5].
- **(c) Size.** First-message input tokens 8,540 (BM25) against 8,529 (RRF); every context fills the budget (D108); files in the context 15.5 against 16.1; share of excerpt characters in paths containing "test" 33.5% against 40.3%. Size does not differ.
- **(d) Bytes beyond the context.** The text before the excerpts (template, issue) is byte-identical in 100 of 100 instances; issue hash, template version and budget are equal in 100 of 100; the contexts differ in 100 of 100; the follow-up message depends only on the fault code. Nothing but the context differs.
- **By repository** (units, final unusable, BM25 / RRF): haystack 28.0% / 8.0% (n 50 each), conan 30.4% / 21.7% (46), openlibrary 10.0% / 2.5% (40), streamlink 14.3% / 7.1% (14), qutebrowser 0% / 2.0% (50); gold file in context in the same order 80 / 96, 61 / 78, 80 / 90, 86 / 86, 100 / 100.

**What the data support:** usability tracks whether the code to be changed is in the context, in both arms and at both levels, and the arms differ in how often it is; most of the arm gap sits in that difference. **What they do not support:** that the arms differ in nothing else (the residual after standardising is 0.4 to 3.8 points with intervals of about ±7); a causal reading (gold presence is itself an outcome of the first stage, so stratifying on it describes a route, it does not estimate an effect); the reason behind a prose reply (keyword reading only).

### 4. Run-to-run agreement at temperature 0 (analysis 4; `rq3_pilot_run_to_run.csv`)

| | pairs | same first-reply text | same final reply text | same final usability | runs disagree on usability | same edits given both usable |
|---|---|---|---|---|---|---|
| BM25 | 100 | 64.0% | 62.0% | 98.0% | 2.0% (2 of 100) | 58.5% (48 of 82) |
| RRF | 100 | 63.0% | 64.0% | 97.0% | 3.0% (3 of 100) | 66.7% (60 of 90) |
| both | 200 | 63.5% [56.6, 69.9] | 63.0% [56.1, 69.4] | 97.5% [94.3, 98.9] | 2.5% [1.1, 5.7] | 62.8% [55.4, 69.7] (108 of 172) |

Temperature 0 does not give identical replies: two runs of the same prompt agree on the reply text in 63% of pairs and on the edits in 63% of usable pairs. Usability itself is stable (97.5%). A resolved-rate study inherits this: the two runs of one arm will often propose different patches; the resolved discordance between two runs of one arm is not measured here (nothing was graded).

### 5. Retrieval side: are the 100 representative? (analysis 5; descriptive, `rq3_pilot_retrieval.csv`)

Share of gold files in context (mean) / share of queries with no gold file, pilot (n 100) against dev matched queries (n 353, `units_all`), BM25: 66.0 / 19.0% [12, 27] against 63.3 / 21.0%; RRF: 75.1 / 9.0% [4, 15] against 70.0 / 13.9%. Unit level (`units_all_nomod`, mean share of gold units): pilot 29.3 / 34.6 against dev 26.0 / 29.6. The pilot is level with dev for BM25 and a little easier for RRF, inside the pilot's interval. **Against the 377 executable instances (D108, L2, 8,000)** the pilot is easier: no gold file in the context 19.0 / 9.0% (BM25 / RRF) against 30.6 / 19.7%; gold unit present 68 / 83 against 51.9 / 64.1%. Estimate, not a measurement: the pilot's within-stratum unusable shares reweighted to the executable subset's coverage give a first-reply unusable share of 32.5% (file strata) to 34.7% (unit strata) for BM25 and 24.2% to 28.4% for RRF, after follow-ups 22.5 to 23.7% and 12.1 to 15.9% (`rq3_pilot_extrapolation_executable.csv`). BM25 would then sit at the one-third line of D104 on the executable subset.

### 6. Cost of the full runs (analysis 6; all figures estimated from the measured rates; `rq3_pilot_cost_grids.csv`)

Per arm-run (377 instances): 533 calls [487, 581] (1.41 per unit times 377), 4.76 million input and 0.35 million output tokens. Requests per day, not tokens per minute, bind: at 13 requests a minute the tokens are 116,000 a minute against the effective limit of 225,000 (52%); at B = 16,000 (input about 17,000 tokens per call, estimate) 13 a minute would be about 220,000, just inside. Calendar days = calls divided by 450 (500 nominal) rounded up, intervals from the calls interval:

| arm-runs | calls | days at 450 a day | days at 500 |
|---|---|---|---|
| 1 | 533 | 2 | 2 (1 to 2) |
| 2 | 1,065 | 3 | 3 (2 to 3) |
| 3 | 1,598 | 4 | 4 (3 to 4) |
| 4 | 2,130 | 5 (5 to 6) | 5 (4 to 5) |
| 6 | 3,195 | 8 (7 to 8) | 7 (6 to 7) |

Grids: RAW against the untrained encoder (D80 fallback), 2 arms x 1 run 3 days, x 2 runs 5, x 3 runs 8; that fallback with BM25 and RRF reference arms (4 arms): x 1 run 5 days (5 to 6), x 2 runs 10 (9 to 11), x 3 runs 15 (13 to 16). Sensitivity (estimate): if the executable subset's higher unusable share (analysis 5) raises BM25's calls per unit to about 1.6 to 1.7, the totals rise by under 10%, which moves a grid by at most one day up to 8 arm-runs. Grading is separate: one pass over the 377 is 3.7 to 4.0 CPU-hours (D106, estimate), so 8 arm-runs is about 30 CPU-hours.

### 7. Power update (analysis 7; `rq3_pilot_power_context.csv`)

The pilot gives **no resolved-rate discordance**; nothing was graded. At n = 377 the placeholder table stays: minimum detectable difference 4.75 / 5.75 / 6.75 / 8.25 points at discordance 10 / 15 / 20 / 30%. Shown beside it as context, and **not the same quantity**: the pilot's paired discordance between BM25 and RRF on the same instance and run (200 pairs) is 17.5% for usability after follow-ups, 21.0% for usability of the first reply, 12.0% for a gold file in the context and 17.0% for a gold unit in the context. The placeholders are not replaced.

### Decisions

1. **The free tier remains workable for the RQ3 runs as designed.** All three criteria pass (1.41 calls per unit, 22.5% first-reply unusable, cap hit with 311 units final); 2 to 8 arm-runs need 3 to 8 days and the 4-arm fallback grid 5 to 15 days. Cautions: BM25's estimated first-reply share on the executable subset is at the one-third line; the limits and the model are not guaranteed over 5 to 15 days (re-read the limits and the model string at the start and the end, as the log records it per call). The paid fallback stays as ADR-008 declares it.
2. **The unusable replies do not damage the contrast as an artefact; no prompt, follow-up or model change is chosen.** 40 of 51 final failures are prose or unseen-file replies that follow the gold being absent (final unusable with a gold unit in context: BM25 3.7%, RRF 1.8%; without: 45.3%, 41.2%); strict format faults are 20 of 400 first replies and 3 of 400 finally. Candidates: (a) a prompt format change is not supported (format faults are 0.75% of units after follow-ups); (b) a different follow-up policy: the two re-asks rescue 43% of unusable units at 29% of the calls, mostly where the gold is present (73% against 28%); a third re-ask or a different message has no data behind it; (c) a different model: no cross-model data. Residual unexplained: 8 final failures with a gold unit shown and 8 empty replies after a re-ask: too few for a test; no test is proposed. If the engineer wants the cheapest test of whether declines are avoidable, it is one more run of the 100 dev instances' 90 first-unusable units with a changed re-ask message (about 90 to 180 calls, one day), a proposal only.
3. **Unusable replies count as failures in the resolved rate, identically for all arms** (a unit with no usable edit is unresolved; the same follow-up policy, parser and counting for every arm). In a pilot-style comparison this puts the usability gap (8.5 points [1.0, 16.5] after follow-ups) inside the BM25-to-RRF difference, which is right: the gap is mostly the first stage not showing the code (analysis 3). A resolved rate among usable replies is reported beside it, labelled as conditional on a post-first-stage outcome.

**Not known.** Resolved rate and its discordance (nothing graded; dev instances have no executable environment); whether SEARCH blocks that match only after whitespace squashing (28) or are absent from the excerpts (78 blocks, 64 units) apply to the repository (the rule of application is Q69); whether the executable-subset rates match the extrapolation; whether another model, prompt or budget behaves alike; why empty replies follow a re-ask; any comparison with trained-checkpoint arms (none exist as contexts).

**Dead ends.** None in the analysis itself; one decision was reversed before the numbers were final: the first draft of the repository table split Pro instance ids by their hash suffix and was corrected to the `owner__name` form (the corrected table is the stored one).

## E-RQ3-PATCHAPPLY: turning edit blocks into the executor's patch; apply rates of the pilot's stored edits; end-to-end check on gold-derived edits. Exploratory (apply rates) and apparatus validation, 2026-11-08 (decision D110)

Status: **exploratory for the apply rates (100 development instances, outside the pre-registered RQ tables); apparatus validation for the end-to-end check.** No model was called and no RQ3 run was made. Evidence class: apply rates measured on 100 dev instances (349 usable units, 493 blocks); pipeline check measured on gold-derived edits of 20 executable instances. Code: `ril/agent/providers/patch_convert.py`, `ril/evaluation/gold_edits.py`, `ril/evaluation/patch_validation.py`, `ril/analysis/rq3_patch_apply.py`, `scripts/rq3_patch.py`, jobs `scripts/ada/rq3_patch/`; tests `tests/unit/test_patch_convert.py`, `test_gold_edits.py`, `test_patch_validation.py`, `test_rq3_patch_apply.py`. Outputs, commands, input hashes: `results/rq3_patch/` (README there).

**Decision D110** (reasoned; fixed before any model output is graded; same for every arm).
1. **Exact match is primary.** A block's SEARCH text must occur in its file as an exact string and exactly once (overlapping occurrences count); a file that does not exist at the base commit fails the block. An instance's edit set is atomic: any failing block means no patch, the instance is unresolved (no partial credit, no repair).
2. **Whitespace-tolerant is a labelled sensitivity**: line endings and trailing whitespace of every line normalised, blank lines at the start and end of the SEARCH text ignored, still exactly one match, replacement inserted as given; no fuzzy matching, no indentation repair, no edit-distance search. Reported beside the exact result wherever the resolved rate is.
3. One switch in the converter (`exact` or `tolerant`); never chosen per arm, instance or after results.
4. An unusable reply stays unresolved (D109); a block that fails to apply is an apply failure, reported separately, also unresolved.
5. **Tactical gap-fill (recorded, not a change of the rule):** blocks of one file are applied in the order of the reply, each to the file as the earlier blocks left it, so the failure classes stay the four of the decision (`file_missing`, `no_match`, `multiple_matches`, `parse`). A repeated block therefore fails (`no_match`), and a block may match text an earlier block produced. A first version matched every block against the base text and added an `overlap` class; it was dropped because it was stricter than the decision and needed a fifth class. Its effect is reported below as a sensitivity. Where a block's replacement is inserted into a file with CRLF line endings the inserted lines carry LF as given.

### 1. Apply rates of the pilot's stored edits (measurement 1; `rq3_patch_apply_*.csv`)

Inputs: the 349 usable units (final reply usable by the pilot's parser; 400 units = 100 dev instances x two first stages x two runs; call log and items hashes as in D109). Base-commit text of the 120 files the 349 units name was read with `git cat-file` from the repository caches of account A at the base commit recorded in the instance caches (job 64286, 120 of 120 present, 0 undecodable; no checkout, no clone). Nothing graded.

| first stage | units | usable | applied, non-empty diff | applied, empty diff (SEARCH equals REPLACE) | file_missing | no_match | multiple_matches | usable and applying (share of all units, Wilson interval) |
|---|---|---|---|---|---|---|---|---|
| BM25, exact | 200 | 166 | 122 | 7 | 0 | 37 | 0 | 129 (64.5% [57.7, 70.8]) |
| RRF, exact | 200 | 183 | 147 | 0 | 0 | 33 | 3 | 147 (73.5% [67.0, 79.1]) |
| both, exact | 400 | 349 | 269 | 7 | 0 | 70 | 3 | 276 (69.0% [64.3, 73.3]) |
| BM25, tolerant | 200 | 166 | 122 | 7 | 0 | 37 | 0 | 129 (64.5%) |
| RRF, tolerant | 200 | 183 | 147 | 0 | 0 | 33 | 3 | 147 (73.5%) |
| both, tolerant | 400 | 349 | 269 | 7 | 0 | 70 | 3 | 276 (69.0%) |

- **The tolerant reading rescues none of the 73 exact-failing units** (0 of 37 BM25, 0 of 36 RRF) and fails no unit that applies exactly. Whitespace is not what makes blocks fail here; D109's 28 blocks that match only after squashing all whitespace differ in indentation or line layout, which the tolerant reading deliberately does not repair.
- **Failing blocks, each on its own (493 blocks):** 396 apply with a change and 11 with none, 3 are `multiple_matches` (all RRF, text shown in the excerpts), 63 are `no_match` and quote text found nowhere in the named file (all 63 are also not in the excerpts shown), none is `file_missing`. Blocks whose text is in the file but not in the excerpts shown: 20, and all 20 apply exactly (the model recalled real code); failing blocks quoting text that is in the file but not in the excerpts: 0. So the 18% of usable units with a block outside the excerpts (D109) split into units that apply anyway and units whose block is invented text; the second group is the apply failures.
- **Effect on the usable counts.** Usable only, 166 (BM25) against 183 (RRF) of 200; usable and applying, 129 against 147: the gap between arms goes from 17 to 18 units (8.5 to 9.0 points of the units), the shares from 83.0 / 91.5% to 64.5 / 73.5%. Applying units are 78% of usable ones for BM25 (129 of 166) and 80% for RRF (147 of 183). Of the 276 applying units, 7 have an empty diff and cannot resolve anything (they leave the base code as it is).
- **Sensitivity to the in-order rule** (`rq3_patch_apply_rescue.csv`): under a stricter base-text rule (no two blocks of a file may overlap in the base text) 5 of the 276 applying units (BM25 2, RRF 3) would fail instead.
- Multi-block replies are common: 252 units have one block, 97 have two to six.

### 2. End-to-end check on gold-derived edits (measurement 2; `validation_gold_derived.csv`, `validation_draw.json`)

Draw: seed 0, 20 of the 377 executable instances, one instance for each of the six repositories with at least 5 executable instances (django, sympy, pytest, xarray, astropy, sphinx) chosen uniformly within the repository, the other 14 places uniformly from the remaining 371 (so by size); requests is drawn by size, pylint, seaborn and flask not at all; the draw was made once, not repeated. Result: django 9, xarray 3, sympy 3, pytest 2, astropy 1, requests 1, sphinx 1.

Derivation (`ril/evaluation/gold_edits.py`): one block per hunk of the gold patch; SEARCH is the hunk's base-side lines (the patch's context lines and the removed lines), REPLACE its result-side lines; if the SEARCH text is not unique in the file one line of context is added on each side until it is; creation, deletion and rename of a file, or a hunk that does not sit at the base text, is a derivation limit, reported, not worked around. The blocks are written in the pilot's reply format, read back with the pilot's own parser and converted with the exact reading, so the path tested is the path of a reply. Each converted patch was first compared with the gold patch by tree id (apply both to the base commit in a temporary index) and then applied by the executor at the base commit, tests run as in E-RQ3-EXEC, one run each.

| instance | hunks = blocks | converted | tree equals gold | executor | FAIL_TO_PASS | PASS_TO_PASS | executor seconds (gold-run mean) |
|---|---|---|---|---|---|---|---|
| astropy__astropy-14598 | 2 | yes | yes | resolved | 1 of 1 | 175 of 175 | 175 (240) |
| django__django-11734 | 3 | yes | yes | resolved | 1 of 1 | 275 of 275 | 27 |
| django__django-12308 | 1 | yes | yes | resolved | 2 of 2 | 20 of 20 | 11 |
| django__django-13568 | 1 | yes | yes | resolved | 1 of 1 | 13 of 13 | 8 |
| django__django-13569 | 1 | yes | yes | resolved | 1 of 1 | 66 of 66 | 8 |
| django__django-14011 | 3 | yes | yes | resolved | 17 of 17 | 2 of 2 | 78 |
| django__django-14404 | 1 | yes | yes | resolved | 2 of 2 | 323 of 323 | 55 |
| django__django-14725 | 5 | yes | yes | resolved | 3 of 3 | 64 of 64 | 148 |
| django__django-15503 | 6 | yes | yes | resolved | 2 of 2 | 78 of 78 | 111 |
| django__django-16136 | 1 | yes | yes | resolved | 2 of 2 | 7 of 7 | 13 |
| psf__requests-1142 | 1 | yes | yes | resolved | 1 of 1 | 5 of 5 | 60 |
| pydata__xarray-2905 | 1 | yes | yes | resolved (rerun, job 64304) | 1 of 1 | 364 of 364 | 345 |
| pydata__xarray-4966 | 1 | yes | yes | resolved (rerun, job 64304) | 4 of 4 | 21 of 21 | 323 |
| pydata__xarray-6721 | 1 | yes | yes | resolved | 1 of 1 | 1,405 of 1,405 | 972 |
| pytest-dev__pytest-10081 | 1 | yes | yes | resolved | 1 of 1 | 63 of 63 | 14 |
| pytest-dev__pytest-5631 | 1 | yes | yes | resolved | 1 of 1 | 15 of 15 | 15 |
| sphinx-doc__sphinx-7910 | 2 | yes | yes | resolved | 1 of 1 | 16 of 16 | 139 |
| sympy__sympy-12096 | 1 | yes | yes | resolved | 1 of 1 | 43 of 43 | 20 |
| sympy__sympy-14531 | 11 | yes | yes | resolved | 2 of 2 | 84 of 84 | 13 |
| sympy__sympy-23413 | 1 | yes | yes | resolved | 1 of 1 | 2 of 2 | 12 |

**20 of 20 converted, 20 of 20 trees identical to the gold patch's, 20 of 20 resolved** (FAIL_TO_PASS and PASS_TO_PASS all pass, as with the gold patch). No converter bug and no derivation limit appeared in this draw. The first execution of two xarray instances (2905, 4966) failed at environment creation after 6 s with a name-resolution error from the node (the package index could not be reached); that is infrastructure, not the patch: the same two converted patches were run again unchanged (job 64304) and resolved. Time column: executor wall time for the one run; the gold runs of E-RQ3-EXEC are in `results/rq3_exec/` (mean of two runs shown where the instance is slower than 100 s). Conversion itself takes about 0.2 s per instance; the conversion times in the derive job include a bare clone for the first instance of a repository and are not a conversion cost.

**What this does and does not show.** The pipeline (reply text, parser, converter, executor) reproduces the gold result on 20 instances, so a model reply that applies is graded the way the gold patch is. Gold-derived blocks are anchored by the patch's own context lines, which a model's blocks need not be; the 63 invented-text blocks of section 1 are exactly the case this cannot cover. Only exact reading was run through the executor (the tolerant reading is a different patch only when a block differs from the file in whitespace, which the pilot's data did not show).

### 3. Cost against expectation (measurement 3; `results/logs/ada_jobs.csv`, account A)

Expected before running: under 0.5 CPU-hours (20 instances, mean 38 s per run of E-RQ3-EXEC, peak memory under 450 MB at p99). Measured: validation job 64288 24.5 min wall, 4 allocated CPUs (1.6 allocated CPU-hours), rerun 64304 5.8 min (0.4), a cancelled first validation start 64287 1.7 min (0.1; cancelled because it had started with the first, stricter converter, see decision item 5), snapshot jobs 64285 and 64286 4 s each (64285 discarded: it derived the repository name of Pro-style instance ids wrongly and reported 59 of 120 files absent; the reader now fails when a repository or commit cannot be read, so a missing mirror cannot look like a missing file, and the mirror is found by name prefix). Total about 2.1 allocated CPU-hours, 4 jobs of use; the executor's own time summed over the 22 runs is 0.71 hours of 2 workers. The excess over the expectation is the bare clones (django, sympy, astropy: a few minutes), one slow instance (xarray-6721, 972 s, 1,405 PASS_TO_PASS tests) and the rerun. Local work: apply tables on the laptop, seconds. No GPU.

**Not known.** Resolved rate of any model patch (nothing graded; the dev instances have no executable environment); how the apply rates carry to the 377 executable instances (these are dev instances with an easier context mix, D109 section 5, and one model at one temperature); whether the invented-text blocks (63) would be repaired by any tolerant rule (the tolerant rule rescues none, a fuzzy rule was excluded by the decision and not tried); the tolerant reading through the executor (not run); how blocks written by a different model apply. Replacement text in CRLF files is untested against real instances (none of the 120 named files was checked for line endings in this entry).

**Remains before the first RQ3 model run.** (1) The model and scaffold decision (ADR-007, ADR-008) and Q45. (2) Contexts of trained checkpoints (blocked on the RQ2 final runs); the declared fallback is RAW against the untrained encoder. (3) A driver that, per unit, parses the reply, reads the 377 instances' base-commit files, converts (both readings from one stored reply set) and passes the patch to the executor; the pieces exist, the driver does not. (4) Prompts for the 377 executable instances (the pilot prepared 100 dev prompts). (5) The 28 sphinx test-start failures are outside the subset. (6) The cluster node-local DNS outage seen here argues for the executor's retry on a failed environment step (a re-run of the unit is the current remedy).

**Dead ends.** A first converter matched blocks against the base text and had an `overlap` class; it was replaced (decision item 5). A first snapshot job guessed repository names from the id and gave a false 59 absent files; fixed and rerun.

## E-RQ3-DRIVER: held-out model-check slice, prompts of the 377, the driver, analysis plan, power with run noise, cost model. Apparatus and plan, 2026-11-08 (decisions D111 to D114)

Status: **apparatus and plan; no model was called, no resolved rate exists.** Evidence class: reasoned for the decisions; measured for the replay test (30 of 30), the prompt counts and the screen findings; estimated (simulation) for power; tokens measured in the pilot and prices unverified for the cost. Code: `ril/agent/providers/{driver,holdout,spend,model_choice,rq3_prompts,replay_variants,cluster}.py` (and `run_unit` split out of `pilot_run.run_units`, `thinking_config` in `GeminiConfig`), `ril/analysis/{rq3_results,rq3_power_noise,rq3_cost}.py`, `scripts/rq3_driver.py`, jobs `scripts/ada/rq3_driver/` (`prepare`, `replay`, `model_check`), `configs/agent/prices.yaml`, `gemini_limits_paid.template.yaml`; tests `tests/unit/test_rq3_{holdout,driver,prompts_and_variants,results,driver_cli}.py`. Outputs and the full text of D111 to D114: `results/rq3_driver/`, `docs/RQ3_PILOT.md` ("Driver, held-out slice and analysis plan"). Jobs (account A, CPU only, `results/logs/ada_jobs.csv`, session RQ3D): 64589 (first prompt pass), 64597 (screen findings), 64598 (prompts), 64590 (replay).

**Why.** The free tier costs about two calendar days per arm-run (533 calls against 450 a day); the pilot left 276 of 400 units applying and 63 failing blocks quoting text found nowhere in the file, so a weak model may leave the resolved rate near zero, which no arm comparison can detect. The project needed the whole path as one tested driver, a set of executable instances kept back to choose the model on graded results, a fixed analysis plan that accounts for run noise, and a spend guard.

**Decisions.** D111 held-out slice (50 of 377, seed 0, stratified; django 30, sympy 10, astropy 2, pytest 2, sphinx 2, xarray 2, pylint 1, requests 1); D112 model-choice rule (cheapest candidate with a resolved rate of at least 15% on the slice, else the strongest with the floor reported as not met); D113 scaffold and analysis plan (ADR-007 Accepted `provisional`, Q45 answered: one primary contrast, RAW against the untrained encoder, paired bootstrap and sign-flip permutation on the 327, k = 3 if the spend allows else 2); D114 spend guard (cap required, worst-case check before each call). Full text in `docs/RQ3_PILOT.md`.

**Results.**
1. *Prompts.* 887 of 1,131 pass the screen, 244 rejected (135 address, 101 home path, 8 both); 109 instances have a rejected prompt, 57 have all three rejected; complete-case counts 232 of 327 confirmatory and 36 of 50 held-out; RRF sendable 258 and 39. 228 distinct unreviewed addresses or path strings; 111 of the 195 addresses look like a real address, 69 are placeholder domains, 14 are GitHub no-reply addresses (a mechanical suggestion, not a review). Text before the excerpts byte-identical across arms (320 of 320 with a prompt). Issue text from the table for all 377, equal to the folder text for 320 of 320.
2. *Replay (job 64590).* 20 of 20 gold-derived edit sets `resolved`; 4 of 4 altered SEARCH texts `apply_failed:no_match`, 3 of 3 ambiguous ones `apply_failed:multiple_matches`, 3 of 3 import-line `raise` variants `executed_unresolved`. 11 min 50 s on 4 allocated CPUs.
3. *Power with run noise.* Minimum detectable difference at power 0.8: 4.4 to 9.7 points at N = 327 across k = 1 to 3 and the scenarios (5.5 to 9.7 at k = 1, 4.4 to 7.7 at k = 3); 5.4 to over 10 at N = 232; size of the test 2.4 to 5.0%. Which inputs are assumptions: `rq3_power_run_noise_assumptions.json`.
4. *Cost (estimated).* One arm-run of 327: about 2.0 dollars on the cheapest candidate (3.8 high), 8.9 (15.7) on a Flash-class model at the stored unverified prices; the 50 held-out about 0.31 and 1.4; 3 arms x k = 3 about 18 and 80. Recommended cap for the graded check of the two priced candidates: 4 dollars in all (1 and 3 per run), provider hard cap 10 to leave room for a third candidate and a rerun.

**Dead ends.** (a) The first prompt pass (job 64589) took issue text from the query folders only and skipped the 57 instances without an L2 label (no folder text); the table's `problem_statement` is used for all 377 (equal to the folder text for the 320 that have both). (b) The pilot's `prepare_items` raises on the first screen finding; a whole run could not be prepared, so a variant that reports rejections was added. (c) An environment variable carrying the operator's address into the job was refused by the harness and is not used; the screen rejects any address not on the reviewed list, so the operator's address is rejected anyway.

**Not known.** Any resolved rate; whether the screen will be relaxed (Q70) and therefore the confirmatory N; the model; the price of a third candidate; whether a stronger model bills thought tokens (the pilot model billed none).

**Remains before the first confirmatory run.** The graded model check (engineer: billing, hard cap, key on the cluster, billed-tier limits, price check, Q70), the choice of k, trained-checkpoint contexts (blocked on RQ2), the 16,000-token prompts (optional, not run).

## E-LIT-SCAFFOLD: the five agent-scaffold papers read in full, scaffold compared with how they use it. Literature, 2026-11-08 (decision D116)

Status: **done; no model call, no cluster job.** Evidence class: read in full. Answers Q63.

**Why.** The standing rule makes a paper a source only after a full, versioned, checked reading. ADR-007 and the report rest on Agentless-style retrieval-supplied repair; the scaffold table of `docs/EVAL_API.md` names five papers.

**Papers (PDF fetched from the paper's own arXiv page, 2026-11-08).** Agentless v2 (25 pp), SWE-agent v3 (118 pp), OpenHands v3 (38 pp): new notes, `scripts/check_paper_note.py` PASS (page counts equal `pdfinfo`, 57, 69 and 19 numbers found on the stated pages). LocAgent v2 (18 pp) and CoSIL v3 (17 pp): notes from 2026-10-17 re-verified (PASS on freshly fetched PDFs, 56 and 69 numbers) and extended with a scaffold section from re-read passages, not a second full reading. None is unread.

**Findings.** (1) The scaffold shares the edit format and the retrieval/repair separation with Agentless; it has no sampling, no test selection and no follow-ups in the paper, and a different context shape (10 lines around locations against 8,000 tokens of ranked units). (2) SWE-agent and OpenHands cannot isolate the retriever (shell open); costs about 1.6 to 1.7 dollars per Lite instance. (3) Fixed-repair swaps in LocAgent and CoSIL give small resolved-rate gains (+1.6 Pass@1 for +15 Acc@5; 14 instances of 300 across four localizers against a ten-instance reproduction spread). (4) SWE-agent six runs: mean 17.94%, pass@6 32.67%, so at least 15.3 points of instances flip between runs (inference). (5) Contradictions with project text and between papers: listed in the ADR-007 addendum and each note.

**Dead ends / limits.** SWE-agent's trajectory pages (45 to 116) were read without the numbered source listings inside observations; the note carries the caveat and the header can be downgraded if the rule requires them. Agentless v1 and OpenHands/SWE-agent earlier versions were not read, so version drift (Agentless 27.3 in OpenHands against 32.00% in v2) is unexplained.

**Report slots fed** (`reports/final/final_report.tex`, not edited here): Related work, a new paragraph on agent scaffolds and the repair stage; RQ3 Design paragraph (scaffold wording, DEV-037); the Threats todo (scaffold sensitivity, model non-determinism).


## E-RQ2-READINESS: which stages between the mined store and the final RQ2 tables are missing, broken or unmeasured at full scale? Audit, dry run and plan, 2026-11-08 (decision D115)

Status: **audit and plan-only tooling; nothing trained, no GPU job, no model call; the running mining job was read, never changed.** Evidence class: measured (dry run, scheduler accounting, the running store's state log), projected (linear in a measured rate), reasoned (the rest). Product: `docs/RQ2_LAUNCH_PLAN.md` (chain, data-location options with calendar days, job graph, preflight list, gaps, decisions, next work packages). Outputs: `results/rq2_readiness/` (dry-run logs of job 64656, the evaluation-set check of job 64658, the partial yield, queue-wait summary). Code: `ril/training/config_io.py` (configuration loading and hashing moved out of the torch module, names re-exported, hash unchanged: six stored runs reproduce their directory prefix), `ril/training/rq2_plan.py` and `scripts/rq2_plan.py` (cell table, in-memory rendering and checks, budget on two bases, job graph, fresh-noise and distinct-example checks), `ril/evaluation/eval_plan.py` (store and cost check of evaluation sets), `ril/data_mining/state_yield.py` and `mine_pilot.py yield`, a one-line fix in `ril/data_mining/report.py`, `scripts/ada/rq2_readiness.sbatch`; tests `test_rq2_plan.py` (13), `test_eval_plan.py` (3), `test_state_yield.py` (2), `test_report_stored_summary.py` (1).

**Decision D115 (tactical, no design content).** (1) The plan uses the seeds 100, 101, 102 and refuses injected cells on seeds 0 to 2, because a noise draw is keyed on the run's seed (`noise.inject`) and D82 requires fresh draws; the count of three is O7. (2) Unit costs are kept as named constants with their evidence class, and the budget is shown on both the protocol basis (reasoned, reproduces 38.9) and the measured basis (28.7). (3) The mining yield is read from `state.jsonl` so that it works for a running or fault-stopped job. No cell, arm, teacher, metric or claim was changed; the choices that are the engineer's are listed in the plan, section 7.

**Dry run (job 64656, account A, CPU, 1 min 15 s, node-local scratch, 20 directories of the pilot store).** Materialise 13 s (921 MB peak), rank-prepare 7 s (18 `non_test` directories), BM25 ranks 6 s, feature table 1 s, held-out selection 1 s, cache 4 s, FILTER size 1 s (15 of 18 examples, 70 of 110 positives), overlap audit 24 s (0 dropped, 0 flagged at floor 20), plan-only launcher 0 s (36 runs, 36 distinct hashes), evaluation-set check 17 s. Every step returned 0 on current main. Not run: the report step on the pilot (the run root with its summary was removed after the store copy was verified; the tracked pilot summary renders after the fix).

**Measured.** Evaluation sets (job 64658): the eight repositories 69,961 distinct unit texts (equal to the build's number) and 224 queries; dev with ansible 212,834 texts, 680 queries; the six Verified folders with stores 114,503 texts, 734 queries; six Verified folders have no stores. Queue waits (scheduler accounting, 2026-10-20 to 2026-11-08, jobs over a minute): account A GPU 44 jobs, median 0.03 h, p90 2.75 h, maximum 8.25 h; account C one GPU job. Running mining job at 2,985 state rows (12:12 IST): 771 rows in 67.5 min since the relaunch; of 2,835 rows 62.6% mined, 1.2% quarantined; store 1.1 GB, projected 3.7 GB at 10,000.

**Findings.** The launch cannot start from what exists: no final cell configurations or run script (gap 1), one run cannot score three evaluation sets (2), no full-scale prep script or drop-list step (3), and the mined cache (5.6 GB projected) does not fit account A's 5.1 GB free (4). Unmeasured and large: a dense teacher over the mined store (upper bound 21 GPU-hours, gap 7). The 1,000-update sensitivity cannot reach the matched unique-example count on any mined store (gap 10). Six of twelve Verified folders have no stores (gap 8). The protocol's eight-repository cost (0.48 per checkpoint, reasoned) is 0.178 measured, so the measured-basis total is 28.7 of 46.7.

**Dead ends and surprises.** (a) The first evaluation-set check counted lines of the store shards (233,064 for the eight) instead of distinct texts (69,961); fixed and tested. (b) The login node's interpreter has no numpy, so the check runs in a job. (c) `report` could not be run on the pilot store at all (no summary file after the store conversion), which is why `yield` exists. (d) Writing the plan graph showed that injected-noise jobs need nothing from mining, which shortens the critical path by 11 hours in the split option.

**Not known.** The `non_test` and `pool_aligned` counts of the full store, the dense teacher's de-duplicated cost, the Verified look's real cost, whether account C's owner agrees to GPU work on it (the operating notes and the state page disagree on who owns it), memory at full scale beyond the projected 26 GB.

**Torch tests after the move (job 64669, account A, 23 s, no GPU).** The cluster's torch-marked set (hooks identity, retention in training, noise arms, loss, measurement, end-to-end training, run-batch, curve hook, training reproducibility, leakage) passes on the commit with the loader moved out of the training module: 41 passed. The local run (`make test` equivalent, no torch): 1,366 passed, 5 skipped.

## E-REPORT-DRAFT-1: the settled sections of the final report, drafted from stored evidence. Writing, 2026-11-08

Status: done. No cluster job, no model call, no GPU. Evidence class: nothing new is measured; every number of the prose is read from a stored file or an entry named in a comment beside it.

**What was written** (`reports/final/final_report.tex`, 13 pages two-column): Introduction (claim and non-claims, contributions), Background (retrieval for agents, evaluation levels, resolved rate), Related work (corrected sentence on the training corpus; the corpus paper's note says CodeRankEmbed was trained on it, not that the published pool builds on it), Data and ground truth (published pool and its limitation, held-out list and leakage controls, mined set and its two readings, overlap audit, label audit design, contamination), System with stated limits, Evaluation setup, RQ2 protocol with arms and noise design, RQ3 method (executable subset and skew, scaffold, edit rules, model-call pilot, analysis plan, power), Threats (T12 to T18 added), Reproducibility. Results appear only as the existing exploratory tables plus three new generated ones (`contamination`, `rq3_subset`, `rq3_power`, built by `ril/analysis/report_tables.py` from `results/`).

**Checks.** `scripts/check_report.py` (`ril/util/report_check.py`, tests `tests/unit/test_report_check.py`): every prose number is closed by a source comment, citations and references resolve, open slots are listed. Compiled with `tectonic`: 13 pages, no error, no undefined reference, no overfull box; underfull boxes come from float placement. The course's report limit is not in the repository; sections were kept tight and the page count is stated, not checked against a limit.

**Conflicts in the sources, later correction followed.** (1) The skeleton and the protocol say the noise-audit sample is stratified under each teacher; the built sheet is stratified by BM25 only (D99). (2) The skeleton says RQ3 uses McNemar over four retrievers and placeholder discordances; D113 fixes one primary contrast (RAW against the untrained encoder), paired bootstrap and sign-flip, and the run-noise power table. (3) The skeleton says the scaffold and model are open; the scaffold is accepted provisionally (ADR-007, D113). (4) The earlier count of 263 buildable instances is superseded by 377 executable (D106). (5) The 1.22 token ratio is against an embedding model's tokenizer; the agent model's own counts gave 1.00.

**Open slots (24) and what each waits for.** Abstract, contributions on contrasts, conclusion: E-RQ2-FILTER, E-RQ3-AGENT. Full mined set size, yield, surviving counts after the audit: E-MINE-FULL, E-OVERLAP-AUDIT. Audited noise rate and agreement: E-LABEL-AUDIT-SHEET. Edge recovery: E-GRAPH-BUILD. Latency table: E-LAT-STAGES. RQ1 ladder reading: E-RQ1-*. Stacked expansion: E-GRAPH-L3. Sibling noise: E-PILOT-NOISE-SIB. Confirmatory contrasts and exploratory arms: E-RQ2-FILTER, E-RQ2-RAW, E-RQ2-CTRL-SUBRAW, E-RQ2-WEIGHT, E-RQ2-CURRICULUM, E-RQ2-SEC-QQ. Evaluation of the eight repositories: E-EVAL-REPOS-BUILD. Agent runs, power from graded runs, agent threats, token budget: E-RQ3-AGENT, E-POWER. A missing citation for the benchmark's verified subset (no note exists); the related-work refresh.

**Not written for lack of evidence.** Any confirmatory contrast, resolved rate, noise rate, full-mined-set figures, RQ1 ladder, latency table, edge-recovery table.

**Dead ends.** None.

