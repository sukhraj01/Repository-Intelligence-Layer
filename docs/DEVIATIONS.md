# Deviations from the Master Project Document

Append-only. Every place this repository departs from the master doc (rev 16, 2026-10-11) gets an
entry **before the code lands**, with a rationale. The master doc is the plan; this file is the
audit trail of where reality forced a change. Departures from *published* recipes (SweRank,
CoRNStack, LocAgent, CORE-Bench) are recorded here too.

Entry format:

```
## DEV-NNN — <short title>        (date · status: proposed | accepted | reverted)
- Master says: <quote or section>
- We do:       <what we do instead>
- Why:         <evidence, not preference>
- Impact:      <which RQ / result / claim this touches; does it change what is controlled?>
- Reversible:  <yes/no, and cost>
- Related:     ADR-0NN
```

A deviation that changes **what an experiment measures or what is held identical** needs an ADR and
engineer sign-off — it is a design decision.

---

## DEV-001 — Data facts that differ from the master document   (2026-10-17 · status: proposed)
- Master says: SweLoc is "released"; Loc-Bench has 660 examples (bug 282, feature 203, security 31, performance 144), post-Oct-2024; L2/L3 "repos" are 632 / 97.
- We find: no dataset named SweLoc is published (an undocumented candidate, `gangiswag/train_data`, exists; `knowledge/datasets/sweloc.md`). Loc-Bench is 660 rows in V0.2 and 560 in V1 with different category counts (V0.2: 275 / 216 / 29 / 140), and not every row post-dates Oct 2024. 632 and 97 are counts of folders; 154 folder names are truncated and are not repository names.
- Why: tree listings, dataset metadata, and sampled files, logged in `results/logs/s2_ground_truth_a_2026-10-17.json`.
- Impact: ADR-001 (pool), ADR-005 (Loc-Bench role), held-out list construction. No experiment definition changed.
- Reversible: yes.
- Related: ADR-001, ADR-005

## DEV-002 — CORE-Bench repository counts, chunk sizes and Rewrite qrels, measured   (2026-10-17 · status: proposed)
- Master says: L2 has 632 repositories and L3 97; chunks are about 1,000 characters; Rewrite variants share corpus and qrels with the originals.
- We find: 632 and 97 are folder counts; read from the instance ids they hold 605 (L2) and 92 (L3) distinct repositories, L3 inside L2, and the 12 Verified repositories inside both. Chunk length is not capped at 4,096 characters (longest 1,009,865; mean 1,004.9 L2 / 1,154.8 L3). Rewrite folders match the originals in queries but not in qrels: 81 Rewrite Multilingual folders have no qrels file and 13 folders have fewer rows (158 fewer in all).
- Why: all 1,458 folders streamed on the cluster, `results/logs/s4_ground_truth_b_2026-10-17.json`, `results/tables/core_bench_card_vs_measured.csv`.
- Impact: held-out list size (605); any Rewrite-based comparison must say which qrels it scored against; chunk-window handling in the evaluation loader (Open question Q11).
- Reversible: yes.
- Related: ADR-001, ADR-004

## DEV-003 — CORE-Bench evaluation is whole-snapshot retrieval, not retrieval from a sampled candidate set   (2026-10-17 · status: proposed)
- Master says: the Level-2/3 candidate set for a query is a sample of the folder corpus; the earlier project state framed each query's `filtered_corpus_id` list as "not the whole folder corpus".
- We find: the paper says the per-query filter keeps "the documents visible at the corresponding PR or issue state" (Sec. 4.1, p.5), and on 11 Verified instances all 12,153 chunks of the lists occur in the checkout at the base commit (`results/tables/r1_c1_snapshot_check.json`). Each list is the repository snapshot at the base commit; the folder corpus is the union of the snapshots of its instances. The chunker and chunk metadata (paths, line spans) are not released (claim C2).
- Why: `knowledge/papers/core-bench-2606.11864.md` (claims C1, C2); the data test above.
- Impact: Q11. Evaluation measures what an agent would see at the base commit; unit-level evaluation needs a checkout per instance and a derived chunk-to-unit mapping (decision D7). No experiment definition changes.
- Reversible: yes (wording and the mapping design).
- Related: ADR-004, ADR-005, `specs/code_unit.md` D7

## DEV-004 — The candidate pool is SweLocMulti's Python part, and it holds benchmark repositories   (2026-10-17 · status: proposed)
- Master says: "SweLoc" is released and is the primary pool candidate.
- We find: no dataset named SweLoc is published. `gangiswag/train_data` (python) has 24,285 PR directories over 2,448 repositories, exactly SweRank+ Table 1's Python row (2,448 repositories, 24,285 PRs, 49,973 function-level instances), so it is SweLocMulti's Python part, not the original SweLoc (3,387 repositories at an 80% Python threshold). SweRank excluded SWE-bench and Loc-Bench repositories from SweLoc (Sec. 3.1, p.4); SweRank+ states no such exclusion anywhere, and the held-out list finds 89 held-out repositories (3,431 PRs, 14.13%; 3.64% of the repositories) in it.
- Why: `knowledge/papers/swerank-plus-2512.20482.md` (claim S2), `knowledge/papers/swerank-2505.07849.md` (claim S1), `data/held_out/pool_filter_report_gangiswag_train_data_python.md`.
- Impact: leakage. Any use of this pool needs the repository filter (a test enforces it); results that use SweRankEmbed-style models trained on it may be contaminated on Verified (SweRank+ Table 2 reports Verified numbers for such models).
- Reversible: yes.
- Related: ADR-001, `specs/held_out_repos.md` (addendum, decisions D1 to D3)

## DEV-005 — Numbers about the graph papers in the master document, corrected by reading   (2026-10-17 · status: proposed)
- Master says: "69.7% of localized bugs needed multi-hop" (KGCompass); Loc-Bench has 660 issues (282 bug, 203 feature, 31 security, 144 performance); SpIDER gains 12.9% Recall@20; LocAgent's ablation numbers are from its Table 5.
- We find: KGCompass v3 (Sec. 5.2, p.14; Figure 8, p.13) reports 89.7% of 146 ground-truth functions two or more hops from the issue node (10.3% direct); 69.7% is the superseded v1 text, and 67.3% is a different quantity (SWE-bench Lite issues that name no ground-truth file or function, Table 4, p.13). LocAgent v2 has 560 Loc-Bench issues (242 bug, 150 feature, 29 security, 139 performance); 660 is v1; its ablation is Table 6. SpIDER states a gain of at least 13% relative over the same encoder's dense list (12.9% was v1). LARGER says LocBench has 5 repositories, which its own Figure 4(b) contradicts (165 measured).
- Why: `knowledge/papers/kgcompass-2503.21710.md` (K1), `locagent-2503.09089.md`, `spider-2512.16956.md`, `larger-2605.16352.md` (G1).
- Impact: references and any text quoting these figures; the derived master copies in `docs/` are not edited (the master wins on conflict, this file is the record). Loc-Bench counts also feed DEV-001.
- Reversible: yes.
- Related: `docs/05_structural_signals.md`, `docs/06_core_bench.md`

## DEV-006 — "Tests and configuration are covered by nobody" no longer holds as worded   (2026-10-17 · status: proposed)
- Master says: no prior work covers tests and configuration in the retrieval structure.
- We find: LARGER builds tested-by, documents and configures links with fixed confidences 0.75, 0.6 and 0.5 (Table 11, p.19) and appends the related tests, documentation and configuration files to its search output. It reports no ablation of those links and no resolution coverage, and its alignment study runs with test files dropped (p.17), so there is no published evidence either way that they help.
- Why: `knowledge/papers/larger-2605.16352.md` (claim G1).
- Impact: report wording only. The defensible form is "no ablation shows the value of test and configuration links" (Open question Q24).
- Reversible: yes.
- Related: ADR-003

## DEV-007 — Reference and claim corrections found by reading the training-supervision papers   (2026-10-17 · status: proposed)
- Master says: CodeR is arXiv 2508.11442; Sun et al. 2022 give "+19.2% MRR" from filtering noisy queries and "over a third noisy"; "false negatives are pervasive" is a measured finding; "expect 70-85% edge recovery".
- We find: 2508.11442 is CoDiEmb, a different paper; CodeR is 2505.12697. The +19.2% MRR is for DeepCS on Java only, relative, on three small evaluation sets, with half the data and half the training time, and the noisy share is 33.1%. The false-negative claim is cited from earlier work, not measured. PyCG reports 69.9% on five small packages against hand-built truth; Jarvis 0.76 and 0.82 against its own truth; DyPyBench 49% of executed edges; none supports 70-85% for arbitrary repositories. Agent Retrieval Bench supports complementarity of two systems, not a signal ablation, and disclaims any resolved-rate claim.
- Why: the notes of the third reading session in `knowledge/papers/` (`coder-2505.12697.md`, `codiemb-2508.11442.md`, `sun-2202.06649.md`, `pycg-2103.00587.md`, `jarvis-2305.05949.md`, `dypybench-2403.00539.md`, `agent-retrieval-bench-2607.24882.md`).
- Impact: `docs/03`, `docs/05`, `docs/11` wording; the edge-recovery expectation must be reported as a measurement, never as an expected range. Edge-recovery definitions are the subject of ADR-012.
- Reversible: yes.
- Related: ADR-002, ADR-012 (stub, planned)

## DEV-008 — Rewrite runs are scored against the original qrels   (2026-10-17 · status: accepted by the engineer, D13)
- Master says: Rewrite variants share queries and qrels with the originals.
- We do: score Rewrite runs against the original qrels (same query ids in every folder) and report the 158 folders whose Rewrite qrels differ (81 Multilingual folders have no qrels file, 13 have fewer rows) as a packaging defect.
- Why: DEV-002 measured the difference; the labels belong to the query ids.
- Impact: any Rewrite comparison; flip experiment: BM25 on original against Rewrite queries scored with both qrels.
- Reversible: yes.
- Related: ADR-005, DEV-002

## DEV-009 — CodeUnit `unit_type` gains "module"   (2026-10-17 · status: accepted by the engineer, D6)
- Master says: `unit_type` is function, method or class.
- We do: add `module`, one residual unit per file for lines outside every definition.
- Why: 16 of 160 sampled positives overlap no definition, so about 10% of gold would be unreachable at unit level; the unit is also the file node of the graph.
- Impact: every index holds one more unit per file; pilots M and E1 measure what it buys. The canonical serialization is unchanged.
- Reversible: yes before an index exists, then by a version bump and re-index.
- Related: ADR-013, ADR-004
