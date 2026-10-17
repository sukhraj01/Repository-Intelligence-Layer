# Project State

> **Current truth only.** Not a history. History lives in `RESULTS.md` and the git log.
> **Hard cap: 200 lines.** If this file exceeds it, the fix is to *delete resolved content*,
> not to add a summary. See the maintenance rule at the bottom.

**Last updated:** 2026-10-17 · **Milestone:** M0 — parser and first graph built; chunk-to-unit mapping and graph reach piloted on flask, requests and seaborn; edge recovery measured under four definitions (none chosen); storage options measured; CodeUnit frozen (v1); held-out list schema 2 · **Tasks completed:** 12

---

## One-line status

Research design is locked (Master Project Document rev 16, 2026-10-11). The repository is a working
Python 3.11 project: `make setup`, `make test`, `make test-all`, `make lint` pass. **Built so far:** the CodeUnit and its
helpers, the held-out filter, the repository parser, the typed graph builder (contain, import, invoke, inherit, override, plus
exploratory tests and configures), the edge-recovery measurements, the graph storage measurement and the
chunk-to-unit mapping with the graph-reach pilot. **No retrieval signal
exists yet** (no BM25, dense encoder, fusion or assembly). Latency harness: **built**; `parse`, `graph_build` and the graph
expansion stages now have real rows (query-set ids `graph-<repo>-<backend>-v1`).

## What is built

| Layer | State | Notes |
|---|---|---|
| Repo scaffold: folders, docs split from master, ADR stubs, specs, folder layout | done | |
| Package `ril/`, `pyproject.toml`, `Makefile`, tests, ruff, `mypy --strict` | done | Python 3.11 pinned; Poetry venv in `.venv`; Ada path (`uv`) in the Makefile header |
| `ril/config`, `ril/util` | done | no experiment parameters yet |
| Commit hook | done, opt-in | `make hooks` installs `scripts/hooks/latency_check.sh` as `10-latency` (runs `make bench-check`, stages the two CSVs; `RIL_LATENCY_HOOK=strict\|relaxed\|off`, strict default); **not installed yet** |
| CodeUnit schema | **FROZEN v1** (ADR-013) | `ril/parsing/code_unit.py`, `unit_id.py`, `repo_id.py`, `path_rules.py` per `specs/code_unit.md` (decision log D4-D11); `unit_type` has `module`; canonical bytes pinned by a golden test; class-unit `source` open (Q28) |
| Data access, formats, statistics | done | every card statistic re-measured; `knowledge/datasets/*.md`; `scripts/ada/README.md`; Ada reachable non-interactively |
| Held-out list, filter, leakage tests | done, list schema 2 | 605 core repositories + 169-repository Loc-Bench tier (switchable) + current-name aliases; `rule_counts`, `rename_resolution`, `content_overlap` in `ril/training/`; rebuild `python -I scripts/build_held_out.py`; resolution is partial without a token (see Blockers) |
| Paper notes and literature scan | done for the reading plan | `knowledge/papers/`, checked quote tables (`scripts/check_paper_note.py`); `LANDSCAPE.md` |
| RepoGraph design | DRAFT v0, options only | `specs/repo_graph.md` (own version constant `REPO_GRAPH_SCHEMA_VERSION`), `docs/GRAPH_DESIGN.md`, ADR-011 Proposed; no choice made, no code |
| Latency harness | **built** | `ril/bench/` (`latency_harness.py`, `profile_stages.py`, `stub_stages.py`); `make bench` / `make bench-check`; logs `results/latency/{latency,throughput}_log.csv`; stages `query_encode`, `bm25`, `dense_search`, `graph_expansion`, `graph_expand_1hop`, `graph_expand_2hop`, `rrf_fusion`, `cross_encoder_rerank`, `assemble`, `end_to_end` (latency) and `parse`, `graph_build` (throughput); thresholds provisional (Q33); a real stage replaces a stub with one `REGISTRY.register` line and a new `query_set_id` |
| Parser and graph | **built** (first build 2026-10-17) | `ril/parsing/` (`repository_parser.py`, `call_graph.py`, `repo_graph.py`, `exploratory_edges.py`, `git_history.py`, `build.py`); `scripts/parse_repo.py PATH --repo-id owner/name --seed N`; own `ast` resolver `own-ast-resolver/v0` (`provisional: ADR-011`); class unit `source` = full class (`provisional: ADR-013`, Q28); byte-identical rebuilds; flask 974 units, requests 678, django 35,860 |
| Edge recovery, exploratory edges, storage options | **measured**, nothing chosen | ADR-012 (four recovery definitions with trade-offs), ADR-011 addendum (storage table), `results/tables/p_*.csv`, `RESULTS.md` rows `p-*`; tracer and comparators in `ril/evaluation/`, storage in `ril/bench/graph_storage.py`, `graph_measure.py` |
| BM25 / dense / fusion / assemble | not started | |
| Training pipeline, supervision arms | not started | |
| Evaluation: chunk-to-unit mapping, graph-reach pilot | **piloted** (exploratory) | `ril/evaluation/chunk_mapping.py`, `graph_reach.py`, `chunk_unit_pilot.py`, `ril/analysis/reach_tables.py`; 160 of 160 positives of flask, requests, seaborn found by exact text (D7 stands), residual share 16 of 160 (D6 stands); `docs/EXPERIMENTS.md` E-GRAPH-REACH, `RESULTS.md` rows `m-*`; job `scripts/ada/m_chunk_unit_reach.sbatch` (about 35 s) |
| Evaluation: CORE-Bench loaders, metrics; agent integration | not started | |

## Decisions log (closed 2026-10-17 by the engineer; reasoning, evidence class and flip experiments in the owning document)

| D (was) | Decision in one line | Owner |
|---|---|---|
| D1 (Q8) | held-out matching = exact names + current-name resolution; fork network = sensitivity only; content-overlap audit reported | `specs/held_out_repos.md`, ADR-001 |
| D2 (Q22) | read-only `GITHUB_TOKEN` on Ada, never printed or stored | same |
| D3 (Q9) | Loc-Bench held out as a separate switchable tier | `specs/held_out_repos.md`, ADR-005 |
| D4 (Q13) | relations in a separate edge store; CodeUnit lists hold resolved ids only | `specs/code_unit.md`, ADR-013 |
| D5 (Q14) | `repo_id` = `owner/name` case-folded; commit in the container; aliases for renames | same |
| D6 (Q15) | top-level functions, methods, classes + one residual `module` unit per file | same, ADR-004 |
| D7 (Q16) | chunk-to-unit link is a derived mapping built by the evaluation loader | same, ADR-004 |
| D8 (Q17) | `last_modified` = last commit time <= snapshot, or `""` | same |
| D9 (Q18) | `is_test` = file-level path rule (agrees with pytest on 3 repositories) | same |
| D10 (Q19) | `tests` filled by the graph build; `[]` = not computed | same |
| D11 (Q20) | id `path::Qual.name`, `#2` ordinal on collisions, converter to the pool form | same |
| D12 (Q21) | unit-level evaluation primary on Verified (432 L2, 302 L3); other sub-datasets chunk-level | ADR-004, ADR-005 |
| D13 (Q23) | Rewrite runs scored against the original qrels; 158 folders reported as a packaging defect | ADR-005, DEV-008 |

## Next task

Pilot E (interventions on BM25 and the graph, all exploratory; tuning discipline in the wave brief: sweeps on non-Verified dev
repositories, Verified only to confirm one pre-stated setting). Start with E1: BM25 at chunk level under the CORE-Bench protocol on
the sample folders (does our loader and metric reproduce the card's 13.0 / 38.8 on L2?), then BM25 at unit level on the mapped
qrels with and without the module unit. The mapping exists (`ril.evaluation.chunk_unit_pilot.analyse_instance`, records under
`data/processed/m_pilot/`, untracked); E3 should seed graph expansion from retrieved units, not gold, against a size-matched random
expansion, and E4 can take edge weights from `results/tables/m_reach.csv`. Engineer: provide `GITHUB_TOKEN` on Ada and rerun
`scripts/ada/resolve_renames.py` (completes held-out v2 counts); decide Q28 and Q39; confirm Q29; read `decisions/ADR-012`, `ADR-011`
(addendum) and `specs/repo_graph.md` "Open design questions" (Q30-Q32, Q35-Q38); settle ADR-001 to ADR-010 by end of week 2.

## Blockers

Data: `GITHUB_TOKEN` is **not set on Ada** (decision D2). The rename cache holds 108 repositories (47 of the
2,448 `gangiswag/train_data` python repositories, 51 of CodeSearchNet's 13,590); every post-rename count is
a lower bound until the token exists (the job is idempotent and resumes). The held-out repositories' own current names are resolved only for the 12
Verified ones (unchanged). Q7: the intended pool is not confirmed. CORE-Bench corpora are streamed, not
stored. Commit: the held-out v2 data files (`data/held_out/*`, `results/tables/*`, the leakage test) are staged but
not committed: the pre-commit trace check rejects three repository names of the new Loc-Bench tier (owners with a hyphenated suffix
matching the provenance patterns); they need the engineer's allowlist, then `git commit` finishes it. No code blocker.

## Open questions

| # | Question | Blocks | Resolve by |
|---|---|---|---|
| Q1 | Which team member is Person A / B / C (owners in `docs/ROADMAP.md`)? | ownership columns | engineer, week 1 |
| Q3 | Does a docs-only commit need a fresh latency row, or may it reference the previous row? Harness implements both behind `RIL_LATENCY_HOOK` (strict default); the hook is not installed until the engineer runs `make hooks` | hook setting | engineer |
| Q33 | Regression thresholds in `configs/bench/latency.yaml` (p50 or p95 up by more than 50% and 0.5 ms vs the previous comparable row) are conservative placeholders, `provisional: Q33`; also whether a failing run is logged (now: not, unless `--append-on-fail`) | `make bench-check`, hook | engineer, before the freeze |
| Q34 | `parse` and `graph_build` are offline, so they sit in the throughput log (units/s), while `graph_expand_1hop/2hop` are per-query latency stages; the first build used exactly this split (workload ids `graph-<repo>-v1`). Confirm it | stage taxonomy | engineer |
| Q4 | GitHub remote(s) for the team repo; the engineer performs every push | publishing only | engineer |
| Q5 | ADR-001...ADR-010 (training pool, quality signal, graph role, granularity, benchmark, encoder, scaffold, LLM, rerank, usable-by-others) | frozen config, RQ2 start | team, end of week 2 |
| Q7 | Is the candidate pool intended, or is the pool built with the published scripts? Read in full: `gangiswag/train_data` python = SweLocMulti's Python part (SweRank+ Table 1: 2,448 repositories, 24,285 PRs, 49,973 instances), not the original SweLoc (3,387 repositories); SweRank+ states no benchmark-repository exclusion; 89 held-out repositories (3,431 PRs, 14.13%) occur in it (DEV-004). Loc-Bench: 560 rows (V1) vs 660 (V0.2) | ADR-001, pool filter | engineer; evidence in ADR-001 addenda |
| Q11 | CORE-Bench evaluation is whole-snapshot retrieval: each query's candidate list is the repository snapshot at the base commit (paper Sec. 4.1; 12,153 of 12,153 list chunks located in 11 base-commit checkouts; DEV-003), and chunk ids carry no path or line span. D7 and D12 fix the mapping and the primary set; pilot M located 160 of 160 positives by exact text (three repositories); still open: the reported-metric granularity and whether chunk-level numbers are also reported (ADR-004) | ADR-004, evaluation | engineer |
| Q12 | CORE-Bench L3 labels are LLM-judged; the paper does not say how the three votes combine into the kept score (R1); released qrels are binary; L2 positives include import blocks (3 of 53 sampled) | RQ3 interpretation | note in report |
| Q24 | Master statement "tests and configuration are covered by nobody" no longer holds as worded (LARGER, Table 11; DEV-006); no ablation of such links exists. Keep it reworded ("no ablation shows the value of test and configuration links") or drop it | `docs/05`, report wording | engineer |
| Q25 | Derived master copies in `docs/` still carry the superseded numbers and identifiers recorded in DEV-003 to DEV-007 (KGCompass 89.7% not 69.7%, Loc-Bench counts, CodeR identifier, edge-recovery expectation, ...). Edit the copies, or keep this file as the record? | `docs/03`, `docs/05`, `docs/06`, `docs/11` | engineer |
| Q27 | Which edge-recovery definition(s) to report: ADR-012 now holds four measured definitions (call-site share 28-72% by denominator; dynamic oracle on the flask suite 48% resolved, 66% with ambiguous, n = 1,057 pairs; Jedi agreement 100% on resolved, 49% on ambiguous; inspection of 100 sites). No single percentage reproduces the master's 70-85% | ADR-012, reporting | engineer |
| Q28 | Class unit `source`: full class text or header only (the `Flask` class is 2,124 lines and its methods are units). The schema is unaffected; the parser stays behind `provisional: ADR-013` until decided | parser, index size | engineer |
| Q29 | Confirm the readings of D6 and D8 made in code: module unit fields (`<module>` name, span = file, `source` = residual lines) and `last_modified` as `YYYY-MM-DDTHH:MM:SSZ` | parser | engineer |
| Q30 | Graph role(s) in the frozen configuration and how a graph signal enters a fusion stack fixed to rank-based RRF (hop-decay score vs ranked list vs edited candidate list); whether graph-derived supervision (structural negatives, test/config positives) is inside RQ2; whether an agent-tool variant belongs to RQ3 (agent fixed). Options and evidence: `docs/GRAPH_DESIGN.md` sections 4 and 9 | ADR-003, frozen config | team, end of week 2 |
| Q31 | ADR-011 schema choices (`specs/repo_graph.md` Q-G3 to Q-G15): `test` as flag or kind; which files are config/document; optional edge fields (`site`, `target_text`, `count`); `external` vs `unresolved` boundary; one graph per commit vs validity ranges; resolver per family; which families are in the first stored graph; storage option (measured in the first graph build) | ADR-011, first graph build | engineer, after the build |
| Q35 | Policy for `ambiguous` sites (Q-G13/Q-G14): 12 of 20 inspected sets were spurious (calls on dictionaries, sockets, test-client objects whose method name matches an in-repository method); the right target was in the set 40% of the time. Options: keep as stored; re-bucket by receiver evidence (literals, `**kwargs`, annotated external types, fixture parameters) as `external`; drop sets above a size; keep only for expansion. Edge taxonomy is the engineer's | ADR-011, graph role | engineer |
| Q36 | `external` vs `unresolved` boundary (Q-G8) measured on 40 inspected sites: `external` was right 20 of 20, `unresolved` sites were external in 10 of 20 and in-repository by name in 2 of 20. Options as in the spec; rules are in `results/tables/p_graph_rule_counts.csv` | ADR-011 | engineer |
| Q37 | Which exploratory families enter the first stored artifact: `tests` precision by reading, n = 60: body call plus name 94%, body call alone 56%, name convention 85%; `configures` 93% (n = 60, seven repositories; only 13 edges exist in the three main ones); `co_change` counts only. All labels by one reader (the author of the build); a second reader is the open step | ADR-011 (Q-G14) | engineer |
| Q38 | Storage option(s): measurements exist (ADR-011 addendum); in-memory structures answer 2 hops in under 1 ms at django scale, SQLite queried directly about 25 times slower, the embedded graph database about 100 times slower; which write format, which read structure, per-commit graphs (Q-G10) are decisions | ADR-011 | engineer |
| Q39 | Unit-level metric definition for chunks that map to several units or to residual lines: pilot M shows 21 of 160 sampled positives span several functions or methods, 5 fall on a class only, 16 on residual lines only, and 6 more span a method and its nested function (one unit under D6). Options: a positive counts for every unit it overlaps; for the largest-overlap unit; for a unit only above an overlap threshold. Metric definitions are the engineer's | ADR-004, E1 | engineer |
| Q32 | Confirm two readings made in the graph spec: `tests(u)` = test units with a resolved `tests` edge to `u`; `configs(u)` = config paths with a resolved `configures` edge to `u` or its file | projections | engineer |

Resolved this block: Q8, Q9, Q13-Q23 (decisions log above), Q26 (recorded in DEV-007). Earlier: Q10, Q2, Q6.

## Carried debt

None.

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Retrieval stack not frozen before RQ2 starts | RQ2 arms differ in more than supervision | latency optimisation and config freeze land before week 6; `configs/frozen/` is immutable after freeze |
| Repository leakage between training pool and L2/L3/Verified | invalidates RQ2 and RQ3 | repo-level disjointness test in `tests/leakage/`; held-out list built first |
| CORE-Bench ships no train split (SFT set unreleased) | "train on CORE-Bench" has no referent | SweLoc + own PR-mined set (ADR-001) |
| Week-12 go/no-go: fewer than two distinguishable retrievers | RQ3 cut | fallback declared in the proposal; ships as RQ1 + RQ2 + latency analysis |
| Ada: throttled downloads, quota, QOS changes, bad GPU nodes | slow or failed jobs | `docs/COMPUTE.md` lessons; resumable downloads; GPU-capability gate |
| Schedule slip on parser/graph (Person A critical path) | RQ1 and graph extension late | week-3 milestone check; CodeUnit frozen in week 1 so others are unblocked |

---

## Maintenance rule

This file is **replaced, not appended.** At the end of each working block:

1. Rewrite the tables above so they describe reality *now*.
2. Delete anything resolved. A closed question leaves this file entirely — its reasoning lives in
   the ADR, `RESULTS.md` row or commit message that closed it.
3. Do not paste benchmark output here. One aggregate number max; details go to `RESULTS.md`.
4. Do not paste narrative here.
5. If you are about to add a fifth row to a table that already has ten, something is being tracked
   at the wrong granularity — move it to `docs/ROADMAP.md`.

**Why the cap exists:** this file is read at the start of every working block. A 200-line file
costs seconds. Left to grow it becomes thousands of lines of resolved history, gets skimmed instead
of read, and stops working precisely when the project is complex enough to need it. Pruning it is
part of the task, not cleanup after the task.

## Boundaries with other docs

| File | Holds | Volatility |
|---|---|---|
| `PROJECT_STATE.md` | what is true right now | rewritten at the end of each block of work |
| `docs/ROADMAP.md` | the plan, weeks 1–16, checkboxes | ticked, rarely restructured |
| `RESULTS.md` | every benchmark ever run, one line each | append-only |
| `decisions/` | why each significant choice was made | ADR per decision, addenda not overwrites |
| `docs/DEVIATIONS.md` | departures from the master doc | append-only |
| `docs/EXPERIMENTS.md` | experiment registry: IDs, protocol, status | updated as experiments are planned/run |
| `docs/0*–12*` | design, split from the master doc by topic | stable; master wins on conflict |

If a fact could go in two of these, it goes in exactly one — the leftmost row that fits.
