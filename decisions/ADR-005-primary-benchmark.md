# ADR-005: Primary benchmark

- **Status:** Proposed — **not decided**
- **Date opened:** 2026-10-12
- **Decide by:** end of week 2 (all ten decisions)
- **Decided by:** _pending — team_
- **Master doc:** open decision #5 (`docs/12_open_decisions.md`)
- **Affects:** Evaluation, RQ1, RQ3 pairing

## Context
L2 is issue-to-edit localization; L3 scores broader context (tests, docs, configuration), which is exactly what our graph extension adds; Loc-Bench (660 examples, post-Oct-2024) checks contamination and category balance.

## Alternatives considered
- CORE-Bench L2
- CORE-Bench L3
- Loc-Bench

## Master doc's recommendation (a recommendation, not a decision)
L2 primary, L3 for the graph question, Loc-Bench as contamination check.

## Decision
_Pending — the team decides._ If work cannot wait, proceed behind a config flag marked
`provisional: ADR-005` (never in `configs/frozen/`) until the decision is made.

## Rationale
_Pending._

## Trade-offs
_Pending._

## Evidence to gather
- [ ] Instance and repository counts per level; overlap with SWE-bench Verified; evaluation cost per level.

## Related benchmarks
_None yet._

## References
See `docs/11_references.md`.

## Conditions to revisit
_Pending._

## Addenda

### 2026-10-17 — Loc-Bench against the held-out list (evidence, no decision)
- Loc-Bench V1 has 165 repositories: 37 are already in the held-out list (CORE-Bench L2/L3 or Verified), 128 are not. V0.2 has 210: 41 in the list, 169 not.
- If Loc-Bench repositories were also held out, CodeSearchNet python would drop from 449,440 to 445,640 instances (13,546 to 13,534 repositories); the `gangiswag/train_data` python candidate would not change (none of the 169 outside repositories occurs in it).
- Not decided here: whether Loc-Bench is held out (Open question Q9). Source: `data/held_out/report.md`, `knowledge/datasets/loc_bench.md`.
