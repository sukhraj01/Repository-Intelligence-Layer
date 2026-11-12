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


## DEV-015 — Mined positives are the innermost unit that owns an edited line, not every unit whose span overlaps a hunk   (2026-11-02 · status: accepted (D83))
- Master says: functions touched by the patch become positives (`docs/04_data_and_ground_truth.md`, "The mining recipe"); the brief of the unfiltered set (D63) words it as every unit of the base commit whose line span overlaps a changed old-side hunk.
- We do: a removed or rewritten old line belongs to the smallest function, method or class that holds it, else to the file's residual module unit; a pure insertion belongs to the unit that strictly contains the gap, or at a unit's edge to the unit it visibly extends (added decorator lines, deeper-indented lines after its last line); an inserted block that is only complete function or class definitions adds units and edits none (`ril/data_mining/mapping.py`).
- Why: the module unit's span is the whole file and a class unit's span holds its methods (`ril/parsing/repository_parser.py`), so a literal span overlap makes the module positive for every edit and a class positive for every method edit; no function-level pool positive is a class. The edge rules are needed because a diff gives insertions as gaps, and a decorator added above a function lies outside its old span.
- Impact: positives per pull request are lower than under literal overlap; class-level and module-level edits appear only when the edit is in the class body or the module residual. The kind and the line counts are stored per positive, so another attribution can be computed later from the same snapshots. Evidence class: reasoned from the parser's span rules, tested on hand-built fixtures (`tests/unit/test_mining_diff_mapping.py`); the agreement with the published pool is the M1 measurement.
- Reversible: yes (recompute from the stored base commits; no re-fetch of diffs if the patches are kept).
- Related: ADR-001, `docs/experiments/B.md` E-MINE-PILOT

## DEV-016 — Class and module positives are kept in a side table, not in the qrels, by default   (2026-11-02 · status: accepted (D83))
- Master says: keep every positive (the brief of the unfiltered set, D63: test units and module-level units kept with a flag).
- We do: `corpus.jsonl` and the qrels hold the unit kinds in `corpus_kinds` (default function and method, as the published pool); positives of other kinds are stored in `<instance>/pr_meta.json` with `in_corpus: false`; `corpus_kinds: [function, method, class, module]` puts them in the qrels and the corpus.
- Why: the pool reader requires every positive to be in the corpus, and the published pool's corpus is functions only. A class or module unit added only when it is a positive would leak the label through the candidate set, so the choice is all kinds for every pull request or functions only for every pull request.
- Impact: pull requests whose only edits are class-body or module-level lines have no positive in the default set and are counted as `no_positive` with `positives_side_only`. Test-file positives stay in the qrels, flagged `is_test`.
- Reversible: yes (a configuration value; the side table holds the rest).
- Related: DEV-015, `ril/training/pool_reader.py`

## DEV-017 — One directory per pull request; a pull request that closes several issues is one directory with the primary issue's text   (2026-11-02 · status: accepted (D83))
- Master says: the brief (D61, D66): the unit is the (issue, PR) pair, and the output is one directory per PR in the pool's format.
- We do: every pair is stored in `<instance>/pr_meta.json` (`pairs`, with `primary`) and counted in the multiplicity table; the directory `owner__name-<PR>` carries one query, the text of the primary issue (same repository first, then the lowest number).
- Why: the reader takes the final `-<digits>` of the directory name as the pull request number and a directory holds exactly one query, so two pairs of one pull request cannot be two directories without changing the reader or the name contract. The positives of the pairs of one PR are identical anyway.
- Impact: the pair count exceeds the directory count by the number of extra issues; a training set that wants every pair as an example needs the other issues' text, which the listing files hold. A change to the name contract is the lead's decision.
- Reversible: yes.
- Related: `ril/training/pool_check.py` `split_instance_dir`

## DEV-018 — Pilot size read as a seeded sample of the linked pull requests; added functions counted from the patch text   (2026-11-02 · status: accepted (D83))
- Master says: the brief (D60, D63): pilot of 200 repositories, up to 2,000 PRs; record the added-function count per PR.
- We do: all merged pull requests of the 200 repositories are listed with their closing issues (GraphQL, cheap), and `max_prs` = 2,000 of the linked ones are mined, chosen by `sha256("0:<repo>#<number>")` order; the added-function count is the number of function names defined by added lines and not by removed lines of the same file (a multiset difference over the patch text; nested definitions and renamed functions count as added or removed accordingly).
- Why: the selection analysis needs each repository's full count of linked pull requests, and taking the first 2,000 pull requests repository by repository would fill the pilot with a handful of repositories. The head commit is not fetched, so the count cannot come from parsing it.
- Impact: the mined sample is a draw across repositories, the share kept by the pool is computed on the full listing and the property comparison (kept against dropped) on the sample; `added_function_defs` is an approximation, stated as such wherever it is reported.
- Reversible: yes.
- Related: `docs/experiments/B.md` E-MINE-PILOT

## DEV-024 — "Kept by the published pool" is taken over the whole filtered pool, not the 5,000 selected directories   (2026-11-02 · status: proposed)
- Master says: the brief (D60): the selection is measurable as "the share of each repository's linked merged PRs that the published pool kept".
- We do: the repositories are those of the first 5,000 directories (D41); a pull request counts as kept by the pool if it is any directory of the pool left after the held-out filter (20,800 directories), for the repositories of the population. The first build counted only the 5,000 selected directories; in the first live listing of four repositories that gave 11 kept of 2,145 linked pull requests, which understates the pool by construction (the 5,000 are a sample of the pool's directories).
- Why: the question asks what the published pool kept, not what a 5,000-directory sample of it kept. The repository population stays as D60 states.
- Impact: `Population.published` is larger; the earlier session counts (smoke run `runs/validation`, 20 pull requests) are not reported. Test: `tests/unit/test_mining_population_snapshot.py`.
- Reversible: yes (a one-line change, no stored data depends on it).
- Related: DEV-015 to DEV-018, `ril/data_mining/population.py`

## DEV-025 — Stage M1 mines the pool's pull requests first and stops after 62 attempts, not every linked pull request of five repositories   (2026-11-02 · status: proposed)
- Master says: the brief (M1): five seeded repositories, all their linked merged pull requests mined.
- We do: `configs/mining/validation.yaml` sets `published_first: true` and `max_prs: 300`: every linked pull request that the published pool holds is mined first (45 of them in these repositories), then the seeded order fills the rest. The stage was stopped after 62 attempts (45 pool pull requests and 17 of the seeded order), because the pool's pull requests are all that the agreement is measured on, and the rest would only have added hours. The listing bound of 400 pages was raised to 2,000 pages of 50 pull requests: one of the five repositories (airflow) has more merged pull requests than 400 pages hold (the first listing stopped on the bound; the other four listings were reused).
- Why: the four listed repositories alone have 2,145 linked pull requests, and the base commit of each must be fetched (a shallow fetch of the airflow base commit took 100 to 300 s in the measurements of 2026-11-02, `results/mining/m1_agreement.md`); taken at seeded random, the pool's pull requests would be about 1 in 40 of the mined ones and the agreement would rest on a handful.
- Impact: the yield figures of M1 describe a published-first sample and are not reported as yield (the yield comes from M2, which has `published_first: false`); the agreement rests on all 42 mined linked pool pull requests of the five repositories (3 of the 45 are quarantined as unparseable).
- Reversible: yes (rerun with a larger cap).
- Related: DEV-018, DEV-024, `configs/mining/validation.yaml`

## DEV-026 — Speed and storage changes found necessary on the live run; one of them corrects an output   (2026-11-02 · status: proposed)
- Master says: the brief (D63, D66): the base-commit snapshot is a sparse checkout of Python files; the output directory is the pool's format; an API client with conditional requests.
- We do: (1) **Correction.** The first snapshot reader used `git archive`, which honours `export-ignore` in a repository's attributes and silently left out whole directories (airflow's `providers/tests`): 19 of the first 51 airflow pull requests were quarantined as `old_file_missing_at_base`, and corpora lacked those files. The reader now walks the commit's tree (`ls-tree`, `cat-file --batch`); the output of the first runs (`runs/validation`, `runs/m1`) was discarded and is not used anywhere. (2) The shallow fetch of the next pull requests' base commits runs in background threads (`--lookahead`, 4 for M1; one bare repository per commit, removed after use), with the compare calls made ahead; pull requests are still mined and recorded in the selected order, so the outputs do not depend on it (tested byte for byte). (3) The run root stores `corpus.jsonl.gz` (fixed header, bytes repeat); `pack` writes the plain `corpus.jsonl` member, so the archive and the reader are unchanged. (4) The ETag cache is off in the pilot (`--etag-cache` turns it on): every URL is requested once, so no stored response is reused, and each costs a file and its compressed body. (5) The listing stage can be split over jobs (`--list-only --shard i n`), writing listing files only.
- Why: measured on the live service (job logs of 2026-11-02): a shallow fetch of a large repository's base commit takes 100 to 300 s, a sequential run did about 6 pull requests per hour in its worst stretch, a write of a 33 MB corpus to the home file system stalled for more than 20 minutes (`dd` of 50 MB with `fsync` gave 1.1 MB/s on the login node), and one repository's merged pull requests need about 1,000 listing pages at 3 to 5 s each.
- Impact: (1) is a bug fix: corpora now contain every Python file of the commit; the test-function share of the corpus is large (see `results/mining/m1_agreement.md`). (2) to (5) change speed and bytes only.
- Reversible: (2) to (5) yes (flags); (1) no, and should not be.
- Related: DEV-015 to DEV-025, `ril/data_mining/snapshot.py`, `ril/data_mining/files.py`

## DEV-027 — Stage M3 reads the pool-like corpora, on a seeded prefix of 300 directories, and two dense passes were not completed   (2026-11-03 · status: proposed)
- Master says: the brief (M3): ranks under BM25, CodeRankEmbed and SweRankEmbed-Small for the pilot directories, stage limit 2 GPU-hours.
- We do: the pool-like reading (no test-file function in the corpora, no test positive; the pool has neither, `results/mining/m1_agreement.md`) on the first 300 directories of the seeded order `sha256("0:<directory>")` that keep a positive; BM25 and SweRankEmbed-Small on all 300, CodeRankEmbed on 254 (the job reached its time limit; directories run repository by repository); SweRankEmbed-Small on the stored text and the dense teachers in the as-mined reading were not run (BM25 only, on 300 directories, in the as-mined reading).
- Why: `rank-estimate` on the first 252 mined directories counted 1,268,309 distinct function texts (542,660 outside tests), i.e. 3.3 and 1.4 GPU-hours for three passes at 320 texts per second (rate of ledger job 38202); the measured rate in this run was 178 texts per second (423,981 texts in 2,378.5 s), so even the pool-like pass needed more than estimated. 0.7 GPU-hours were spent by jobs that produced no ranks (a command-line error, CPU preparation inside a GPU job, and a node whose file-system client hung before the model loaded). Total 1.99 of 2.0.
- Impact: the dense shares rest on 300 and 254 directories (89 and 72 repositories), above the 100-directory minimum of the reading rule; the CodeRankEmbed set is whole repositories, not a random part; no stored-text comparison with the 19.3% Verified row.
- Reversible: yes (rerun the remaining passes with `mine_ranks.sbatch`; ranks are resumable per directory and teacher; needs about 1 more GPU-hour for the missing 46 directories and 2 for the stored-text pass).
- Related: DEV-024 to DEV-026, `docs/COMPUTE.md`

## DEV-019 — The base encoder is CodeRankEmbed, not Qwen3-Embedding-0.6B   (2026-11-03 · status: accepted by the lead, ADR-006)
- Master says: open decision 6 recommends Qwen3-0.6B ("CORE-Bench reports strong post-SFT results at CPU-feasible size").
- We do: CodeRankEmbed is trained in RQ2; Qwen3-Embedding-0.6B is used zero-shot only.
- Why (measured, E-ENCODER-NUMBERS): Qwen3 runs out of memory at every batch shape from 32 to 1 on 10.57 GiB usable, and no card above 11 GB is reachable; CodeRankEmbed trains at 12.2 to 12.4 examples/s with a peak of 6,880 MiB. Zero-shot, RRF(BM25, Qwen3) is ahead of RRF(BM25, CodeRankEmbed) by about 4 points on dev, but three of four Verified-six intervals include 0.
- Impact: RQ2 and RQ3 claims are scoped to the CodeRankEmbed base; nothing is said about Qwen3 after fine-tuning. The retrieval stack is unchanged.
- Reversible: yes, if a card of about 24 GB becomes reachable and an adapter recipe is tested on RAW (one day of cluster time, D34).
- Related: ADR-006, E-ENCODER-NUMBERS

## DEV-028 — The memory fix streams the corpus file; listings are not streamed   (2026-11-03 · status: proposed)
- Master says: the brief of the scale-up preparation (prompt 27, item 3): implement streamed listings so a run over all 1,473 repositories fits in the memory limit.
- We do: the corpus of a mined directory is streamed into its compressed file (`write_gzip_lines`, `ril/data_mining/store.py`) instead of being built as one string; listings stay in memory.
- Why: measured, not assumed: the 200 pilot listings take 265 MB in memory (job 55965), about 2 GB by the same ratio for 1,473 repositories, whereas the 10.0 GB peak of the pilot came from the largest snapshot (630,017 functions): 3.8 GB after mining it and 7.8 GB after building the file bytes. With the streamed writer the same pull request peaks at 3.8 GB (4.0 GB in `sacct`), and a repeat of the 462 mined pull requests of the first 20 repositories peaks at 3.16 GB with all directories byte-identical.
- Impact: none on outputs (462 of 462 directories and the largest one identical to the pilot's). Whether a full-population run fits 10 GB is an estimate (about 4 GB snapshot + 2 GB listings + fetches), not a measurement at that scale.
- Reversible: yes. Streamed listings remain an option if the estimate is wrong.
- Related: DEV-026, `results/mining/full_run_plan.md`

## DEV-020 — Primary update count is 100, not 20,000   (2026-11-03 · status: accepted by the lead, D68)
- Master says: `docs/08_experimental_design.md`: optimizer updates, target 20,000, identical across arms.
- We do: every arm trains for 100 updates of a 3,000-update schedule (warm-up 7, linear decay), matched across arms; 1,000 updates is a sensitivity check on a subset of cells.
- Why (measured, E-PILOT-CURVE): the RAW encoder reaches its gain by 100 updates and stays flat to 2,000 (increments within 1.0 point). A 20,000-update run costs about 15 GPU-hours for training alone (reasoned, E-TRAIN-STACK); a 100-update run with its dev evaluation costs 0.37 to 0.45.
- Impact: a supervision effect that appears only after the curve is flat would not be seen; the claim is scoped to short fine-tuning (protocol threat 6). Matched optimization budgets is unchanged: updates and distinct examples are matched.
- Reversible: yes, at the cost of the longer runs and a larger mined pool (32 x N distinct pairs for N updates).
- Related: ADR-002, `docs/RQ2_PROTOCOL.md` O1, DEV-013, DEV-014

## DEV-021 — FILTER and WEIGHT act at the positive level with a BM25 or SweRankEmbed-Small teacher; no self-teacher cells   (2026-11-03 · status: accepted by the lead, D70)
- Master says: `docs/08_experimental_design.md`: FILTER and WEIGHT use SweRank's K-rank; the arm table gives mined hard negatives to FILTER, WEIGHT and CURRICULUM.
- We do: K = 20 at the positive level; BM25 is the primary teacher and SweRankEmbed-Small is reported with the caveat that it shaped the public pool; the base encoder is never its own teacher. The negative policy is identical across arms (DEV-012).
- Why: K = 20 is SweRank's published reference point (one run per point, no seeds), not a tuned value; the master's rule is a separately pretrained encoder, and a self-teacher is the self-confirming case.
- Impact: the K-rank of the arms is a published signal applied at one level; K and weight-form sweeps are exploratory.
- Reversible: yes (configuration).
- Related: ADR-002, DEV-012, `docs/RQ2_PROTOCOL.md` O3

## DEV-022 — If the arms do not separate, RQ3 contrasts RAW with the untrained encoder   (2026-11-03 · status: accepted by the lead, D80)
- Master says: RQ3 uses the retrievers from RQ2; the fallback for fewer than two distinguishable retrievers is to cut RQ3 (`docs/10_timeline_and_fallback.md`).
- We do: declared before any final run, if no pair of arms is distinguishable by the rule of `docs/RQ2_PROTOCOL.md` section 6, RQ3 contrasts RAW with the untrained encoder. This measures "does training help" (measured retrieval difference about +9.6 L2 and +11.1 L3 at 100 updates, E-PILOT-ARMS2), not "does supervision quality help", and is labelled so wherever it appears.
- Why: it needs no arm to separate and tests whether a retrieval gain of that size reaches the resolved rate.
- Impact: it redefines what RQ3 measures in that branch; it never replaces the four-arm contrast when the arms separate.
- Reversible: yes; it is declared in advance so it cannot be chosen after seeing results.
- Related: `docs/RQ2_PROTOCOL.md` O13

## DEV-023 — A pull-request label sheet is added for the noise audit   (2026-11-03 · status: accepted by the lead, D78)
- Master says: no noise audit of mined labels is specified.
- We do: a new sheet (relevance of each edited function to its issue, three-way verdict, reason) for the audit of the mined set. The existing second-reader sheet is for call-edge labels (ADR-012) and stays separate.
- Why: the audit estimates the share of harmful pairs and what a K-rank filter can find (protocol section 7); the call-edge sheet does not apply.
- Impact: adds person-time (about 8 hours per reader for 400 pairs); no effect on what is held identical.
- Reversible: yes.
- Related: ADR-002, `docs/RQ2_PROTOCOL.md` O11

## DEV-029 — The mined-set pilot is evaluated on the five dev repositories without ansible, not on six   (2026-11-03 · status: proposed)
- Master says: the brief of the mined-set integration pilot (D91): evaluation "on the six dev repositories for L2 and every dev repository with L3 labels as in Waves 6 and 7", at the measured 0.45 GPU-hours per run, with the stage aborted above 3.2 GPU-hours.
- We do: the evaluation set of Waves 5 to 8: openlibrary and qutebrowser at L2 and L3, conan, haystack and streamlink at L2 (five repositories, 351 L2 and 155 L3 queries), the same configuration file and query set as E-PILOT-ARMS2 (`configs/experiments/e1_bm25_reproduction.yaml`). Pro ansible is not evaluated.
- Why: the brief's own anchors disagree. Waves 6 and 7 did not evaluate ansible (E-STORED-ANALYSIS lists the set as five L2 and two L3 repositories), the 0.45 GPU-hours per run was measured on that set, and reading (ii) needs "same code, same evaluation" against the stored Wave 6 RAW rows, which exist for these five repositories only (no checkpoint is retained, so ansible could not be added to them without a retrain). An evaluation with ansible costs about 0.33 GPU-hours more per run (`docs/experiments/B.md`, checkpoint inventory), i.e. about 0.78 per run and 4.7 for six runs, above the 3.2 abort limit. The two readings of "six" cannot both hold; the one that keeps the comparison and the cost is used.
- Impact: five L2 and two L3 repositories, so the repository-clustered intervals rest on two L3 repositories (stated beside every L3 number); no ansible column. The number of dev repositories in the brief (six) is not met.
- Reversible: yes. An ansible evaluation needs a retrain of every cell it covers (about 0.78 GPU-hours per run) and the Wave 6 RAW cells retrained as well for reading (ii).
- Related: `docs/experiments/B.md` E-MINED-PILOT, `docs/COMPUTE.md`

## DEV-030 — The pool-like reading of the mined pilot keeps `async def` functions, as the BM25 numbers of the earlier stage did   (2026-11-03 · status: proposed)
- Master says: the brief (D89): the mined pilot directories "in the pool-like reading (no test functions or test positives, no async def; the reading used in M3)"; D90: the first 300 directories must reproduce the M3 BM25 numbers exactly.
- We do: the reading that M3 actually used, `READING=non_test` (`rank-prepare --drop-tests`): no test-file function in the corpora, no test positive, directories left without a positive dropped. Functions defined with `async def` stay in the corpora and as positives.
- Why: the M3 reading did not remove `async def` functions (`ril/data_mining/pack.py` `instance_bytes` drops test-file functions only; `results/mining/m3_ranks.md` lists the reading as "no test-file functions, no test positives"); "no async def" describes the published pool's corpora (M1: 43 of the mined extras are absent from the pool for that reason), not a filter of M3. Removing them would change every candidate set and the reproduction of the M3 ranks to the last digit (D90) would fail by construction.
- Impact: the mined training set contains async functions and positives that the published pool never has (4,637 mined-only `async def` functions outside tests in the M1 sample); stated beside every comparison with the pool.
- Reversible: yes (a corpus filter in `instance_bytes`); a different reading needs new ranks and new runs.
- Related: `results/mining/m3_ranks.md`, DEV-027, DEV-029

## DEV-031 — The mined set gets a labelled "pool-aligned" reading as a view; a sensitivity reading beside the primary `non_test` reading   (2026-11-05 · status: proposed (D95); the default amended by D96)
- Master says: the brief of the unfiltered set (D63) keeps every unit that owns an edited line and every non-test function; DEV-015 accepts the miner's positives (the innermost unit that owns a removed or rewritten line, plus the unit a pure insertion visibly extends); DEV-030 records that the M3 reading kept `async def`.
- We do: three readings of one run root, selected by name and never by re-mining (`ril/data_mining/readings.py`, `--reading` of `pack` and `rank-prepare`): `unrestricted`, `non_test` (the M3 reading), and `pool_aligned` (a sensitivity reading for comparisons with the published pool; D95 first named it the default, D96 of 2026-11-05 keeps `non_test` as the primary reading, evidence class measured on 300 directories, exploratory: the no-positive-in-top-10 share is 53.3% under both, 160/300 and 128/240 with interval [47.0, 59.5]; the reading drops 20% of the directories and needs new ranks and cells). `pool_aligned` drops from the corpus every `async def` function and every function whose repository-relative path contains `test` in any case (a substring, as the released code tests it), keeps a positive only if it is still in that corpus and owns a removed or rewritten old-side line (`removed_lines > 0` in the directory's metadata), and drops a directory left with no positive.
- Why: the sources (`docs/POOL_CONSTRUCTION.md`) define the pool's corpus and positives by these rules; the mined data carries what a view needs (the corpus rows and, per positive, the removed and inserted line counts), so no re-mining is needed. Note a correction of the brief's wording: D95 says added-only functions are not positives "already DEV-015"; DEV-015 does keep positives that only received inserted lines (a pure insertion at a unit's edge; 42 mined extras in M1), so the view applies the rule through `removed_lines > 0` and the unrestricted reading keeps them.
- Not reproduced (the rows are not mined): nested functions and vendored directories, which the released code keeps; the released code tests the lower-cased path from the structure root, which starts with the repository folder name, while the view tests the repository-relative path, so a repository whose own name contains `test` is not excluded wholesale here. `async def` is recognised from the first definition line of a row's text; the check agrees with the syntax tree on every function and method of the standard library's `asyncio` package (`tests/unit/test_mining_readings.py`).
- Impact: a different candidate set and fewer positives than the M3 reading; every earlier number (M3, E-MINED-PILOT) is the `non_test` reading and keeps its label. Moving the E-MINED-PILOT training inputs to this reading needs new ranks and new cells (not done).
- Reversible: yes (a view; the default is one constant, `DEFAULT_READING`, now `non_test`).
- Related: DEV-015, DEV-030, Q61, `docs/POOL_CONSTRUCTION.md`, `docs/experiments/B.md` E-MINE-STORE

## DEV-032 — The full mining run keeps a de-duplicated store on a shared home and mines on node-local disk   (2026-11-05 · status: proposed (D93, D94))
- Master says: the plan of the scale-up preparation (`results/mining/full_run_plan.md`, 2026-11-03): the run root, one `corpus.jsonl.gz` per directory, lives on a shared area; the size of the full run was "disk binds first".
- We do: the miner can write rows once per repository plus a manifest per pull request (`--store-layout dedup`, `ril/data_mining/cas.py`); `materialise` rebuilds today's directory layout on node-local disk for a job, byte-identical to the directories the miner wrote before; a job mines in node-local space and pushes the store and run state to a shared home every 25 outcomes or 10 minutes (`ril/data_mining/durable.py`) and restores from it on a node that has none. The readers (`pool_reader`, rank tooling, training) are unchanged.
- Why: D93 and D94 (disk: 25.6 GB for 20,000 attempted as stored before; the target is 10,000). The layout is not part of the configuration hash because the materialised bytes are identical.
- Impact: none on outputs where the check ran (`docs/experiments/B.md` E-MINE-STORE); a run root has one layout (recorded in the run record; a mismatch is refused). Work done since the last push is lost on a node failure; the bound is the sync interval.
- Reversible: yes; a store converts back to directories with `materialise`.
- Related: DEV-026, DEV-028, `results/mining/dedup_measure.md`

## DEV-033 — Context assembly takes units in rank order and does not attach callee signatures   (2026-11-06 · status: proposed (D102))
- Master says: `assemble()` dedupes overlapping units, orders them for truncation survival, attaches callee signatures and applies a hard token budget (`docs/09_architecture.md`, `ril/retrieval/README.md`).
- We do: first-fit in rank order under a per-unit cap and a hard budget, blocks ordered by file and line for the reader, class units in header form; no callee signatures, no overlap deduplication beyond repeated unit ids (`specs/assembly.md`, ADR-014).
- Why: callee signatures are a graph-derived addition whose value is unmeasured (E-GRAPH-ROLE found no benefit of typed edges over the same-file control); a policy that reads only the ranked list, the unit text and the budget keeps assembly identical across arms by construction.
- Impact: the agent sees less context per unit than the master document describes; the budget is spent only on units the ranker chose.
- Reversible: yes (assembly is the last stage; an option can be added behind a flag and reported separately).
- Related: ADR-014, `specs/assembly.md`, `docs/experiments/B.md` E-ASSEMBLY


## DEV-034 — The miner's transport treats a cut response body as a network failure, and a listing job pushes what it has finished   (2026-11-06 · status: proposed)
- Master says: the plan of the full run (`results/mining/full_run_plan.md`): the API client retries network-level failures; a listing job pushes its listing files to the store at its end (DEV-032).
- We do: `UrllibTransport` converts `http.client.HTTPException` (`IncompleteRead`, `RemoteDisconnected`) into `TransportError`, so the client's existing retry with backoff applies; a listing-only job pushes finished listings every `SYNC_SECONDS` and in a `finally`, so a job that fails keeps every listing it completed. No configuration value, sampling order, seed or target changed, and no output of a successful run differs.
- Why: all three listing jobs of E-MINE-FULL (60032, 60034, 60041) died after 2.6 to 3.0 hours on an unretried `IncompleteRead` of a GraphQL response body, and the listings they had finished lived only on node-local disk, so about three hours of listing per job were lost. The mining session reads the same client and would have hit the same fault.
- Impact: none on outputs; listing and mining jobs survive a truncated response (retried up to the client's retry limit, then still raised).
- Reversible: yes.
- Related: DEV-032, `docs/experiments/B.md` E-MINE-FULL, `tests/unit/test_mining_api.py`, `tests/unit/test_mining_dedup_store.py`


## DEV-035 — The full mining run rides out a network outage, refuses to mine on an incomplete listing, and quarantines a snapshot whose unit ids are rejected   (2026-11-07 · status: proposed)
- Master says: the plan of the full run (`results/mining/full_run_plan.md`): listing jobs, then mining sessions chained with `afterany`; the client retries network failures (DEV-034).
- We do: (1) `ClientConfig.network_retries` (default 12, about 14 minutes at the 120 s backoff cap) and `retries` 8 for server errors; (2) a mining session raises `ListingIncomplete` (exit code 4) when any repository could not be listed, and a listing-only job exits 4 when it left one out, so a dependent job is cancelled; (3) `mine_pr` quarantines a pull request whose snapshot makes the parser reject a unit id (reason `corpus_unit_id_rejected:ValueError`); (4) job layout: one listing-completion job (list-only, no shard; it reuses every stored listing), session 1 on `afterok:<listing>`, session 2 on `afterok:<listing>,afterany:<session 1>`, both with `--kill-on-invalid-dep=yes`. No configuration value, seed, sampling order or target changed.
- Why: the three listing jobs (61677 to 61679) died together after 6.5 hours on a name-resolution failure of about a minute, beyond five retries; session 2 (61681), released by `afterany` on a cancelled job, listed the missing third, silently skipped one repository whose listing failed (`googleapis/google-api-python-client`) and stopped after 150 pull requests on a Kannada identifier the id grammar rejects. A listing without a repository would change the seeded sample without a trace.
- Impact: on a successful run no output differs. Pull requests of a repository with a non-ASCII identifier in its snapshot are lost to quarantine (the reason is counted in the report); the pilot had none in 2,000, the rate at 10,000 is unknown until the report.
- Open design option (not decided): accept non-ASCII identifiers in unit ids. That changes the id grammar of the frozen CodeUnit (`specs/code_unit.md`, ADR-013): a version bump and a re-index plan. Cheapest check: the quarantine count in the report after session 1.
- Reversible: yes.
- Related: DEV-034, `docs/experiments/B.md` E-MINE-FULL, `tests/unit/test_mining_api.py`, `test_mining_pipeline.py`, `test_mining_jobs_summary.py`

## DEV-036 — A pull request's content can no longer end a mining session; the job relaunches the miner; a systemic quarantine rate stops the session   (2026-11-08 · status: proposed)
- Master says: the plan of the full run (`results/mining/full_run_plan.md`): sessions of 5,000 pull requests chained with `afterany`; a pull request that cannot be parsed completely is quarantined with its reason (DEV-035 added the unit-id case).
- We do: (1) `mine_pr` quarantines a pull request whose content raises an exception that no named reason covers, with the reason `corpus_error:<ExceptionClass>`; a `git` step of a pull request's base commit that runs past its 900 s limit is quarantined as `snapshot_timeout` and not retried. (2) Infrastructure errors are told apart by exception type (`ril/data_mining/failure.py`: API, URL, HTTP, connection, timeout, memory errors and an `OSError` whose errno is disk, quota, memory or network) and still end the miner process with a non-zero exit. (3) A session stops, after recording the row, with exit code 5 when more than 5% of its last 200 attempted pull requests are quarantined (`QUARANTINE_WINDOW`, `QUARANTINE_MAX_SHARE` in `runner.py`; session-level safeguards, not in the configuration hash). (4) The job script starts the miner again inside the same allocation up to 5 times after a non-zero exit, resuming from `state.jsonl` (`STOP_AFTER` counts only what is still missing); exit codes 3, 4 and 5 end the job and, with `DURABLE`, write a `HALT` file there that a following job refuses to run past (exit 6). (5) `GIT_HTTP_LOW_SPEED_*` makes git itself abort a stalled transfer after 120 s. (6) A failed session pushes the rows it recorded to the durable area. No configuration value, seed, sampling order or target changed.
- Why: sessions 63965 and 63966 on account C ended on a bare `subprocess.TimeoutExpired` (a `git fetch --depth 1` of one commit of a very large repository ran past 900 s), the first after 2 h 58 min and the second after 54 min, with 2,214 state rows between them; the same exception type had already stopped the label-audit job 60209. The miner handled `SnapshotError` only, so a timeout of the fetch process was not seen as a snapshot failure at all.
- Impact: pull requests whose base commit cannot be fetched within the limit leave the set, counted under `snapshot_timeout`; they are probably the very large repositories, so the mined set under-represents them (stated limitation, listed in the report with the other reasons). `corpus_error:*` rows are expected to be rare; the 5% limit makes a systemic bug visible. Rows quarantined for a bug stay recorded and are skipped on resumption, so a stop on exit code 5 needs the engineer to decide which rows to drop before a relaunch.
- Design reading (for the engineer): the brief lists "checkout" among content errors and "network" among infrastructure errors; a fetch timeout of one commit is read as checkout, because a retry of the same commit fails the same way and the run could not otherwise pass it. The cheaper alternative, ending the session on the timeout, makes the run stop on every heavy commit forever.
- Open: whether a partial fetch (blobs on demand) should replace the whole-tree shallow fetch so heavy commits are mined instead of quarantined. It changes how bytes are fetched, not the files written; cost: a different fetch path to test on the cluster.
- Reversible: yes.
- Related: DEV-034, DEV-035, `docs/experiments/B.md` E-MINE-FULL, `tests/unit/test_mining_failure.py`, `tests/unit/test_mining_pipeline.py`

## DEV-037 — The RQ3 scaffold is a retrieval-supplied one-shot repair, not the Agentless pipeline the master recommends   (2026-11-08 · status: accepted (D121))
- Master says: open decision 7, "Agentless — simplest to hold constant; complexity is a liability here".
- We do: ADR-007 (D113) takes only the edit-block format and the separation of retrieval from repair: one call per run at temperature 0, up to two follow-ups for an unusable reply, no candidate sampling, no test-based selection, an assembled 8,000-token context in place of localized snippets.
- Why: read in full (Agentless v2): the paper's default runs 40 repair samples and 40 reproduction-test samples with test execution and its localization is several calls; a controlled retriever contrast needs one fixed call. Detail: `decisions/ADR-007-agent-scaffold.md` addendum of 2026-11-08 (second).
- Impact: absolute resolved rates are not comparable with Agentless's; selection is its largest component (77 against 96 of 300), so the repair stage is weaker; the claim is scoped to one-shot repair without candidate selection.
- Reversible: yes.
- Name: ruled D121 ("retrieval-supplied one-shot repair"; the earlier label is retired).
- Related: D113, D116, D121, `knowledge/papers/agentless-2407.01489.md`, `docs/RQ3_PILOT.md`

## DEV-038 — The single look at SWE-bench Verified uses the 377 executable instances, not the twelve folders   (2026-11-09 · status: accepted (D127), provisional until launch)
- Master / protocol say: `docs/RQ2_PROTOCOL.md` section 4 and D32 (ADR-005): Verified is the final test, twelve folders (432 L2 and 302 L3 queries), looked at exactly once after the dev analysis.
- We do: the Verified look is the executable subset of D106: 377 instances, 320 L2 and 224 L3 queries, scored once from the retained mined-set models after the dev analysis. The eight repositories of D100 are scored in the same step. Matplotlib and scikit-learn have no executable instance and are not in the look.
- Why: six of the twelve folders have no unit records or stores; the executable subset has unit records, BM25 and untrained dense scores for all 377 (D107); one encoding pass per retained checkpoint serves both this look and RQ3's retrieved contexts. Evidence class: measured (counts), reasoned (the choice).
- Impact: **lost:** 432 L2 queries become 320 and 302 L3 become 224, so the minimum detectable difference is about 16% larger (reasoned: the square root of 432/320 and of 302/224, both 1.16); two repositories drop out; a result describes the executable subset only and does not carry to the excluded instances. **Gained:** no new CPU build for six folders, the same population as RQ3, and one encoding pass per checkpoint instead of two. Cost per checkpoint: 0.388 GPU-hours measured for the 341 built instances plus up to 0.292 projected for the 36 earlier ones (their six-folder store is encoded whole unless a per-instance restriction is built).
- Reversible: yes (stores for the other six folders can still be built).
- Related: D100, D106, D107, D127, `docs/RQ2_LAUNCH_PLAN.md` section 10, `docs/experiments/B.md` E-RQ2-FINAL-CELLS

## DEV-039 — The 1,000-update sensitivity is not run on the mined set   (2026-11-09 · status: accepted (D128), provisional until launch)
- Master / protocol say: D68 (`docs/RQ2_PROTOCOL.md` section 11, O1): 1,000 updates as a sensitivity check on a subset of cells.
- We do: no 1,000-update run on the mined set. It may run on the injected-noise family if the ledger has room after the primary runs; that is an option, not a plan.
- Why: 32,000 example visits against about 5,800 mined examples cannot reach the matched unique-example count (about 5.5 passes for RAW, 9.3 for FILTER); the pilots already show the learning curve flat from 100 to 2,000 updates (E-PILOT-CURVE). Evidence class: measured (curve), projected (example count).
- Impact: the robustness of the primary contrasts to the update count rests on the pilot curve on the pool, not on a run on the mined set; the report says so.
- Reversible: yes.
- Related: D68, D128, `docs/EXPERIMENTS.md` E-PILOT-CURVE, `docs/RQ2_LAUNCH_PLAN.md` section 10

## DEV-040 — Contrast decisions are read from a cluster-robust t interval; the repository bootstrap stays beside it   (2026-11-09 · status: accepted (D136), before any final row exists)
- Master / protocol say: D17 (ADR-005): mean over queries with repository-clustered bootstrap intervals; D72 (`docs/RQ2_PROTOCOL.md` section 4): Holm within each family, decisions read from those intervals (2,000 draws, seed 0).
- We do: the decision interval is the cluster-robust t interval over repositories with R - 1 degrees of freedom (every query its own cluster below three repositories), inside the same Holm step-down (family, set and ordering unchanged; contrasts ordered by the t p-value). The percentile bootstrap over whole repositories (D17) is reported beside it in every table, at the same Holm step levels, and its family-wise rate stays pinned in a test.
- Why: measured by simulation (E-RQ2-ANALYSIS, 1,000 simulations per cell, four confirmatory contrasts under no effect, three seeds): any Holm rejection with the percentile bootstrap occurs in 0.19 and 0.16 of simulations at 8 repositories, 0.16 and 0.10 at 12, 0.11 and 0.08 at 20 (repository spread of the effect 0 and 1.5 points) against the nominal 0.05; with the t interval it is 0.044 and 0.027 at 8, 0.054 and 0.034 at 12, 0.044 and 0.035 at 20. The change is made before any final row exists, so no outcome influences it. Evidence class: measured (simulation, synthetic rows), reasoned (a t interval with few clusters is the standard small-sample reading).
- Impact: intervals and Holm decisions of every RQ2 table change; point estimates, the family structure, delta, the verdict words and the seed spread do not. Intervals carry query and repository sampling, not retraining variance, as before. A statement that "the interval excludes zero" refers to the t interval; the bootstrap interval is always shown beside it.
- Reversible: yes (the percentile intervals are computed and stored; the decision function is one place).
- Related: D17, D72, D123, D136, `docs/experiments/B.md` E-RQ2-ANALYSIS, `docs/RQ2_PROTOCOL.md` section 11

## DEV-041 — The mined family's updates follow the FILTER pool when it is smaller than 3,200 directories   (2026-11-09 · status: accepted (D140), conditional; filled by the launch step when F is known)
- Master / protocol say: D68 (`docs/RQ2_PROTOCOL.md` section 11, O1): 100 optimizer updates of 32 examples (3,200 directory visits) for every arm. D133 (launch rulings): when a pool is smaller than the visits, every arm keeps 100 updates and cycles its own pool, with distinct examples stored.
- We do: for every arm of the mined family, N = min(100, floor(F / 32)) updates, F being the FILTER pool after the held-out and overlap drops (32 directories per update). Every arm makes the same number of directory visits and no arm repeats an example. The injected family keeps N = 100. If F is at least 3,200 then N = 100 and nothing departs from D68. The distinct-examples-per-arm diagnostic stays in every table. This replaces the cycling rule of D133 (D133's code path remains as a safeguard and is not used when N is computed).
- Condition and fill: the launch step reads the prepared store's summary, computes F and N, writes both with the hash of the summary into the run directory, and writes N into the run configurations and their hashes before any submission; the submit script refuses if N was not computed from a prepared store. Filled at launch: F = ___ (not yet known), N = ___ (100 if F is at least 3,200).
- Why: the earlier rule made RAW and FILTER differ in repeated examples whenever the FILTER pool was short, which confounds the FILTER-against-RAW contrast with repetition; equal visits and no repeats remove the confound at the price of fewer updates for every arm alike. Evidence class: reasoned (the FILTER pool was projected at about 3,430 before the drops: N would be 100).
- Impact: none if F is at least 3,200. Below it, every mined arm trains for fewer updates (a stated departure from D68's 100 for the mined family only) and the primary contrasts are read at that N; the pilots' curve (flat from 100 updates) says the loss in absolute level is small, which is evidence from the pool, not from the mined set.
- Reversible: yes (N is a configuration value and part of each run's hash).
- Related: D68, D133, D140, `docs/RQ2_LAUNCH_PLAN.md` sections 9 and 10, `docs/experiments/B.md` E-RQ2-FINAL-CELLS

## DEV-042 — The final-sets job keeps the per-instance scores of the executable 377   (2026-11-12 · status: accepted (D152))
- Master / plan say: the final-sets scoring (D100, D127, `docs/RQ2_LAUNCH_PLAN.md` section 10.3) writes metric tables and removes its node-local work directory at exit, so the per-instance scores of the executable 377 do not outlive the job.
- We do: the job copies those scores (the executable 377 only, not the eight repositories) to the retention directory with the checkpoint hash and a SHA-256 per file and for the set, and records the hash in the scoring row. What the job computes, the metrics it writes and the sealed order (no scoring without the id and record of the finished dev analysis) are unchanged.
- Why: the agent study (RQ3, trained arms) needs exactly these scores. Encoding them again costs 0.68 GPU-hours per model, which exceeds the Block 4 cap for the full set of models (the 15 mined models of the five confirmed cells cost 10.2 against 5.623 left); keeping them costs no GPU time. Reading them for RQ3 reveals nothing the sealed scoring has not already produced. Evidence class: reasoned for the cost, tested for the equality of the metrics (byte-identical with and without retention, three parts).
- Impact: none on any RQ2 number; a few hundred megabytes more on the account that scores (to be measured). The RQ3 encode stage remains as a fallback for a model whose scores are missing, within the cap.
- Reversible: yes (`--no-retain-scores`; the scores can be re-encoded at the stated cost).
- Related: D100, D127, D129, D142, D152, `docs/experiments/B.md` E-RQ3-SCORE-RETENTION
