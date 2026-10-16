# ril/parsing/

**Planned files:** `code_unit.py`, `repository_parser.py`, `call_graph.py`.
Contracts: `specs/code_unit.md` (DRAFT), `specs/parse_one_repo.md`. Design: `docs/05_structural_signals.md`, `docs/09_architecture.md`.

- Walk a repository, skipping `__pycache__`, `.git`, vendored and generated files; parse with `ast`.
- Emit `CodeUnit`s; build call / import / inherit graphs (LocAgent node and edge types).
- **Measure and report edge-recovery coverage** (expected 70–85%; definition pending — see the
  provisional ADR from `specs/parse_one_repo.md`).
- Later (weeks 7–10): test and configuration nodes with `tests` / `configures` edges.

Depends on: `config/` only.
