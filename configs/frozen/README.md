# configs/frozen/ — freeze records, one per consumer

The retrieval setting is not the same in every consumer (the RRF k is 60 in the RQ2 evaluation and 100
in the RQ3 contexts and the dev selection; the truncation and the budgets differ as well), and changing
a consumer would invalidate the RQ2 run hashes or the contexts already built, so nothing is unified.
Each consumer's setting is frozen as its own record, written by `scripts/freeze_records.py write` from
the consumer's stored configuration (never retyped):

| Record | Consumer | Setting |
|---|---|---|
| `rq2_evaluation.json` | checkpoint evaluation of the RQ2 final runs (45 rendered configurations, templates and cell table) | dense alone and RRF(BM25, dense) at k 60, 512 tokens, dev role |
| `rq3_contexts.json` | retrieved contexts of the executable instances and the assembly stage | RRF k 100, 512 tokens, 200 candidates, unit cap 1,000, budgets 8,000 and 16,000 |
| `rq1_dev_selection.json` | the dev selection and the RQ1 ladder | RRF k 100, 1,024 tokens |

Every record carries: the sources with their SHA-256 and the hash the consumer itself stores or computes,
the configuration as the consumer uses it, the encoder (revision pinned) and BM25 variants, the resolver
version, the assembly rule and budgets, the measured dev difference between its setting and the other
consumers' settings, a latency snapshot (stored rows of the stages on its path, p50 / p95 / p99, host,
query set, index size) with the stages that have no row listed, and `not_found` for any stored
configuration that could not be located. No expansion and no recency prior is on in any record. Values
that carry a `provisional` label in their consumer keep it in `provisional_in_consumer`.

`MANIFEST.json` holds the SHA-256 of every record. `tests/unit/test_frozen_records.py` fails when a
record, the manifest, a source configuration, an RQ2 run configuration or a recorded latency row
changes. A record is never rewritten; a changed setting is a new record with its own entry.

The held-identical block of the RQ2 design stays in `docs/08_experimental_design.md`.
