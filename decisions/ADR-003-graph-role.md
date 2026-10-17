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

## Addendum 2026-10-17 — pilot M: how near L3 positives lie to L2 positives in the graph (evidence only; no choice made)

Exploratory pilot, three repositories, 7 instances, 126 new Python L3 positives (`docs/EXPERIMENTS.md` E-GRAPH-REACH).
Seeds were the gold L2 units, so this bounds what a perfect first stage could seed; it does not measure retrieval.

- Hop distance from the L2 units over the five core families: 88% of new L3 positives within three hops, but a
  random set of units from the same files reaches 78%, and random units of the same kind from the whole repository
  50%. Most of the nearness is file and directory locality.
- Excess over the same-file chance, within three hops: resolved call edges (both directions) +13 points (95%
  bootstrap over positives +6 to +20; over the 7 instances +5 to +27), +5 points at one hop (ratio 1.8); `contain`
  and `import` add nothing over same-file chance; `inherit` reaches 5 of 126; exploratory `tests`, `configures` and
  `co_change` add nothing measurable. Heterogeneous across repositories: the call-edge excess is present in flask
  and requests and absent in seaborn.
- Bearing on the role of the graph (A signal, B training structure, C agent tool): for A, the locality that carries
  most of the reach is also reachable without a graph (same file, same directory); the part only the graph
  provides here is the call-edge excess. For B, 12 of 141 L3 positives are text-identical to an L2 positive and
  7% are test units, which is the scale of "test positives" a graph-derived supervision could add. Evidence class:
  measured, n small; the controlled retrieval-level test is pilot E3.
- Cheapest experiment that could flip an inference from this: E3 (hop-decay expansion from retrieved, not gold,
  seeds against a size-matched random expansion). Conditions to revisit: resolver recall (ADR-012 definitions), more
  repositories (including the non-Verified L3 folders once base commits are obtained).
