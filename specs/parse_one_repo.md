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

## Acceptance criteria

- [ ] Parses the chosen repo with no unhandled exceptions; files that fail to parse are counted and listed, not silently dropped.
- [ ] Ten CodeUnits printed; each satisfies the schema validation in `specs/code_unit.md`.
- [ ] Edge counts by type reported; **edge-recovery %** reported with its definition and the provisional-ADR link.
- [ ] Deterministic: two runs with the same seed produce byte-identical unit tables and graph dumps (reproducibility test).
- [ ] Memory estimated from a small sample before the first full run; if the repo is too large for 8 GB, run on Ada.
- [ ] Parse time and units/s recorded in `throughput_log.csv` and `RESULTS.md`.
- [ ] Unit tests: nested functions, methods, decorated functions, a class with inheritance, an unresolvable dynamic call (counts as unrecovered, not dropped).
- [ ] `docs/ARCHITECTURE.md` (parsing → Interface, Limitations) updated with the measured coverage.
