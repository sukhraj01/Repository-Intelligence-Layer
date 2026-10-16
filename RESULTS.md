# RESULTS

Every benchmark ever run, **append-only, one line per run**. Do not edit or delete past rows; a
wrong row gets a new row that supersedes it (`supersedes: <run_id>`).

Rules:

- Each row traces to a run log in `results/logs/` carrying a **config hash**, a **seed**, and the
  **hardware spec**.
- `kind` is `measured` or `paper_reported`. Never mix them in one row.
- Latency rows also go to `results/latency/latency_log.csv` (the per-commit harness writes it).
  This file records the summary line; the CSV holds the per-stage detail.
- Report p50/p95/p99 for latency, never the mean. Report mean ± SD over ≥3 seeds for RQ2 arms.
- One aggregate number per line; details live in `results/`.

## Runs

| date | run_id | kind | what | config_hash | seed | hardware | headline result | log |
|---|---|---|---|---|---|---|---|---|
| 2026-10-17 | s2-probe-login | measured | Ada login node reaches huggingface.co/github.com/pypi.org; 50 MB HF range request | 301fcc313c33 | none (deterministic) | ada-gw1 Xeon Gold 5215 | 8.87 MB/s (5.64 s for 50 MB) | `results/logs/s2_ground_truth_a_2026-10-17.json` |
| 2026-10-17 | s2-probe-compute | measured | Same probe from compute node (u22, qos low) | 301fcc313c33 | none (deterministic) | ada gnode002, 2 CPU | 6.46 MB/s (7.74 s for 50 MB); u22-cpu not usable by account research | `results/logs/s2_ground_truth_a_2026-10-17.json` |
| 2026-10-17 | s2-quota | measured | Free space on Ada home filesystem (Q6) | n/a | none (deterministic) | ada-gw1 | 24 GB avail of 50 GB (27 GB used); CORE-Bench L2+L3 originals are 17.0 GB | `results/logs/s2_ground_truth_a_2026-10-17.json` |
| 2026-10-17 | s2-listing-core-bench | measured | CORE-Bench tree listing with byte sizes | 89d7ace3094d,d0426872454b | none (deterministic) | ada-gw1 + local | 32,238,633,709 B; 4,945 files; L2+L3 16,998,825,388 B | `results/logs/s2_ground_truth_a_2026-10-17.json` |
| 2026-10-17 | s2-listing-vs-card | measured | Card vs manifest vs listing for L2/L3 counts | d0426872454b | none (deterministic) | local | 632/5,061/9,377,120/52,712 (L2) and 97/2,580/2,609,581/106,479 (L3) reproduced exactly by manifest; folder counts match listing | `results/logs/s2_ground_truth_a_2026-10-17.json` |
| 2026-10-17 | s2-fetch-core-bench-samples | measured | Fetched 3 Verified repos x L2, L3, Rewrite-L2 (33 files) | df257b3d8d14,366161ecd6ca | none (deterministic) | ada gnode job 24592 | 11 MB in 33 s total; sha256 = LFS oid for all LFS files | `results/logs/s2_ground_truth_a_2026-10-17.json` |
| 2026-10-17 | s2-format-analysis | measured | Fields, id format, qrels semantics from sample | 1768f88e29bb | none (deterministic) | ada-gw1 | corpus {_id UUID,text}; qrels binary; corpus = union of per-query filtered_corpus_id; no path/span in ids | `results/logs/s2_ground_truth_a_2026-10-17.json` |
| 2026-10-17 | s2-django-queries-stream | measured | Why Verified queries.jsonl is large (django, streamed) | n/a | none (deterministic) | ada-gw1 | 173.7 MB, 188 queries, 99.85% of bytes are filtered_corpus_id (19,049-25,391 ids/query) | `results/logs/s2_ground_truth_a_2026-10-17.json` |
| 2026-10-17 | s2-hf-metadata | measured | SWE-bench Verified and Loc-Bench V1/V0.2 metadata | df257b3d8d14 | none (deterministic) | ada-gw1 + local pyarrow | Verified 500 rows/12 repos; Loc-Bench V1 560 rows/165 repos, V0.2 660 rows/210 repos | `results/logs/s2_ground_truth_a_2026-10-17.json` |
| 2026-10-17 | s2-sweloc-search | measured | SweLoc availability: HF search, GitHub, zip listings | 5f28f3e626a0 | none (deterministic) | ada-gw1 | no dataset named SweLoc; undocumented gangiswag/train_data: 56,279 instances (python 24,285) | `results/logs/s2_ground_truth_a_2026-10-17.json` |

## Published anchors (`paper_reported`)

Reference points we will compare against. They come from the Master Project Document and have **not
been re-verified against the papers**; check each against its source before quoting it in a report
(`knowledge/papers/README.md` tracks which papers have been read in full).

| source | quantity | value |
|---|---|---|
| CORE-Bench (Zhang et al. 2026) | nDCG@10, Qwen3-8B, L1 / L2 / L3 | 71.7 / 20.3 / 34.4 |
| CORE-Bench | nDCG@10, e5-mistral-7b, L1 / L2 / L3 | 54.7 / 18.3 / 33.9 |
| CORE-Bench | SFT on 53,301 PRs, Qwen3-0.6B (L2 nDCG@10) | 17.0 → 26.5 |
| CORE-Bench | SFT on 53,301 PRs, Qwen3-8B (L2 nDCG@10) | 20.3 → 32.8 |
| LocAgent (Chen et al. 2025) | full / w/o graph traversal / w/o BM25, File Acc@5 | 88.32 / 86.13 / 75.18 |
| LocAgent | full / w/o graph traversal / w/o BM25, Function Acc@10 | 71.53 / 66.06 / 60.22 |
| Sun et al. 2022 | filtering noisy queries, MRR | +19.2% |
| SweRank (Gangi Reddy et al. 2025) | filter rank K, optimal | moderate, K ≈ 20 |
| KGCompass (Yang et al. 2025) | localized bugs needing multi-hop traversal | 69.7% |
