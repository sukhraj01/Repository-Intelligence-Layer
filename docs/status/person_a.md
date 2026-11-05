# Status: workstream A (retrieval stack and RQ1)

> Current truth only, replaced at the end of each block (at most 150 lines). Result rows are in
> `results/ledger_a.md`; protocols and full tables in `docs/experiments/A.md` (sections A1-PILOT, A2a, A2c, A2b-PREP, A2b).

**Last updated:** 2026-11-03 · branch `a/rq1-2` from `main` (A1-PILOT and A2a merged; A2c and A2b carried over from `a/rq1`) · block 1 partly done (A1 code and a local pilot; A2 parts a and c; A2 part b static reading).

## Done

| Session | What | State | Evidence |
|---|---|---|---|
| A2 (a) | Incremental graph update (`ril/parsing/incremental.py`): re-parses changed files, rebuilds structure edges from summaries, re-resolves only files that changed or depend on a changed module summary or method name | **done**, gate met: 100 of 100 updates equal to the full rebuild (5 repositories x 20 commits); median speedup 1.3x to 9.6x (django 29.2 s to 3.0 s per commit) | A2a, `results/tables/a2_incremental_update.csv` |
| A2 (a) | Resolver cache made order-independent (cycle-cut results no longer cached; `ril/parsing/call_graph.py`) | done; full-build effect 2 of 4,163 edges on requests, 0 on flask and django | A2a; regression test in `tests/unit/test_incremental_graph.py` |
| A2 (c) | Stored graph as a versioned, hashed edge-list directory (`ril/parsing/edge_store.py`, format v1): byte-identical writes, load refuses unknown versions and damaged files | **done**: round trip exact on 5 repositories; 16-20x smaller than raw JSONL; django loads in 2.3 s with hash checks | A2c, `results/tables/a2c_edge_store.csv` |
| A2 (b) prep | Static breakdown of failed call sites by rule (no oracle needed) | done: 80% of ambiguous or unresolved sites are calls on a receiver of unknown type | A2b-PREP |
| A2 (b) static | Three resolver typing options (`ResolverOptions`: return inference, merged locals, parameter defaults), off by default; stored resolver byte-identical | done (static): combined +1,133 resolved sites over 5 repositories (+1.2%), unknown-receiver sites -4.3%, build +9%; untyped receivers are mostly attribute chains and parameters (inter-procedural typing needed) | A2b, `results/tables/a2b_resolver_pilot_static.csv` |
| A1 (code) | Identifier splitting (`split_identifier`, `tokenize_code`, option to keep the whole identifier) and integer field weights (`field_tokens`) in `ril/retrieval/bm25_index.py`; the reference form is unchanged | done, tested | `tests/unit/test_bm25_index.py` |
| A1 (pilot) | Docstring-to-function retrieval on 5 local checkouts, docstrings removed from the index (exploratory) | done: splitting +8.9 MRR [+6.9, +10.5] clustered, name weight +13.1 [+10.3, +15.9]; query latency unchanged | A1-PILOT, `results/tables/a1_bm25_docstring_pilot.csv` |

## Not done yet (in order)

1. A1 on the development repositories (cluster): one-factor runs (splitting, keep-original, fields, k1/b), E1 reproduction
   as regression control, unit vs chunk granularity under both gold readings; Verified-six once with the chosen setting.
2. A2 (b) dynamic reading: recall and precision of each pilot against the flask suite trace (needs the trace from the
   engineer's terminal or the cluster, `scripts/ada/trace_flask_suite.sbatch`); then, if worth it, inter-procedural
   argument typing for parameters and `self` attributes (the largest share of untyped receivers).
3. A3 structural signals against the same-file control (needs the dense scores of the dev caches on the cluster).
4. A4 RQ1 ablation table with latency columns; A5 rerank; A6 end-to-end latency profile.

## Requests for the lead

| # | Question | Options | Evidence class | Cheapest settling experiment | Recommendation | Used meanwhile |
|---|---|---|---|---|---|---|
| RA-1 | The resolver cache fix changes resolver output (2 edges on requests). Bump `RESOLVER_VERSION`? | (a) bump to v0.1 at the next cache rebuild; (b) keep v0 (two outputs under one name); (c) revert the fix and drop incremental updates | measured (A2a) | none needed: the edge diff is listed in A2a | (a): the evaluation caches keyed on the resolver string rebuild once | v0 kept, fix in place |
| RA-2 | Adopt the incremental updater as the per-commit graph build (agent setting, freshness)? | adopt / keep full rebuilds only | measured (A2a) | none | adopt; it is equal by test and never slower in the runs | full build stays the default of `build_repository` |
| RA-3 | A1 tuned index: which variants go into the dev sweep? | the four of A1-PILOT plus k1/b | measured locally only (A1-PILOT, exploratory) | the A1 dev runs on the cluster | run all four; the pilot's gain is an upper bound (docstrings share the function's vocabulary) | reference form (`provisional: ADR-004`) |

## Requests for workstream C

None yet.

## Compute

Local only so far (no cluster job, 0 GPU-hours of the 16). Cluster access for the A1 dev runs: account login supplied by
the engineer; not yet configured on this machine.
