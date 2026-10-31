# results/

Machine-generated outputs. **Every number in a report traces to a file here** (and to a line in
`RESULTS.md`).

```
results/
├── latency/   latency_log.csv, throughput_log.csv   — append-only, written by the harness (TRACKED)
├── rq1/       signal ablation, one directory per experiment run (empty until the RQ1 ablation runs)
├── rq2/       supervision runs: one directory per experiment id, one subdirectory per run
│              (pilot runs of the smoke, learning-curve and arms pilots; no frozen-configuration run yet)
├── rq3/       agent runs, paired per-instance outcomes, failure breakdowns (empty until the agent runs)
├── logs/      run logs: config hash, seed, hardware spec, counts; ada_jobs.csv lists every cluster job (TRACKED)
├── tables/    tables written by the table builders in ril/analysis/ and scripts/; the CSVs behind the
│              numbers quoted in docs/EXPERIMENTS.md, named by experiment prefix (e1, x2, t5, ...)
├── figures/   generated figures for the report (empty so far)
└── ledger_*.md  result rows of one workstream (ledger_a.md: workstream A), in the RESULTS.md row
               format; the maintainer merges them into RESULTS.md, which stays the single list
```

Layout of one run: `results/<rq>/<exp_id>/<YYYY-MM-DD>_<confighash8>/` with the configuration,
`results.json` and the hardware record (training runs add per-query rows and, for a curve, one
`step_<n>/` subdirectory per evaluated update count).

Rules:

- Append-only logs (`latency_log.csv`, `RESULTS.md`) are never edited; supersede with a new row.
- Latency is p50/p95/p99, never the mean. RQ2 reports mean ± SD over ≥3 seeds.
- Large raw outputs (per-instance dumps, embeddings) stay on Ada; keep summaries and per-instance
  *outcome* tables here.
- `measured` vs `paper_reported` is always labelled.
