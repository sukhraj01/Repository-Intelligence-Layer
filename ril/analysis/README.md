# ril/analysis/

**Files:** one table builder per experiment (`graph_tables.py`, `reach_tables.py`, `e1_tables.py`, `e3_tables.py`, `x1_tables.py` to `x5_tables.py`, `s1_tables.py`, `e7_tables.py`, `t2_tables.py` to `t5_tables.py`, and others; the list is in `docs/ARCHITECTURE.md`). **Not written yet:** `error_analysis.py`, `visualization.py`.

- Retrieval-vs-reasoning failure split for RQ3 (was the gold-patch file in context?).
- Paired McNemar on per-instance outcomes; confidence intervals, not bare percentages.
- Latency Pareto (nDCG per millisecond), budget-accounting tables, figures for the report.

Reads `results/` only; never imports from training or retrieval internals.
