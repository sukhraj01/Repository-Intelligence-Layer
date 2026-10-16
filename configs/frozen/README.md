# configs/frozen/ — the RQ2 held-identical configuration

Empty until the freeze. At the freeze (all latency optimisation landed, before the RQ2 runs begin):

1. Write the full configuration here — base checkpoint, seed policy, architecture, pooling, batch
   size, learning rate + schedule, warmup, weight decay, optimizer updates (target 20,000),
   temperature τ (0.05), max sequence length, evaluation set, metric code version, index type
   (flat exact), RRF k, context-assembly step version.
2. Record its hash and a **benchmark snapshot** (latency p50/p95/p99 per stage) in `RESULTS.md`.
3. Record an ADR "Retrieval stack frozen" and mark this directory immutable in `PROJECT_STATE.md`.

Varies across arms: the supervision strategy, and nothing else. A CI/test check should fail if any
file here changes after the freeze hash was recorded.

Reference defaults to start from (`docs/09_architecture.md`): mean pooling (masked), τ 0.05
(range 0.03–0.07), lr 2e-5 linear decay with 10% warmup, 20,000 updates, max length 512, RRF k=60,
≥3 seeds. These are starting points, not frozen values.
