# Person C status

Updated 2026-10-30. Branch `c/eval-rq3`, based on `foundation-v0` (04da656).

## Current state

C1 apparatus is implemented: D13 original-label L2/L3 Rewrite loader; BM25 and validated cached
dense scorer; shared statistics with power and legacy metric compatibility; `make eval CONFIG=...`;
config/git/input hashes, per-query paired metrics, anchor diagnostic, timing/throughput CSV output;
CPU synthetic fixture and actual dev configurations. API: `docs/EVAL_API.md`.

Evidence class measured: 48 focused C1/loader/metric/power tests pass under preliminary Python
3.12. Full-project ruff check/format passes (266 source files). Focused strict typing passes for
C1 modules with imported modules suppressed; full strict typing has six existing NumPy-version
errors outside C ownership on the host environment. Target Python 3.11 integration remains pending
its environment. Full host unit baseline reported four environment-only failures. No local model
runtime imports, model encoding or training occurred.

`make eval` runs through the synthetic two-repository L2/L3 split on CPU. Config hash
`66d0c46d7b3a0bf6ba2517d107a427a2ec52ce37525dff1851dcd2e29c462b3e`, seed 0, 2000 clustered draws:
per level n=2, Rewrite-original nDCG@10 -36.9070 pp [-36.9070,-36.9070], Recall@100 0 [0,0].
This tests intentional fixture anchor removal only. Results: `results/ledger_c.md` and E-C1-EVAL.

Published BM25 artifact rows are pinned exactly at recorded precision and match paper rounding.
The full-corpus reproduction gate is **blocked**, not passed by the artifact regression.
Statistics agree with the nine 2026-10-18 MDE cells and 45 exact power cells; shared bootstrap
compatibility matches the existing table implementation. Off-grid measured discordance is handled.

## Blockers and compute

Original/Rewrite corpora and dense model/score caches are absent. Account C connection, quota,
partition and CUDA card remain unverified. Actual dev Rewrite ablation has n=0 and no interval.
GPU-hours used: 0 of the C allocation. Dense score lookup timing is not encoding/search latency.
No dataset or model acquisition was attempted locally.

## Requests for the lead

| Question | Options | Evidence class | Cheapest experiment | Recommendation | Meanwhile |
|---|---|---|---|---|---|
| Migrate existing analysis bootstrap consumers into the shared API? | replace duplicate implementations after parity review; retain compatibility indefinitely | measured: shared Boot matches current weights/results | run all analysis table tests using the shared class, no new data | owner migrates imports and retains frozen output parity | old analysis code retained; power/metric exports delegate to stats |
| Supply original/Rewrite dev corpus and pinned CodeRankEmbed cache on account C? | acquire and run registered dev ablation; keep apparatus only | measured absence; no actual-data estimate | verify account/quota, stage one dev folder, measure memory, then paired evaluation | run BM25 and pinned dense on stated dev repos before any new final-test look | ready configs, original qrels D13, query weighting D17; no substitution |
| Admit evaluator timing stages to central harness taxonomy? | add bm25_index/cached_scores_load/cached_scores_lookup; keep per-run schema only | reasoned: lookup timing excludes model/search | inspect one fixture CSV and one real-cache run | retain explicit cache-only names until full search latency is available | standard CSV columns in per-run outputs only; no central harness edits |

## Next work

Acquire original/Rewrite dev data and pinned dense artifacts on verified account C; size from a
measured small sample, then run both stated configurations. Continue the raw mining pilot against
recorded responses while service access is unavailable. No design decision was made in C1.
