# ADR-002: Quality signal for FILTER and WEIGHT

- **Status:** Proposed — **not decided**
- **Date opened:** 2026-10-12
- **Decide by:** end of week 2 (all ten decisions)
- **Decided by:** _pending — team_
- **Master doc:** open decision #2 (`docs/12_open_decisions.md`)
- **Affects:** RQ2 FILTER and WEIGHT arms; `ril/training/supervision.py`

## Context
We cannot label examples "noisy" without evidence. SweRank filters by K = minimum rank of the positive relative to negatives under a base retriever; raising K relaxes filtering; optimal at moderate K ≈ 20. Docstring-era heuristics (docstring length, auto-generated detection) were designed for docstring–code pairs and break on issue text. If a learned model computes the signal it must be a separately pretrained encoder, never the model being trained.

## Alternatives considered
- SweRank K-rank
- Hand-written heuristics
- LLM judge

## Master doc's recommendation (a recommendation, not a decision)
K-rank — published, continuous, makes FILTER and WEIGHT the same signal applied as a hard threshold vs a soft weight.

## Decision
_Pending — the team decides._ If work cannot wait, proceed behind a config flag marked
`provisional: ADR-002` (never in `configs/frozen/`) until the decision is made.

## Rationale
_Pending._

## Trade-offs
_Pending._

## Evidence to gather
- [ ] Distribution of K-rank over a sample of the chosen pool under the candidate base retriever.
- [ ] Drop rate at several thresholds; how FILTER's pool size compares with RAW's.
- [ ] Confirmation that the filtering encoder is a different model from the trained encoder (leakage test (c)).

## Related benchmarks
_None yet._

## References
See `docs/11_references.md`.

## Conditions to revisit
_Pending._

## Addenda
_None._
