# Spec: Per-commit latency and throughput harness

Source: `docs/07_latency_and_profiling.md`. The professor requires latency and throughput analysis on
every project, profiled **per component**, and recorded **before every commit**. It is also an open gap
CORE-Bench names explicitly, so it is a contribution as well as compliance. Build it in week 1 — cheap
now, and it gives the final report a longitudinal record rather than one snapshot.

## Purpose

A benchmark script running a **fixed query set**, writing p50/p95/p99 **per stage** plus the hardware
spec to an **append-only CSV**, and **failing loudly** on regression past a threshold.

## Stages (the harness times each separately)

`query_encode` · `bm25` · `dense_search` · `graph_expansion` · `rrf_fusion` · `cross_encoder_rerank` ·
`assemble` · `end_to_end`. Each component registers its stage as it comes online; until then the
harness runs against stubs/synthetic workloads so the plumbing, CSV contract and regression check are
tested from day one. Hypothesis (not fact): rerank dominates by ~two orders of magnitude.

## Measurement rules (correctness)

- `torch.cuda.synchronize()` before and after every timed GPU section — without it CUDA is async and timings are fiction.
- Discard the first N calls (warmup/JIT/cache population); N is a parameter recorded in the CSV.
- Report **p50/p95/p99**, never the mean.
- Cold-cache and warm-cache paths are separate rows (`cache_state`).
- Latency = per-query, **batch size 1**. Throughput (indexing units/s, training samples/s) is a **separate** table/file.
- Use `cProfile`/`py-spy` for CPU attribution and `torch.profiler` for GPU in `profile_stages.py` — wall-clock alone is not enough.
- The fixed query set is versioned; changing it starts a new `query_set_id` (rows are not comparable across ids).

## CSV contract — `results/latency/latency_log.csv` (append-only)

One row per (run × stage × cache_state):

`timestamp_utc, commit, dirty, branch, host, cpu_model, cpu_cores, ram_gb, gpu_name, gpu_driver, cuda_version, python, torch, config_hash, query_set_id, n_queries, warmup_n, cache_state, stage, p50_ms, p95_ms, p99_ms, n`

Throughput goes to `results/latency/throughput_log.csv` with its own columns (`stage, units, seconds, units_per_s, …` plus the same environment columns).

## Regression check

`make bench-check` compares the new run against the most recent comparable row (same hardware spec,
same `query_set_id`, same `cache_state`, same stage) and exits non-zero past a threshold.
**Threshold:** a config parameter. Pick a conservative default, record it, and flag it
as provisional; the engineer may change it. With no comparable previous row, the check passes and says so.

## Hook

`make hooks` installs a git pre-commit hook that runs the harness and appends the row. Open question
Q3 (do docs-only commits need a fresh row?) is unresolved: **implement the strict reading** (every
commit) behind a documented switch so the engineer can relax it, and record the choice.

## Open design questions

- Which signals/stages belong in the "frozen" benchmark snapshot (decided at the config freeze, before week 6).
- Any change to the stage taxonomy that would alter what the professor's "sourcing vs ranking" split means.

## Acceptance criteria

- [ ] `ril/bench/latency_harness.py` and `profile_stages.py` exist; `make bench` and `make bench-check` work.
- [ ] Running twice appends two rows per stage; existing rows are never rewritten (test).
- [ ] The regression check fails on a synthetic slowdown and passes on noise (test).
- [ ] Hardware spec is captured automatically (CPU, RAM, GPU/driver/CUDA when present).
- [ ] p50/p95/p99 computed from raw samples, not means; warmup discarded (test).
- [ ] `docs/07_latency_and_profiling.md` is *not* edited; `docs/ARCHITECTURE.md` (bench) and `PROJECT_STATE.md` ("harness: built") are.
- [ ] One latency row for the harness's own commit is in `RESULTS.md`.
