# ril/training/

Design: `docs/08_experimental_design.md`, `docs/04_data_and_ground_truth.md`. Everything that trains is
`provisional: ADR-001, ADR-002, ADR-006` until the engineer settles those ADRs; nothing here enters
`configs/frozen/` (a provisional configuration is refused there).

**Training stack** (built 2026-10-25):

| File | Role |
|---|---|
| `pool_reader.py` | select pool directories (held-out list D1/D3, feature-table coverage), stream them by range request, yield `PoolExample` (query, positives, negative candidates, repository, ids); untracked example cache |
| `negatives.py` | negative policies, **held identical across arms** (Q46): `random_repo`, `teacher_top_m`, `teacher_top_m_poscut` (cut relative to the positive's teacher score), `structural` (pilot factor only, refused in arm runs); teacher mining (BM25, dense) |
| `supervision.py` | the **three arm hooks** — filter (FILTER), weigher (WEIGHT), ordering (CURRICULUM) — and the K-rank quality signal from the E-POOL-RANKS feature table (minimum rank over an example's positives); RAW = the three identities |
| `data_loader.py` | shared batch planner: distinct examples per batch, seeded positives and negatives keyed by (seed, instance, visit), in-batch negatives with masks for the same function or text as a positive; exposure counts |
| `contrastive_loss.py` | multi-positive InfoNCE (CORE-Bench form or mean over positives), per-example weights |
| `encoders.py` | tiny CPU test model (not a retriever) and the `sentence-transformers` wrapper of a registered encoder; both readable by the X2 evaluation code |
| `training.py` | one run: fixed optimizer updates, AdamW and schedule, budget table, step checkpoints and exact resumption by plan replay, result directory, configuration-comparability check |
| `train_jobs.py` | job bodies (select, cache, mine, train) behind `scripts/train.py` |

The arms differ only through the three hooks: `tests/unit/test_arms_only_differ_through_hooks.py` runs
every arm at its hook's identity limit and requires bit-identical batches, gradients and parameters to
RAW's; `training.check_comparable` refuses configurations that differ outside the `arm` section.
The checkpoint evaluation lives in `ril/evaluation/checkpoint_eval.py` and is wired in
`scripts/train.py eval`: the training package does not import evaluation code (leakage check (d)).

Earlier modules: held-out list and filter (`held_out.py`, `held_out_build.py`, `rename_resolution.py`,
`content_overlap.py`, `leakage.py`), pool check and pool ranks (`pool_check.py`, `pool_ranks.py`,
`pool_rank_jobs.py`), contamination scan (`contamination*.py`).

Depends on: `parsing/`, `config/`, `util/`, and the encoder classes of `retrieval/` (never trained
weights for the K-rank, which comes from a precomputed table).
