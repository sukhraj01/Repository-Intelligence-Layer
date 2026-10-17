# ril/analysis/

**Files:** `graph_tables.py` (tables of the first parse-and-graph build), `reach_tables.py` (pilot M), `e1_tables.py` and `e1_run_log.py` (pilot E1/E2). **Planned:** `error_analysis.py`, `visualization.py`.

- Retrieval-vs-reasoning failure split for RQ3 (was the gold-patch file in context?).
- Paired McNemar on per-instance outcomes; confidence intervals, not bare percentages.
- Latency Pareto (nDCG per millisecond), budget-accounting tables, figures for the report.

Reads `results/` only; never imports from training or retrieval internals.
