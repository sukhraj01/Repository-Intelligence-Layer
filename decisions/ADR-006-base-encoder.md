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

## Addendum 2026-10-23 — GPU use authorised; the encoder is decided by measurement (engineer decisions D21 and D24 of 2026-10-18; this ADR stays Proposed)

- **D21 (closes Q42).** GPU jobs on the cluster are authorised within a budget of 8 GPU-hours for the first block of the
  current wave and 24 GPU-hours for the second, summed over jobs from `sacct` and logged per job in `docs/COMPUTE.md`. Every
  GPU job is gated by a real CUDA matrix multiplication and requests a supported card. *Rationale:* the CPU estimate for
  encoding the roughly 52,000 distinct unit texts of the dev snapshots with CodeRankEmbed was about 30 hours (0.85 chunks/s
  on 4 CPUs, `docs/EXPERIMENTS.md`), against about an hour on one GPU; a smaller sample or a shorter cut would be a different,
  lower-fidelity experiment. *Evidence class:* measured (CPU throughput), estimated (GPU). *Flip:* a job that would exceed
  the block budget stops, records its partial result and the resumable command.
- **D24 (not decided now).** The base encoder is chosen by the engineer after measurement: CodeRankEmbed (137M) and
  Qwen3-Embedding-0.6B (the master document's candidate) on the dev and Verified-six unit texts, with encode throughput on
  CPU and GPU, peak memory, query-encode and flat-index search latency (p50/p95/p99), and retrieval quality alone and fused
  with BM25.
