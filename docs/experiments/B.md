# Experiments: stored-output analysis

Append-only log, entries by this workstream only. Rules, interpretation rules and the index of all entries are in
`docs/EXPERIMENTS.md`; the same rules apply here. Entry ids are unique across all experiment logs.

## Registry

| ID | RQ | What varies | Held fixed | Seeds | Primary outputs | Status |
|---|---|---|---|---|---|---|
| E-STORED-ANALYSIS | RQ2 (evidence) | nothing is trained or re-run: four readings of per-query rows already stored under `results/rq2/` | every stored run, query set, gold reading and metric as in E-PILOT-ARMS2 | none (no randomness except the bootstrap, seed 0) | variance components and minimum detectable differences; per-query gain by slice; per-query winner and best-of-arms oracle; per-query loss under injected noise | readings stated 2026-11-02 before any table; tables follow |

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

**Tables** (written before they were read; filled in below once produced).
