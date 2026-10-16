# datasets/ — what we use and where it stands

Facts below are from the master doc (rev 16); update the **Status** column as data arrives on Ada.
Data is fetched **on Ada** by `scripts/ada/` jobs, never by hand (`docs/COMPUTE.md`); each fetch
writes `data/raw/<dataset>/provenance.json`.

| Dataset | Stage / role | Known facts | Status |
|---|---|---|---|
| SweLoc (SweRank) | A — primary training pool candidate | purpose-built for issue localization; released | not fetched |
| Own PR-mined set | A — contamination-safe replication | merged PRs closing an issue; issue text = query; patch-touched functions = positives | not built |
| CodeSearchNet | A — transfer-gap arm | ~2M comment–code pairs, 6 languages | not fetched |
| CORE-Bench L2 | C — primary retrieval metric | 632 repos, 5,061 queries, 9,377,120 chunks; layout `LEVEL-2/<dataset>/<repository>/{corpus,queries,qrels}.jsonl` | not fetched |
| CORE-Bench L3 | C — structural/graph question | 97 repos, 2,580 queries, 2,609,581 chunks | not fetched |
| CORE-Bench L2/L3 REWRITE | C — free query-rewriting ablation | paper reports rewriting can hurt | not fetched |
| CORE-Bench L1 | context only | 172,961 queries; 2,412,296 corpus items | not needed |
| Loc-Bench | C — contamination check, category balance | 660 examples (bug 282, feature 203, security 31, performance 144), post-Oct-2024 | not fetched |
| CoIR | C — generalization (cut first if behind) | 10 datasets, 8 retrieval tasks, ~2M documents | not fetched |
| SWE-bench Verified | D — agent eval (resolved rate) | overlaps L2/L3 repositories and instances | not fetched |

Notes:

- CORE-Bench releases **evaluation data only**; the 53,301-PR SFT set from the paper was not released.
- Dropped from scope: Nokia / Stack Overflow code-search data (a third distribution, serves no RQ).
- Source registered groups in CORE-Bench: `CORE_BENCH_LEVEL1`, `LEVEL2`, `LEVEL3`, `LEVEL2_REWRITE`, `LEVEL3_REWRITE`; built on MTEB.
