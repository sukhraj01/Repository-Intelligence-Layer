# Spec: Parse one real repository end to end

Source: `docs/09_architecture.md` (offline indexing), `docs/05_structural_signals.md`. Week-1
deliverable and the **week-3 milestone** shown to the professor: *"Parser running on a real
repository; ten CodeUnits and the edge-recovery percentage."*

## Purpose

Prove the parser → CodeUnit → graph path works on real code, and measure how much of the call graph
static analysis recovers. Static call-graph extraction in Python is incomplete (dynamic dispatch,
`getattr`, decorators, monkey-patching, duck typing); the expected recovery is 70–85% and **the
number must be measured and reported** — it is the credible explanation if RQ1 finds structural
signals weak.

## Inputs

- A real Python repository. Choosing it is an implementation choice: pick a well-known mid-size open-source repo
  that is not exotic (dynamic-metaprogramming-heavy repos distort the measurement). Record which, at
  which commit. It need not be a CORE-Bench repo; if it is, it is used for parsing only (never training).
- `CodeUnit` per `specs/code_unit.md` (draft is fine).

## Outputs

- `ril/parsing/repository_parser.py`, `code_unit.py` (per `specs/code_unit.md`), `call_graph.py`.
- Skips `__pycache__`, `.git`, vendored and generated files (rules documented and tested).
- Builds **call, import and inherit** graphs; node types per the LocAgent schema (directory, file, class, function), edge types contain / import / invoke / inherit; entity id = fully qualified name.
- A script `scripts/parse_repo.py <path> --seed N` that prints **ten CodeUnits** (deterministic selection) and the graph statistics.
- `results/` entry with: unit counts by type, edges by type, parse time (and throughput units/s → `throughput_log.csv`), and the **edge-recovery percentage**.

## Open design question (propose a provisional definition; the team finalises)

**What "edge-recovery" means.** The master doc says "70–85% edge recovery" without a definition. A
metric definition is a design decision. Implement one **provisional** definition in a
clearly named function, state its numerator/denominator in the docstring and `RESULTS.md`, list at
least one alternative with its trade-off, and open an ADR stub (next free number) titled "Edge-recovery
metric definition". Example of the kind of option to compare: resolved call sites ÷ call sites whose
target is repository-internal, versus a comparison against a dynamic trace on the repo's own tests.

## Acceptance criteria (met by the first build of 2026-10-17)

- [x] Parses the chosen repositories with no unhandled exceptions; files that fail to parse are counted and listed, not silently dropped (flask 0 of 80, requests 0 of 35, django 1 of 2,752: a test file that is a deliberate syntax error, listed in `results/logs/p_stats_django_ada_2026-10-17.json`).
- [x] Ten CodeUnits printed (`scripts/parse_repo.py PATH --repo-id owner/name --seed N`); each satisfies the schema validation in `specs/code_unit.md` (`CodeUnit.validate` runs on construction).
- [x] Edge counts by type and status reported (`results/tables/p_graph_status_counts.csv`); **edge recovery reported under four definitions, none chosen** (ADR-012, which replaces the provisional ADR stub asked for above).
- [x] Deterministic: rebuilds write byte-identical unit tables and graph files (`tests/reproducibility/test_graph_repro.py`; also on the real flask checkout; also across `PYTHONHASHSEED` values; the three repositories were rebuilt on Ada with identical files).
- [x] Memory estimated from measured per-unit numbers before the django-scale run (`results/logs/p_django_prediction_2026-10-17.json`); the django build ran on Ada as instructed and was repeated on the laptop afterwards as a check of the estimate.
- [x] Parse time and units/s recorded in `throughput_log.csv` (stages `parse` and `graph_build`, workload ids `graph-<repo>-v1`) and in `RESULTS.md`.
- [x] Unit tests: nested functions, methods, decorated functions, a class with inheritance, an unresolvable dynamic call that counts as unrecovered (`tests/unit/test_repository_parser.py`, `test_call_graph.py`).
- [x] `docs/ARCHITECTURE.md` (parsing: Interface, Limitations) updated with the measured coverage.

## What the first build measured

Outputs of the build and their meaning are in `results/tables/p_*.csv` and `results/logs/p_*`; the edge-recovery definitions with
their trade-offs are in `decisions/ADR-012-edge-recovery-definitions.md`, and the storage measurements in
`decisions/ADR-011-repo-graph-schema.md` (addendum). The exploratory families are `tests` and `configures` (written to their own
files, never projected into the CodeUnit lists) and `co_change` (counts of file pairs changed together in at least N = 2, 3, 5
commits that are ancestors of the snapshot, commits touching more than 50 files skipped; no edge is stored).
