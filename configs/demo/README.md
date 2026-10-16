# configs/demo/ — the product / portfolio configuration

Tuned freely for the best demo: reranker settings, token budget, query handling, caching. Kept
**separate from `frozen/`** so that tuning the product never contaminates the experiment, and
freezing the experiment never blocks the product. Nothing in `demo/` may be used in an RQ2 or RQ3 run.
