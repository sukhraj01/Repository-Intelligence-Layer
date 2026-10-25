# Project State

> **Current truth only.** Not a history. History lives in `RESULTS.md` and the git log.
> **Hard cap: 200 lines.** If this file exceeds it, the fix is to *delete resolved content*,
> not to add a summary. See the maintenance rule at the bottom.

**Last updated:** 2026-10-25 · pool filter state measured (E-POOL-RANKS: qrels not filtered per positive; directories selected with respect to SweRankEmbed-Small; filter vs teacher fit open) · first dense numbers: CodeRankEmbed and Qwen3-Embedding-0.6B zero-shot, BM25+dense fusion and the graph on a fused first stage (E-DENSE-FUSION, nothing decided) · 2026-10-23: engineer decisions D14-D24 recorded; references audited (DEV-011); derived copies corrected (DEV-010); class-unit source forms, ambiguous-site policies and the L3 positive census measured (Q28, Q35, Q36 evidence; nothing decided) · **Milestone:** M0 — parser and first graph built; graph reach piloted; BM25 index, CORE-Bench loader and metrics built and checked against the published BM25 rows; graph expansion, fitted edge weights and a recency prior piloted on BM25 seeds (exploratory); dev/test repositories fixed; edge recovery measured under four definitions (none chosen); CodeUnit frozen (v1); held-out list schema 2; pool check, power table and a contamination slice measured · **Tasks completed:** 20

---

## One-line status

Research design is locked (Master Project Document rev 16, 2026-10-11). The repository is a working
Python 3.11 project: `make setup`, `make test`, `make test-all`, `make lint` pass. **Built so far:** the CodeUnit and its
helpers, the held-out filter, the repository parser, the typed graph builder (contain, import, invoke, inherit, override, plus
exploratory tests and configures), the edge-recovery measurements, the graph storage measurement and the
chunk-to-unit mapping with the graph-reach pilot, the BM25 index and the CORE-Bench loader and metrics (reproduce the published BM25 rows). BM25 and a **dense encoder with a flat exact index** (`provisional: ADR-006`) exist as retrieval signals; fusion,
graph expansion and a recency prior exist as measurement code only; no assembly. Latency harness: **built**; `parse`, `graph_build`, the graph
storage stages and now `bm25`, `graph_expand_1hop/2hop` and `graph_expansion` with a real index have rows (query-set ids `graph-<repo>-<backend>-v1`, `retrieval-<repo>-v1`).

## What is built

| Layer | State | Notes |
|---|---|---|
| Repo scaffold: folders, docs split from master, ADR stubs, specs, folder layout | done | |
| Package `ril/`, `pyproject.toml`, `Makefile`, tests, ruff, `mypy --strict` | done | Python 3.11 pinned; Poetry venv in `.venv`; Ada path (`uv`) in the Makefile header |
| `ril/config`, `ril/util` | done | no experiment parameters yet |
| Commit hook | done, opt-in | `make hooks` installs `scripts/hooks/latency_check.sh` as `10-latency` (runs `make bench-check`, stages the two CSVs; `RIL_LATENCY_HOOK=strict\|relaxed\|off`, strict default); **not installed yet** |
| CodeUnit schema | **FROZEN v1** (ADR-013) | `ril/parsing/code_unit.py`, `unit_id.py`, `repo_id.py`, `path_rules.py` per `specs/code_unit.md` (decision log D4-D11); `unit_type` has `module`; canonical bytes pinned by a golden test; class-unit `source` open (Q28; three forms measured, ADR-013 addendum of 2026-10-23) |
| Data access, formats, statistics | done | every card statistic re-measured; `knowledge/datasets/*.md`; `scripts/ada/README.md`; Ada reachable non-interactively |
| Held-out list, filter, leakage tests | done, list schema 2 | 605 core repositories + 169-repository Loc-Bench tier (switchable) + current-name aliases; `rule_counts`, `rename_resolution`, `content_overlap` in `ril/training/`; rebuild `python -I scripts/build_held_out.py`; resolution is partial without a token (see Blockers) |
| Paper notes and literature scan | done for the reading plan; fourth pass 2026-10-23 | `knowledge/papers/`, checked quote tables (`scripts/check_paper_note.py`); `LANDSCAPE.md` (per-RQ taken / open / contradicted, scan refreshed 2026-10-23 with queries and dates; RQ2 and graph leads still unread are listed there) |
| RepoGraph design | DRAFT v0, options only | `specs/repo_graph.md` (own version constant `REPO_GRAPH_SCHEMA_VERSION`), `docs/GRAPH_DESIGN.md`, ADR-011 Proposed; no choice made, no code |
| Latency harness | **built** | `ril/bench/` (`latency_harness.py`, `profile_stages.py`, `stub_stages.py`); `make bench` / `make bench-check`; logs `results/latency/{latency,throughput}_log.csv`; stages `query_encode`, `bm25`, `dense_search`, `graph_expansion`, `graph_expand_1hop`, `graph_expand_2hop`, `rrf_fusion`, `cross_encoder_rerank`, `assemble`, `end_to_end` (latency) and `parse`, `graph_build` (throughput); thresholds provisional (Q33); a real stage replaces a stub with one `REGISTRY.register` line and a new `query_set_id` |
| Parser and graph | **built** (first build 2026-10-17) | `ril/parsing/` (`repository_parser.py`, `call_graph.py`, `repo_graph.py`, `exploratory_edges.py`, `git_history.py`, `build.py`); `scripts/parse_repo.py PATH --repo-id owner/name --seed N`; own `ast` resolver `own-ast-resolver/v0` (`provisional: ADR-011`); class unit `source` = `full` by default, `header` and `header_sigs` selectable (`ParseOptions.class_source`, `provisional: ADR-013`, Q28); ambiguous invoke sites read through a policy (`ril/parsing/ambiguity_policy.py`: keep, drop, rebucket, max3; stored graph unchanged; Q35); byte-identical rebuilds; flask 974 units, requests 678, django 35,860 |
| Edge recovery, exploratory edges, storage options | **measured**, nothing chosen | ADR-012 (four recovery definitions with trade-offs), ADR-011 addendum (storage table), `results/tables/p_*.csv`, `RESULTS.md` rows `p-*`; tracer and comparators in `ril/evaluation/`, storage in `ril/bench/graph_storage.py`, `graph_measure.py` |
| BM25 | **built** (reference form), latency rows exist | `ril/retrieval/bm25_index.py`: reference tokenisation (stemmed, 33-word stop list) and Lucene-variant scoring, k1 1.5 / b 0.75 `provisional: ADR-004`, `top_k`; no identifier splitting or fields yet; `bm25` p50 0.04 ms on 974 units, 0.20 ms on 35,860 (local) |
| Graph expansion, recency prior (pilot code) | **piloted** (exploratory) | `ril/retrieval/graph_expansion.py` (hop decay, edited list and RRF-fused list, chance controls), `recency.py`; `ril/evaluation/e3_prepare.py` (instance cache), `e3_eval.py` (grids; refuses to sweep on test instances), `e6_dense.py` (dense scores, never run); `ril/analysis/e3_tables.py`, `fitted_weights.py`; `docs/EXPERIMENTS.md` E-GRAPH-SIGNAL, E-GRAPH-WEIGHTS, E-RECENCY, `RESULTS.md` rows `e3-*`, `e4-*`, `e5-*`; structure variants on the same cache: `ril/evaluation/{x1_prepare,x1_eval,policy_readers}.py`, `ril/analysis/{x1_tables,l3_census}.py` (E-CLASS-SOURCE, E-AMBIG-POLICY, E-L3-CENSUS, rows `x1-*`; clustered bootstrap added to `e3_tables.Boot`); none of it is a design choice (Q30) |
| Dense encoder, flat exact index | **built**, measured zero-shot | `ril/retrieval/dense_encoder.py` (CodeRankEmbed, Qwen3-Embedding-0.6B, revisions pinned, `provisional: ADR-006`); cluster pipeline `ril/evaluation/{x2_dense,x2_jobs}.py`, evaluation `x2_eval.py`, tables `ril/analysis/x2_tables.py`; latency `ril/bench/dense_measure.py` (stages `query_encode`, `dense_search`, throughput `dense_encode`); `docs/EXPERIMENTS.md` E-DENSE-FUSION, rows `x2-*`, ADR-006/ADR-003 addenda; 2.84 GPU-hours of block 1 |
| Pool ranks (K-rank teachers) | **measured** (exploratory) | `ril/training/{pool_ranks,pool_rank_jobs}.py`, `ril/analysis/x3_tables.py`, `scripts/pool_ranks.py`, jobs `scripts/ada/x3_*.sbatch`; SweRankEmbed-Small registered as a teacher (`dense_encoder.py`); 160 stratified directories, 1,522 positives, plus the never-filtered Verified export (457); per-positive rank table `results/tables/x3_pool_ranks_features.csv`; full-pool job resumable, about 4.9 GPU-hours per dense teacher (not run); 1.25 GPU-hours of block 1 |
| Fusion, assemble | fusion measured (RRF, score level), not a stage; assembly not started | |
| Training pipeline, supervision arms | not started | |
| Evaluation: chunk-to-unit mapping, graph-reach pilot | **piloted** (exploratory) | `ril/evaluation/chunk_mapping.py`, `graph_reach.py`, `chunk_unit_pilot.py`, `ril/analysis/reach_tables.py`; 160 of 160 positives of flask, requests, seaborn found by exact text (D7 stands), residual share 16 of 160 (D6 stands); `docs/EXPERIMENTS.md` E-GRAPH-REACH, `RESULTS.md` rows `m-*`; job `scripts/ada/m_chunk_unit_reach.sbatch` (about 35 s) |
| Evaluation: CORE-Bench loader, metrics, unit-level BM25, label-noise readings | **built, piloted** (exploratory) | `ril/evaluation/{core_bench,metrics,unit_retrieval,label_noise,e1_run}.py`; reproduces Verified L2 11.94 / 46.74, L3 22.19 / 33.89 and all-L2 13.00 / 38.82 (mean over folders; paper 11.9 / 46.7, 22.2 / 33.9, 13.0 / 38.8); `docs/EXPERIMENTS.md` E-BM25-REPRO, E-LABEL-NOISE, `RESULTS.md` rows `e1-*`, `e2-*`; jobs in `scripts/ada/README.md` |
| Agent integration | not started | |
| Dev / test repositories | **set** (2026-10-18) | dev: Pro openlibrary and qutebrowser, Live conan, haystack, streamlink (355 instances; base commits from the datasets' metadata); test: Verified (12 folders, six with units); `configs/experiments/e1_bm25_reproduction.yaml`; sweeps on role `dev` only |

## Decisions log (closed 2026-10-17 and 2026-10-18 by the engineer; reasoning, evidence class and flip experiments in the owning document; index in `decisions/README.md`)

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
| D14 (Q24, Q25) | "covered by nobody" reworded to "no ablation shows the value of test and configuration links"; derived copies corrected in place with "(corrected, see DEV-0nn)" | DEV-010, DEV-011, ADR-003 |
| D15 (Q27) | edge recovery reported as dynamic-oracle recall (with and without implicit callees, n stated) beside the call-site breakdown with denominators named; "70-85%" not repeated | ADR-012 |
| D16 (Q38) | first stored graph read into an in-memory adjacency from a typed edge-list file; no graph database | ADR-011, `specs/repo_graph.md` |
| D17 (Q40) | primary averaging = mean over queries with repository-clustered bootstrap intervals; folder means only in the reproduction table | ADR-005 |
| D18 (Q39, Q41) | a chunk's positive counts for every unit it overlaps; gold without module residuals primary for graph decisions, CORE-Bench-faithful reading beside it; **provisional**; checked 2026-10-23: class-source and policy orderings do not flip, some edge-subset orderings do (among overlapping intervals, ADR-004 addendum); X2 (2026-10-25): the stated selections and every Verified ordering are the same under both readings; on dev, CodeRankEmbed alone is 3.5 below BM25 at L3 under the primary reading and level with it under `units_all` (one flip larger than 2.5 points; ADR-006 addendum) | ADR-004 |
| D19 (Q37) | first stored graph: contain, invoke, import, inherit/override; tests, configures, co_change built but off by default | ADR-011 |
| D20 (Q29, Q32, Q34) | readings in code accepted (module unit fields, timestamp form; `tests(u)`/`configs(u)` projections; offline stages in the throughput log); Q3 strict, Q33 provisional | `specs/code_unit.md`, `specs/repo_graph.md`, `specs/latency_harness.md`, ADR-013 |
| D21 (Q42) | GPU use authorised: block 1 <= 8 GPU-hours, block 2 <= 24, logged per job | ADR-006, `docs/COMPUTE.md` |
| D22 (Q43) | pool filter-state experiment (X3) runs; the pool is `gangiswag/train_data` python minus the held-out list, `provisional: ADR-001`; X3 reported 2026-10-25 (ADR-001, ADR-002 addenda): qrels unfiltered per positive (RAW available), directories selected w.r.t. SweRankEmbed-Small (PR-level filter or teacher fit, open: Q50) | ADR-001 |
| D23 (Q44) | full documents-only contamination scan in the background (X4), base-commit functions above a size floor; not part of the frozen evaluation; **pending X4** | ADR-005, `docs/EXPERIMENTS.md` |
| D24 | not decided in advance, settled by this wave's measurements: Q28, Q35/Q36, Q30, ADR-006 encoder, ADR-001 pool (after X3); Q45 waits for ADR-007; Q1, Q4 the engineer's | owning ADRs |

## Next task

Block 1 of the wave is complete (H, R4, X1, X2, X3); GPU-hours used in block 1: 4.09 of 8 (`docs/COMPUTE.md`). The orchestrator's
checkpoint message to the engineer is next, then Block 2 with session T1 (training stack, `provisional: ADR-001, ADR-002, ADR-006`),
whose pool reader can take X3's per-instance feature table (`results/tables/x3_pool_ranks_features.csv`; full pool by
`scripts/ada/x3_dense.sbatch SELECT=all`, about 4.9 GPU-hours per dense teacher, block 2).
For the engineer: ADR-001/ADR-002 now have pool evidence (addenda of 2026-10-25, Q7, Q50); ADR-006 and Q30 dense evidence; Q28, Q35, Q36
evidence; answer `data/review/spot_check.md` and run `python -I scripts/spot_check_agree.py ANSWERS.csv`; correct the master document per
DEV-011 and DEV-005 to DEV-007.

## Blockers

Data: `GITHUB_TOKEN` is **not set on Ada** (decision D2). The rename cache holds 108 repositories (47 of the
2,448 `gangiswag/train_data` python repositories, 51 of CodeSearchNet's 13,590); every post-rename count is
a lower bound until the token exists (the job is idempotent and resumes). The held-out repositories' own current names are resolved only for the 12
Verified ones (unchanged). Q7: the intended pool is not confirmed (the directories hold 307,996 positive rows; X3: not the table's 49,973 instances under any teacher and K tried; Q50). CORE-Bench corpora are streamed, not
stored. The training pool stays provisional (D22, ADR-001 open). No code blocker.

## Open questions

| # | Question | Blocks | Resolve by |
|---|---|---|---|
| Q1 | Which team member is Person A / B / C (owners in `docs/ROADMAP.md`)? | ownership columns | engineer, week 1 |
| Q3 | Does a docs-only commit need a fresh latency row, or may it reference the previous row? Harness implements both behind `RIL_LATENCY_HOOK` (strict default); the hook is not installed until the engineer runs `make hooks` | hook setting | stays strict (D20); engineer |
| Q33 | Regression thresholds in `configs/bench/latency.yaml` (p50 or p95 up by more than 50% and 0.5 ms vs the previous comparable row) are conservative placeholders, `provisional: Q33`; also whether a failing run is logged (now: not, unless `--append-on-fail`) | `make bench-check`, hook | stays provisional until real stages have rows (D20); engineer, before the freeze |
| Q4 | GitHub remote(s) for the team repo; the engineer performs every push | publishing only | engineer |
| Q5 | ADR-001...ADR-010 (training pool, quality signal, graph role, granularity, benchmark, encoder, scaffold, LLM, rerank, usable-by-others) | frozen config, RQ2 start | team, end of week 2 |
| Q7 | Is the candidate pool intended, or is the pool built with the published scripts? Read in full: `gangiswag/train_data` python = SweLocMulti's Python part (SweRank+ Table 1: 2,448 repositories, 24,285 PRs, 49,973 instances), not the original SweLoc (3,387 repositories); SweRank+ states no benchmark-repository exclusion; 89 held-out repositories (3,431 PRs, 14.13%) occur in it (DEV-004). Loc-Bench: 560 rows (V1) vs 660 (V0.2) | ADR-001, pool filter | engineer (D22: provisional pool meanwhile); X3 evidence in the ADR-001 addendum of 2026-10-25 |
| Q11 | CORE-Bench evaluation is whole-snapshot retrieval: each query's candidate list is the repository snapshot at the base commit (paper Sec. 4.1; 12,153 of 12,153 list chunks located in 11 base-commit checkouts; DEV-003), and chunk ids carry no path or line span. D7 and D12 fix the mapping and the primary set; pilot M located 160 of 160 positives by exact text (three repositories); still open: the reported-metric granularity and whether chunk-level numbers are also reported (ADR-004) | ADR-004, evaluation | engineer |
| Q12 | CORE-Bench L3 labels are LLM-judged; the paper does not say how the three votes combine into the kept score (R1); released qrels are binary; L2 positives include import blocks (3 of 53 sampled) | RQ3 interpretation | note in report |
| Q28 | Class unit `source`: `full`, `header` or `header_sigs` (schema unaffected; parser option behind `provisional: ADR-013`). Measured 2026-10-23 on dev (ADR-013 addendum): under D18's every-overlapped-unit gold `full` leads by 2-3 points (BM25 and `core` expansion, L2 and L3) and the stated rule keeps it; under pilot M's mapping the forms are level; `full` indexes about 55% more tokens. The answer turns on how a class becomes gold (D18 part 1) | parser, index size | engineer (with ADR-004's class reading) |
| Q30 | Graph role(s) in the frozen configuration and how a graph signal enters a fusion stack fixed to rank-based RRF (hop-decay score vs ranked list vs edited candidate list); whether graph-derived supervision (structural negatives, test/config positives) is inside RQ2; whether an agent-tool variant belongs to RQ3 (agent fixed). Options and evidence: `docs/GRAPH_DESIGN.md` sections 4 and 9; first retrieval-level evidence (pilots E3 to E5, ADR-003 addendum): expansion from BM25 seeds gains at L3 and little at L2, containment carries it, edited list and fused list give the same L3 Recall@100 and the fused list a smaller L2 gain | ADR-003, frozen config | measured (2026-10-25, ADR-003 addendum): on RRF(BM25, Qwen3) the three forms overlap on dev; Verified-six core +4.4 [+0.5, +8.8] at L3, +0.2 at L2, not distinguishable from same-file chance at L3; team |
| Q31 | ADR-011 schema choices still open (`specs/repo_graph.md` Q-G3 to Q-G11, Q-G13; storage read structure D16, first families D19, projections D20 and recovery reporting D15 are decided): `test` as flag or kind; which files are config/document; optional edge fields (`site`, `target_text`, `count`); `external` vs `unresolved` boundary; one graph per commit vs validity ranges; resolver per family; which families are in the first stored graph; storage option (measured in the first graph build) | ADR-011, first graph build | engineer, after the build |
| Q35 | Policy for `ambiguous` sites (Q-G13/Q-G14): 12 of 20 inspected sets were spurious (calls on dictionaries, sockets, test-client objects whose method name matches an in-repository method); the right target was in the set 40% of the time. Options: keep as stored; re-bucket by receiver evidence (literals, `**kwargs`, annotated external types, fixture parameters) as `external`; drop sets above a size; keep only for expansion. Edge taxonomy is the engineer's | ADR-011, graph role | measured 2026-10-23 (ADR-011 addendum): no policy beats `drop` in expansion (`keep` -2.4, `rebucket` -1.6, `max3` +0.1 L3 Recall@100); oracle precision 0.62 `drop`, 0.32 `keep`, 0.48 `max3`; the fixture rule is not supported by the oracle; engineer |
| Q36 | `external` vs `unresolved` boundary (Q-G8) measured on 40 inspected sites: `external` was right 20 of 20, `unresolved` sites were external in 10 of 20 and in-repository by name in 2 of 20. Options as in the spec; rules are in `results/tables/p_graph_rule_counts.csv`. 2026-10-23: 4 of 650 executed `external` sites in flask had an in-repository callee of that name; Jedi reads 30 of 44 answered `unresolved` sites as in-repository (resolver recall limit) | ADR-011 | engineer |
| Q47 | D17's repository-clustered interval at dev L3: only two dev repositories have L3 qrels (openlibrary, qutebrowser), so the clustered interval there is not informative (it can be narrower than the query-level one); options: quote the query-level interval at dev L3 (done in the 2026-10-23 tables), add a dev L3 repository (SWE-bench Pro ansible has L3 qrels and is now mapped, 83 instances), or pool L3 dev and Verified for intervals only | how L3 dev numbers are quoted | engineer (D17 owner) |
| Q48 | Qwen3-Embedding query instruction: the report gives the format only; X2 used a task sentence of its own (ADR-006 addendum). If this encoder is chosen, the instruction belongs in the RQ2 "held identical" block; no instruction variant was measured | ADR-006, frozen config | engineer (with ADR-006) |
| Q49 | Is the graph's L3 gain more than file-level expansion? On the fused first stage it is not distinguishable from same-file chance on Verified (ADR-003 addendum); cheapest test: a same-file expansion ordered by first-stage score instead of random (minutes, existing inputs) | Q30 | evidence by a short CPU run, then team |
| Q50 | Pool selection: every sampled pool directory has a positive in SweRankEmbed-Small's top 10 (0 of 160) against 19.3% [15.7, 23.2] without one on the never-filtered Verified export; a PR-level filter and the checkpoint's fit to these PRs both explain it. Options: accept the pool with the limitation stated (RAW = "given one easy positive"), mine an own raw PR set, or settle it first by PR creation dates against the checkpoint release (needs `GITHUB_TOKEN`, D2). Also: SweRankEmbed-Small may not be an independent K-rank teacher for this pool; CodeRankEmbed is | ADR-001, ADR-002, RQ2 arms | engineer (with ADR-001/ADR-002); evidence `docs/EXPERIMENTS.md` E-POOL-RANKS |
| Q45 | Which discordance (0.10 to 0.30) and run-to-run SD (2 to 5 points) to plan the RQ3 sample with: the power table gives minimum detectable effects of 4.5 to 7.75 points at n = 432 (`docs/EXPERIMENTS.md`, E-POWER); the values need an agent pilot | RQ3 sample size, run count | after an agent pilot; waits for ADR-007 (D24) |
| Q46 | Negative policy held identical across the RQ2 arms: random repository-local (CORE-Bench), teacher top-M (SweRank), or teacher top-M with a cut relative to the positive's teacher score (read in full: the selection rule alone moved a text retriever 4.5 to 9 nDCG points, `nv-retriever-2407.15831.md`; BM25-mined negatives weakest in two text studies); with several positives the cut needs a stated reference positive; if the K-rank teacher is also the miner, FILTER and the negative policy share one signal. No code measurement exists | T1 negative hook, E-PILOT-NEG | evidence from T2 (E-PILOT-NEG), then engineer (ADR-002) |

Resolved this block: Q24, Q25, Q27, Q29, Q32, Q34, Q37, Q38, Q40, Q42 (decisions D14-D21 above); Q39, Q41 provisionally (D18); Q43 reported by X3 (D22; evidence only, ADR-001 open, Q50); Q44 pending X4 (D23). Earlier: Q8, Q9, Q13-Q23, Q26, Q10, Q2, Q6.

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
