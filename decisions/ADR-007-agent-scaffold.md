# ADR-007: Agent scaffold

- **Status:** Proposed — **not decided**
- **Date opened:** 2026-10-12
- **Decide by:** end of week 2 (all ten decisions)
- **Decided by:** _pending — team_
- **Master doc:** open decision #7 (`docs/12_open_decisions.md`)
- **Affects:** RQ3, `ril/evaluation/agent_integration.py`

## Context
RQ3 needs one fixed scaffold, one fixed base model, fixed temperature and seed, over the same instances, with the retriever as the only thing that changes.

## Alternatives considered
- SWE-agent
- OpenHands
- Agentless
- Custom

## Master doc's recommendation (a recommendation, not a decision)
Agentless — simplest to hold constant; complexity is a liability for a controlled study.

## Decision
_Pending — the team decides._ If work cannot wait, proceed behind a config flag marked
`provisional: ADR-007` (never in `configs/frozen/`) until the decision is made.

## Rationale
_Pending._

## Trade-offs
_Pending._

## Evidence to gather
- [ ] Whether the scaffold accepts a pluggable retriever without other changes; install and run cost on Ada.

## Related benchmarks
_None yet._

## References
See `docs/11_references.md`.

## Conditions to revisit
_Pending._

## Addenda
_None._
