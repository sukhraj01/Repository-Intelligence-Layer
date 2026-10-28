# ADR-001: Training pool

- **Status:** Proposed — **not decided**
- **Date opened:** 2026-10-12
- **Decide by:** end of week 2 (all ten decisions)
- **Decided by:** _pending — team_
- **Master doc:** open decision #1 (`docs/12_open_decisions.md`)
- **Affects:** RQ2 (all arms), leakage tests, `ril/training/data_loader.py`

## Context
CORE-Bench releases evaluation data only; its 53,301-PR SFT set was not released, so "train on CORE-Bench supervision" has no referent. The pool must be repository-disjoint from CORE-Bench L2/L3 and SWE-bench Verified. SweLoc (SweRank) is released and purpose-built for issue localization; an own PR-mined set (merged PRs closing an issue; issue text = query; functions touched by the patch = positives; other functions in the repo = negatives, hard ones mined by similarity) is the contamination-safe replication and the one piece that must be built.

## Alternatives considered
- SweLoc
- Own PR-mined set
- Both

## Master doc's recommendation (a recommendation, not a decision)
Both — SweLoc to avoid being blocked, own set for contamination safety.

## Decision
_Pending — the team decides._ If work cannot wait, proceed behind a config flag marked
`provisional: ADR-001` (never in `configs/frozen/`) until the decision is made.

## Rationale
_Pending._

## Trade-offs
_Pending._

## Evidence to gather
- [ ] Size, licence and access path of SweLoc; whether it can be fetched on Ada (docs/COMPUTE.md).
- [ ] How many SweLoc instances / repositories survive the repo-level held-out filter (needs `specs/held_out_repos.md` output).
- [ ] Estimated effort and yield of the PR-mining recipe on repositories post-dating the base model's cutoff.

## Related benchmarks
_None yet._

## References
See `docs/11_references.md`.

## Conditions to revisit
_Pending._

## Addenda

### 2026-10-17 — public-page check (not a decision)
- The master doc describes SweLoc as released. The public pages checked do not show a dataset release:
  the SweRank README documents how SweLoc is *collected* (`src/collect/collect_data.sh`,
  `negative_mining.sh`, output `repo_contrastive_mined_filtered.jsonl`) and links only models and
  the SWE-bench-Lite / Loc-Bench evaluation data; the paper's Hugging Face page says "Code, Data and
  Models: Coming soon!" and lists no dataset; the follow-up paper (arXiv:2512.20482) says its
  multilingual extension (4,060 repositories, 56,279 PRs, 155,663 instances) "will be released" at the
  same GitHub repository. A Hugging Face search for "SweLoc" returns nothing.
- Consequence if confirmed: "SweLoc" is obtainable only by running the published collection scripts,
  which makes the "both" option closer to "one pipeline, two scales". The wave-1 audit should confirm
  or refute availability before any pool is chosen.
- The CORE-Bench paper states its 628-repository SFT set is "disjoint from the SWE-bench family" and
  does not state that the SFT data is released.


## Addendum 2026-10-17 — availability evidence (no decision)

- No dataset named SweLoc is published on the Hugging Face Hub (name and author searches) or linked from the SweRank repository.
- `gangiswag/train_data` (no card; created 2025-09-23) holds a function-level, BEIR-style training set: 56,279 instances in 10 languages, 24,285 of them Python from 2,448 repository directories, with `repo` and `base_commit` in query metadata. Whether its Python part is the SweLoc of the SweRank paper is unconfirmed. Details: `knowledge/datasets/sweloc.md`.
- The published collection recipe computes the positive's rank with `cornstack/CodeRankEmbed` (a separately pretrained encoder) and keeps instances whose positive ranks 0 to 10 and negatives ranked 3 to 25.

## Addendum 2026-10-17 — survival under the held-out list (evidence, no decision)

The held-out list has 605 repositories (CORE-Bench L2 union L3 union SWE-bench Verified; `data/held_out/report.md`). Applied by repository to the pools that can be identified by repository:

| Pool | Instances before / after | Repositories before / after | Note |
|---|---|---|---|
| `gangiswag/train_data` python (candidate, unconfirmed as SweLoc) | 24,285 / 20,854 (85.87%) | 2,448 / 2,359 (96.36%) | 89 held-out repositories present; 3 more surviving repositories are renamed forms of held-out ones (54 instances) |
| CodeSearchNet python | 457,461 / 449,440 (98.25%) | 13,590 / 13,546 (99.68%) | 44 held-out repositories present; 16 more survivors are renamed forms of held-out ones (1,603 rows), for example `pycqa/pylint` |
| CoRNStack python | not filterable | not filterable | no repository identifier in the schema |

Exact-name filtering is not sufficient for pools built before a repository was renamed; whether renamed repositories and forks are held out is Open question Q8 (fork / near-duplicate rule). Details: `data/held_out/pool_filter_report_*.md`, `knowledge/datasets/sweloc.md`.

## Addendum 2026-10-17 — held-out matching rule, token, and what the candidate pool is (decisions D1, D2, Q7 reframed)

**D1 (closed Q8): held-out matching.** A pool repository is held out if its name or its current GitHub
name equals a held-out repository's name or current name (current-name resolution through GitHub
redirects). The fork network is a sensitivity report only and is never a filter. A content-overlap
audit is added and reported, not applied.
- *Why.* Exact names miss repositories renamed or transferred after a dataset was built: of 108
  repositories looked up, 23 now have a different name, and 19 of the 59 same-name candidates in two
  pools resolve to a held-out repository, none being a fork. The SweRank paper itself removed
  repositories by source-code overlap (`knowledge/papers/swerank-2505.07849.md`, Sec. 3.1, p.4).
- *Evidence class.* Measured (lookups, `data/held_out/rename_cache.json`; audit,
  `results/logs/d_content_overlap_audit_2026-10-17.json`) and read in full (SweRank).
- *Cheapest experiment that could flip it.* Train a small encoder with and without the renamed
  held-out-repository instances and compare on Verified (planned as E-PILOT-LEAK; the
  experiments session registers it in `docs/EXPERIMENTS.md`). If the inflation is negligible the rule costs
  data for no gain. Time-box: one small run.
- *Conditions to revisit.* The pilot; a fork-network sensitivity row that drops a large share; the
  audit finding overlap in repositories the name rules keep.
- *Result so far.* Held-out list v2 and the pool filters are in `specs/held_out_repos.md` (addendum)
  and `data/held_out/pool_filter_report_*.md`. Resolution is partial without a token (47 of 2,448
  gangiswag python repositories, 11% of its instances), so the post-rename counts are lower bounds.

**D2 (closed Q22): token.** A read-only token (public-repository scope, no write scope) in the
environment variable `GITHUB_TOKEN` on the cluster, never printed or stored in the repository.
Presence is tested without printing; `GET /rate_limit` verifies it. Without it the resolver runs
against the unauthenticated limit (60 requests per hour) and reports what it did not reach.
- *Status on 2026-10-17.* Not present on the cluster (login shell and batch environment). The resolver
  and its tests use a fake transport; a data blocker is recorded in `PROJECT_STATE.md`.
- *Evidence class.* Measured (presence check). *Flip experiment.* None needed; the limit is
  documented by the service and was reached in practice (`docs/COMPUTE.md`).

**Q7 reframed (not decided).** Read in full: SweRank+ Table 1 gives for Python 2,448 repositories,
24,285 PRs and 49,973 function-level instances, exactly the counts measured in the candidate, so the
candidate is SweLocMulti's Python part and not the original SweLoc (3,387 repositories); that paper
states no exclusion of benchmark repositories, and 89 held-out repositories (3,431 instances, 14.13%
of the PRs) are present in it (`knowledge/papers/swerank-plus-2512.20482.md`, claim S2). Whether it is
the intended pool remains the engineer's decision.

## Addendum 2026-10-18 — pool check of the candidate (evidence, no decision)

Measured (`docs/EXPERIMENTS.md`, E-POOL-CHECK; `results/tables/x_pool_check_*.csv`): the candidate's 24,285 directories are pull requests with one query each and 307,996 positive rows in total (mean 12.68, median 4 per directory), not
the 49,973 instances of the SweRank+ Python row; the counts that agree with that paper are the 24,285 PRs and the 2,448 repositories only. The data carries no rank or filter field, so whether the directories are before or after the
top-40 consistency filter is undecided (a 16% survival of positives would explain the difference; the experiment that would settle it is in E-POOL-CHECK). Corpora are whole-repository function lists (sample median 410 functions). No creation dates.
60 (repository, PR) pairs coincide with CORE-Bench L2 queries (SWE-bench-Live and plus-plus; 18 repositories, all on the held-out list), none with Verified or L3, so the repository-level filter removes all direct same-PR leakage; the filter is required: without it the pool contains
the pull requests of 60 L2 queries. Evidence class: measured. Conditions to revisit: a token on the cluster (creation dates, current names), and the rank experiment above if FILTER's K or teacher is to be compared with the pool's own filtering.

## Addendum 2026-10-23 — provisional pool until the filter-state experiment reports (engineer decision D22 of 2026-10-18; this ADR stays Proposed)

**D22 (Q43 pending the experiment).** The pool filter-state experiment is run (X3 in the experiment plan: rank the positives
of at least 150 sampled pool instances under SweRankEmbed-Small, CodeRankEmbed and BM25, and compare the share outside the
top 40 with the 307,996 positive rows against 49,973 instances, ratio 6.2). Until it reports, the training pool is
**provisional**: `gangiswag/train_data` python minus the held-out list (core list plus the Loc-Bench tier, D1 and D3),
marked `provisional: ADR-001` wherever it is used and never in `configs/frozen/`.
- *Rationale.* Whether the directories are before or after the top-40 consistency filter decides how the four RQ2 arms are
  built (if they are already filtered by one teacher, RAW is not available from this pool); the provisional choice lets the
  training stack be built and smoke-tested without fixing that.
- *Evidence class.* Measured (E-POOL-CHECK: counts and the absence of a rank field) and read in full (SweRank+ Table 1).
- *Experiment that could flip it.* X3 itself: a positive-rank distribution with essentially no positives outside the top 40
  under one teacher would say the pool is post-filter, which removes RAW from this pool and reopens the choice between this
  pool and an own PR-mined set; time-box as sized in the plan (GPU budget of the current block).
- *Conditions to revisit.* X3; a token on the cluster (current names, creation dates; D2); the authors' code being released.

## Addendum 2026-10-25 — filter state of the candidate pool (evidence for D22 / Q43, no decision; this ADR stays Proposed)

Measured (`docs/EXPERIMENTS.md`, E-POOL-RANKS; `results/logs/x3_pool_ranks_2026-10-25.json`, config hash `755b27136e9d`): every positive of
160 directories (stratified by corpus size and held-out flag, seed 0; 1,522 positives) ranked against the other functions of its
snapshot under SweRankEmbed-Small (the SweRank+ filter teacher), CodeRankEmbed and BM25.
- *Certain within the sample:* the qrels are not consistency-filtered per positive. Under SweRankEmbed-Small 39.4% [24.1, 48.0] of the
  pool's positives lie outside the top 40 (34.9% on the stored text), and the estimated count inside the top 40 is 186,531
  [160,311, 233,797], not the 49,973 instances of SweRank+ Table 1; no K in {10, 20, 40} and no teacher gives that count. A RAW arm at
  the positive level is available from this pool.
- *Measured:* the directories are selected with respect to SweRankEmbed-Small: none of 160 lacks a positive in its top 10 (stored text;
  exact upper bound 2.3%), against 19.3% [15.7, 23.2] of the authors' never-filtered Verified export under the same teacher; under
  CodeRankEmbed the gap is smaller (16.9% against 35.7%).
- *Not decidable from these data:* whether that selection is a PR-level filter (a PR kept if one positive passes) or the released
  checkpoint's fit to these PRs (it was fine-tuned on the same authors' Python PR collection).
- *What it means for the pool decision.* If PR-level filtered, the pool lacks the PRs whose every positive fails (on Verified that rule
  would remove 9 to 19% of PRs): RAW from this pool is "RAW given one easy positive", and RAW-versus-FILTER effects measured on it would be
  conservative. If not, the pool is raw at both levels. Either way the four arms can be built from it; an own PR-mined set (the master
  document's alternative) would be raw by construction at the cost of building it.
- *Evidence class:* measured (exploratory, n = 160 plus a 457-directory reference). *Experiment that could flip it:* creation dates of
  the pool's PRs against the checkpoint's release (needs `GITHUB_TOKEN`, D2): post-release PRs that still never lack a top-10 positive
  mean a filter. *Conditions to revisit:* that experiment; the authors' code or data card.

## Addendum 2026-10-29 — smoke pilot E-PILOT-LEAK (evidence, no decision; this ADR stays Proposed)

Evidence class: measured, exploratory, 2 seeds, 63 updates. Two training sets of 2,000 directories by the same seeded order, one with
the held-out list applied (selection A) and one without (selection L: 292 held-out directories in place of 292 others, about 30 of
them from the development repositories haystack and streamlink). No Verified-six repository has a directory in the pool (92 held-out
repositories occur in it). Effect of not filtering, dense: dev +0.18 [-0.25, 0.57] L2 nDCG@10, +0.16 [-0.21, 0.53] L3 Recall@100;
Verified-six (uses test repositories deliberately, for the leakage effect; not a final number) +0.51 [-0.46, 1.59] L2, -0.25
[-0.90, 0.34] L3. At this budget the held-out filter changes no measured number; the evidence says it is hygiene for the
disjointness claim rather than a number-changer, and it says nothing about larger budgets or about repositories (Verified-six) that the
pool does not contain. Cheapest experiment that could flip it: the same pair at a larger budget with the held-out directories of the
development repositories over-represented (all 249), evaluated on dev, about 2 GPU-hours.
