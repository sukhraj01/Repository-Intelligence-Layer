# ril/evaluation/

**Planned files:** `metrics.py`, `core_bench.py`, `agent_integration.py`.
Design: `docs/06_core_bench.md`, `docs/08_experimental_design.md`.

- `core_bench.py` — loaders for `LEVEL-2/<dataset>/<repository>/{corpus,queries,qrels}.jsonl` and the
  REWRITE variants; chunk-level granularity for reported metrics (ADR-004).
- `metrics.py` — nDCG@10, MRR, Recall@10; one metric implementation shared by every experiment.
  Sanity check: reproduce a published CORE-Bench figure before trusting new numbers.
- Built for pilot E1/E2: `core_bench.py` (folder loader and the chunk-level protocol, with the ranks of every positive), `metrics.py`
  (binary-gain nDCG/Recall from ranks, bootstrap intervals), `unit_retrieval.py` (BM25 over the units of one snapshot, with and without
  the module unit), `label_noise.py` (import-only, comment-only, documentation and edit-overlap readings of the positives),
  `e1_run.py` (resumable runner). The metric reproduced the published BM25 row of the benchmark on Verified (`docs/EXPERIMENTS.md`).
- `agent_integration.py` — run the fixed scaffold with each retriever; for every failure log
  **whether the gold-patch file was in the retrieved context** (retrieval vs reasoning failure);
  paired per-instance outcomes for McNemar; resolved rate per agent wall-clock.

- `dynamic_trace.py`, `edge_recovery.py`, `jedi_agreement.py`, `edge_samples.py` — the edge-recovery measurements of
  `specs/parse_one_repo.md` (ADR-012): a function-level tracer for a repository's own test suite and the comparison
  with the static graph (definition (b)), the second-resolver agreement sample (c), and seeded samples for
  inspection by reading (d) and for the exploratory edges' precision.

Depends on: `retrieval/`, `parsing/`, `config/`.
