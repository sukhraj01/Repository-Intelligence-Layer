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
