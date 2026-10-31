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

## Addendum 2026-10-29 — four numbers for the choice (E-ENCODER-NUMBERS; evidence only, this ADR stays Proposed)

Source: `docs/EXPERIMENTS.md` E-ENCODER-NUMBERS (configuration hashes `6aaef4fd84df`, `7485fdfc6c5f`, `8ac6819f9ba6`; run log
`results/logs/e7_encoder_numbers_2026-10-29.json`; tables `results/tables/e7_*.csv`; seed 0; one RTX 2080 Ti, 0.07 GPU-hours).
Evidence class: measured, exploratory, zero-shot encoders, one seed. Encoders as selected on dev earlier and held fixed
(CodeRankEmbed at 1,024 tokens with RRF k 100, Qwen3-Embedding-0.6B at 512 tokens with k 20).

1. **Paired RRF(BM25, Qwen3) minus RRF(BM25, CodeRankEmbed)** (`units_all_nomod`; intervals query-level, then repository-clustered).
   Dev L2 +4.29 [+2.95, +5.74], clustered [+2.22, +6.55] (351 queries, 5 repositories, all five positive); dev L3 +4.08
   [+2.85, +5.37] (155 queries, 2 repositories, clustered interval not informative). Verified-six, read as a final-test-style
   reading (both configurations were fixed on dev; nothing was chosen on Verified): L2 +1.85 [-1.67, +5.50], clustered [-2.01,
   +5.93] (83 queries; 3 of 6 repositories positive); L3 +3.43 [+0.87, +6.33], clustered [-1.07, +5.68] (55 queries; 4 of 6
   positive). Under `units_all` the picture is the same (Verified-six L3 +2.89 [+0.60, +5.44], clustered [-1.19, +4.69]).
   Dense alone, Verified-six: L2 -0.87 [-5.28, +3.39], L3 +5.54 [+2.09, +9.57].
2. **Class-unit text `full` against `header`, dense, dev** (D25's flip experiment; reported, nothing switched). `header` is below
   `full` in every cell: dense alone -1.79 [-2.66, -1.00] (CodeRankEmbed L2), -0.50 [-1.06, +0.05] (L3), -1.57 [-2.34, -0.83] and
   -1.13 [-1.65, -0.58] (Qwen3); fused -1.90 / -1.97 (CodeRankEmbed) and -1.86 / -2.06 (Qwen3), none with an interval above
   zero. Truncation does not make `full` lose to `header` at these cuts. The caveat of the BM25 result (the gold reading counts a
   class as gold whenever one of its methods is) applies unchanged and was not separated.
3. **Training step at the D31 shape** (32 x (1+1), 512 tokens, float16 autocast, gradient checkpointing, AdamW as the training
   path builds it, 2080 Ti with 10.57 GiB usable). CodeRankEmbed: 12.24 and 12.35 examples/s (2.6 s per update), peak 6,880 MiB.
   **Qwen3-Embedding-0.6B: out of memory at every shape from 32 down to 1.** Probe: 595.8 million parameters, 2,273 MiB of float32
   weights, 4,562 MiB with gradients, 9,107 MiB with both AdamW moments (per-tensor update; the default multi-tensor update fails at
   the first optimizer step), peak 10,600 MiB at the step. No Qwen3 throughput was measured. Reasoned, not measured: a fitting
   step would need of the order of 24 GiB and run about 2.4 to 4.3 times slower than CodeRankEmbed. `sinfo` and
   `sbatch --test-only` show no card above 11 GB usable from the `research` account (D31 check). Recipe changes that might fit
   (8-bit optimizer states, half-precision master weights, adapters, gradient caching) are design choices and were not tried.
4. **Query latency next to the gain** (warm p50 / p95 / p99, batch 1): GPU encode 18.1 / 19.3 / 22.2 ms against 45.2 / 46.6 / 47.6
   ms (ratio of p50 2.5); CPU encode, 4 threads, 411 / 1,265 / 2,555 ms against 1,533 / 3,591 / 3,628 ms (3.7); flat search at
   35,860 units on CPU 4.95 and 5.98 ms p50. The extra encode is +27 ms (GPU) or +1.1 s (CPU) per query for the paired
   differences in item 1. D33 (instruction variants of the Qwen3 query) was not run: it applies only if Qwen3 would win the choice.

**What would have to be true for each choice** (no recommendation).

- *CodeRankEmbed* is the choice if: the Verified-six L2 difference of +1.85 (interval including zero) and the L3 difference of
  +3.43 (clustered interval including zero) are small enough that a smaller model's training cost matters more, or are
  expected to shrink after fine-tuning (not measured; the T3/T4 pilots run on it); the RQ2 runs (4 arms, at least 3 seeds,
  the 2.6 s update measured here) must fit on the 11 GB cards the account can reach, which this encoder does with 4 GB to
  spare; and the CPU query budget of the demo matters (411 ms against 1.5 s at p50).
- *Qwen3-Embedding-0.6B* is the choice if: a card with about 24 GB or more is available to every run of every arm (or a changed
  training recipe, itself a design decision, is accepted and held identical across arms), since at the D31 shape it does not
  fit the cards measured; the dev gap (+4.3 and +4.1) rather than the Verified-six gap is the better guide to how the
  encoder will behave after fine-tuning, and the Verified-six intervals that include zero are a sample-size matter (55 and 83
  queries); the extra training cost (2.4 to 4.3 times per update, reasoned) fits the 24 GPU-hour block together with the arms
  and seeds; and 45 ms (GPU) or 1.5 s (CPU) of query encoding fits the latency requirement, which the repository does not yet
  state as a number.
- *Either* encoder: the gap between them after fine-tuning is not known; item 1 compares zero-shot retrievers. The cheapest
  experiment that could flip the choice is the one in the 2026-10-25 addendum (a short fine-tune of each on the same dev
  evaluation); for Qwen3 it needs the memory question in item 3 settled first.

## Addendum 2026-10-29 (second) — engineer decision D33

**D33 (Q48).** No Qwen3 instruction variants are measured unless E-ENCODER-NUMBERS shows that Qwen3 would win the encoder choice on its own terms.
- **Why.** Each variant is a full re-encode of the corpora; the choice may be decided by memory before accuracy (the 0.6B encoder does not take one float32 AdamW step on an 11 GB card, see the addendum above), which would make the variants moot.
- **Evidence class.** Measured (the memory result) plus reasoned.
- **Cheapest experiment that could flip it.** If a larger card or a changed recipe makes Qwen3 trainable, run two instruction sentences on dev (about 1 GPU-hour); until then the instruction stays the one X2 used and is recorded in the held-identical block only if this encoder is chosen.

## Addendum 2026-10-30 — cost note on the D31 figures after the RAW learning curve (evidence only; this ADR stays Proposed)

The D31 cost figure (2.65 s per update, about 15 GPU-hours for 20,000 updates, `t1-train-throughput` rows) was measured for training alone. The RAW curve (E-PILOT-CURVE, measured) adds two costs the figure did not include: one evaluation of the full dev set costs 43 minutes on an 11 GB card (590k unit texts at 229 per second), and the whole curve (2 seeds, 2,000 updates, evaluation on a dev subset) cost 5.14 GPU-hours. Any plan that evaluates several checkpoints per run should budget evaluation separately. The curve also suggests the encoder settles near 100 updates under RAW (reasoned beyond that, see the ADR-002 addendum of the same date), so the 20,000-update figure is an upper bound on the training cost rather than a requirement. No encoder or shape decision follows from this.

## Addendum 2026-10-31 — engineer defaults D34 and D35 (Q54, Q55) and the plateau reading

**D34 (Q54).** RQ2 trains CodeRankEmbed only; Qwen3-Embedding-0.6B stays zero-shot (retrieval only). Evidence class: measured (one float32 AdamW step runs out of memory on an 11 GB card, peak 10.6 GiB) and reasoned (the fused gain over CodeRankEmbed is +1.85 L2 and +3.43 L3 with intervals that include 0; 4x CPU latency). Cheapest experiment that could flip it: a 24 GB card on a partition the account can use plus a recipe with documented equivalence (adapters), tested on RAW only; time-box one day of cluster time.

**D35 (Q55).** Query-latency budget (provisional, reasoned): median dense query encode on CPU at most 500 ms and end-to-end p95 at most 1 s on CPU for one query. Qwen3 (1,533 ms median) fails it, CodeRankEmbed (411 ms) passes. Cheapest experiment that could flip it: count retrieval calls per instance in the agent pilot; added wall time per instance is calls times latency.

**Evidence from E-PILOT-ARMS (measured, exploratory).** The RAW run on the 2,000-example pool reaches +10.7 (L2) and +11.9 (L3) at 100 updates and falls 3.0 and 2.4 points by 1,000 updates (16 passes); the 5,000-directory curve stayed flat to 2,000. So the plateau is a property of the pool size as well as of the base encoder.
