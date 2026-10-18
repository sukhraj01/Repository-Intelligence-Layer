# CoRNStack (Python)

- **URL:** Hub dataset `cornstack-python-v1`, Python split of CoRNStack (Nomic organisation; card sha 25fb04bd, licence apache-2.0 per card metadata). Schema-only check on 2026-10-17 from Ada.
- **Files (measured, tree listing of 2026-10-16, re-read 2026-10-18):** `shard-00000` to `shard-00239` `.jsonl.gz`, 240 files, 0.74 to 1.35 GB each, 307.6 GB in total. (The earlier entry of 38 shards and about 49 GB read only the first page of a paginated listing and was wrong.)
- **Row schema (first 200 rows of shard 0, 3 MB range request):** `query`, `document`, `document_rank`, `document_score` (strings), `metadata` (objective triplet descriptor), `negatives` (list of code strings, 100 or 101 per row in the rows measured), `negative_scores`. Measured on the first 200 rows of shards 0, 120 and 239: all seven fields present in every row; `document` median 393 to 476 characters; negatives median 203 to 228 characters.
- **Rows (estimate, `E-CONTAM-PROBE`):** about 15,000 to 16,000 rows per 200 MB of compressed stream at three shard positions, and each of the 24 whole shards scanned holds exactly 100,000 rows, so about 24 million rows overall (an extrapolation; the last shard is shorter and the other 216 shards were not counted).
- **No repository identifier** in the schema (no repo name, path or URL). A repository-level filter cannot be applied from the schema alone. Same for the other language variants if they share the schema (not checked).

## Repository filter (S4)

**Cannot be repo-filtered: no repository identifier.** The Python split carries no repository name, path or URL, so the held-out list cannot be applied to it (`data/held_out/pool_filter_report_cornstack_python.md`). Whether a repository can be recovered from the `document` text or by matching against GitHub was not attempted; recovering one would be a pool-construction step, not a filter.
