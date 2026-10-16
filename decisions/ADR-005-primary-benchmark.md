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
_None._
