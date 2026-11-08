# results/rq3_units/

Unit records, BM25 scores and unit-text vectors of the executable subset of Verified (decision D107, entry `E-RQ3-UNITS` in `docs/experiments/B.md`). Build only: no retrieval result, no agent call.

| File | What |
|---|---|
| `instances.csv` | one row per built instance (341): units, labelled levels, issue-text source, unit-stage and cache seconds, peak resident size, rank check, gold readings present |
| `distinct_counts_five.json`, `distinct_counts_xarray.json` | unit slots and distinct texts per repository, saving factor, and the encoding rule evaluated on the count |
| `vector_check_five.json`, `vector_check_xarray.json` | per-text check that every unit text of every instance has a vector (0 missing) |
| `encode_coderankembed_five_63012.json`, `encode_coderankembed_xarray_63024.json` | encoder run logs: CUDA gate, revision, seconds and texts per second per store, peak GPU memory, float16 agreement (the model id is written without the organisation prefix, as in earlier logs; the revision hash is kept) |
| `env_cpu_62880.txt`, `env_encode_63012.txt` | node and code-label records of the first pass |
| `manifest.csv` | path (under `ril_rq3u/` or `ril_rq3u_x/` on account A), size and SHA-256 of the files that stay on the cluster |

The 36 executable instances that already had unit records are not rebuilt: caches in `ril_t1/work/e3_cache`, dense scores in `ril_x2/dense/coderankembed__t512` on account A.
