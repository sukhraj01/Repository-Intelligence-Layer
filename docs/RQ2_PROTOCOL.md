# RQ2 final-experiment protocol (draft for the lead's approval)

Drafted 2026-11-02. **Status: proposal.** Nothing here is decided and nothing has been run for it. Where the protocol needs a
choice, the options and their evidence are given and the item is marked **OPEN FOR THE LEAD**; a recommendation is marked
*recommendation* and is never a decision. The collected list is section 10. Python only.

Sources are cited by entry id and file. `EXP` = `docs/EXPERIMENTS.md`, `B` = `docs/experiments/B.md`, `ADR-0NN` =
`decisions/ADR-0NN-*.md`, `BRIEF` = `docs/ADR_DECISION_BRIEF.md`. Evidence classes: **measured** (a run in this project),
**read in full** (a note in `knowledge/papers/`), **reasoned** (arithmetic or argument, no new data). Every Wave 5 to 8 result
is exploratory by its own entry (dev repositories, one encoder, 100 updates unless stated): Wave 5 = E-PILOT-ARMS, Wave 6 =
E-PILOT-ARMS2, Wave 7 = E-PILOT-NOISE, Wave 8 = E-PILOT-NOISE-SIB. Wording that does not drift: RQ2 is about **matched optimization
budgets** (`docs/02_research_questions.md`).

## 1. Question and hypotheses

**Question (RQ2).** Under matched optimization budgets, how does the quality and composition of a retriever's training
supervision change repository-level retrieval?

**What the pilots now support (measured, exploratory).** On the published pool nothing separates from RAW beyond seed noise: no
FILTER, WEIGHT or CURRICULUM cell is above RAW at both levels, and the FILTER cells with the two stronger teachers are 1.07 to
1.10 below the size-matched subsample at L3 (Wave 6, EXP E-PILOT-ARMS2; Wave 5, E-PILOT-ARMS). When noise of a known kind is
injected at a known rate, RAW degrades (r = 0.4: -3.52 [-4.90, -1.55] L2, -1.86 [-2.71, -0.97] L3) and FILTER K = 20 recovers a
large part of it (three seeds: +1.82 / +1.19 with a BM25 teacher, +3.01 / +2.57 with SweRankEmbed-Small; shares of the
ORACLE-CLEAN recovery 0.68 / 0.40 and 1.13 / 0.87), WEIGHT less on L3 (Wave 7, E-PILOT-NOISE and its three-seed addendum). The
published pool looks pre-selected by one retriever (0 of 160 sampled directories lack a top-10 positive under SweRankEmbed-Small,
against 19.3% on never-filtered data; E-POOL-RANKS). Noise of the sibling kind (replacement from the same file) cost RAW about a
quarter as much and its pre-registered sanity check failed, so transfer from uniform to plausible noise is unanswered (Wave 8,
E-PILOT-NOISE-SIB).

**Hypotheses, in the form the evidence supports.**

- **H1 (main).** Supervision-quality methods help in proportion to the amount of findable, harmful noise in the training pairs.
  Where the pairs carry no such noise (the pre-selected public pool), no method is expected to beat RAW or the size-matched
  subsample; where they do, FILTER and WEIGHT are expected to recover part of what RAW loses. *Findable* means that a teacher's
  K-rank separates the noisy pairs from the clean ones (AUC well above 0.5); *harmful* means that RAW trained on them loses against RAW
  trained without them.
- **H1a (dose-response, injected noise).** The paired gain of FILTER over RAW, and its share of the ORACLE-CLEAN recovery, rise with
  the injected rate r in {0, 0.2, 0.4}. Evidence so far: FILTER with SweRankEmbed-Small, r = 0: -0.56 / +0.21 against RAW (Wave 6,
  two seeds); r = 0.2: +1.55 / +1.67; r = 0.4: +3.01 / +2.57 (Wave 7; r = 0.2 has two seeds).
- **H1b (real labels).** On an unfiltered set of pull-request pairs, FILTER's gain over RAW is predicted by the audited noise rate
  of that set and the dose-response curve of H1a (section 7). If the audit cannot be done, H1b is not tested (section 7).
- **H2 (quality beyond quantity).** A method beats RAW *and* the size-matched random subsample of RAW (RQ2 text,
  `docs/02_research_questions.md`; data-budget threat, `docs/08_experimental_design.md`). Beating RAW alone is reported but is not
  called quality.
- **H3 (arms).** FILTER, WEIGHT and CURRICULUM differ from one another. The pilots give no support for CURRICULUM (Wave 5: reversed
  order level with RAW; Wave 6: +0.87 L3 against RAW, below the minimum detectable difference), and WEIGHT's L3 gains are below the
  minimum detectable difference at every rate (Wave 7).

**Arms and controls.** Arms: RAW, FILTER (K-rank, SweRank's published signal), WEIGHT (the same signal as a soft weight), CURRICULUM
(easy to hard on the same signal). Controls: RAW on a size-matched random subset (`RAW_SUBSAMPLE`); ORACLE-CLEAN (RAW on the pairs
that were not injected; defined only where the injection ledger exists); NOISE (positives replaced by random functions of the same
repository; Wave 5: stays at the untrained encoder, so correct positives matter, but it carries no consistent signal and says nothing
about partly-correct labels). The reversed-order CURRICULUM from Wave 5 is a control for order, not an arm.

**Confirmatory and exploratory, proposed.**

| Part | Status | Why |
|---|---|---|
| FILTER (BM25 and SweRankEmbed-Small teachers) against RAW and against the size-matched subsample, on the mined set (primary) and on the injected-noise pool (calibration), final look on Verified | confirmatory | the pilots fixed the design and the decision rule (section 6) before the final runs; the effect sizes come from pilots whose own entries call them exploratory, so these are replications with new seeds, not a re-reading of old runs |
| H1a dose-response at r in {0, 0.2, 0.4} with at least three seeds at every rate | confirmatory | r = 0.2 has two seeds in Wave 7 and r = 0 was taken from Wave 6 |
| WEIGHT and CURRICULUM against RAW and the subsample | confirmatory-secondary: reported with the same rule, no claim is conditional on them | WEIGHT's gains sit below the minimum detectable difference; CURRICULUM has no positive evidence |
| H1b (prediction from the audited rate) | confirmatory only if the audit is done; else dropped | depends on section 7 |
| Everything in Waves 5 to 8 (all teachers, K, the teacher-equals-base cells, sibling noise, slices, complementarity, the learning curve) | exploratory, labelled so wherever it appears | stated as such by their own entries; none enters the pre-registered tables |
| Quantity-quality tradeoff and positive-versus-negative quality (`docs/08_experimental_design.md`, secondary and ablation) | exploratory, only if the core completes | the design document makes them conditional on the core |

*OPEN FOR THE LEAD: O2 (which comparisons are confirmatory).*

## 2. Data

**Unfiltered PR-mined set (workstream C2, E-MINE-PILOT in `B`).** Built from scratch from the repositories of the 5,000-directory
population (D60), linking merged pull requests to closing issues through the platform's closing-issue references (D61), with the issue
title and body as the query (D62), positives = the innermost units of the base commit that own an edited line (D63, DEV-015), no
retriever involved anywhere in the selection. **State at the time of writing: code and 85 offline tests on hand-built inputs; no
number measured; the live stages M1 to M4 wait for the read-only token on the cluster (D2).** Without the token the job stops before
any call (`B`, "Blocker"). Until the pilot has run, the set's size, yield and agreement with the published pool are unknown, and so is
whether the protocol below can be run on it. The decision rules for scaling after the pilot, in the order they are checked:

| Gate | What the pilot must show before the full mining run | Source | Threshold |
|---|---|---|---|
| G1 agreement (M1) | for pull requests in both the pilot and the published pool: positive-set agreement (exact share, mean Jaccard) in both readings, every disagreement outside the two expected kinds (extras in test files, class and module positives in the side table) listed with examples, 20 pull requests hand-checked | `B`, question 1 | no unexplained class of disagreement; a low agreement is reported as a difference of constructions, not as an error of either |
| G2 yield (M2) | quarantined share by reason, pull requests with at least one positive, positives per pull request, parse-failure share by cause | `B`, question 2 | **OPEN (O10):** numerical limits are not set in `B` (it is descriptive); *recommendation* in section 10 |
| G3 selection (M2) | what the published pool kept versus dropped among the same linked pull requests, with repository-clustered intervals | `B`, question 3 | the pool "selected for" a property only if the interval of the difference excludes 0 |
| G4 rank comparison (M3, GPU, limit 2 GPU-hours) | share of directories with no top-10 positive under BM25, CodeRankEmbed and SweRankEmbed-Small next to the pool's (23.2%, 15.3%, 1.7%) and the never-filtered Verified export's (SweRankEmbed-Small 19.3%, CodeRankEmbed 35.7%); counts only with at least 100 pilot directories that have a positive, else "too small to compare" with the pull requests needed at the measured yield | `B`, question 4; E-POOL-RANKS | the rule of `B` (intervals of both sets exclude each other's point estimate); if the mined set's share matches the pool's, the pool is not pre-selected and the published pool alone suffices (BRIEF, ADR-001, item 5) |
| G5 scale cost (M4) | linear extrapolation of API calls, wall time and bytes to 2,000 repositories and to 20,000 and 100,000 pull requests against the rate and disk limits | `B`, question 5 | the pairs obtainable must cover the final update count: **32 x N distinct pairs** for N updates at batch 32 to avoid repeats (3,232 at N = 100, about 32,000 at N = 1,000), divided by the share FILTER keeps (BM25 keeps about 83% of clean pairs at K = 20: E-PILOT-NOISE, N0) |

If G1 fails in a way that cannot be explained, or G4 shows the mined set is as pre-selected as the pool, the unfiltered-set arm of the
experiment is dropped and the injected-noise pool is the only noise condition (section 8, threat 1). The content-overlap audit of the
mined corpora against the held-out corpora is **not built** (D65 in `B`); it is a precondition for training on the mined set and is
listed in section 10.

**Published pool, as the comparison population.** `gangiswag/train_data` Python minus the held-out list (`provisional: ADR-001`;
D22, D29): 24,285 directories (one pull request each) and 307,996 positive rows, not the 49,973 instances of the SweRank+ table (E-POOL-CHECK; Q7 open).
The experiments use the first 5,000 directories outside the held-out list in the order `sha256("0:<directory>")`: 62,238 positives, 0
held-out (E-PILOT-ARMS2). Its limitation is stated and accepted (D29): directories look selected with respect to SweRankEmbed-Small,
positives inside them are not filtered one by one (39.4% [24.1, 48.0] lie outside that teacher's top 40; E-POOL-RANKS).

**Injected-noise sets, the calibration.** Same 5,000 directories; for each pair independently with probability r the positives are
replaced by the same number of non-positive functions of the same snapshot (uniform kind, Wave 7: r in {0.2, 0.4}) or of the same file
(sibling kind, Wave 8: r = 0.4); the true positives are masked; the indicator is stored in a ledger that only ORACLE-CLEAN and the
size-matched subsample's size read (E-PILOT-NOISE design, E-PILOT-NOISE-SIB design). Separation of the teachers, measured (pair level, minimum
rank over the pair's positives): AUC 0.83 to 0.84 (BM25) and 0.97 to 0.98 (SweRankEmbed-Small) for uniform noise; 0.77 to 0.79 and 0.94 for sibling noise.
Injected noise is a proxy (section 8, threat 3). *Whether the final calibration reuses these exact realisations (same
seeds and ledger rule) or draws new ones is part of the design:* new draws with the same rule are *recommended*, so the confirmatory
runs share no realisation with the exploratory ones.

**Held-out filter.** Repository-level disjointness, not instance-level: the training pool shares no repository with CORE-Bench L2 and
L3 or SWE-bench Verified (rule in `specs/held_out_repos.md`; list schema 2: 605 core repositories, 169-repository Loc-Bench tier switched
on, current-name aliases). The mined set is filtered by exact names, current-name resolution and the content-overlap audit (D65). Every
count after the filter is reported (population counts at repository and directory level). The leakage tests (training pool and
evaluation repositories disjoint; no patch or gold text in any query; the quality-signal encoder is not the encoder being trained; no
evaluation data reachable from a training path) must pass before any final run. *Caveat (measured):* without the token the rename cache
holds 108 repositories, so every post-rename count is a lower bound; the final experiment should not start on that basis (open item O10).

## 3. Arms and fixed settings

Held identical across arms, unchanged from `docs/08_experimental_design.md` and `docs/09_architecture.md` except where noted: base
checkpoint, architecture, pooling, batch size, learning-rate schedule, warm-up, weight decay, temperature, maximum length, negative
policy, evaluation set and metric code, flat exact index, RRF fusion, context assembly byte-identical. **This document does not edit that
block.** Four places where the pilots depart from it or leave it open are in section 10 (O1, O14).

| Setting | Value in the pilots (measured basis) | Final protocol |
|---|---|---|
| Base encoder | CodeRankEmbed (D30, ADR-006); Qwen3-Embedding-0.6B cannot take one optimizer step on the reachable 11 GB cards (E-ENCODER-NUMBERS) | CodeRankEmbed; differs from the master's recommendation, no DEV entry yet (BRIEF, ADR-006) |
| Update count and schedule | 100 updates of a 3,000-update schedule (warm-up 7, linear decay; the rate at update 100 is about 97% of the peak), 1,000 updates in stage 2 of Wave 5 and 6 | **OPEN FOR THE LEAD (O1)** |
| Batch shape | 32 x (1+1), float16 autocast, gradient checkpointing, 512 tokens, learning rate 2e-5 (D31, DEV-013) | as pilots (smaller than the master's batch; DEV-013) |
| Negatives | one policy for all arms: random repository-local (D28 primary); teacher top-M is exploratory (DEV-012) | as pilots; the master's arm table lists mined hard negatives for FILTER, WEIGHT and CURRICULUM, which DEV-012 replaced (O14) |
| Positive-side K and level | K = 20, positive level in Waves 5 to 7 (E-PILOT-ARMS, E-PILOT-NOISE config); the separation gate is reported at pair level | K = 20, positive level, unless the lead chooses otherwise (O3) |
| Teachers | BM25; SweRankEmbed-Small; CodeRankEmbed (equal to the base) | see below |
| WEIGHT | power form, k = 20, floor 0.1 | as pilots |
| CURRICULUM | 4 quantile buckets, easy to hard; reversed order as the control | as pilots |
| Seeds | 2 (Waves 5 to 8), 3 at r = 0.4 | at least 3 per cell; the number is decided in section 5 (O7) |
| Pool order | seeded, same permutation for RAW and WEIGHT (same pool) | as pilots |

**K and teachers, with the caveat.** SweRank selected K = 20 among {5, 10, 20, 50, none} with one run per point and no seeds
(`knowledge/papers/swerank-2505.07849.md`, read in full); the project's own K sweep (K = 10, 20, 40 at 63 updates, E-PILOT-K, ADR-002)
shows no cell above RAW and K = 10 below it. K = 20 is therefore a published reference point, not a tuned value. **SweRankEmbed-Small
is the favoured teacher**: it shaped the published pool (0 of 160 directories lack a top-10 positive under it) and was trained on the
data family the pool comes from, so on the published pool and on injected noise its AUC and its FILTER gain are the upper end; every
conclusion states which teacher it rests on, and **BM25, which the pool's construction does not favour, is the teacher that carries
the primary claim**. On the *mined* set no teacher shaped the selection, but SweRankEmbed-Small's own training data comes from the same
repository family, so pretraining exposure remains (section 8). The CodeRankEmbed teacher is the base encoder itself; the master's rule
is a separately pretrained encoder, never the model being trained, and a self-teacher is the self-confirming case the design warns
about (`docs/08_experimental_design.md`, "Second warning"); the pilots ran those cells as exploratory. *Recommendation (O3):* the final
runs use BM25 and SweRankEmbed-Small only.

**Matching rule.** Equal optimizer updates **and** reported unique-example counts (D42; `docs/08_experimental_design.md`). Every
table row states optimizer updates, distinct examples seen, effective epochs, the pool it drew from and its size; a cell that cannot
reach the common distinct-example count without repeating examples is flagged and not silently included (measured instances: the
size-matched subsample and ORACLE-CLEAN at r = 0.4 saw 3,017 to 3,054 distinct examples for 3,232 draws, E-PILOT-NOISE). In the
pilots every cell trained on 3,200 example visits and saw 3,232 distinct examples (E-PILOT-ARMS2). At N updates the common count is
32 x N visits; at N = 1,000 the 5,000-directory pool is exhausted (6.4 passes for RAW, 7.0 for the subsample), so a 1,000-update
cell on that pool is below the common unique count by construction (E-PILOT-ARMS2, stage 2) and needs a larger pool, i.e. the mined set.
The subsample has one draw per seed in Wave 7; three draws were configured in Wave 6 and not run. The final design takes one new draw per
seed and reports the between-draw spread.

## 4. Evaluation

**Where choices are made.** Every choice (K, teacher, weight form, update count, evaluation reading) is made on the **development
repositories** only: five at L2 (Pro openlibrary and qutebrowser, Live conan, haystack, streamlink; 351 queries) and two at L3
(openlibrary, qutebrowser; 155 queries) (E-PILOT-ARMS2; dev set from `configs/experiments/e1_bm25_dev3.yaml`). Pro ansible (83 L3
queries) was added as a third dev L3 repository (D32, E-DEV-ANSIBLE) and left out of Waves 5 to 8 because its 274k unit texts cost
about 0.33 GPU-hours per checkpoint. **SWE-bench Verified is the final test and is looked at exactly once**: after the protocol, the cell
list and the decision rules are registered and the dev analysis is complete (ADR-005, D32). No Verified number is computed before that, and
none is recomputed after it; if a Verified evaluation must be redone for a technical fault, the fault and the repeat are reported.
When the look takes place (same job as the dev evaluation or after the dev analysis) is O9.

**Levels, metric and reading.** L2 (file-and-function context needed to edit) and L3 (context beyond the edited files), unit-level
primary under D12 and D18, the reading `units_all_nomod`, dense column. L2 is nDCG@10; L3 is Recall@100 (the `metric` column of
every Wave 6 and Wave 7 table says `recall100` for L3 although the Wave 7 entry's text says "L3 nDCG@10 points"; the entry is
append-only and the tables are the source: **a recorded inconsistency, O4**). Chunk-level folder means, the reading that reproduces the
published BM25 rows (E-BM25-REPRO), are reported beside it where the evaluation set allows (ADR-004 recommendation).

**Number of repositories per level, and what it does to claims.**

| Set | L2 repositories (queries) | L3 repositories (queries) | Source |
|---|---|---|---|
| Development | 5 (351; six with ansible) | **2** (155; three with ansible, D32) | E-PILOT-ARMS2, D32 |
| Verified, final test | 12 folders (432 instances) | 12 folders (302 instances), very unequal: django 136, sympy 51, sphinx 26, scikit-learn 21, pytest 10, pylint 3, the six repositories with dense stores 55 in all | E-BM25-REPRO, E-L3-CENSUS |

The premise that L3 has few repositories with labels is exact for the dev set and the consequence is the same for every L3 claim made
on it: **with two clusters a repository-clustered interval is not estimable (three distinct resamples; it can be narrower than the
query-level one), so every dev L3 interval is query-level and carries query sampling only.** The repository term is reported beside it
and is large: the minimum detectable difference at three seeds is 1.02 at query level and 3.08 with the repository term (Wave 6,
E-STORED-ANALYSIS), 2.20 and 4.88 at r = 0.4 (Wave 7 three-seed addendum). A dev L3 difference therefore describes these queries in
these two repositories, not repositories in general; no dev L3 result alone supports a positive claim (section 6). On Verified the
L3 set has 12 repositories but django alone is 45% of the instances, so the effective number of clusters is lower than 12; the clustered
interval is reported with a leave-django-out sensitivity. Only six Verified repositories have unit-level records and dense stores built
(Verified-six: 83 L2 and 55 L3 queries); the other six have L3 positives mapped to units in the census (E-L3-CENSUS) but no dense
stores, and no unit records at L2 are stored here; building them, and their encoding cost per checkpoint (not measured for the trained-model path), is part of O9.

**Intervals.** Primary: mean over queries (D17) with 95% bootstrap intervals, 2,000 draws, seed 0; **repository-clustered where there
are at least three repositories (L2), query-level otherwise (dev L3)**, always with the other interval beside it; the repository
variance term is reported as in E-STORED-ANALYSIS. **Paired differences:** every contrast is the difference of two cells trained with
the same seed, on the same queries, per query; seed-to-seed spread is reported (per-cell values and the pooled seed SD), because the
bootstrap carries query and repository sampling and not retraining variance. If two cells overlap within one seed SD they are called
indistinguishable at this sample size (`docs/08_experimental_design.md`).

**Multiplicity across arms.** The pilots ran about 60 contrasts with no correction and the entries say so (ADR-002 addendum
2026-10-29). The final family is fixed in advance: the primary family is {FILTER-BM25, FILTER-SweRankEmbed-Small} against RAW and against the
subsample at each of two levels (8 contrasts); WEIGHT and CURRICULUM form a secondary family of 8. Options: (a) Holm step-down over each
family, on the interval level (adjusted intervals reported); (b) Bonferroni; (c) no correction, all contrasts reported with the family
size stated; (d) gatekeeping (secondary family tested only if the primary passes). *Recommendation (O5):* Holm within each family plus
the uncorrected intervals beside them, because the pilots showed that several "excludes 0" readings came from one low subsample draw
(Wave 7 addendum), and a correction would have caught exactly those.

## 5. Power

**What is known (measured, `B` E-STORED-ANALYSIS; Wave 6 cells, paired differences against RAW on the same queries, 5% two-sided, 80%
power).** Minimum detectable difference in points:

| seeds per arm | L2, with repository term | L2, query level | L3, with repository term | L3, query level |
|---|---|---|---|---|
| 2 | 1.99 [1.14, 2.99] | 1.32 [0.95, 2.71] | 3.15 [2.21, 4.73] | 1.23 [0.90, 2.39] |
| 3 | 1.85 [1.01, 2.56] | 1.10 [0.81, 2.23] | 3.08 [2.12, 4.59] | 1.02 [0.75, 1.96] |

Earlier entries: 1.4 (L2) and 1.7 (L3) at three seeds (E-PILOT-ARMS2: the larger of a seed bound and a query bound); with injected
noise at r = 0.4 and three seeds, 1.78 / 2.18 by that table method and 1.40 / 2.20 at query level and 2.16 / 4.88 with the repository
term by the variance-component method (E-PILOT-NOISE addendum). The two methods agree at query level; they disagree at L3 with the
repository term (three disagreements by the stated rule, all L3, E-STORED-ANALYSIS) because that term rests on two repositories. Seed
noise is a small part of a level's variance at L2 (2% seed, 1% seed-by-query, 85% repository, 12% query) and the largest identifiable part
after the query term at L3 (22%), while the repository term dominates absolute levels and cancels in a paired difference only
partly (the table above shows it does not at L3).

**What each design buys (reasoned from the stored variance components; the formula of E-STORED-ANALYSIS, which reproduces the table above
exactly).** The minimum detectable difference is 2.8016 x sqrt(s2_repo/R + s2_query/n + (s2_seedquery/n + s2_seed)/k) for R
repositories, n queries and k seeds. Seeds divide only the last bracket, which is small; repositories (with queries in proportion)
divide all three terms. With the pooled Wave 6 components and 70 (L2) or 78 (L3) queries per repository:

| design | L2, with repository term | L3, with repository term |
|---|---|---|
| the dev set as it is (R = 5 / 2), k = 3 | 1.85 | 3.08 |
| dev set, k = 5 | 1.73 | 3.0 (approx.) |
| dev set, k = infinity (the floor) | 1.54 | about 2.9 |
| R = 8, k = 3 | 1.54 | 1.64 |
| R = 12, k = 3 (the Verified repository count, equal queries per repository assumed) | 1.34 | 1.39 |
| R = 12, k = 5 | 1.22 | 1.32 |
| R = 20, k = 3 | 1.16 | 1.15 |

Reading, labelled *reasoned*: moving from three to five seeds lowers the L2 value by 0.12 and the L3 value by almost nothing, while
raising the repositories from five to eight or twelve lowers it by 0.3 to 0.5 (L2), and from two to eight or twelve by 1.4 to 1.7 (L3). **Seeds cannot buy a repository term; to reduce it,
repositories are needed**, and the dev set has five and two. Caveats: the components come from the clean pool at 100 updates and
two seeds, with one degree of freedom per cell pair for the seed term; the L3 repository variance is estimated from two repositories
(interval [2.12, 4.59]); queries per repository are assumed equal, which Verified is not (django is 45% of L3), so the effective R on
Verified is smaller than 12; noise conditions have larger components (Wave 7: 2.16 / 4.88 at r = 0.4, k = 3).

**Number of repositories and seeds for a target difference (reasoned).** For a target of 1.5 points with the repository term:

- L2: **dev alone does not reach it at any number of seeds** (floor 1.54 at R = 5); R = 8 reaches it at k = 3 (1.54) and R = 12 gives 1.34.
  The Verified set (12 L2 folders) is the first set that reaches it, at k = 3.
- L3: R = 8 and k = 3 give 1.64; R = 12 gives 1.39; two dev repositories give 3.08 at any k (query-level 1.02 describes those queries only).
- A target of 1.0 point needs about R = 20 at k = 5 at L2 (1.02) and R = 30 at k = 5 at L3 (0.92), more repositories than either the dev set or
  Verified has; the observed gaps between arms in Waves 5 and 6 (0.1 to 1.4) are mostly below 1.0, so a null at these designs is "no
  effect larger than about 1.5 points", not "no effect".

**Options and GPU-hours** at the measured cost of 0.38 to 0.45 GPU-hours per 100-update run (0.37 to 0.40 on most nodes: training
loop 4.5 min, evaluation of the five dev repositories, 316k unit texts, about 18 min; E-PILOT-ARMS2, E-PILOT-NOISE; 0.45 on the first node).
A 1,000-update run is 1.06 (E-PILOT-ARMS2). The calculation uses 0.40 per run; evaluation on more repositories adds about 0.06 GPU-hours
per repository per checkpoint at the dev repositories' mean size (reasoned from 0.30 for five), and Verified evaluation is added at a
placeholder of 0.4 per final run (measured only for Verified-six at 1,024 tokens through another code path, 0.43, job 38109; unmeasured
for all 12).

| Option | Cells x seeds | Runs | Training and dev evaluation | Final look on Verified (placeholder) | Total |
|---|---|---|---|---|---|
| A, mined set + calibration, 3 seeds | 12 cells (6 mined, 6 injected at r = 0.4) x 3 | 36 | 14.4 | 6 primary cells x 3 x 0.4 = 7.2 | 21.6 |
| B, A plus the clean published pool at r = 0 and r = 0.2 re-run | 24 cells x 3 | 72 | 28.8 | 7.2 | 36.0 |
| C, B at 5 seeds | 24 cells x 5 | 120 | 48.0 | 12.0 | 60.0 |
| D, A at 5 seeds | 12 cells x 5 | 60 | 24.0 | 12.0 | 36.0 |
| E, A at 3 seeds with 8 extra evaluation repositories per run | 12 x 3 | 36 | 36 x (0.40 + 8 x 0.06) = 31.7 | 7.2 | 38.9 |

Cells: mined set = RAW, subsample, FILTER-BM25, FILTER-SweRankEmbed-Small, WEIGHT, CURRICULUM; injected = RAW, ORACLE-CLEAN,
subsample matched to the oracle, FILTER-BM25, FILTER-SweRankEmbed-Small, WEIGHT. Teacher scoring of the mined set is on top: about 2.2
GPU-hours per 5,000 directories for the dense teacher (E-PILOT-NOISE, N0: 2.17 for both teachers' per-function scores of 5,000 directories), plus
M3's 2 GPU-hours limit; BM25 is CPU. None of the options fits under the remaining Block 2 allowance (3.19 of 66 GPU-hours, section 9), so
the final experiment needs its own authorisation (O12). *Recommendation (O7):* option A as the minimum with Verified as the repository-rich
confirmatory set, and a decision between D (seeds) and E (evaluation repositories) only after the mined set's yield is known; the arithmetic above
favours repositories over seeds, but the only repositories available beyond the dev set are the 12 Verified folders (final look once),
ansible, or further CORE-Bench L2 folders from other sub-datasets (632 L2 folders exist, E-BM25-REPRO; none beyond the five dev
and Verified has unit records here), which is a design choice (O8).

## 6. Decision rules, written before any final run

Applied per arm (each of FILTER-BM25, FILTER-SweRankEmbed-Small, WEIGHT, CURRICULUM) and per level, to the paired difference against RAW
and, separately, against the size-matched subsample, using the Holm-adjusted intervals of section 4 and the uncorrected ones beside them.
Let u be the upper end and l the lower end of the interval, and **delta** the smallest difference the lead would call worth reporting
(O6; *recommendation:* delta equal to the design's minimum detectable difference computed before the runs, about 1.5 to 2.0 points,
so that the "negative with a bound" statement has the same resolution as the test).

| Verdict | Rule |
|---|---|
| **Positive** | l > 0 at L2 (repository-clustered) **and** l > 0 at L3 (query level) on the final test (Verified), the same sign on dev at both levels, and the same rule holds against the subsample for the claim "quality beyond quantity". An interval that excludes 0 on one level only is "level-specific", not positive |
| **Negative, with a bound** | l <= 0 <= u (or u < 0) and u < delta on both levels: reported as "no gain larger than u points at this design"; if u < 0 with an interval excluding 0, the arm is reported as harmful at that level |
| **Inconclusive** | l <= 0 and u >= delta on either level: the design cannot separate the arm from RAW; the minimum detectable difference and the repositories and seeds that would are reported |

Further rules, fixed now:

1. **Sanity before reading.** For the injected-noise cells: RAW must degrade against the clean cell (interval excluding 0 at L2, query
   level at L3) and ORACLE-CLEAN must recover it; if not, the calibration is reported as not informative and nothing is read from it (the
   rule of E-PILOT-NOISE, D47 (i) and (ii), which failed once, in Wave 8).
2. **Dose-response (H1a).** Reported as the paired gain over RAW and the share of the ORACLE-CLEAN recovery at each r with three
   seeds; "rises with r" is claimed only if the gain at r = 0.4 exceeds the gain at r = 0.2 by more than the difference's own interval; otherwise "not
   separable at this design".
3. **L3 on dev** carries query sampling only (two repositories). It can confirm the sign of an L2 result or withhold it; it cannot make a
   positive. L3 on Verified uses the repository-clustered interval over its 12 folders and the leave-django-out sensitivity; if the two
   disagree in sign, the L3 verdict is inconclusive.
4. **Overlap within one seed SD** between any two cells is reported as indistinguishable at this sample size (`docs/08_experimental_design.md`).
5. **Mined set (H1b).** Reported per teacher, with the audited noise rate (section 7). If the mined set shows no gain for FILTER and
   the audit finds a low findable-noise share, the result is stated as consistent with H1 (nothing to filter); if the audit finds a high
   findable-noise share and FILTER does not gain, H1 is not supported on real labels, and that is reported as such.
6. **Nothing is reframed.** A null stays a null (`docs/EXPERIMENTS.md`, interpretation rules): if arms differ in retrieval but not in
   resolved rate, RQ3 reports the retrieval-versus-reasoning failure breakdown; a retrieval null at RQ2 is reported with its bound, never as an absence.
7. **RQ3 gate.** "Fewer than two distinguishable retrievers" (risk table in `PROJECT_STATE.md`, week-12 go/no-go) means: no pair of arms
   whose paired difference is positive by the rule above on both levels. What RQ3 uses in that case is O13.
8. Every number carries its label: `measured` with the run log, config hash, seed and hardware; `paper_reported` for literature values.
   Absolute levels are not capability claims; contamination inflates arms identically (ADR-005).

## 7. The noise audit

**What is estimated.** The share of the mined set's pairs that carry noise and of what kind: (a) wrong positive (an edited function that
does not answer the issue: incidental or refactoring edit, test helper, formatting), (b) missing positives (a function the issue is about that
the patch did not edit), (c) sibling (the edited function is a neighbour of the relevant one). Only (a) and (c) are harmful positives; (b) is
a false negative in the in-batch or repository-local negatives (the RLHN finding for text retrieval, `knowledge/papers/rlhn-2505.16967.md`, read in full:
false negatives in up to 56% of one dataset's training pairs and about 3% of another's, so no rate transfers across domains).

**What it is used for.** (i) To place the mined set on the dose-response curve of H1a (is the real rate near 0.2, 0.4, or far below);
(ii) to measure how much of it a K-rank filter can find (precision of the dropped pairs, share of noisy pairs dropped), which is what H1
calls *findable*; (iii) to decide whether the injected rates bracket reality and whether sibling-kind noise needs a stronger test (Wave 8
left it open: the RAW loss under sibling noise at r = 0.4 was -1.01 [-1.77, 0.06] / -0.52 [-1.14, 0.12]).

**Methods, with what exists.** (1) *Second-reader spot check.* The existing sheet and scorer (`scripts/build_spot_check.py`,
`scripts/spot_check_agree.py`) were built for call-edge labels (ADR-012), not for pull-request labels, so a label sheet (issue text, the
patch's edited units, the unit text, a three-way verdict, a free-text reason) must be built before this method can run; two readers
on a sample report agreement (kappa). Cost: the hand-read figure in ADR-002 is about one hour for 50 positives, so 400 pairs is about 8
hours per reader. (2) *Model-judged sample.* A cheap judge on the sample with a stronger judge on its flags, after RLHN; that paper used
closed-source judges at about 300 and 3,000 USD in two stages for 1.6M pairs, and found a reranker detecting only 52.5% to 63.8% of what
the cascade found (its Table 7); validated against 670 human-judged pairs. No judge has been run on code here and none is chosen
(ADR-008 is open); a judge's agreement with the human sample is the check. (3) *Both*: the second reader on a stratified sample, the model
judge on a larger one, the judge calibrated against the readers.

**Sample size (reasoned).** For a binomial rate estimated to a half-width h at 95% confidence, n = 1.96^2 x 0.25 / h^2: h = 0.10
needs 96 pairs, h = 0.07 about 196, h = 0.05 about 384. The sample is stratified by K-rank (kept and dropped at K = 20 under each teacher, at
least 100 per cell), so that precision and recall of the filter are estimated, not only the overall rate; at 400 pairs the overall
half-width is about 0.05 and the stratified cells about 0.10. Two readers on the same 400: about 16 hours, which is a person-time
decision for the lead (O11).

**If the audit cannot be done.** The protocol reports what it can: the K-rank profile of the mined set (the share of pairs with no
top-10 or top-20 positive under each teacher, which is a proxy for findable noise, not a noise rate); H1b is **not tested**; the mined-set
comparison is stated as "FILTER and WEIGHT against RAW on a set whose noise rate is unknown", and any gain or null there carries no
statement about proportionality; the injected-noise calibration remains the only evidence on H1 and is labelled a proxy (section 8,
threat 3).

## 8. Threats to validity, and what each pilot already tells

| Threat | What the pilots tell | Mitigation in this protocol |
|---|---|---|
| 1. **Pre-filtered pool.** The published pool was built with a retriever in the loop, so RAW on it is "RAW given a pre-selected pull request" and there may be nothing to filter | Wave 6: no gain; E-POOL-RANKS: 0 of 160 directories without a top-10 positive under SweRankEmbed-Small; ADR-001 addendum; the flip experiment (E-POOL-DATES) was skipped for lack of a token (D29) | the mined set (section 2) and the rank comparison G4; the pool is kept as the comparison population so the selection stays measurable |
| 2. **Pretraining exposure.** SweRankEmbed-Small was trained on data from this repository family; the base encoder and the benchmark's language models may have seen the repositories (contamination: 13.7% of base-commit functions occur in the corpus, 8.9% of edited functions; E-CONTAM-SCAN, E-CONTAM-EDITED) | the SweRankEmbed-Small cells are favoured (D50); BM25 carries the primary claim | report each teacher separately; arms are compared inside one benchmark so inflation is equal across arms (ADR-005) |
| 3. **Injected noise is a proxy.** Uniform replacement is easy to find (AUC 0.83 to 0.98); the sibling kind is harder and cost RAW about a quarter as much (-1.01 / -0.52, intervals including 0); real noise is of unknown kind | Wave 7 vs Wave 8; E-STORED-ANALYSIS: damage under uniform noise is spread over about half of the queries, concentrated in repositories (qutebrowser 5.20 against openlibrary 0.99 at L2) | section 7 audit; "findable" is measured, not assumed; the dose-response is stated as a calibration, not a model of real labels |
| 4. **Checkpoint retention for RQ3.** No trained checkpoint of a result run is retained: node-local `/tmp` is deleted at job exit; the only retained one is a 3.7 MB validation toy (checkpoint inventory in `B`); a new evaluation needs a retrain (0.38 GPU-hours plus evaluation); a final half-precision model is about 274 MB | RQ3 needs the retrievers of the four arms, so the final runs must retain them | retention policy (O9): the primary cells' final models (6 cells x 3 seeds = 4.9 GB, 6 x 5 = 8.2 GB) against 3.2 GB to the soft quota on account A and 38 GB free on account C at its first check (before about 10 GB of staging) |
| 5. **Few repositories.** Five at L2 and two at L3 on dev; django is 45% of Verified L3 | Variance components, section 5; three disagreements with the older minimum detectable figures, all L3 with the repository term | repository-clustered intervals where possible; the repository term beside every query-level interval; leave-django-out |
| 6. **Short training.** 100 updates is 0.5% of the master's 20,000; the learning curve shows RAW flat from 100 to 2,000 updates (increments within 1.0 point) but a supervision effect could appear only later | E-PILOT-CURVE (knee at or before 100); Wave 5 stage 2 at 1,000 updates (differences +0.2 to +0.6, intervals include 0) on a 2,000-example pool, where RAW itself fell 3.0 and 2.4 | O1: the update count is decided by the lead; at least one longer cell on the mined set is recommended |
| 7. **Data-budget confound.** FILTER sees fewer distinct examples at equal updates | Wave 6: no cell repeats at 100 updates; the subsample is above RAW at L3 in Wave 6 stage 1 and below it at 1,000 updates (stage 2, one seed, one draw) | the size-matched subsample is in every comparison and one draw per seed; unique-example counts are reported |
| 8. **Teacher equals base / self-confirming loop** | pilots included it as an exploratory cell | removed from the final cells (O3) |
| 9. **Multiplicity and flexibility of analysis** | about 60 contrasts in the pilots | family fixed in advance (section 4), decision rules in section 6 |
| 10. **Single language, single encoder, L3 labels judged by models** | Python only; L3 labels are model-judged and the vote combination is not stated (Q12) | claims scoped to Python and to the CodeRankEmbed base; L3 is secondary evidence for the context question |

## 9. Budget and schedule

**Cap and ledger.** Block 2 is capped at 66 GPU-hours (D44, D53, D58) with 62.81 used (account A 60.57, account C 2.24, account B 0;
`PROJECT_STATE.md`, `docs/COMPUTE.md`): **3.19 left.** Every option in section 5 (21.6 to 60.0 GPU-hours) needs a new authorisation
(O12); this document proposes none and does not assume one.

**Stages and cost (GPU-hours; measured unit costs, the rest reasoned).**

| Stage | What | GPU-hours | Where |
|---|---|---|---|
| S0 | mining pilot M1 to M4 (API, CPU) and M3 rank measurement | M3 limit 2 | CPU for mining; GPU for M3; needs the token (D2) |
| S1 | full mining run, content-overlap audit (to be built, D65), teacher scores of the mined set (dense teacher about 2.2 per 5,000 directories) | about 2 to 5 | CPU and GPU |
| S2 | noise audit sample (section 7) | person-time; judge cost not estimated | readers; a judge if chosen |
| S3 | calibration: injected noise at r in {0, 0.2, 0.4} | 0.40 per run | GPU |
| S4 | mined-set arms | 0.40 per run (1.06 at 1,000 updates) | GPU |
| S5 | final look on Verified | placeholder 0.4 per run | GPU |
| S6 | RQ3 (agent runs) | not estimated (no scaffold installed or timed; ADR-007, ADR-008) | outside this protocol |

**Per-user limits and accounts.** One GPU job at a time per account: the two research logins (A and C) have `cpu=10,
gres/gpu=1, mem=32,000 MB` and 5 jobs (QOS `low`; 4-day wall time on C); the course login has 1 job and a 6-hour wall time
(`docs/COMPUTE.md`). A job of six cells at 100 updates takes about 2.4 to 2.7 GPU-hours (E-PILOT-NOISE: 2.71, 2.23, 2.25, 2.24, 2.40),
so a 6-hour wall limit fits one such job and not a longer one; checkpoints are node-local and a resubmission restarts a run. Queue waits
have been 3 to 8 hours per job. Only account A has an alias on the engineer's machine; accounts B and C answer by full login, have private homes
(each needs its own staged copy, about 10 GB; C was staged for the last N1 job, B not), and the GPU budget is summed over all three. Run
order follows dependency: S0, S1 and S2 (data) before any arm; S3 can run on account A while S0 to S2 wait for the token (the injected-noise
pool exists), and the rest of S3 can be placed on C in parallel; S4 follows S1; S5 follows the dev analysis. Job counts: option A is
six jobs of six cells at three seeds (one job per seed and cell group), about 14 hours of GPU wall time on one account (plus queue waits),
about half that on two accounts; calendar dates are the lead's. Disk: account A had 3.17 GB to the soft quota at the last check;
results of a run take about 1.25 MB, retained models 274 MB each.

**Fallback if RQ3 is cut.** The master's fallback ships RQ1 + RQ2 + latency (`docs/10_timeline_and_fallback.md`, risk table). Then S6 is
not run, the retention of four retrievers is not needed, and the final look on Verified reports retrieval metrics only. RQ2's claim is
unchanged (retrieval supervision effect under matched budgets, with the noise calibration); only the downstream-agent statement is
lost. The RQ1 ladder and the latency harness are outside this experiment's GPU budget.

## 10. OPEN FOR THE LEAD

Each item: options, evidence, recommendation (*recommendation*, never a decision). Items touching the master document are also to be
recorded in `docs/DEVIATIONS.md` when settled.

| # | Item | Options and evidence | Recommendation |
|---|---|---|---|
| O1 | **Update count and schedule** | (a) 100 updates of the 3,000-update schedule, as every pilot (curve flat from 100: E-PILOT-CURVE; 0.40 GPU-hours per run); (b) 1,000 (1.06 per run; Wave 5 stage 2 and Wave 6 stage 2 on a pool too small to avoid repeats); (c) the master's 20,000 (`docs/08_experimental_design.md`; about 15 GPU-hours per run for training alone, E-TRAIN-STACK, ADR-002); (d) a run that decays to zero at N, which is not the pilots' recipe (E-PILOT-CURVE limits). The master's "held identical" block says 20,000; this document does not edit it | (a) as the primary plus one (b) cell per primary arm on the mined set, which also needs a mined pool of at least 32,000 pairs to avoid repeats; a DEV entry for the departure from 20,000 |
| O2 | Confirmatory scope (section 1) | the table in section 1; alternative: all arms confirmatory (the family grows, section 4) | as proposed in section 1 |
| O3 | Teachers and K | BM25 only; BM25 + SweRankEmbed-Small; add the self-teacher cells; K in {10, 20, 40}. Evidence: AUC and gains by teacher (Wave 7), the favoured-teacher caveat, the master's separate-encoder rule, the K sweep at 63 updates (ADR-002) | BM25 (primary) and SweRankEmbed-Small, K = 20 positive level, no self-teacher cells |
| O4 | Primary metrics and the L3 metric | L3 Recall@100 (every stored table, `metric` = `recall100`) or L3 nDCG@10 (the Wave 7 entry's text). The entry is append-only; an addendum should correct the text | L3 Recall@100, nDCG@10 beside it; addendum to E-PILOT-NOISE |
| O5 | Multiplicity | Holm, Bonferroni, none with all contrasts shown, gatekeeping (section 4) | Holm within families, uncorrected intervals beside |
| O6 | delta, the smallest difference worth reporting | the design's minimum detectable difference (about 1.5 to 2.0), 1 point, 3 points; it is the same question as Q45 for RQ3 (a difference of 5 to 6 points makes a test feasible at Verified sizes; 3 points or less only an estimate; E-POWER) | the design's minimum detectable difference, stated before the runs |
| O7 | Seeds against repositories | options A to E in section 5; evidence: the minimum detectable differences and floors above | option A, with the Verified set as the repository-rich confirmatory set; decide between more seeds and more repositories after the mined yield is known |
| O8 | Evaluation set size | add ansible (0.33 GPU-hours per checkpoint, 83 L3 queries); add other CORE-Bench L2 folders as further dev repositories (unit records and dense stores must be built); keep five and two | add ansible (it makes dev L3 three repositories, D32) and decide on other folders after the cost of building one is measured |
| O9 | Checkpoint retention and when the Verified look happens | (a) evaluate Verified in the same job as dev, no retention, one look by registration; (b) retain the primary cells' final models (4.9 to 8.2 GB; needs space beyond account A's 3.2 GB) and evaluate Verified after the dev analysis; the other six Verified repositories need unit stores and an encoding cost measurement | (b), because RQ3 needs the models anyway and "exactly once" is easier to defend after the dev analysis is complete |
| O10 | Mined-set gates and prerequisites | the thresholds of G2 (no figure is set in `B`); the token (D2); the content-overlap audit of mined corpora (not built, D65); whether the final run waits for the full rename cache. *Evidence:* none measured; the design rules are in `B` | thresholds fixed before M2 is read; proposed: quarantined share reported and the set accepted only if positives-per-pull-request and pairs obtainable satisfy G5 (no numeric quarantine limit is recommended without a measured yield) |
| O11 | Noise-audit method and person-time | section 7: spot check, model judge, both; sample size 96 to 384; readers available; judge choice (ADR-008) | both, 400 stratified pairs, two readers on a 100-pair overlap for kappa |
| O12 | GPU authorisation and accounts | a new block sized to option A to D (21.6 to 60 GPU-hours), aliases for B and C (`PROJECT_STATE.md`, item 4e) | a block sized to option A plus the teacher-scoring and M3 stages, about 30 GPU-hours, set before S3 starts |
| O13 | RQ3 retrievers if the arms do not separate | (a) cut RQ3 (the master's fallback); (b) run RQ3 on the arms with the largest gap although inside noise (a null by construction); (c) contrast RAW with the untrained encoder, a retrieval difference of about +9.6 (L2) and +11.1 (L3) that is measured (E-PILOT-ARMS2), which tests whether a retrieval gain of that size reaches the resolved rate and needs no arm to separate. This redefines RQ3's "four retrievers from RQ2" | (c) as the minimum RQ3, in addition to the four arms when they separate; needs the lead's approval because it changes what RQ3 measures |
| O14 | Departures from the master document that this protocol would carry | update count (O1); CodeRankEmbed instead of the master's encoder (no DEV entry, BRIEF ADR-006); one negative policy for all arms against the master's arm table (DEV-012); FILTER at the positive level; the second-reader sheet is not a label audit. `docs/08_experimental_design.md` "held identical" block untouched | record each in `docs/DEVIATIONS.md` when settled |
| O15 | Realisations of injected noise | reuse the Wave 7 realisations (comparable with the pilots) or draw new ones with the same rule (confirmatory runs share nothing with exploratory ones) | new draws, same rule |

---

Not claimed here: any result of the final experiment; any number not traced above; any effect for another language, encoder or
trained-to-convergence retriever; that injected noise stands for real noise. The pilots are exploratory and enter the final tables only
as the stated basis of the design.
