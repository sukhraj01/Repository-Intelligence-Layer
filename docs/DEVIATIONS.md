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
