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

