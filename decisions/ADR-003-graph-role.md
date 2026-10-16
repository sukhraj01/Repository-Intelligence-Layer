# ADR-003: Graph role: retrieval signal vs agent tool

- **Status:** Proposed — **not decided**
- **Date opened:** 2026-10-12
- **Decide by:** end of week 2 (all ten decisions)
- **Decided by:** _pending — team_
- **Master doc:** open decision #3 (`docs/12_open_decisions.md`)
- **Affects:** `ril/retrieval/hybrid_retriever.py`, RQ1, the graph extension, agent integration

## Context
LocAgent uses the graph as a tool the agent calls; RIL's design uses it as a signal (struct(u) = γ^dist(ℓ,u), γ ≈ 0.5, then possibly personalized PageRank). These are different systems with different latency profiles. Pick deliberately; do not drift between them.

## Alternatives considered
- Retrieval signal (hop-decay score fused with BM25 and dense)
- Agent tool (LocAgent-style TraverseGraph)

## Master doc's recommendation (a recommendation, not a decision)
Signal — matches RIL's architecture and keeps latency predictable.

## Decision
_Pending — the team decides._ If work cannot wait, proceed behind a config flag marked
`provisional: ADR-003` (never in `configs/frozen/`) until the decision is made.

## Rationale
_Pending._

## Trade-offs
_Pending._

## Evidence to gather
- [ ] Measured latency of graph expansion (2 hops) on a real repository.
- [ ] Edge-recovery coverage from `specs/parse_one_repo.md` (static Python call graphs are incomplete).

## Related benchmarks
_None yet._

## References
See `docs/11_references.md`.

## Conditions to revisit
_Pending._

## Addenda
_None._
