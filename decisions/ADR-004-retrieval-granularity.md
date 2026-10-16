# ADR-004: Retrieval granularity

- **Status:** Proposed — **not decided**
- **Date opened:** 2026-10-12
- **Decide by:** end of week 2 (all ten decisions)
- **Decided by:** _pending — team_
- **Master doc:** open decision #4 (`docs/12_open_decisions.md`)
- **Affects:** `CodeUnit`, evaluation, metrics comparability

## Context
L2 retrieves files or chunks (≈15,000 chunks per repository on average); our CodeUnit design is function-level. Reported metrics must be comparable to the benchmark's.

## Alternatives considered
- Function-level units
- CORE-Bench chunks
- Both

## Master doc's recommendation (a recommendation, not a decision)
Both — CORE-Bench chunking for reported metrics so numbers are comparable; function-level units internally for the graph.

## Decision
_Pending — the team decides._ If work cannot wait, proceed behind a config flag marked
`provisional: ADR-004` (never in `configs/frozen/`) until the decision is made.

## Rationale
_Pending._

## Trade-offs
_Pending._

## Evidence to gather
- [ ] CORE-Bench's chunking procedure and chunk-size distribution from `corpus.jsonl` on a sample repository.
- [ ] A mapping between function-level CodeUnits and benchmark chunks, and what is lost in it.

## Related benchmarks
_None yet._

## References
See `docs/11_references.md`.

## Conditions to revisit
_Pending._

## Addenda
_None._
