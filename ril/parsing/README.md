# ril/parsing/

**Files:** `code_unit.py`, `unit_id.py`, `repo_id.py`, `path_rules.py` (the frozen CodeUnit and its helpers);
`repository_parser.py` (phase one: files to units and per-file symbol summaries), `call_graph.py` (phase two: the
`ast` resolver and the graph builder), `repo_graph.py` (the typed edge store, DRAFT v0), `exploratory_edges.py`
(`tests` and `configures`), `git_history.py` (D8 `last_modified` and the `co_change` counts), `build.py` (one build,
its timings and canonical artifacts), `report.py` (ten sample units and the statistics).
Contracts: `specs/code_unit.md` (FROZEN v1), `specs/repo_graph.md` (DRAFT v0), `specs/parse_one_repo.md`.
Design: `docs/05_structural_signals.md`, `docs/09_architecture.md`, `docs/GRAPH_DESIGN.md`.

- The parse skips caches, environments, build output, vendored directories and generated files; files that
  fail to parse are counted and listed, never dropped silently.
- Units: top-level functions, methods and classes, plus one residual `module` unit per file (D6); ids follow D11.
- Edges: `contain`, `import`, `invoke` (one edge per call site, with a status), `inherit`, `override`. Exploratory
  and written to their own files: `tests`, `configures`. `co_change` is counts only.
- The resolver is the project's own `ast` resolver (`provisional: ADR-011`); it records the rule behind every edge.
- Output is canonical: the same checkout builds byte-identical files (`tests/reproducibility/test_graph_repro.py`).
- Compatible with Python 3.10, so the same code runs on the cluster nodes.

Depends on: `config/` only.
