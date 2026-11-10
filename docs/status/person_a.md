# Status: workstream A (retrieval stack and RQ1)

> Current truth only, replaced at the end of each block (at most 150 lines). Result rows are in
> `results/ledger_a.md`; protocols and full tables in `docs/experiments/A.md` (sections A1-PILOT, A2a, A2c, A2b-PREP, A2b).

**Last updated:** 2026-11-05 · branch `a/rq1-2` from `main` (A1-PILOT and A2a merged; A2c and A2b carried over from `a/rq1`) · block 1 nearly done (A2 done: parts a, b and c; A1 chunk-level dev selection done, fields and granularity open).

## Done

| Session | What | State | Evidence |
|---|---|---|---|
| A2 (a) | Incremental graph update (`ril/parsing/incremental.py`): re-parses changed files, rebuilds structure edges from summaries, re-resolves only files that changed or depend on a changed module summary or method name | **done**, gate met: 100 of 100 updates equal to the full rebuild (5 repositories x 20 commits); median speedup 1.3x to 9.6x (django 29.2 s to 3.0 s per commit) | A2a, `results/tables/a2_incremental_update.csv` |
| A2 (a) | Resolver cache made order-independent (cycle-cut results no longer cached; `ril/parsing/call_graph.py`) | done; full-build effect 2 of 4,163 edges on requests, 0 on flask and django | A2a; regression test in `tests/unit/test_incremental_graph.py` |
| A2 (c) | Stored graph as a versioned, hashed edge-list directory (`ril/parsing/edge_store.py`, format v1): byte-identical writes, load refuses unknown versions and damaged files | **done**: round trip exact on 5 repositories; 16-20x smaller than raw JSONL; django loads in 2.3 s with hash checks | A2c, `results/tables/a2c_edge_store.csv` |
| A2 (b) prep | Static breakdown of failed call sites by rule (no oracle needed) | done: 80% of ambiguous or unresolved sites are calls on a receiver of unknown type | A2b-PREP |
| A2 (b) | Three resolver typing options (`ResolverOptions`: return inference, merged locals, parameter defaults), off by default; stored resolver byte-identical | **done**: static, combined +1,133 resolved sites over 5 repositories (+1.2%), unknown-receiver sites -4.3%, build +7.1% (within timing noise); dynamic on the flask suite trace, recall 48.3% to 49.2%, precision lower bound 61.8% to 62.0%, all 13 added pairs right by trace or source; the remaining failures are mostly attribute chains and parameters (inter-procedural typing) | A2b, `results/tables/a2b_summary.json` |
| A1 (code) | Identifier splitting (`split_identifier`, `tokenize_code`, option to keep the whole identifier) and integer field weights (`field_tokens`) in `ril/retrieval/bm25_index.py`; the reference form is unchanged | done, tested | `tests/unit/test_bm25_index.py` |
| A1 (dev, chunk level) | BM25 tokenizer then k1/b on the CORE-Bench dev folders (6 repositories, 680 queries), rule fixed before the run; own cluster account | **done**: regression control exact (E1 dev default, 23.8244); `split` +5.9 nDCG@10 over `ref`, clustered [+3.3, +8.2], every repository; k1 2.0 / b 0.75 +0.6 [+0.1, +1.0] (edge of grid); candidate `configs/candidates/bm25_A.yaml` | A1-DEV, `results/tables/a1_bm25_dev.csv` |
| A1 (pilot) | Docstring-to-function retrieval on 5 local checkouts, docstrings removed from the index (exploratory) | done: splitting +8.9 MRR [+6.9, +10.5] clustered, name weight +13.1 [+10.3, +15.9]; query latency unchanged | A1-PILOT, `results/tables/a1_bm25_docstring_pilot.csv` |

## Not done yet (in order)

1. A1 rest (cluster): field weights and unit vs chunk granularity under both gold readings (needs unit texts at each
   instance's base commit: the lead's E3 dev cache, or clones and a cache built in A's account); then the Verified six
   once with the single final setting.
2. A3 structural signals against the same-file control (needs the dense scores of the dev caches on the cluster).
3. A4 RQ1 ablation table with latency columns; A5 rerank; A6 end-to-end latency profile.
4. Optional, after A3 shows whether call edges matter for retrieval: inter-procedural argument typing for parameters and
   `self` attributes (the largest share of untyped receivers in A2b).

## Requests for the lead

| # | Question | Options | Evidence class | Cheapest settling experiment | Recommendation | Used meanwhile |
|---|---|---|---|---|---|---|
| RA-1 | The resolver cache fix changes resolver output (2 edges on requests). Bump `RESOLVER_VERSION`? | (a) bump to v0.1 at the next cache rebuild; (b) keep v0 (two outputs under one name); (c) revert the fix and drop incremental updates | measured (A2a) | none needed: the edge diff is listed in A2a | (a): the evaluation caches keyed on the resolver string rebuild once | v0 kept, fix in place |
| RA-2 | Adopt the incremental updater as the per-commit graph build (agent setting, freshness)? | adopt / keep full rebuilds only | measured (A2a) | none | adopt; it is equal by test and never slower in the runs | full build stays the default of `build_repository` |
| RA-3 | A1 tuned index (ADR-004 evidence): take the dev-selected BM25 `split`, k1 2.0, b 0.75 (`configs/candidates/bm25_A.yaml`) as the lexical stage? | adopt the candidate / keep the reference form / wait for the field and granularity stage | measured on dev (A1-DEV: +5.9 then +0.6 nDCG@10, clustered intervals above 0; regression control exact) | the field and granularity stage; one Verified-six reading after the final setting | adopt the tokenizer now (large, consistent gain); treat k1 2.0 as provisional until fields are measured | reference form (`provisional: ADR-004`) |
| RA-4 | Adopt the A2b typing options (`merge_locals`, `infer_returns`; `param_defaults` adds almost nothing) in the stored resolver? | (a) adopt with the RA-1 version bump, one cache rebuild for both; (b) adopt with a bump of its own; (c) keep them off | measured (A2b; dynamic on one repository) | none needed for correctness (13 of 13 added pairs right on flask); a second traced suite would size the gain | (a): the moved pairs are right and nothing is removed, but the gain (+0.9 recall points on flask) does not justify a rebuild of its own | options off (stored resolver) |

## Requests for workstream C

None yet.

## Compute

Own cluster account (course allocation: 1 job, 6 h, 10 CPU, 1 GPU, 25 GB) configured 2026-11-05; three CPU jobs so far
(`results/logs/ada_jobs_a.csv`), 0 GPU-hours of the 16. Dev folders under the account's `ril_a/raw` (0.8 GB).

## Closed by the lead while the owner is away (dated lines)

- 2026-11-10 (E-FREEZE-AND-LATENCY, D148): item 1 of "Not done yet" for the development set: unit-level BM25 variants and field weights, one factor at a time with the E1 default as control (508 of 508 levels reproduce the stored scores), alone and inside RRF with the stored dense scores. Identifier splitting is the best variant by the rule and does not change the fusion on L2 nDCG@10 (-0.29 [-1.74, +1.16]); the path field and the pilot weights raise L2 Recall@100 inside the fusion (+2.93 [+0.88, +4.98], +2.64 [+0.82, +4.45]); at L3 (two repositories, query level) splitting is +2.75 [+1.59, +3.90] at Recall@100. Still open: one Verified reading of the final setting, only after the lead says so.
- 2026-11-10 (same entry): item 3, the stages of the ablation table that had no latency row, measured on the M3 at django and flask size: rank fusion 5.04 ms p50 at django size, same-file expansion 0.41, recency prior 2.04; the ladder's latency column is rebuilt from the log. A5 (rerank) and A6 (end-to-end latency profile) stay open.
- 2026-11-10 (same entry): the retrieval settings are recorded per consumer in `configs/frozen/` (RQ2 evaluation k 60, RQ3 contexts and dev selection k 100; nothing unified); a test fails when a record changes.
