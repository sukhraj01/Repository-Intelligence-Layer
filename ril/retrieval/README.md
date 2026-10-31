# ril/retrieval/

**Built:** `bm25_index.py` (reference tokenisation and Lucene-variant scoring, k1/b `provisional: ADR-004`; identifier splitting and field weights as options), `dense_encoder.py` (registered encoders and a flat exact index, `provisional: ADR-006`), `graph_expansion.py` and `recency.py` (measurement code; fusion forms in `graph_expansion.py`). **Not written yet:** the fusion stage, rerank and `assemble()`.
Design: `docs/09_architecture.md` "Offline indexing" / "Online retrieval".

- BM25: identifier splitting (camelCase, snake_case); name / signature / docstring / body as
  separately weighted fields; k₁=1.2, b=0.75 (tune b).
- Dense: encode units; **flat exact** index (never ANN — ANN recall must not be a confound).
- Structural: `γ^dist(ℓ,u)` hop decay from the query location, γ≈0.5 (PPR second).
- Fusion: **RRF, k=60** (rank-based; no per-corpus retuning).
- Rerank: cross-encoder over the top 100 (ADR-009 — include but measure).
- `assemble()`: dedupe overlapping units, order for truncation survival, attach callee signatures,
  hard token budget. **Byte-identical across RQ2 arms** (reproducibility test).

Every stage registers with the latency harness. Depends on: `parsing/`, `config/`.
