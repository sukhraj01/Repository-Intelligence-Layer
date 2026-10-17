# System Architecture

**Last updated:** 2026-10-17
**Status:** Package skeleton, config, paths and utilities exist; no research component is implemented. This file is **live**: update it whenever a
boundary changes. The static design rationale is in `09_architecture.md` (derived from the master doc).

---

# System overview

RIL is a retrieval layer over a Python repository, plus the training and evaluation machinery for a
controlled study of retriever supervision (RQ2) and its effect on a fixed coding agent (RQ3).

```python
context = engine.retrieve(location, task, max_results=20, max_tokens=4096)
```

(Interface shape per the master doc; exact types are fixed when the CodeUnit and parser land.)

# Design goals

Optimised for: reproducibility; **a frozen, controllable retrieval stack** (only supervision varies);
comparability across arms; measurable per-stage latency; engineering clarity.
Deliberately **not** optimised for: production serving, distributed execution, multi-language support,
approximate-NN scale. These trade-offs follow from the study's goals.

# Architectural principles

1. One variable moves per experiment; everything else is frozen and hashed.
2. Reproducibility before performance; optimise only after bottlenecks are measured.
3. Explicit interfaces (`CodeUnit` is the only shared data type between components).
4. Rank-based fusion (RRF) so the stack needs no per-corpus retuning.
5. Exact search (flat index) so ANN recall is never a confound.
6. Benchmark before replacing a component; record latency before every commit.
7. Prefer reversible decisions early; document decisions before they become tribal knowledge.

# System data flow

```text
Held-out repo list (CORE-Bench L2/L3 + SWE-bench Verified)
        │  (built first; repo-level disjointness)
        ▼
Training pool: SweLoc  +  own PR-mined set   ──filter by held-out list──►  pool + counts
        │
        ▼
Supervision arm  (RAW | FILTER | WEIGHT | CURRICULUM)   ← quality signal: SweRank K-rank
        │  matched optimizer updates (target 20,000), ≥3 seeds
        ▼
Encoder checkpoint (only box that changes between arms)
        ▼
OFFLINE per repo:  parse → CodeUnits → call/import/inherit graph → BM25 fields → dense vectors (flat index)
        ▼
ONLINE:  interpret(query) → BM25 | dense | graph neighbours → RRF(k=60) → cross-encoder rerank → assemble(token budget)
        ▼
Evaluation:  CORE-Bench L2/L3 (chunk-level metrics)   →   Agent (fixed scaffold, model, seed)  →  resolved rate
        ▼
Analysis:  retrieval-vs-reasoning failure split · paired McNemar · latency Pareto
```

# Components

Each component below lists purpose, responsibilities, dependencies, artifacts, interface, consumers,
assumptions, limitations and governing decisions. **Interfaces marked TBD are fixed by the first
implementation and then written here.**

## parsing (`ril/parsing/`)

- **Purpose:** turn a repository into `CodeUnit`s and a typed relationship graph.
- **Files:** `code_unit.py`, `unit_id.py`, `repo_id.py`, `path_rules.py` (the frozen CodeUnit and helpers); `repository_parser.py` (phase one: units and per-file symbol summaries), `call_graph.py` (phase two: `ast` resolver and graph builder), `repo_graph.py` (typed edge store, DRAFT v0), `exploratory_edges.py`, `git_history.py`, `build.py`, `report.py`.
- **Responsibilities:** walk the repo skipping `__pycache__`, `.git`, vendored and generated files; parse with `ast`; emit `CodeUnit`s; build call, import, inherit graphs; **record edge-recovery coverage** (expected 70–85%; must be measured and reported).
- **Dependencies:** `config/`.
- **Artifacts:** per-repo unit table and graph under `data/index/<repo_id>/` (gitignored).
- **Interface:** `ril.parsing.code_unit.CodeUnit` (dataclass, fields exactly as `specs/code_unit.md`, FROZEN v1, ADR-013) with `CODEUNIT_SCHEMA_VERSION = "v1"`, `validate()`, `to_dict()` / `from_dict()` (strict: missing or unknown keys are errors), `to_json()` / `from_json()`, and `units_to_jsonl()` / `units_from_jsonl()`. Serialization is canonical (sorted keys, compact separators, UTF-8, list order kept as given). Validation: an `id` that parses and agrees with `file` and `qualified_name`, `repo_id` as case-folded `owner/name`, `language == "python"`, `unit_type` in {function, method, class, module}, `end_line >= start_line`, `loc >= 0`, `last_modified` empty or `YYYY-MM-DDTHH:MM:SSZ`. Helpers: `ril.parsing.unit_id` (id builder, converter to and from the pool form `path/Class/function`), `ril.parsing.repo_id` (repository identity), `ril.parsing.path_rules` (`is_test` path rule). Relation lists hold resolved unit ids only (projections of the separate edge store). Parse and graph: `ril.parsing.repository_parser.parse_repository(root, repo_id, last_modified=, options=)` returns a `ParsedRepository` (units in a deterministic order, per-file summaries, the list of files that did not parse, skip counts); `ril.parsing.call_graph.build_graph(parsed, snapshot_commit)` returns a `RepoGraph` whose `Edge` records carry `type`, `src`, `dst`, `status` in {resolved, ambiguous, unresolved, external}, the resolver rule, the candidate set for ambiguous edges, the site and the target as written; `apply_projections` fills `calls` / `called_by` from resolved `invoke` edges; `ril.parsing.build.build_repository` runs history, parse, graph build and the exploratory families with timings and `write_artifacts` writes canonical `units.jsonl`, `nodes.jsonl`, `edges.jsonl` and `meta.json` (byte-identical on rerun). `scripts/parse_repo.py PATH --repo-id owner/name --seed N` prints ten CodeUnits and the statistics.
- **Consumers:** retrieval (all three signals), training data builder, evaluation harness.
- **Assumptions:** Python-only; static analysis is incomplete (dynamic dispatch, `getattr`, decorators, monkey-patching, duck typing produce unresolvable edges).
- **Limitations:** edge recovery <100% — a candidate explanation if RQ1 finds structural signal weak. **Measured in the first build** (flask, requests and django at their Verified base commits; `results/tables/p_graph_status_counts.csv`; definitions and trade-offs in `decisions/ADR-012-edge-recovery-definitions.md`): the share of call sites resolved to exactly one in-repository unit is 28% (flask), 36% (requests) and 39% (django) of all sites, 51%, 72% and 62% of the sites that are not external; against the flask test suite as a dynamic oracle 48% of the executed in-repository caller-callee pairs are recovered as `resolved` edges and 66% as `resolved` or `ambiguous` (n = 1,057 pairs); implicit calls (operators, `with`, property access, instantiation through classes defined in a function) have no call site and are counted as unrecovered. No definition is chosen (ADR-012). The resolver is flow-insensitive, tracks the type of `self`, annotated parameters, constructor assignments, module variables and `self.x` attributes, and follows re-exports and star imports; it does not infer return types except from annotations and does not model decorators that change a callable.
- **Governing decisions:** ADR-003 (graph role), ADR-004 (granularity), ADR-011 (graph schema; `specs/repo_graph.md` DRAFT v0, `docs/GRAPH_DESIGN.md`).

## retrieval (`ril/retrieval/`)

- **Purpose:** the online path — three candidate generators, fusion, rerank, assembly.
- **Files:** `bm25_index.py`, `dense_encoder.py`, `hybrid_retriever.py`, `ranking.py`.
- **Responsibilities:** BM25 over identifier-split, field-weighted text (k₁=1.2, b=0.75, tune b); dense encode + flat exact search; structural score `γ^dist` (γ≈0.5) from the graph; **RRF (k=60)**; cross-encoder rerank of the top 100; `assemble()` — dedupe overlapping units, order for truncation survival, attach callee signatures, fit a hard token budget.
- **Dependencies:** `parsing/`, `config/`.
- **Consumers:** evaluation, bench, analysis, the agent.
- **Assumptions:** flat exact index is cheap at 10³–10⁵ units per repo; RRF needs no retuning.
- **Limitations:** rerank likely dominates latency (hypothesis: ~500–1000 ms for 100 candidates vs a few ms for the rest).
- **Invariant:** `assemble()` is **byte-identical across RQ2 arms** (reproducibility test).
- **Governing decisions:** ADR-003, ADR-006 (encoder), ADR-009 (rerank).

## training (`ril/training/`)

- **Purpose:** produce the four supervision-arm encoders under matched optimizer updates.
- **Files:** `contrastive_loss.py`, `training.py`, `data_loader.py`, `supervision.py`.
- **Responsibilities:** multi-positive InfoNCE (τ=0.05) with repository-local hard negatives; arm logic (RAW/FILTER/WEIGHT/CURRICULUM) isolated in `supervision.py`; K-rank quality signal from a **separately pretrained** encoder; record compute cost, unique examples seen, effective epochs for every run.
- **Dependencies:** `parsing/`, `config/`; imports the encoder *class* from `retrieval/`, never trained weights, for K-rank.
- **Defaults:** mean pooling (masked), lr 2e-5 linear decay, 10% warmup, 20,000 updates, max length 512, ≥3 seeds.
- **Assumptions:** the training pool is repository-disjoint from all evaluation repos.
- **Limitations:** FILTER reuses data more at equal updates (data-budget confound) — reported, plus a subsampled-RAW control.
- **Governing decisions:** ADR-001 (pool), ADR-002 (quality signal), ADR-006 (base encoder).

## evaluation (`ril/evaluation/`)

- **Purpose:** retrieval metrics on CORE-Bench and agent integration for RQ3.
- **Files:** `metrics.py`, `core_bench.py`, `agent_integration.py` (planned); `dynamic_trace.py`, `edge_recovery.py`, `jedi_agreement.py`, `edge_samples.py` (edge-recovery measurements of the first graph build, `specs/parse_one_repo.md`).
- **Responsibilities:** nDCG@10, MRR, Recall@10 at CORE-Bench chunk granularity (any additional metric, e.g. Recall@100, is a metric-definition decision for the team); loaders for `LEVEL-2/<dataset>/<repository>/{corpus,queries,qrels}.jsonl`; run the fixed agent with each retriever; log, per failure, whether the gold-patch file was in the retrieved context.
- **Dependencies:** `retrieval/`, `parsing/`, `config/`.
- **Assumptions:** same instances carry retrieval qrels and executable tests (L2 ∩ Verified), enabling paired per-instance analysis.
- **Limitations:** gold locations derived from patches are approximate targets.
- **Governing decisions:** ADR-005 (benchmark), ADR-007 (scaffold), ADR-008 (base LLM).

## bench (`ril/bench/`)

- **Purpose:** latency and throughput measurement; the per-commit harness.
- **Files:** `latency_harness.py`, `profile_stages.py`, `stub_stages.py`.
- **Responsibilities:** see `specs/latency_harness.md`. Per-stage p50/p95/p99 (nearest-rank, from raw samples), hardware spec, append-only CSV, regression failure.
- **Implemented:** a stage registry with a closed name taxonomy (`LATENCY_STAGES`: `query_encode`, `bm25`, `dense_search`, `graph_expansion`, `graph_expand_1hop`, `graph_expand_2hop`, `rrf_fusion`, `cross_encoder_rerank`, `assemble`, `end_to_end`; `THROUGHPUT_STAGES`: `parse`, `graph_build`). A real component is timed by one `REGISTRY.register(name, fn, reset=...)` line. Warm rows run the fixed query set `repeats` times and discard the first `warmup_n` calls (recorded in the log); cold rows call the stage's `reset` before every call (stage-level caches only, not the OS page cache). Batch size 1; `torch.cuda.synchronize()` brackets every timed call when a GPU exists and is skipped on a CPU-only box. Latency goes to `results/latency/latency_log.csv`, offline stages (units per second) to `throughput_log.csv`, both append-only and refused if the header differs. `make bench` measures and appends; `make bench-check` also compares with the most recent comparable row (same hardware spec, query set, cache state, stage) and exits non-zero when p50 or p95 grows past the thresholds in `configs/bench/latency.yaml` (provisional, Q33); a failing run is not appended unless `--append-on-fail`. `profile_stages.py` gives `cProfile` attribution inside a stage and `torch.profiler` when a GPU exists. The shipped stages are synthetic stubs (`stub_stages.py`, query set `synthetic-v1`); their numbers are not measurements of any component. `graph_measure.py` registers the real `parse` and `graph_build` throughput stages and the `graph_expand_1hop` / `graph_expand_2hop` latency stages per storage backend (`graph_storage.py`), under query-set ids `graph-<repo>-<backend>-v1` (200 queries of three seed units, `configs/bench/query_sets/graph-<repo>-v1.txt`), so that the regression check never compares them with the stubs.
- **Hook:** `make hooks` installs `scripts/hooks/latency_check.sh` as pre-commit step `10-latency`; `RIL_LATENCY_HOOK=strict|relaxed|off` selects the reading of "before every commit" (Q3), strict by default.
- **Dependencies:** may call everything; nothing calls back.

## analysis (`ril/analysis/`)

- **Purpose:** error analysis, statistics, figures.
- **Files:** `error_analysis.py`, `visualization.py`.
- **Dependencies:** reads `results/` only.

## config (`ril/config/`)

- **Purpose:** parameters and paths; depends on nothing.
- **Files:** `parameters.py`, `paths.py`.
- **Implemented (bootstrap):** `paths.py` resolves every location from the repository root (no absolute paths); the data root can be redirected with `RIL_DATA_ROOT`. `parameters.py` holds `RunConfig` (seed, name): a frozen dataclass loaded from YAML with a stable SHA-256 `config_hash()`. Experiment parameters are added by the components that own them, in `configs/`, not as code defaults.
- **Shared utilities:** `ril/util/` (`set_seed`, project logger, environment sanity checks) is a leaf package that any component may import; it depends on nothing internal.
- **Invariant:** the frozen configuration is hashed and recorded with every run; `configs/frozen/` is immutable after the freeze.

---

# Decision traceability

| Component | Governing ADRs |
|---|---|
| parsing | ADR-003, ADR-004, ADR-011, ADR-012, ADR-013 |
| retrieval | ADR-003, ADR-004, ADR-006, ADR-009 |
| training | ADR-001, ADR-002, ADR-006 |
| evaluation | ADR-004, ADR-005, ADR-007, ADR-008 |
| packaging / CLI | ADR-010 |

# Cross-cutting concerns

- **Configuration:** centralised in `ril/config/` + `configs/`; environment-independent execution.
- **Logging:** structured, execution-traceable; no `print`.
- **Reproducibility:** seeds, dataset versioning (`provenance.json`), config hashing.
- **Experiment tracking:** saved configs, metrics with CIs, artifacts, benchmark history (`RESULTS.md`).
- **Testing:** unit, integration, leakage, reproducibility.
- **Error handling:** explicit failures, helpful diagnostics.

# Architectural assumptions

| Assumption | Rationale | Validation | Risk |
|---|---|---|---|
| Flat exact search is fast enough per repo | 10³–10⁵ units × 768 dims | measure with the latency harness / RQ1 | low |
| Static call-graph recovers 70–85% of edges | typical for Python `ast` analysis | measure per `specs/parse_one_repo.md` | medium — drives RQ1 interpretation |
| Cross-encoder dominates latency | ~100 candidates through a transformer | profile per stage | medium — shapes where to optimise |
| RRF needs no per-corpus retuning | rank-only | verify on L2 vs L3 | low |
| Chunk metrics + function-level internals can coexist | CORE-Bench averages ~15,000 chunks/repo | ADR-004 | medium |

# Known limits and expected bottlenecks

*To be filled with measured numbers after week 3 (Performance / Memory / Storage / Accuracy).*
Expected at 10×: reranking; indexing throughput for L2-scale corpora; disk on Ada.

# Architecture changelog

## 2026-10-12 — Scaffold

- **What changed:** repository scaffold created; component boundaries recorded from the master doc.
- **Why:** start implementation from a documented design.
- **Impact:** none on behaviour (no code yet).
- **Related ADR:** ADR-001 … ADR-010 (stubs, all `Proposed`).
- **Benchmark:** not applicable.

## 2026-10-17 — Package skeleton

- **What changed:** `ril/` is an installable package (Python 3.11 pinned); `config/` (paths, run config) and `util/` (seed, logger, sanity checks) implemented; tests, lint and type checks wired through `make`.
- **Why:** give every later component a tested place to land.
- **Impact:** none on behaviour (no research code).
- **Related ADR:** none.
- **Benchmark:** not applicable (latency harness not built).

# Architecture health checklist

When modifying this architecture, verify:

- [ ] Interfaces remain explicit; `CodeUnit` remains the only shared data type.
- [ ] Components remain loosely coupled; the dependency rule in `ril/README.md` still holds.
- [ ] The retrieval stack that RQ2 holds frozen has not been changed after the freeze.
- [ ] New decisions are captured in ADRs; benchmarks exist for performance-sensitive changes.
- [ ] Latency row recorded; changelog updated; documentation reflects the implementation.
