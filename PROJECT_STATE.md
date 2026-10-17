# Project State

> **Current truth only.** Not a history. History lives in `RESULTS.md` and the git log.
> **Hard cap: 200 lines.** If this file exceeds it, the fix is to *delete resolved content*,
> not to add a summary. See the maintenance rule at the bottom.

**Last updated:** 2026-10-17 · **Milestone:** M0 — empty package bootstrapped; data sources located and sampled; twelve data, training and graph papers read in full · **Tasks completed:** 6

---

## One-line status

Research design is locked (Master Project Document rev 16, 2026-10-11). The repository is now a
working, empty Python 3.11 project: `make setup`, `make test`, `make test-all`, `make lint` pass.
**No research code exists.** Latency harness: **not built** (commits are exempt until it is).

## What is built

| Layer | State | Notes |
|---|---|---|
| Repo scaffold: folders, docs split from master, ADR stubs, specs | done | |
| Package `ril/`, `pyproject.toml`, `Makefile`, tests, ruff, `mypy --strict` | done | Python 3.11 pinned; Poetry venv in `.venv`; Ada path (`uv`) documented in the Makefile header |
| `ril/config` (paths, `RunConfig` + hash), `ril/util` (seed, logger, sanity) | done | no experiment parameters yet |
| Commit hook | done, opt-in | `make hooks` installs `scripts/hooks/latency_check.sh` as `pre-commit.d/10-latency`; not installed yet |
| CodeUnit schema | draft implemented, **not frozen** | `ril/parsing/code_unit.py` (+ unit and reproducibility tests) per `specs/code_unit.md` DRAFT v0, `CODEUNIT_SCHEMA_VERSION = "v0-draft"`; eight open questions Q13-Q20 below; freeze is the engineer's sign-off |
| Data access, formats, statistics (CORE-Bench, Verified, Loc-Bench, SweLoc search, CoRNStack/CSN) | done | every card statistic re-measured and agrees (`results/tables/core_bench_card_vs_measured.csv`); `knowledge/datasets/*.md`; `scripts/ada/README.md`; Ada reachable non-interactively |
| Held-out repository list, filter, leakage tests | done | 605 repositories in `data/held_out/` (report, pool reports); `filter_pool` and leakage helpers in `ril/training/`; `tests/leakage/` real tests; rebuild with `python -I scripts/build_held_out.py` |
| Paper notes (data, training, graphs) | partly done | `knowledge/papers/`: CORE-Bench, SweRank, SweRank+, CoRNStack, SWE-bench, LocAgent, KGCompass, LARGER, SpIDER, GREPO, ARISE, CoSIL read in full, each with a quote table re-found in the extracted text by `scripts/check_paper_note.py` (logic in `ril/util/paper_note.py`, unit tests); each graph note records graph role, edge types, ablation, resolution coverage, latency and held-out handling; remaining papers in `knowledge/papers/README.md` are not read |
| Latency harness | **not built** | `make bench` / `make bench-check` print "latency harness: not built" |
| Parser / call graph / BM25 / dense / fusion / assemble | not started | |
| Training pipeline, supervision arms | not started | |
| Evaluation (CORE-Bench loaders, metrics), agent integration | not started | |

## Next task

Next in the plan: read the call-graph accuracy papers (PyCG, Jarvis), the supervision-quality papers and run the literature scan; the items below stay with the engineer.

Engineer: close Q13-Q20 and freeze the CodeUnit (set the spec status, bump the version, write the ADR); settle Q8 (fork and rename rule)
and Q9 (Loc-Bench) so the held-out list can be finalised. Then: the latency harness, then parsing one repository
(`specs/latency_harness.md`, `specs/parse_one_repo.md`). Available for RQ3 pairing: 432 instances with L2 labels and 302 with L2 and L3 labels,
all in SWE-bench Verified (`results/tables/paired_n.json`).

## Blockers

None for code. Data: no confirmed SweLoc pool (Q7). Renames and forks can only be resolved for short lists (unauthenticated GitHub API,
60 requests per hour; Q22). CORE-Bench corpora are streamed, not stored; evaluation by unit needs checkouts (Q21).

## Open questions

| # | Question | Blocks | Resolve by |
|---|---|---|---|
| Q1 | Which team member is Person A / B / C (owners in `docs/ROADMAP.md`)? | ownership columns | engineer, week 1 |
| Q3 | Does a docs-only commit need a fresh latency row, or may it reference the previous row? | commit hook design | engineer, before the latency harness closes |
| Q4 | GitHub remote(s) for the team repo; the engineer performs every push | publishing only | engineer |
| Q5 | ADR-001...ADR-010 (training pool, quality signal, graph role, granularity, benchmark, encoder, scaffold, LLM, rerank, usable-by-others) | frozen config, RQ2 start | team, end of week 2 |
| Q7 | SweLoc: master doc says released; no dataset by that name exists. Candidate `gangiswag/train_data` (no card; 56,279 instance directories, Python 24,285 / 2,448 repository directories; function-level; `repo` in metadata). Read in full (R1): the SweRank+ paper's Table 1 gives exactly 24,285 PRs, 2,448 repositories and 49,973 function-level instances for Python and 56,279 PRs overall, so the candidate is SweLocMulti's Python part (the directories are PRs, not instances), and that paper states no exclusion of benchmark repositories loses 14.1% of its Python instances (3,431) and 3.6% of its repositories (89) to the held-out list. Is it the intended pool, or is the pool built with the published scripts? Also Loc-Bench: 560 rows (V1) vs 660 (V0.2), category counts differ from the master doc | ADR-001, pool filter | engineer; options and evidence in `decisions/ADR-001` addenda |
| Q8 | Fork / near-duplicate rule for the held-out list. Measured: exact names miss renamed repositories (19 of 59 same-name candidates in two pools now resolve to a held-out repository, for example `pycqa/pylint` to `pylint-dev/pylint`; CodeSearchNet 1,603 rows, candidate 54 instances), and 0 of 59 are forks. Options: exact names only / plus current-name resolution / plus fork network / plus same-name proxy. No recommendation in the master doc | held-out list, pool filters | engineer |
| Q9 | Is Loc-Bench held out of training? 128 of its 165 (V1) repositories are not in the held-out list; the others overlap Verified (django, sympy, sklearn, ...). Effect on pools is in the ADR-005 addendum | ADR-005 | engineer |
| Q11 | CORE-Bench chunk ids are random UUIDs with no path or line span; chunks are text windows (mean about 1,000 characters, longest 1,009,865, so not capped at 4,096); each query scores against its own `filtered_corpus_id` list (mean about 9,800 ids in L2, 11,400 in L3, minimum 32, maximum 348,310) rather than the whole folder corpus. Read and measured (R1): the paper says the filter keeps the documents visible at the PR state, and on 11 Verified instances all 12,153 list chunks occur in the checkout at the base commit (`results/tables/r1_c1_snapshot_check.json`), so each list is the snapshot and evaluation is whole-snapshot retrieval; the folder corpus is the union of snapshots. Chunk-to-CodeUnit mapping and the matching evaluation protocol need a decision | CodeUnit, ADR-004, evaluation | engineer |
| Q12 | CORE-Bench L3 labels are LLM-judged (paper, three-vote ensemble); L2 labels are chunk-vs-patch alignment (a sample of 53 L2 positives was 50 code chunks, 3 import blocks; whether positives are the edited code is untested). The paper does not say how the three Level-3 judge votes combine into the kept score (R1); released qrels are binary | RQ3 interpretation | note in report |
| Q13 | CodeUnit Q1: what do `calls` / `called_by` / `tests` / `configs` hold? Options: unit ids / qualified names / paths. Proposal: unit ids (unresolved targets dropped and counted in edge-recovery coverage); `configs` = repo-relative file paths | parser, graph | engineer, freeze |
| Q14 | CodeUnit Q2: `repo_id` form. Options: `owner/name` / `owner/name@commit` / folder name (unusable: truncated, Q10). Proposal: `owner/name` (compare case-folded), commit kept in the index manifest | held-out filter | engineer, freeze |
| Q15 | CodeUnit Q3: nested defs, lambdas, properties, decorators, class attributes. Flask at the flask-5014 base commit: 513 nested defs, 613 decorated, 16 property-like, 24 lambdas, 114 class attributes, `Flask` class 2,124 lines. Proposal: top-level functions, classes, methods only (nested folded into the parent, decorators in the span, lambdas and class attributes never units); class `source` (full vs header-only) is unresolved | parser, ADR-004 | engineer, freeze |
| Q16 | CodeUnit Q4: chunk link (ADR-004). Of 160 sampled L2/L3 positives (3 Verified repos), 111 overlap one function/method, 28 overlap 2+, 5 only a class, 16 no definition (module-level), 39 cut a unit at the window edge. Options: `chunk_id` field / derived mapping table / chunk-level only. Proposal: derived table built by the evaluation loader at the instance base commit, schema unchanged; module-level code needs an ADR-004 answer (a new unit type would change the schema) | evaluation, ADR-004 | engineer, freeze |
| Q17 | CodeUnit Q5: `last_modified`. Options: last-touching commit time / mtime / empty / snapshot time. Proposal: commit time (ISO-8601 UTC) when full history exists, else `""`; never mtime (breaks byte-identity) | reproducibility | engineer, freeze |
| Q18 | CodeUnit Q6: `is_test`. Options: path rule / name rule / framework markers. Proposal: file-level path rule (component `tests` or `test`, or `test_*.py`, `*_test.py`, `conftest.py`); `examples/` is not test | parser | engineer, freeze |
| Q19 | CodeUnit Q7: `tests` filled at parse time or by the graph extension? Proposal: graph extension (weeks 7-10); `[]` until then, and empty does not mean untested | graph | engineer, freeze |
| Q20 | CodeUnit Q8: `id` format. Options: `file::Qual.name` / `file:Qual.name` / both with a mapping. Proposal: `::` as in the master example, repo-relative posix path, deterministic `#<start_line>` suffix only on same-name collisions (the suffix rule is part of the question) | everything | engineer, freeze |
| Q21 | CORE-Bench evaluation by unit needs the checkout at each instance base commit; base commits were available only for Verified instances (SWE-bench parquet), unknown for the other sub-datasets. Which sub-datasets enter the evaluation? | evaluation, Q11 | engineer |
| Q22 | Resolving renames and forks (Q8) at scale needs authenticated GitHub access (the unauthenticated limit of 60 requests per hour allowed 59 lookups). Should an access token be provided on Ada (never stored in the repository), and should the held-out repositories themselves be checked for renames (CORE-Bench ids carry the name at collection time)? | Q8 | engineer |
| Q23 | Rewrite qrels are not identical to the originals: 81 Rewrite SWE-bench_Multilingual folders have no qrels file and 13 other folders have fewer rows (158 in all), although the card says Rewrite shares qrels with the originals. Score Rewrite runs against the original qrels (same query ids in every folder) or the Rewrite ones? | Rewrite evaluation | engineer |
| Q24 | Master-document statement "tests and configuration are covered by nobody" no longer holds as worded. Read in full (R2): LARGER builds tested_by, documents and configures links with fixed confidences 0.75, 0.6, 0.5 (Table 11, p.19) and appends related tests, documentation and configuration files to search output; it reports no ablation of those links and its alignment study runs with test files dropped (p.17), so there is no published evidence either way that they help. Options: keep the claim reworded as "no ablation shows the value of test and configuration links", or drop it. Not edited in the derived docs | graph design, `docs/05`, report wording | engineer |
| Q25 | Corrections to master-document numbers about the graph papers, found by reading: KGCompass multi-hop share is 89.7% of 146 ground-truth functions in v3 (69.7% was v1; 67.3% is the share of Lite issues with no named file or function); LocAgent Loc-Bench is 560 = 242 / 150 / 29 / 139 in v2 (660 is v1) and its ablation is Table 6; SpIDER gain is "at least 13% relative over the same encoder's dense list" (12.9% was v1); LARGER says LocBench has 5 repositories, which its own Figure 4(b) contradicts (165 measured). Derived docs not edited; decide whether to log in `docs/DEVIATIONS.md` | `docs/05`, `docs/06`, references | engineer |

Resolved this block: Q10 (folder counts 632 / 97 are 605 / 92 distinct repositories, read from instance ids; L3 inside L2; Verified inside both;
17 L2 and 2 L3 folders hold several repositories; see `data/held_out/report.md`). Earlier: Q2 (Ada reaches HF and GitHub), Q6 (24 GB free; L2+L3 originals 17.0 GB).

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
