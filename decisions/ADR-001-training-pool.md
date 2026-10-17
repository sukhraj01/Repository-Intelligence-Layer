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
