# results/

Machine-generated outputs. **Every number in a report traces to a file here** (and to a line in
`RESULTS.md`).

```
results/
├── latency/   latency_log.csv, throughput_log.csv   — append-only, written by the harness (TRACKED)
├── rq1/       signal ablation, one directory per experiment run
├── rq2/       supervision arms × seeds, budget-accounting tables
├── rq3/       agent runs, paired per-instance outcomes, failure breakdowns
├── logs/      run logs: config hash, seed, hardware spec, stdout (TRACKED)
├── tables/    generated tables for the report
└── figures/   generated figures for the report
```

Layout of one run: `results/<rq>/<exp_id>/<YYYY-MM-DD>_<confighash8>/` with `config.yaml`,
`results.json`, `hardware.json`.

Rules:

- Append-only logs (`latency_log.csv`, `RESULTS.md`) are never edited; supersede with a new row.
- Latency is p50/p95/p99, never the mean. RQ2 reports mean ± SD over ≥3 seeds.
- Large raw outputs (per-instance dumps, embeddings) stay on Ada; keep summaries and per-instance
  *outcome* tables here.
- `measured` vs `paper_reported` is always labelled.
