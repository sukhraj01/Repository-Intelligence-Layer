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
| 2026-10-17 | s4-core-bench-instance-ids | measured | Query ids and qrels rows streamed for all 1,458 CORE-Bench folders (L2, L3, Rewrite) | 1d6a4a651435 | none (deterministic) | ada gnode002 job 24595, 4 CPU, 19.6 min | queries 5,061 (L2) / 2,580 (L3) = card; qrels 52,712 / 106,479 = card; all scores 1; every query has a positive; 6.1 GB streamed, ids and counts kept | `results/logs/s4_ground_truth_b_2026-10-17.json` |
| 2026-10-17 | s4-core-bench-corpus-stats | measured | Corpus rows and chunk lengths streamed for 729 L2/L3 folders | 1d6a4a651435 | none (deterministic) | ada gnode002 job 24596, 4 CPU, 17.0 min | corpus rows 9,377,120 / 2,609,581 = card; mean chunk 1,004.9 / 1,154.8 characters = card; longest chunk 1,009,865 characters; all ids 36-char UUIDs; 13.8 GB streamed | `results/logs/s4_ground_truth_b_2026-10-17.json` |
| 2026-10-17 | s4-core-bench-query-stats | measured | Mean query length and per-query candidate-list size, 729 L2/L3 folders | 1d6a4a651435 | none (deterministic) | ada gnode002 jobs 24605+24606, 4 CPU, 5.3 min | mean query 1,558.5 (L2) / 1,074.4 (L3) characters = card; candidates per query mean 9,783 / 11,391, min 32, max 348,310 / 139,977 | `results/logs/s4_ground_truth_b_2026-10-17.json` |
| 2026-10-17 | s4-repo-resolution | measured | Canonical owner/name of every CORE-Bench folder from its instance ids | 1d6a4a651435 | none (deterministic) | local, scripts/build_held_out.py | 1,458 of 1,458 folders resolved; L2 632 folders = 605 distinct repositories, L3 97 = 92; 17 L2 and 2 L3 folders hold several repositories; 242 L2 / 17 L3 folder names differ from their repository | `results/logs/s4_ground_truth_b_2026-10-17.json` |
| 2026-10-17 | s4-held-out-list | measured | Held-out list = L2 union L3 union Verified (Rewrite sets identical to originals) | 1d6a4a651435 | none (deterministic) | local, scripts/build_held_out.py | 605 repositories; L2&L3 = 92 (L3 inside L2); Verified 12 inside both; sha256 7ba5c9d8d27d...f477783 (data/held_out/held_out_repos.sha256) | `results/logs/s4_ground_truth_b_2026-10-17.json` |
| 2026-10-17 | s4-loc-bench-overlap | measured | Loc-Bench repositories against the held-out list (reported, not held out) | 1d6a4a651435 | none (deterministic) | local | V1: 165 repositories, 37 in list, 128 not; V0.2: 210, 41 in list, 169 not | `results/logs/s4_ground_truth_b_2026-10-17.json` |
| 2026-10-17 | s4-paired-n | measured | Instance ids of L2/L3 Verified folders against SWE-bench Verified metadata | 1d6a4a651435 | none (deterministic) | local | L2&Verified 432, L3&Verified 302, L2&L3 (Verified) 302; 0 ids absent; all datasets: distinct ids L2 5,035, L3 2,567, both 2,567 | `results/logs/s4_ground_truth_b_2026-10-17.json` |
| 2026-10-17 | s4-rewrite-qrels | measured | Rewrite folders against originals | 1d6a4a651435 | none (deterministic) | local | query id sets identical in 729 of 729 folders; 81 Multilingual Rewrite folders have no qrels; 13 folders have fewer qrels rows (158 in all); Rewrite qrels 51,258 (L2) / 101,145 (L3) | `results/logs/s4_ground_truth_b_2026-10-17.json` |
| 2026-10-17 | s4-pool-filter-codesearchnet | measured | filter_pool on CodeSearchNet python by repository_name | 1d6a4a651435 | none (deterministic) | ada gnode002 job 24604 (counts) + local | 457,461 rows / 13,590 repositories before; 449,440 / 13,546 after exact-name filter (44 held-out repositories, 8,021 rows dropped); with current-name resolution of 51 candidates 447,837 / 13,530; with Loc-Bench 445,640 / 13,534 | `results/logs/s4_ground_truth_b_2026-10-17.json` |
| 2026-10-17 | s4-pool-filter-gangiswag-candidate | measured | filter_pool on the gangiswag/train_data python candidate (provisional, Q7), repositories from zip directory names | 1d6a4a651435 | none (deterministic) | ada job 24604 + local | 24,285 instances / 2,448 repositories before; 20,854 / 2,359 after (89 held-out repositories, 3,431 instances dropped); current-name resolution 20,800 / 2,356; Loc-Bench adds none | `results/logs/s4_ground_truth_b_2026-10-17.json` |
| 2026-10-17 | s4-pool-filter-cornstack | measured | CoRNStack python repository filter | 1d6a4a651435 | none (deterministic) | schema read (S2) | cannot be repo-filtered: no repository identifier | `results/logs/s4_ground_truth_b_2026-10-17.json` |
| 2026-10-17 | s4-github-name-check | measured | Same-name-other-owner pool repositories looked up on the GitHub API | 1d6a4a651435 | none (deterministic) | ada login node, unauthenticated | 59 lookups (CodeSearchNet 51, candidate 10, 2 shared): 19 now resolve to a held-out repository under its current name, 0 forks of held-out repositories, 2 no longer exist; lower bound (renames with a different name part are not found) | `results/logs/s4_ground_truth_b_2026-10-17.json` |
| 2026-10-17 | s4-label-quality | measured | 30 seeded L2 Verified instances over six repositories, 53 positives classified (counts only) | 1d6a4a651435 | 0 | ada login node, seed 0 | 50 code, 3 import blocks, 0 docs/comments/tests/config by a crude heuristic; 35 of 53 start at a def/class; 17 single-positive and 13 multi-positive instances in the sample (44 / 39 in the 83-instance population) | `results/logs/s4_ground_truth_b_2026-10-17.json` |

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
