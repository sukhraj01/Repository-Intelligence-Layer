# results/rq3_contexts

Retrieved contexts of the 377 executable instances (E-RQ3-CONTEXTS, D108; `docs/experiments/B.md`).

- `rq3_contexts_coverage.csv`: per level, arm, budget and view (file / unit), the denominators and shares.
- `rq3_contexts_size.csv`: tokens, units and files per arm and budget; share of contexts whose budget binds.
- `rq3_contexts_contexts.csv`: one row per (instance, arm, budget) with the context's SHA-256, tokens, units, files.
- `rq3_contexts_manifest.csv`: path, size and SHA-256 of the 377 per-instance files kept on the cluster.
- `determinism.json`: 30 instances built twice, hashes compared.
- `env_63792.txt`, `config_hash_63792.txt`: node, interpreter, code commit and configuration hash of the run.

The per-instance files (context text and manifest of every arm and budget) are not in the repository.
