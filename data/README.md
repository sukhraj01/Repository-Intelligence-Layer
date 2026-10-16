# data/

Almost everything here is **gitignored** and rebuilt by scripts. Never commit data. The one tracked
exception is `held_out/` — a small experimental artifact (the repository list that guards against leakage).

```
data/
├── raw/          downloaded datasets, one subdir each, with provenance.json   (ignored)
├── processed/    cleaned/normalised training pools and eval views            (ignored)
├── index/        per-repository CodeUnit tables, graphs, BM25/dense indices  (ignored)
├── checkpoints/  trained encoders (also copied to a durable location on Ada)  (ignored)
└── held_out/     held_out_repos.json (+ hash, report, pool-filter reports)    (TRACKED)
```

## Rules

- **The engineer does not download datasets by hand.** Data is acquired **on Ada** by jobs in
  `scripts/ada/` (resumable, idempotent, CPU-only), then synced here only if small enough for the
  8 GB local box. See `docs/COMPUTE.md`.
- Every fetched dataset has `data/raw/<dataset>/provenance.json`: source URL, date, sha256, row/file
  counts. Verify before use.
- **Measure before you stage:** check on-disk size and free quota first. CORE-Bench L2 is ~9.4M chunks.
- Treat the training pool and the held-out list as a pair: nothing enters `processed/` for training
  without passing the repository-level filter (`specs/held_out_repos.md`).
- Index artifacts record the `CODEUNIT_SCHEMA_VERSION` and config hash they were built with.
