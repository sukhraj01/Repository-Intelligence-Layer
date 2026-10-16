# ADR-006: Base encoder

- **Status:** Proposed — **not decided**
- **Date opened:** 2026-10-12
- **Decide by:** end of week 2 (all ten decisions)
- **Decided by:** _pending — team_
- **Master doc:** open decision #6 (`docs/12_open_decisions.md`)
- **Affects:** RQ2, latency, `ril/retrieval/dense_encoder.py`

## Context
CORE-Bench SFT lifted Qwen3-0.6B from 17.0 to 26.5 nDCG@10 and Qwen3-8B from 20.3 to 32.8; a 0.6B model reaches ~80% of the 8B model's post-SFT result. The four RQ2 encoders are architecturally identical, so query latency does not vary across arms.

## Alternatives considered
- CodeBERT
- UniXcoder
- Qwen3-Embedding-0.6B

## Master doc's recommendation (a recommendation, not a decision)
Qwen3-0.6B — CORE-Bench reports strong post-SFT results at CPU-feasible size.

## Decision
_Pending — the team decides._ If work cannot wait, proceed behind a config flag marked
`provisional: ADR-006` (never in `configs/frozen/`) until the decision is made.

## Rationale
_Pending._

## Trade-offs
_Pending._

## Evidence to gather
- [ ] Encode latency and memory on the local box and on Ada for each candidate.
- [ ] Training memory feasibility at the intended batch size (batch size = in-batch negative count).

## Related benchmarks
_None yet._

## References
See `docs/11_references.md`.

## Conditions to revisit
_Pending._

## Addenda
_None._
