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

## Addendum 2026-10-25 — first dense measurements of the two candidates (E-DENSE-FUSION; evidence only, this ADR stays Proposed)

Zero-shot, on the same unit texts as the BM25 pilots (`docs/EXPERIMENTS.md`, E-DENSE-FUSION; rows `x2-*`; gold
`units_all_nomod`; means over queries with query-level intervals). What changed relative to BM25 only:

| | CodeRankEmbed (137M) | Qwen3-Embedding-0.6B |
|---|---|---|
| Cut selected on dev (stated rule) | 1024 tokens (+1.1 [+0.4, +1.9] at L2 over 512) | 512 (1024 not distinguishable) |
| Dense alone vs BM25, dev L2 / L3 | -2.9 / -3.5 (below BM25) | +3.5 [+1.1, +6.1] / +9.2 [+6.9, +11.8] |
| Dense alone vs BM25, Verified-six L2 / L3 | -0.1 / +1.8 | -0.9 [-5.7, +3.8] / +7.3 [+2.5, +12.1] |
| RRF with BM25 vs BM25, dev | +2.9 [+1.2, +4.6] / +5.5 [+4.0, +7.2] (k 100) | +7.2 [+5.4, +8.9] / +9.6 [+8.0, +11.5] (k 20) |
| RRF with BM25 vs BM25, Verified-six | +5.1 [+1.4, +8.8] / +6.2 [+2.9, +9.7] | +6.9 [+3.6, +10.5] / +9.7 [+6.8, +12.7] |
| Chunk level, RRF vs BM25, Verified-six | +5.3 [-0.4, +10.8] / +11.4 [+6.9, +16.1] | +8.6 [+4.1, +13.2] / +16.1 [+12.0, +20.2] |
| Query encode, batch 1, warm p50 / p95 (GPU 2080 Ti) | 18.5 / 19.5 ms | 45.2 / 46.6 ms |
| Query encode, warm p50 / p95 (4 CPU threads, Xeon E5-2640 v4) | 378 / 937 ms | 1,533 / 3,591 ms |
| Flat exact search, 35,860 units, CPU p50 | 4.95 ms (768 dimensions) | 5.98 ms (1,024) |
| Encoding throughput (dev units, 512, GPU / 4 CPU threads) | 201 / 2.2 texts per s | 84 / 0.67 texts per s |
| Peak memory (GPU encoding at 512 / 1024; CPU resident after load) | 1.4 / 4.4 GB; 1.7 GB | 2.3 / 4.6 GB; 4.0 GB |

- D18 check: the selections and every Verified ordering are the same under `units_all`; on dev, CodeRankEmbed alone
  is level with BM25 at L3 under `units_all` (-0.2) instead of 3.5 below (module-residual positives favour it).
- Read together: both encoders improve on BM25 only when fused with it (except Qwen3 at L3, where dense alone is level
  with the fusion); Qwen3 is ahead on dev at both levels (RRF vs RRF +4.3 [+3.0, +5.7] / +4.1 [+2.9, +5.4]) and ahead
  at Verified L3 (+3.4 [+0.9, +6.3], clustered [-1.1, +5.7]) but not distinguishable at Verified L2 (+1.9 [-1.7, +5.5]).
  It costs about 2.4 times the GPU query-encoding time, 4 times the CPU time and 2.4 times the CPU memory; on the 8 GB
  local box Qwen3 at 1024 tokens peaked at 6.3 GB resident.
- For RQ2 (training cost, not measured here): encoding throughput scales the same way (about 2.4 times slower for
  Qwen3 on the GPU); training memory at the intended batch size is still unmeasured (the remaining item of this ADR's
  evidence list).
- Query instruction used for Qwen3 (stated so it can be held identical across arms if this encoder is chosen):
  `Instruct: Given a GitHub issue, retrieve the code units (functions, methods, classes or modules) that have to be
  changed to resolve it\nQuery:<issue>`; the report gives the format only. Model revisions are pinned in
  `ril/retrieval/dense_encoder.py`.
- **Evidence class:** measured, exploratory, zero-shot, one seed; latency per hardware spec (no cross-machine
  comparison). **Conditions to revisit / cheapest experiment:** the comparison that matters for RQ2 is after
  fine-tuning; a one-epoch, 2,000-instance fine-tune of each (pilot T2's budget) on the same dev evaluation would show
  whether the zero-shot gap survives training (about 1 to 2 GPU-hours each at the measured throughput).
