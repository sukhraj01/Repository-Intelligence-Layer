# CoRNStack (Python)

- **URL:** Hub dataset `cornstack-python-v1`, Python split of CoRNStack (Nomic organisation; card sha 25fb04bd, licence apache-2.0 per card metadata). Schema-only check on 2026-10-17 from Ada.
- **Files (measured):** `shard-00000` to `shard-00037` `.jsonl.gz`, about 1.3 GB each (about 49 GB total).
- **Row schema (first 200 rows of shard 0, 3 MB range request):** `query`, `document`, `document_rank`, `document_score` (strings), `metadata` (objective triplet descriptor), `negatives` (list of code strings), `negative_scores`.
- **No repository identifier** in the schema (no repo name, path or URL). A repository-level filter cannot be applied from the schema alone. Same for the other language variants if they share the schema (not checked).

## Repository filter (S4)

**Cannot be repo-filtered: no repository identifier.** The Python split carries no repository name, path or URL, so the held-out list cannot be applied to it (`data/held_out/pool_filter_report_cornstack_python.md`). Whether a repository can be recovered from the `document` text or by matching against GitHub was not attempted; recovering one would be a pool-construction step, not a filter.
