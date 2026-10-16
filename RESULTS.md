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
| — | — | — | no runs yet | — | — | — | — | — |

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
