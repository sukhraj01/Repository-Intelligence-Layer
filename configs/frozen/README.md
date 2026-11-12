# configs/frozen/ — freeze records, one per consumer

A record is frozen when a registered or built artefact depends on it; settings kept only for provenance are in `configs/records/`.

The retrieval setting is not the same in every consumer (the RRF k is 60 in the RQ2 evaluation and 100
in the RQ3 contexts and the dev selection; the truncation and the budgets differ as well), and changing
a consumer would invalidate the RQ2 run hashes or the contexts already built, so nothing is unified.
Each consumer's setting is frozen as its own record, written by `scripts/freeze_records.py write` from
the consumer's stored configuration (never retyped):

| Record | Consumer | Setting |
|---|---|---|
| `rq2_evaluation.json` | checkpoint evaluation of the RQ2 final runs (45 rendered configurations, templates and cell table) | dense alone and RRF(BM25, dense) at k 60, 512 tokens, dev role; **frozen at launch**: the 45 runs were submitted from commit `c2a8db6` on the registered cell table (SHA-256 `f441e765…6f16f90`, as recorded in the record) |
| `rq3_contexts.json` | retrieved contexts of the executable instances and the assembly stage | RRF k 100, 512 tokens, 200 candidates, unit cap 1,000, budgets 8,000 and 16,000; **frozen**: the contexts of the 377 executable instances are built on it (configuration hash `e2f011c3…8b4d4c`, context manifest `9784f5ae…fb7`) and the pilot used them; a change after 2026-11-12 invalidates both and needs a new decision |

The dev selection (`rq1_dev_selection.json`, CodeRankEmbed at 1,024 tokens, RRF k 100) is not a frozen
configuration: no final run consumes it. It is kept as a record in `configs/records/`.

Every record carries: the sources with their SHA-256 and the hash the consumer itself stores or computes,
the configuration as the consumer uses it, the encoder (revision pinned) and BM25 variants, the resolver
version, the assembly rule and budgets, the measured dev difference between its setting and the other
consumers' settings, a latency snapshot (stored rows of the stages on its path, p50 / p95 / p99, host,
query set, index size) with the stages that have no row listed, and `not_found` for any stored
configuration that could not be located. No expansion and no recency prior is on in any record. Labels
the consumer carried before the ruling are kept in `labels_in_consumer_before_ruling`.

`MANIFEST.json` holds the SHA-256 of every frozen record. `tests/unit/test_frozen_records.py` fails when a
record, the manifest, a source configuration, an RQ2 run configuration or a recorded latency row
changes; it does not cover `configs/records/`. A record is never rewritten; a changed setting is a new
record with its own entry.

Correction, 2026-11-12: an earlier statement gave the largest difference between the settings as at
most 0.5 points. As measured on dev (L2 nDCG@10) it is at most 0.59 points (RQ3 contexts against the
dev selection) and 0.48 for the RQ2 evaluation against either other setting. The records carry the
same correction line. On 2026-11-12 the records' "provisional" labels were replaced by their status
(`status` field); the earlier ADR and decision labels are kept as `labels_in_consumer_before_ruling`.

The held-identical block of the RQ2 design stays in `docs/08_experimental_design.md`.
