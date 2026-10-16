# ril/evaluation/

**Planned files:** `metrics.py`, `core_bench.py`, `agent_integration.py`.
Design: `docs/06_core_bench.md`, `docs/08_experimental_design.md`.

- `core_bench.py` — loaders for `LEVEL-2/<dataset>/<repository>/{corpus,queries,qrels}.jsonl` and the
  REWRITE variants; chunk-level granularity for reported metrics (ADR-004).
- `metrics.py` — nDCG@10, MRR, Recall@10; one metric implementation shared by every experiment.
  Sanity check: reproduce a published CORE-Bench figure before trusting new numbers.
- `agent_integration.py` — run the fixed scaffold with each retriever; for every failure log
  **whether the gold-patch file was in the retrieved context** (retrieval vs reasoning failure);
  paired per-instance outcomes for McNemar; resolved rate per agent wall-clock.

Depends on: `retrieval/`, `parsing/`, `config/`.
