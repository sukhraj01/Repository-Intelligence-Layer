# ADR-009: Cross-encoder rerank

- **Status:** Proposed — **not decided**
- **Date opened:** 2026-10-12
- **Decide by:** end of week 2 (all ten decisions)
- **Decided by:** _pending — team_
- **Master doc:** open decision #9 (`docs/12_open_decisions.md`)
- **Affects:** Latency Pareto, RQ1, the rerank step of the retrieval stack (not written yet)

## Context
Hypothesis from the master doc: reranking 100 candidates costs ~500–1000 ms while every other stage is a few ms, so ranking dominates sourcing by ~two orders of magnitude. Optimisation axes: rerank 20 instead of 100, distil the cross-encoder, or drop it and measure the nDCG cost.

## Alternatives considered
- Include
- Exclude

## Master doc's recommendation (a recommendation, not a decision)
Include but measure — it likely dominates latency.

## Decision
_Pending — the team decides._ If work cannot wait, proceed behind a config flag marked
`provisional: ADR-009` (never in `configs/frozen/`) until the decision is made.

## Rationale
_Pending._

## Trade-offs
_Pending._

## Evidence to gather
- [ ] Per-stage latency profile (p50/p95/p99) with rerank on and off.
- [ ] nDCG@10 delta for rerank depth 0 / 20 / 50 / 100 on a fixed query set.

## Related benchmarks
_None yet._

## References
See `docs/11_references.md`.

## Conditions to revisit
_Pending._

## Addenda
_None._
