# System Architecture

**Last updated:** 2026-11-06
**Status:** Parsing, retrieval signals, evaluation, the training stack, the benchmark harness and the analysis tables exist and run; the fusion
stage, rerank and agent integration are not built (context assembly is built, ADR-014), and no configuration is frozen. This file is **live**: update it whenever a
boundary changes. The static design rationale is in `09_architecture.md` (derived from the master doc). Each module named below was checked to
exist on the date above; "planned" marks those that do not.

---

# System overview

RIL is a retrieval layer over a Python repository, plus the training and evaluation machinery for a
controlled study of retriever supervision (RQ2) and its effect on a fixed coding agent (RQ3).

```python
context = engine.retrieve(location, task, max_results=20, max_tokens=4096)
```

(Interface shape per the master doc. The CodeUnit and the parser exist; `retrieve` as a single entry point does not, because fusion and assembly are not built.)

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
- **Files:** `code_unit.py`, `unit_id.py`, `repo_id.py`, `path_rules.py` (the frozen CodeUnit and helpers); `repository_parser.py` (phase one: units and per-file symbol summaries), `call_graph.py` (phase two: `ast` resolver `own-ast-resolver/v0` and graph builder), `repo_graph.py` (typed edge store, DRAFT v0), `ambiguity_policy.py` (readers of ambiguous call sites), `exploratory_edges.py` (`tests`, `configures`, co-change; off by default), `git_history.py`, `build.py`, `report.py`, `incremental.py` (per-commit updater).
- **Responsibilities:** walk the repo skipping `__pycache__`, `.git`, vendored and generated files; parse with `ast`; emit `CodeUnit`s; build call, import, inherit graphs; **record edge-recovery coverage** (no expected range; measured and reported as in ADR-012; corrected, see DEV-007).
- **Dependencies:** `config/`.
- **Artifacts:** per-repo unit table and graph under `data/index/<repo>@<label>/` (gitignored; `units.jsonl`, `nodes.jsonl`, `edges.jsonl`, a metadata file).
- **Interface:** `ril.parsing.code_unit.CodeUnit` (dataclass, fields exactly as `specs/code_unit.md`, FROZEN v1, ADR-013) with `CODEUNIT_SCHEMA_VERSION = "v1"`, `validate()`, `to_dict()` / `from_dict()` (strict: missing or unknown keys are errors), `to_json()` / `from_json()`, and `units_to_jsonl()` / `units_from_jsonl()`. Serialization is canonical (sorted keys, compact separators, UTF-8, list order kept as given). Validation: an `id` that parses and agrees with `file` and `qualified_name`, `repo_id` as case-folded `owner/name`, `language == "python"`, `unit_type` in {function, method, class, module}, `end_line >= start_line`, `loc >= 0`, `last_modified` empty or `YYYY-MM-DDTHH:MM:SSZ`. Helpers: `ril.parsing.unit_id` (id builder, converter to and from the pool form `path/Class/function`), `ril.parsing.repo_id` (repository identity), `ril.parsing.path_rules` (`is_test` path rule). Relation lists hold resolved unit ids only (projections of the separate edge store). Parse and graph: `ril.parsing.repository_parser.parse_repository(root, repo_id, last_modified=, options=)` returns a `ParsedRepository` (units in a deterministic order, per-file summaries, the list of files that did not parse, skip counts); `ril.parsing.call_graph.build_graph(parsed, snapshot_commit)` returns a `RepoGraph` whose `Edge` records carry `type`, `src`, `dst`, `status` in {resolved, ambiguous, unresolved, external}, the resolver rule, the candidate set for ambiguous edges, the site and the target as written; `apply_projections` fills `calls` / `called_by` from resolved `invoke` edges; `ril.parsing.build.build_repository` runs history, parse, graph build and the exploratory families with timings and `write_artifacts` writes canonical `units.jsonl`, `nodes.jsonl`, `edges.jsonl` and a metadata file (byte-identical on rerun). Edge statuses are `resolved` (one in-repository target), `ambiguous` (candidate set kept; dropped from the stored graph by default, ADR-011 addendum), `unresolved` and `external`. `ril.parsing.incremental.full_state(root, config)` and `update_state(state)` re-read only the files a commit changed and the files that depend on them (changed bytes or module name, an imported module whose summary changed, or an attribute name whose method set changed); the result equals the full rebuild in graph digest and unit bytes (100 of 100 commits on five repositories, `results/ledger_a.md` A2a; the full build stays the default of `build_repository`, Q58). The resolver cache is order-independent since the fix recorded as Q57. `scripts/parse_repo.py PATH --repo-id owner/name --seed N` prints ten CodeUnits and the statistics.
- **Consumers:** retrieval (all three signals), training data builder, evaluation harness.
- **Assumptions:** Python-only; static analysis is incomplete (dynamic dispatch, `getattr`, decorators, monkey-patching, duck typing produce unresolvable edges).
- **Limitations:** edge recovery <100% — a candidate explanation if RQ1 finds structural signal weak. **Measured in the first build** (flask, requests and django at their Verified base commits; `results/tables/p_graph_status_counts.csv`; definitions and trade-offs in `decisions/ADR-012-edge-recovery-definitions.md`): the share of call sites resolved to exactly one in-repository unit is 28% (flask), 36% (requests) and 39% (django) of all sites, 51%, 72% and 62% of the sites that are not external; against the flask test suite as a dynamic oracle 48% of the executed in-repository caller-callee pairs are recovered as `resolved` edges and 66% as `resolved` or `ambiguous` (n = 1,057 pairs); implicit calls (operators, `with`, property access, instantiation through classes defined in a function) have no call site and are counted as unrecovered. No definition is chosen (ADR-012). The resolver is flow-insensitive, tracks the type of `self`, annotated parameters, constructor assignments, module variables and `self.x` attributes, and follows re-exports and star imports; it does not infer return types except from annotations and does not model decorators that change a callable.
- **Governing decisions:** ADR-003 (graph role), ADR-004 (granularity), ADR-011 (graph schema; `specs/repo_graph.md` DRAFT v0, `docs/GRAPH_DESIGN.md`).

## retrieval (`ril/retrieval/`)

- **Purpose:** the online path — three candidate generators, fusion, rerank, assembly. Built so far: the three signals as separate, measured components; fusion exists as measurement code only.
- **Files (built):** `bm25_index.py`, `dense_encoder.py`, `graph_expansion.py`, `recency.py`. **Planned, not written:** a fusion module and rerank. Context assembly lives in `ril/assembly/` (next section).
- **Interfaces:**
  - `bm25_index.BM25Index` (reference tokenisation, Lucene-variant scoring, `BM25Params` k₁=1.5 / b=0.75, `provisional: ADR-004`; `top_k_of`, `order_by_score`). Options added by workstream A and merged 2026-10-31: `split_identifier`, `tokenize_code(keep_original=...)` and `field_tokens` with integer field weights. The reference form is the default and the reproduction of the published BM25 rows depends on it.
  - `dense_encoder.DenseEncoder` over a registered `EncoderSpec` (CodeRankEmbed, Qwen3-Embedding-0.6B, SweRankEmbed-Small as a teacher; revisions pinned, `provisional: ADR-006`) and `FlatIndex`, an exact search over normalised vectors (never ANN). Needs torch, so it runs on the cluster.
  - `graph_expansion` (hop-decayed expansion over a `FamilyGraph`, the edited list and the RRF-fused list, chance controls) and `recency.recency_prior` / `blend`: pilot code for E-GRAPH-SIGNAL, E-GRAPH-ROLE and E-RECENCY.
  - Fusion forms in code: rank-level RRF in `graph_expansion.rrf_ranks` / `rrf_graph_list` (constant `RRF_K = 60`) and RRF over whole rankings in `ril.evaluation.x2_eval.rrf_scores` (a sweep over k, `x2_dense.RRF_KS`). The stack to be frozen uses RRF; the constant is the freeze's to fix.
- **Dependencies:** `parsing/`, `config/`.
- **Consumers:** evaluation, bench, analysis, the agent.
- **Assumptions:** flat exact index is cheap at 10³–10⁵ units per repo (dense search latency rows in `results/latency/`); RRF needs no retuning (to be checked on L2 versus L3).
- **Limitations:** no rerank yet; the graph's role is undecided (ADR-003: on the fused first stage, same-file expansion ordered by score is level with the stored graph, E-GRAPH-ROLE); the measured encoder numbers are zero-shot on development repositories. Rerank is hypothesised to dominate latency (about 500–1000 ms for 100 candidates versus a few ms for the rest); unmeasured.
- **Governing decisions:** ADR-003, ADR-006 (encoder), ADR-009 (rerank).

## assembly (`ril/assembly/`)

- **Purpose:** the last stage of the online path: a ranked list of units becomes the text an agent reads, under a token budget. Implements `specs/assembly.md` (ADR-014, D102, `provisional`).
- **Files:** `assemble.py` (policy, manifest), `tokens.py` (pluggable tokenizer, deterministic approximation, ratio helper), `config.py`, `gold.py` (`gold_in_context`), `snapshot.py` (parsed units to the assembler's view), `measure.py` (E-ASSEMBLY runner on the E3 cache).
- **Interface:** `assemble(candidates, snapshot, config, tokenizer) -> Assembled(context, manifest)`; `gold_in_context(manifest, gold_units, gold_files)`.
- **Dependencies:** `parsing/`, `config/`; `measure.py` also reads the evaluation cache (`evaluation/`). Nothing in `retrieval/` is imported by the policy, so the stage cannot depend on how a list was made.
- **Consumers:** the agent integration (RQ3), `bench/assembly_measure.py` (stages `assemble`, `end_to_end`), `analysis/assembly_tables.py`.
- **Invariant:** **byte-identical for the same ranked list** (same candidates, snapshot, configuration and tokenizer give the same bytes; `tests/unit/test_assembly.py`), which is what makes assembly identical across RQ2 arms. The budget is never exceeded (tested on random inputs).
- **Assumptions:** class units arrive in header form (`BuildConfig(class_source="header")`); the final agent run supplies the agent model's tokenizer.
- **Limitations:** no callee signatures (DEV-033); no overlap deduplication beyond repeated ids; token counting dominates the time (about 90% in a profile).

## data mining (`ril/data_mining/`)

- **Purpose:** builds the unfiltered PR-mined training set (E-MINE-PILOT, `docs/experiments/B.md`): merged pull requests with their closing issues, the changed units of the base commit as positives, one directory per pull request in the layout `training/pool_reader.py` reads.
- **Files:** `github_api.py` (client), `links.py`, `diff.py`, `mapping.py`, `snapshot.py`, `miner.py`, `store.py`, `runner.py`, `population.py`, `summary.py`, `pack.py`, `rank_compare.py`, `jobs.py`, `config.py`.
- **Dependencies:** `parsing/` (parser, CodeUnit, ids), `training/` for the pool's ordering, directory-name and rank helpers (`pool_check.py`, `pool_ranks.py`), `util/`. Nothing imports it except `scripts/`. It computes nothing retriever-dependent; the rank tools of `training/` measure its output.
- **Assumptions:** the live stages need a read-only token (D2); without it the job stops before any call.

## training (`ril/training/`)

- **Purpose:** produce the four supervision-arm encoders under matched optimizer updates.
- **Files:** `pool_reader.py` (select pool directories against the held-out list, stream them, yield `PoolExample`), `negatives.py` (policies `random_repo`, `teacher_top_m`, `teacher_top_m_poscut`; `structural` refused in arm runs), `supervision.py`, `data_loader.py` (shared batch planner with exposure counts), `contrastive_loss.py`, `encoders.py`, `training.py`, `train_jobs.py`; ranks and pool checks in `pool_ranks.py`, `pool_rank_jobs.py`, `pool_check.py`; held-out machinery and leakage checks in `held_out*.py`, `rename_resolution.py`, `content_overlap.py`, `leakage.py`, `contamination*.py` (`ril/training/README.md`).
- **Responsibilities:** multi-positive InfoNCE with repository-local hard negatives; arm logic isolated in `supervision.py` as exactly three hooks (filter, weigher, ordering; the negative policy is held identical across arms, DEV-012). `ARM_NAMES` are RAW, FILTER, WEIGHT, CURRICULUM plus two controls: NOISE (positives replaced by random functions of the same repository; `NoisePositives`) and RAW_SUBSAMPLE (a size-matched random subset of RAW; `RandomSubset`); `ordering.reverse` gives the reversed-order CURRICULUM. The K-rank quality signal is read from a precomputed table of a **separately pretrained** teacher (`TableKRank`, `AgreementKRank`). Budget accounting: `training.budget_record` writes optimizer updates, schedule updates, batch size, loop hours and the loader's exposure counts (unique examples seen, effective epochs) with every run; `budget.stop_after` ends a run early on the schedule of `budget.updates`, so a short run is the prefix of a longer one (`planned_end`).
- **Dependencies:** `parsing/`, `config/`, `util/` (GPU gate, machine description); imports the encoder *class* from `retrieval/`, never trained weights, for K-rank. Never `evaluation/`, `analysis/` or `bench/` (leakage check (d)); the checkpoint evaluation (`evaluation/checkpoint_eval.py`) takes a trained encoder object and is wired in `scripts/train.py`.
- **Defaults:** every training value is `provisional: ADR-001, ADR-002, ADR-006` and measured values replace the master's plan where they differ: 100 to 1,000 updates (not 20,000) after the learning-curve and arms pilots, batch 32 × (1+1), fp16 with checkpointing, max length 512 (DEV-013), at least 3 seeds for a reported arm. Nothing here is frozen.
- **Assumptions:** the training pool is repository-disjoint from all evaluation repos.
- **Limitations:** FILTER reuses data more at equal updates (data-budget confound) — answered by the RAW_SUBSAMPLE control; the pilots (E-PILOT-ARMS, E-PILOT-ARMS2) use two seeds and dev repositories only (DEV-014); the pool directories were selected with respect to one teacher (ADR-001 addendum). Torch is imported only on the cluster.
- **Governing decisions:** ADR-001 (pool), ADR-002 (quality signal), ADR-006 (base encoder).

## evaluation (`ril/evaluation/`)

- **Purpose:** retrieval metrics on CORE-Bench and agent integration for RQ3.
- **Files (built):**
  - loaders and metrics: `core_bench.py` (`read_folder`, `rank_positives`, `evaluate_folder`), `metrics.py` (`ndcg_at_k`, `recall_at_k`, `first_rank`, bootstrap and paired intervals), `unit_retrieval.py`, `label_noise.py`, `e1_run.py`;
  - chunk-to-unit mapping: `chunk_mapping.py` (`locate_chunk`, `map_span`), `graph_reach.py`, `chunk_unit_pilot.py`;
  - first-stage and graph pilots: `e3_prepare.py`, `e3_eval.py`, `x1_prepare.py`, `x1_eval.py`, `policy_readers.py`, `x2_dense.py`, `x2_eval.py`, `x2_jobs.py`, `e6_dense.py`, `s1_graph_role.py`, `e7_encoders.py`;
  - training hooks: `checkpoint_eval.py` (score a trained encoder on the dev repositories with the X2 machinery) and `curve_eval.py` (the same at chosen update counts);
  - statistics: `power.py` (exact McNemar power, minimum detectable effect, seed-count tables);
  - edge-recovery and review: `dynamic_trace.py`, `edge_recovery.py`, `jedi_agreement.py`, `edge_samples.py`, `spot_check.py` (`specs/parse_one_repo.md`); `contamination_edited.py` (edited-function contamination check, kept here so `training/` imports no evaluation code).
  - **Planned, not written:** the agent integration module.
- **Responsibilities:** nDCG@10, MRR, Recall@10 and Recall@100 from the ranks of the positives (binary gain), reproducing the published BM25 rows of CORE-Bench on Verified (L2 11.94 / 46.74, L3 22.19 / 33.89; `RESULTS.md` rows `e1-*`); loaders for `LEVEL-2/<dataset>/<repository>/{corpus,queries,qrels}.jsonl`; mapping of chunks to code units by exact text (160 of 160 positives found on three repositories, D7); averaging over queries with repository-clustered bootstrap intervals (D17). Still to build: run the fixed agent with each retriever and log, per failure, whether the gold-patch file was in the retrieved context.
- **Dependencies:** `retrieval/`, `parsing/`, `config/`.
- **Assumptions:** same instances carry retrieval qrels and executable tests (L2 ∩ Verified), enabling paired per-instance analysis. Evaluation is whole-snapshot retrieval at the base commit (DEV-003). Tuning uses the development repositories only; Verified is the final test (D32).
- **Limitations:** gold locations derived from patches are approximate targets; L3 labels are LLM-judged (Q12); a chunk's positive counts for every unit it overlaps and two gold readings are reported (D18, `provisional: ADR-004`); no agent runs exist.
- **Governing decisions:** ADR-005 (benchmark), ADR-007 (scaffold), ADR-008 (base LLM).

## bench (`ril/bench/`)

- **Purpose:** latency and throughput measurement; the per-commit harness.
- **Files:** `latency_harness.py`, `profile_stages.py`, `stub_stages.py`; measurement drivers `graph_measure.py`, `graph_storage.py`, `retrieval_measure.py`, `dense_measure.py`, `incremental_measure.py`, `train_measure.py`.
- **Responsibilities:** see `specs/latency_harness.md`. Per-stage p50/p95/p99 (nearest-rank, from raw samples), hardware spec, append-only CSV, regression failure.
- **Implemented:** a stage registry with a closed name taxonomy (`LATENCY_STAGES`: `query_encode`, `bm25`, `dense_search`, `graph_expansion`, `graph_expand_1hop`, `graph_expand_2hop`, `rrf_fusion`, `cross_encoder_rerank`, `assemble`, `end_to_end`; `THROUGHPUT_STAGES`: `parse`, `graph_build`, `dense_encode`, `train_step`). A real component is timed by one `REGISTRY.register(name, fn, reset=...)` line. Warm rows run the fixed query set `repeats` times and discard the first `warmup_n` calls (recorded in the log); cold rows call the stage's `reset` before every call (stage-level caches only, not the OS page cache). Batch size 1; `torch.cuda.synchronize()` brackets every timed call when a GPU exists and is skipped on a CPU-only box. Latency goes to `results/latency/latency_log.csv`, offline stages (units per second) to `throughput_log.csv`, both append-only and refused if the header differs. `make bench` measures and appends; `make bench-check` also compares with the most recent comparable row (same hardware spec, query set, cache state, stage) and exits non-zero when p50 or p95 grows past the thresholds in `configs/bench/latency.yaml` (provisional, Q33); a failing run is not appended unless `--append-on-fail`. `profile_stages.py` gives `cProfile` attribution inside a stage and `torch.profiler` when a GPU exists. The default registry of `make bench` is still the synthetic stubs (`stub_stages.py`, query set `synthetic-v1`); their numbers are not measurements of any component. Real stages have rows under their own query-set ids: `graph_measure.py` registers the real `parse` and `graph_build` throughput stages and the `graph_expand_1hop` / `graph_expand_2hop` latency stages per storage backend (`graph_storage.py`), under query-set ids `graph-<repo>-<backend>-v1` (200 queries of three seed units, `configs/bench/query_sets/graph-<repo>-v1.txt`), so that the regression check never compares them with the stubs; `retrieval_measure.py` the `bm25` and graph-expansion stages with a real index (`retrieval-<repo>-v1`); `dense_measure.py` `query_encode`, `dense_search` and the `dense_encode` throughput; `train_measure.py` the `train_step` throughput per batch shape; `incremental_measure.py` the update-versus-rebuild timings. `rrf_fusion`, `cross_encoder_rerank` and `assemble` have no real stage yet.
- **Hook:** `make hooks` installs `scripts/hooks/latency_check.sh` as pre-commit step `10-latency`; `RIL_LATENCY_HOOK=strict|relaxed|off` selects the reading of "before every commit" (Q3), strict by default.
- **Dependencies:** may call everything; nothing calls back.

## analysis (`ril/analysis/`)

- **Purpose:** error analysis, statistics, figures.
- **Files (built):** table builders per experiment, each reading run outputs and writing `results/tables/`: `e1_tables.py`, `e3_tables.py` (with the clustered bootstrap `Boot`), `x1_tables.py`, `x2_tables.py`, `x3_tables.py`, `x4_tables.py`, `x5_tables.py`, `s1_tables.py`, `e7_tables.py`, `t2_tables.py`, `t3_tables.py`, `t4_tables.py`, `t5_tables.py`, `reach_tables.py`, `graph_tables.py`, `l3_census.py`, `fitted_weights.py`, `rq3_power.py`, `rq1_docstring_pilot.py`, and run-log writers `e1_run_log.py`, `e3_run_log.py`. **Planned, not written:** the retrieval-versus-reasoning error analysis and the figure code.
- **Dependencies:** reads `results/` only (the table builders of the pilots also import the evaluation helpers they summarise).

## config (`ril/config/`)

- **Purpose:** parameters and paths; depends on nothing.
- **Files:** `parameters.py`, `paths.py`.
- **Implemented:** `paths.py` resolves every location from the repository root (no absolute paths); the data root can be redirected with `RIL_DATA_ROOT`. `parameters.py` holds `RunConfig` (seed, name): a frozen dataclass loaded from YAML with a stable SHA-256 `config_hash()`. Experiment parameters are added by the components that own them, in `configs/`, not as code defaults.
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
- **Reproducibility:** seeds, dataset versioning (a provenance record per dataset), config hashing.
- **Experiment tracking:** saved configs, metrics with CIs, artifacts, benchmark history (`RESULTS.md`).
- **Testing:** unit, integration, leakage, reproducibility.
- **Error handling:** explicit failures, helpful diagnostics.

# Architectural assumptions

| Assumption | Rationale | Validation | Risk |
|---|---|---|---|
| Flat exact search is fast enough per repo | 10³–10⁵ units × 768 dims | measure with the latency harness / RQ1 | low |
| Static call-graph recovery is high enough for a graph signal | no published range applies (corrected, see DEV-007); measured: flask dynamic-oracle recall 47.9% resolved, 65.8% with ambiguous sets (ADR-012) | measure per `specs/parse_one_repo.md` | medium — drives RQ1 interpretation |
| Cross-encoder dominates latency | ~100 candidates through a transformer | profile per stage | medium — shapes where to optimise |
| RRF needs no per-corpus retuning | rank-only | verify on L2 vs L3 | low |
| Chunk metrics + function-level internals can coexist | CORE-Bench averages ~15,000 chunks/repo | ADR-004 | medium |

# Known limits and expected bottlenecks

Measured so far (numbers in `results/latency/` and `RESULTS.md`; per hardware spec, p50/p95/p99): parse and graph-build throughput on flask, requests and django; `bm25` and graph expansion on 974 and 35,860 units; dense query encode, flat search and encode throughput; training step throughput per batch shape. Memory: the local box is 8 GB and runs none of the torch work; training memory was checked on the cluster (E-ENCODER-NUMBERS). Storage: graph storage options measured (ADR-011 addendum). `assemble` and a BM25-only `end_to_end` on flask, requests and django (E-ASSEMBLY, ADR-014). Not measured: rerank, end-to-end latency with dense search, fusion and rerank.
Expected at 10×: reranking; indexing throughput for L2-scale corpora; disk on Ada (`$HOME` quota, `docs/COMPUTE.md`).

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

## 2026-10-17 to 2026-10-18 — Waves 1 and 2: CodeUnit, graph, harness, first pilots

- **What changed:** `CodeUnit` frozen at v1 (`code_unit.py`, id, repo and test-path helpers); held-out list and filter with leakage tests in `training/`; `parsing/` gained the repository parser, the typed graph with per-site status, exploratory edge families and history; `bench/` gained the latency and throughput harness; `evaluation/` gained the loaders, rank-based metrics, BM25 reproduction, chunk-to-unit mapping and the edge-recovery measurements; `retrieval/` gained `bm25_index.py`, `graph_expansion.py`, `recency.py`.
- **Why:** settle the data contract first, then measure whether a structural signal can pay off at all.
- **Impact:** parsing and evaluation boundaries as written above; the graph's role stayed open.
- **Related ADR:** ADR-004, ADR-005, ADR-011, ADR-012, ADR-013; DEV-001 to DEV-009.
- **Benchmark:** first `parse`, `graph_build`, `bm25` and graph-storage rows in `results/latency/`.

## 2026-10-23 to 2026-10-26 — Wave 3: dense retrieval, pool check, training stack

- **What changed:** `retrieval/dense_encoder.py` (encoders, flat exact index); `evaluation/x1_*`, `x2_*`, `policy_readers.py`; `parsing/ambiguity_policy.py` and class-source forms; `training/` gained `pool_ranks.py`, `pool_reader.py`, `negatives.py`, `supervision.py`, `data_loader.py`, `contrastive_loss.py`, `encoders.py`, `training.py`, `train_jobs.py` and the three arm hooks; `evaluation/checkpoint_eval.py`; `bench/dense_measure.py`, `bench/train_measure.py`.
- **Why:** obtain the first dense and fusion numbers and a working RQ2 apparatus before any decision.
- **Impact:** training imports no evaluation code (leakage check (d)); the training package depends on the encoder classes of `retrieval/` only.
- **Related ADR:** ADR-001, ADR-002, ADR-003, ADR-006; DEV-010 to DEV-012.
- **Benchmark:** `query_encode`, `dense_search`, `dense_encode` and `train_step` rows.

## 2026-10-29 to 2026-10-30 — Wave 4: supervision pilots, evidence block 1

- **What changed:** `evaluation/s1_graph_role.py`, `e7_encoders.py`, `power.py` extensions, `curve_eval.py` and a step hook in `training.py`; `contamination_edited.py` moved from `training/` to `evaluation/`; `analysis/` gained the table builders `s1`, `e7`, `x4`, `x5`, `t2`, `t3`.
- **Why:** find how long a run must be before the encoder moves, and put numbers on the graph role, the encoder choice and RQ3 power.
- **Impact:** none on boundaries; the 20,000-update assumption was replaced by 100 to 1,000 updates.
- **Related ADR:** ADR-002, ADR-003, ADR-005, ADR-006; DEV-013.
- **Benchmark:** training throughput per batch shape; no query-path change.

## 2026-10-30 to 2026-10-31 — Wave 5: arms pilot

- **What changed:** `supervision.py` gained the NOISE control and `ordering.reverse`; `training.py` gained `budget.stop_after` and `planned_end`; `analysis/t4_tables.py`.
- **Why:** first comparison of RAW, FILTER, WEIGHT and CURRICULUM at stated updates, with a control showing the gain needs correct positives.
- **Impact:** the arm list is now six names (`ARM_NAMES`); the held-identical block is unchanged.
- **Related ADR:** ADR-002 addendum.
- **Benchmark:** not applicable (no query-path change).

## 2026-10-31 — Wave 6: matched-pool arms pilot

- **What changed:** teacher ranks for the 5,000-directory pool; `RandomSubset` (RAW_SUBSAMPLE) in `supervision.py`; `analysis/t5_tables.py`.
- **Why:** remove the pool-size confound of the first arms pilot.
- **Impact:** none on boundaries.
- **Related ADR:** ADR-001, ADR-002 addenda; DEV-014.
- **Benchmark:** not applicable.

## 2026-10-31 — Merge of workstream A (`a/rq1`)

- **What changed:** `parsing/incremental.py` (per-commit graph updater); an order-independent resolver cache in `call_graph.py`; identifier splitting and field weights in `retrieval/bm25_index.py` (the reference form is unchanged); `bench/incremental_measure.py`; `analysis/rq1_docstring_pilot.py`.
- **Why:** per-commit freshness for the agent setting and a tuned lexical index for the RQ1 ablation.
- **Impact:** the resolver output differs on 2 of 4,163 edges of requests (Q57); the full build remains the default (Q58).
- **Related ADR:** ADR-004, ADR-011; open requests Q57 to Q59.
- **Benchmark:** update-versus-rebuild timings in `results/ledger_a.md` (A2a); no change to the stored latency rows.

# Architecture health checklist

When modifying this architecture, verify:

- [ ] Interfaces remain explicit; `CodeUnit` remains the only shared data type.
- [ ] Components remain loosely coupled; the dependency rule in `ril/README.md` still holds.
- [ ] The retrieval stack that RQ2 holds frozen has not been changed after the freeze.
- [ ] New decisions are captured in ADRs; benchmarks exist for performance-sensitive changes.
- [ ] Latency row recorded; changelog updated; documentation reflects the implementation.
