# ril/bench/

**Files:** `latency_harness.py`, `profile_stages.py`, `stub_stages.py` (synthetic workloads until real stages register), `graph_storage.py` (storage options S1 to S7 for the RepoGraph) and `graph_measure.py` (parse, graph build and storage measurement through the harness, one process per step). Contract: `specs/latency_harness.md`.
Design: `docs/07_latency_and_profiling.md`.

The professor's standing requirement: latency/throughput profiled **per component**, recorded
**before every commit**, p50/p95/p99 (never the mean), per hardware spec, with ablations on latency.
`torch.cuda.synchronize()` around GPU sections; warmup discarded; cold vs warm separate; latency
(per-query, batch size 1) and throughput (indexing, training) in separate tables.

May call everything; nothing calls back into it.
