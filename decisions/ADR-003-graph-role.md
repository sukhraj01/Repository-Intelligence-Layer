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

## Addendum 2026-10-17 — what the CodeUnit holds for relations (decision D4, context only)

Decision D4 (`specs/code_unit.md`) does not choose the graph's role. It fixes that relations live in
a separate typed edge store and that the CodeUnit lists `calls`, `called_by`, `tests` and `configs`
are projections of resolved ids only, so that signal-or-tool (this ADR) and the edge taxonomy
(ADR-011) stay open. Experiment that could flip D4: the resolution coverage measured in the first
parse and graph build.

## Addendum 2026-10-17 — what the graph design adds (context only; no decision)

`docs/GRAPH_DESIGN.md` (section 4) describes three roles with the experiment that would show the value
of each, a latency profile for each, and what each needs from the schema. Section 9 lists nine
questions for this ADR; the first four are: which role or roles are in the frozen configuration; how a
graph signal enters a fusion stack fixed to rank-based RRF; whether graph-derived supervision belongs to
RQ2; whether an agent-tool variant belongs to RQ3, which holds the agent fixed. None is answered
there. Evidence still to gather for this ADR: the per-status coverage and the 1- and 2-hop expansion
latency from the first graph build, and pilots M and E3.
