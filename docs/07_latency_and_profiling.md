# Latency and throughput

> **Derived copy** of the team's Master Project Document (rev 16, dated 2026-10-11).
> The master doc is the source of truth. If this file and the master disagree, the master wins; record the drift as an Open question in `PROJECT_STATE.md` instead of silently editing here.

*Master-doc section(s): Latency and throughput.*

The professor requires this on every project. It is also an open gap CORE-Bench names explicitly, which means it can be a contribution rather than a compliance exercise.

## His stated requirements

- Latency and throughput analysis: what takes the time, sourcing or ranking
- Detailed benchmarking and profiling: per-query, per-component time attribution
- Ablation on latency — if this element changes, how do latency and throughput change
- Record latency and throughput before every commit
- Benchmark per hardware spec
- Plan experiments around where time actually goes, and invest there

## Expected time distribution — hypotheses, not facts

| Stage | Rough expectation |
|---|---|
| Query encode (one forward pass) | ~5 ms |
| BM25 over 10⁴ units | ~1–10 ms |
| Flat exact ANN over 10⁴ × 768 | ~1–5 ms |
| Graph expansion | ~1 ms |
| RRF fusion | <1 ms |
| Cross-encoder rerank, 100 candidates | ~500–1000 ms |

If this holds, ranking dominates sourcing by about two orders of magnitude, and the entire RQ1 signal debate is latency-irrelevant. That is a genuine finding and it is exactly his "this is where my time is going" instruction. It also names the optimization axis: rerank 20 instead of 100, distil the cross-encoder, or drop it and measure the nDCG cost.

## Reframe RQ1 as a Pareto question

"Which signals improve nDCG" is done. "Which signals improve nDCG per millisecond" is not. Same four configurations, every row carrying p50/p95/p99 latency and a quality-per-unit-cost column. A signal adding 0.4 nDCG for 1 ms is free; for 200 ms it is not.

## Keep these separate

Latency is per-query, batch size 1, interactive — what the agent experiences. Throughput is indexing (units/sec) and training (samples/sec). Batch size 1 is the worst case for GPU utilization and documenting that gap is itself a result. Separate tables.

## Profiling correctness

- `torch.cuda.synchronize()` before and after every timed GPU section — without it CUDA is async and timings are fiction. Most common mistake.
- Discard the first N calls; warmup, JIT and cache population make call 1 unrepresentative.
- Report p50/p95/p99, never the mean. Tail latency is what hurts an interactive system.
- Separate cold-cache from warm-cache paths explicitly.
- `cProfile` / `py-spy` for CPU attribution, `torch.profiler` for GPU — not just wall-clock timers.

## Per-commit harness — build in week 1

A benchmark script running a fixed query set, writing p50/p95/p99 per stage plus hardware spec to an append-only CSV, failing loudly on regression past a threshold. Cheap to build, gives the final report a longitudinal record rather than one snapshot, and is strong portfolio material.

## The connection to RQ3

An agent calls retrieval repeatedly while exploring. At 800 ms per call and 30 calls, that is 24 seconds per task of pure retrieval. Retrieval latency is therefore part of the agent's cost budget, not just an engineering concern. **Resolved rate per unit of agent wall-clock** is a metric nobody reports, follows directly from his emphasis, and strengthens RQ3.

## Scheduling constraint

RQ2 requires the retrieval stack frozen across all arms. All latency optimization must land **before** the RQ2 runs start, with the frozen config getting its own benchmark snapshot. Note also that the four RQ2 encoders are architecturally identical, so query latency does not vary across arms — RQ2's cost story is training throughput, not inference latency.
