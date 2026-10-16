# ADR-008: Base LLM for the agent

- **Status:** Proposed — **not decided**
- **Date opened:** 2026-10-12
- **Decide by:** end of week 2 (all ten decisions)
- **Decided by:** _pending — engineer / team (budget)_
- **Master doc:** open decision #8 (`docs/12_open_decisions.md`)
- **Affects:** RQ3 cost and reproducibility

## Context
A cost and reproducibility decision: hosted API models drift and cost money; local quantized models need Ada GPU time.

## Alternatives considered
- API model
- Local quantized model

## Master doc's recommendation (a recommendation, not a decision)
Decide on budget; if local, quantize identically across all arms.

## Decision
_Pending — the team decides._ If work cannot wait, proceed behind a config flag marked
`provisional: ADR-008` (never in `configs/frozen/`) until the decision is made.

## Rationale
_Pending._

## Trade-offs
_Pending._

## Evidence to gather
- [ ] Cost per instance estimate; GPU memory needed for the candidate local model; reproducibility at fixed temperature/seed.

## Related benchmarks
_None yet._

## References
See `docs/11_references.md`.

## Conditions to revisit
_Pending._

## Addenda
_None._
