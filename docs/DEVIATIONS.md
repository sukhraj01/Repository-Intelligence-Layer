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
- Impact: wording in `docs/03_literature_map.md`, `docs/05_structural_signals.md` and `docs/11_references.md`; the edge-recovery expectation must be reported as a measurement, never as an expected range. Edge-recovery definitions are the subject of ADR-012.
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

## DEV-010 — Derived copies in `docs/` are corrected in place where the master is factually wrong   (2026-10-23 · status: accepted by the engineer, D14 of 2026-10-18)
- Master says: the files in `docs/` split from the master are derived copies; where they disagree with the master, the master wins and the copy is not edited (DEV-005 followed this).
- We do: where the master is factually wrong about an identifier or a figure, the derived copy is corrected in place with an inline marker "(corrected, see DEV-0nn)" naming the entry that records the evidence; this file keeps the record. The master document itself is edited by the engineer. Design text, recommendations and wording that is not a factual error are not touched. The statement that tests and configuration are "covered by nobody" (DEV-006) is reworded to "no ablation shows the value of test and configuration links".
- Why: the derived copies are what the code and the reports are written against; leaving known wrong identifiers and figures in them invites their reuse (one wrong identifier, CodeR, was already copied into a note before it was caught).
- Impact: wording only; no experiment definition changes. Corrected in this pass: `docs/02_research_questions.md` (Sun et al. figure, DEV-007), `docs/03_literature_map.md` (Sun et al. figures, the false-negative claim and the CodeR identifier, DEV-007; LocAgent's ablation table and the KGCompass multi-hop share, DEV-005), `docs/04_data_and_ground_truth.md` (SweLoc availability, DEV-001 and DEV-004; Loc-Bench size and dates, DEV-001), `docs/05_structural_signals.md` (the "covered by nobody" statement, DEV-006; the KGCompass share, DEV-005; the edge-recovery expectation, DEV-007), `docs/06_core_bench.md` (repository counts that are folder counts, DEV-002), `docs/08_experimental_design.md` (edge-recovery expectation, DEV-007), `docs/11_references.md` (DEV-005, DEV-007, DEV-011), the project documents that repeated the edge-recovery expectation (`docs/ARCHITECTURE.md`, `specs/parse_one_repo.md`; DEV-007), the published-anchor rows of `RESULTS.md` for KGCompass and Sun et al. (DEV-005, DEV-007), and `knowledge/papers/README.md` and the SpIDER note (DEV-011). Edge recovery is reported as decided in D15 (ADR-012 addendum).
- Reversible: yes.
- Related: DEV-001, DEV-002, DEV-004 to DEV-007, DEV-011, ADR-003, ADR-012

## DEV-011 — Reference audit of 2026-10-23: identifiers, titles, first authors and years checked against arXiv and publisher records   (2026-10-23 · status: proposed)
- Master says: the references in `docs/11_references.md` ("All links verified October 2026") and the paper table in `knowledge/papers/README.md`.
- We find: every arXiv identifier cited in `docs/11_references.md`, `knowledge/papers/README.md` and the ADRs (35 identifiers) was looked up on its arXiv abstract page on 2026-10-23 (title, author list, first-version date, latest version, comments field); venues not stated on arXiv were looked up in Crossref; the dataset and code links were requested (all HTTP 200). Mismatches:
  1. CodeR: cited as arXiv 2508.11442, which is CoDiEmb (Zhang, B. et al. 2025); CodeR, "Towards A Generalist Code Embedding Model Based On Massive Data Synthesis", Li, C. et al., is 2505.12697 (already DEV-007). The NeurIPS 2025 venue is confirmed by Crossref (Advances in Neural Information Processing Systems 38).
  2. CoRNStack: the cited title "... for Better Code Ranking" is the title of arXiv v1 and v2; the current version v3 (the one read in full) is titled "CoRNStack: High-Quality Contrastive Data for Better Code Retrieval and Reranking". Authors, year and ICLR 2025 venue confirmed.
  3. KGCompass: the cited author order (Yang, Tian, Ren, Jin, Liu, Liu, Le) is that of v1; v3 (read in full) lists Yang, B., Ren, J., Jin, S., Liu, Y., Liu, F., Le, B., Tian, H. First author and year unchanged.
  4. CoSIL: the cited title "CoSIL: Software Issue Localization via LLM-Driven Code Repository Graph Searching" is that of v1; v2 is "CoSIL: Issue Localization via LLM-Driven Code Graph Searching" and v3 (read in full) "Issue Localization via LLM-Driven Iterative Code Graph Searching". The reference gives no author: first author Jiang, Z. (2025); venue ASE 2025 per the arXiv comments of v2 and v3.
  5. SpIDER: `knowledge/papers/README.md` gives the venue as ICML 2026; the arXiv comment of v3 says "EMNLP 2026 camera-ready" (v1 and v2: "Initial preprint"). First arXiv version December 2025; first author Chaudhari, S.
  6. OpenHands: cited without an identifier; arXiv 2407.16741, "OpenHands: An Open Platform for AI Software Developers as Generalist Agents", first author Wang, X., 2024, comment "Accepted by ICLR 2025": title, first author and venue confirmed.
  7. Agent Retrieval Bench: cited without an author; first author Qin, B. (2026). Title and identifier confirmed.
  8. Loc-Bench: "660 examples; bug 282, feature 203, security 31, performance 144" is LocAgent v1; v2 (read in full) has 560 (242 / 150 / 29 / 139); the released dataset has 560 rows in V1 and 660 in V0.2 with other category counts (already DEV-001, DEV-005).
  9. CORE-Bench: cited without a venue; the arXiv comment of v3 says "Accepted By EMNLP 2026 Main". Title, eight authors in the cited order and year confirmed.
- Confirmed without mismatch (identifier, title, first author, year): SweRank (2505.07849; ICLR 2026 per the arXiv comment), LocAgent (2503.09089; ACL 2025 per Crossref), SWE-bench (2310.06770; arXiv 2023, cited by its ICLR 2024 year), Sun et al. (2202.06649, ICSE 2022), Rethinking Negative Pairs (2310.08069, EMNLP 2023), Agentless (2407.01489), SWE-agent (2405.15793), CodeRAG-Bench (2406.14497), SweRank+ (2512.20482), LARGER (2605.16352), GREPO (2602.13921), ARISE (2605.03117), PyCG (2103.00587; ICSE 2021 per Crossref), Jarvis (2305.05949; the ICSE 2023 venue was not found on arXiv or by a Crossref title search, so it stays unconfirmed), DyPyBench (2403.00539; FSE 2024, published in Proceedings of the ACM on Software Engineering per Crossref), GraphLocator (2512.22469), SemNav (2609.31176), SWE-Explore (2606.07297), Exploration Structure (2606.11976), CodeGrep (2608.05886), RLHN (2505.16967; EMNLP 2025 Findings), Cost-Effective Exploration (2608.29675; Al Awad and Ivanov), the five scan candidates (2605.04615, 2604.16021, 2410.00603, 2512.20957, 2105.03099), Total Recall? (Helm et al., ISSTA 2024, DOI 10.1145/3650212.3652114 per Crossref).
- Why: arXiv abstract pages and Crossref records fetched on 2026-10-23; the metadata as found, with a status per identifier, is in `results/tables/h_reference_audit.csv` (36 rows: the 35 cited identifiers plus OpenHands).
- Impact: references only; no figure used in an experiment changes. Corrected in the derived copies with the marker of DEV-010; the master document is the engineer's to correct.
- Reversible: yes.
- Related: DEV-005, DEV-007, DEV-010

## DEV-012 — The negative policy is held identical across the four RQ2 arms   (2026-10-25 · status: proposed)
- Master says: `docs/08_experimental_design.md`, "The four supervision arms": RAW uses "random in-batch" negatives, FILTER, WEIGHT and CURRICULUM use "mined hard" negatives; "Varies: the supervision strategy, and nothing else."
- We do: the training stack holds the negative policy identical across the arms; an arm enters only through three hooks (example filter, per-example weights, ordering), and a comparison of arm configurations that differ in the negative policy is refused (`ril/training/training.py`, `check_comparable`). This follows the answer to the previous wave's pushback ("structural negatives stay out of the four arms ... with the negative policy held identical across arms", ADR-003 addendum) and open question Q46. Which policy is held (random repository-local, teacher top-M, teacher top-M with a positive-relative cut) is open.
- Why: with the table as written, RAW would differ from the other arms in two things (supervision of positives and the negative source), so a RAW-versus-FILTER difference could not be attributed to filtering. The two statements in the master section conflict; the code takes "nothing else varies".
- Impact: RQ2's definition of RAW. It changes what is held identical, so ADR-002 owns it. If the engineer keeps the master's table, the negative policy becomes a fourth hook (one configuration key moves from the held-identical part to the arm; the identity test gains a case); the data loader already takes the policy as a parameter.
- Reversible: yes, at the cost of that change and of stating RAW's two differences in the report.
- Related: ADR-002, ADR-003, Q46
- Status update 2026-10-29: the engineer's default D28 keeps the negative policy identical across the arms (primary: random repository-local; secondary, exploratory: teacher top-M with the score-relative cut); the entry stays `proposed` until ADR-002 is settled.

## DEV-013 — Pilot batch shape smaller than the master's and than SweRank's   (2026-10-29 · status: proposed)
- Master says: `docs/08_experimental_design.md`: batch size = the number of in-batch negatives; SweRank's recipe uses batch 64 with 15 hard negatives (1,024 documents per update).
- We do: the pilots hold 32 x (1+1), float16 autocast, gradient checkpointing, 512 tokens identical across arms (engineer default D31).
- Why: the larger shapes do not fit the 11 GB cards reachable from the cluster account; the chosen shape is the largest measured to fit for the 137M base (2.65 s per update). The 0.6B alternative encoder does not take one float32 AdamW step on these cards at any batch size (ADR-006 addendum).
- Impact: fewer in-batch negatives than the master's recipe; absolute pilot numbers are not comparable with SweRank's. The "held identical" block of `docs/08_experimental_design.md` is not edited; ADR-002 owns the final batch.
- Reversible: yes (gradient caching, a larger card, or a smaller held-identical batch are the options, Q53).
- Related: ADR-002, ADR-006, Q53

## DEV-014 — The matched-pool arms pilot ran a reduced design   (2026-10-31 · status: proposed)
- Master says: `docs/ROADMAP.md` milestone 12: four RQ2 arms, three seeds each; the Wave 6 plan: three seeds at 100 updates, three independent subsample draws per seed, ansible among the dev repositories, a second stage at 1,000 updates for RAW, the subsample and the two largest cells with two seeds.
- We do: two seeds instead of three at 100 updates; one subsample draw per seed (draw 0) instead of three (configurations for draws 1 and 2 exist, not run); Pro ansible not evaluated in any cell (five dev repositories, 351 L2 and 155 L3 queries); stage 2 at 1,000 updates on seed 0 only, with RAW, the subsample and WEIGHT (FILTER with SweRankEmbed-Small and the second seed not run).
- Why: measured per-run cost exceeded the plan (0.38 GPU-hours at 100 updates, 1.06 at 1,000; stage 2 about 8.5 GPU-hours against the planned 3) and Block 2 had 46 GPU-hours, 45.15 used. Ansible's 274k unit texts serve L2 and L3 alike and cost 20 minutes a run.
- Impact: intervals carry query sampling only and are descriptive; the minimum detectable difference at three seeds (1.4 L2, 1.7 L3) exceeds every observed gap, so the pilot cannot rule out smaller effects. The stage 2 subsample (4,592 distinct examples against 5,000) is below the common unique count and is flagged. Nothing here enters the pre-registered RQ tables.
- Reversible: yes, at about 2.6 GPU-hours per extra seed and 0.4 per extra subsample draw run at 100 updates.
- Related: ADR-002, ADR-001


## DEV-015 — Mined positives are the innermost unit that owns an edited line, not every unit whose span overlaps a hunk   (2026-11-02 · status: proposed)
- Master says: functions touched by the patch become positives (`docs/04_data_and_ground_truth.md`, "The mining recipe"); the brief of the unfiltered set (D63) words it as every unit of the base commit whose line span overlaps a changed old-side hunk.
- We do: a removed or rewritten old line belongs to the smallest function, method or class that holds it, else to the file's residual module unit; a pure insertion belongs to the unit that strictly contains the gap, or at a unit's edge to the unit it visibly extends (added decorator lines, deeper-indented lines after its last line); an inserted block that is only complete function or class definitions adds units and edits none (`ril/data_mining/mapping.py`).
- Why: the module unit's span is the whole file and a class unit's span holds its methods (`ril/parsing/repository_parser.py`), so a literal span overlap makes the module positive for every edit and a class positive for every method edit; no function-level pool positive is a class. The edge rules are needed because a diff gives insertions as gaps, and a decorator added above a function lies outside its old span.
- Impact: positives per pull request are lower than under literal overlap; class-level and module-level edits appear only when the edit is in the class body or the module residual. The kind and the line counts are stored per positive, so another attribution can be computed later from the same snapshots. Evidence class: reasoned from the parser's span rules, tested on hand-built fixtures (`tests/unit/test_mining_diff_mapping.py`); the agreement with the published pool is the M1 measurement.
- Reversible: yes (recompute from the stored base commits; no re-fetch of diffs if the patches are kept).
- Related: ADR-001, `docs/experiments/B.md` E-MINE-PILOT

## DEV-016 — Class and module positives are kept in a side table, not in the qrels, by default   (2026-11-02 · status: proposed)
- Master says: keep every positive (the brief of the unfiltered set, D63: test units and module-level units kept with a flag).
- We do: `corpus.jsonl` and the qrels hold the unit kinds in `corpus_kinds` (default function and method, as the published pool); positives of other kinds are stored in `<instance>/pr_meta.json` with `in_corpus: false`; `corpus_kinds: [function, method, class, module]` puts them in the qrels and the corpus.
- Why: the pool reader requires every positive to be in the corpus, and the published pool's corpus is functions only. A class or module unit added only when it is a positive would leak the label through the candidate set, so the choice is all kinds for every pull request or functions only for every pull request.
- Impact: pull requests whose only edits are class-body or module-level lines have no positive in the default set and are counted as `no_positive` with `positives_side_only`. Test-file positives stay in the qrels, flagged `is_test`.
- Reversible: yes (a configuration value; the side table holds the rest).
- Related: DEV-015, `ril/training/pool_reader.py`

## DEV-017 — One directory per pull request; a pull request that closes several issues is one directory with the primary issue's text   (2026-11-02 · status: proposed)
- Master says: the brief (D61, D66): the unit is the (issue, PR) pair, and the output is one directory per PR in the pool's format.
- We do: every pair is stored in `<instance>/pr_meta.json` (`pairs`, with `primary`) and counted in the multiplicity table; the directory `owner__name-<PR>` carries one query, the text of the primary issue (same repository first, then the lowest number).
- Why: the reader takes the final `-<digits>` of the directory name as the pull request number and a directory holds exactly one query, so two pairs of one pull request cannot be two directories without changing the reader or the name contract. The positives of the pairs of one PR are identical anyway.
- Impact: the pair count exceeds the directory count by the number of extra issues; a training set that wants every pair as an example needs the other issues' text, which the listing files hold. A change to the name contract is the lead's decision.
- Reversible: yes.
- Related: `ril/training/pool_check.py` `split_instance_dir`

## DEV-018 — Pilot size read as a seeded sample of the linked pull requests; added functions counted from the patch text   (2026-11-02 · status: proposed)
- Master says: the brief (D60, D63): pilot of 200 repositories, up to 2,000 PRs; record the added-function count per PR.
- We do: all merged pull requests of the 200 repositories are listed with their closing issues (GraphQL, cheap), and `max_prs` = 2,000 of the linked ones are mined, chosen by `sha256("0:<repo>#<number>")` order; the added-function count is the number of function names defined by added lines and not by removed lines of the same file (a multiset difference over the patch text; nested definitions and renamed functions count as added or removed accordingly).
- Why: the selection analysis needs each repository's full count of linked pull requests, and taking the first 2,000 pull requests repository by repository would fill the pilot with a handful of repositories. The head commit is not fetched, so the count cannot come from parsing it.
- Impact: the mined sample is a draw across repositories, the share kept by the pool is computed on the full listing and the property comparison (kept against dropped) on the sample; `added_function_defs` is an approximation, stated as such wherever it is reported.
- Reversible: yes.
- Related: `docs/experiments/B.md` E-MINE-PILOT
