# Project State

> **Current truth only.** Not a history. History lives in `RESULTS.md` and the git log.
> **Hard cap: 200 lines.** If this file exceeds it, the fix is to *delete resolved content*,
> not to add a summary. See the maintenance rule at the bottom.

**Last updated:** 2026-10-17 · **Milestone:** M0 — empty package bootstrapped; data sources located and sampled · **Tasks completed:** 3

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
| Data access and formats (CORE-Bench, Verified, Loc-Bench, SweLoc search, CoRNStack/CSN schemas) | done | `knowledge/datasets/*.md`, `results/tables/`, `scripts/ada/README.md`; Ada reachable non-interactively |
| Held-out repository list, filter, leakage tests | not started | needs canonical repo names per CORE-Bench folder (folder names are truncated) |
| Latency harness | **not built** | `make bench` / `make bench-check` print "latency harness: not built" |
| Parser / call graph / BM25 / dense / fusion / assemble | not started | |
| Training pipeline, supervision arms | not started | |
| Evaluation (CORE-Bench loaders, metrics), agent integration | not started | |

## Next task

Engineer: close Q13-Q20 and freeze the CodeUnit (set the spec status, bump the version, write the ADR). Then: held-out repository list, filter and leakage tests (`specs/held_out_repos.md`, steps 3-5 of the held-out brief), then the
latency harness, then parsing one repository. Start from `knowledge/datasets/core_bench.md`: derive owner/name per CORE-Bench
folder from the query ids (stream `queries.jsonl` heads on Ada; folder names are truncated), not from folder names.

## Blockers

None for code. Data: the CORE-Bench corpora beyond the nine sample folders are not on Ada (commands in `scripts/ada/README.md`);
no confirmed SweLoc pool (Q7).

## Open questions

| # | Question | Blocks | Resolve by |
|---|---|---|---|
| Q1 | Which team member is Person A / B / C (owners in `docs/ROADMAP.md`)? | ownership columns | engineer, week 1 |
| Q3 | Does a docs-only commit need a fresh latency row, or may it reference the previous row? | commit hook design | engineer, before the latency harness closes |
| Q4 | GitHub remote(s) for the team repo; the engineer performs every push | publishing only | engineer |
| Q5 | ADR-001...ADR-010 (training pool, quality signal, graph role, granularity, benchmark, encoder, scaffold, LLM, rerank, usable-by-others) | frozen config, RQ2 start | team, end of week 2 |
| Q7 | SweLoc: master doc says released; no dataset by that name exists. Candidate `gangiswag/train_data` (no card; 56,279 instances, Python 24,285 / 2,448 repo dirs; function-level; `repo` in metadata). Is it the intended pool, or is the pool built with the published scripts? Also Loc-Bench: 560 rows (V1) vs 660 (V0.2), category counts differ from the master doc | ADR-001, pool filter | engineer; options and evidence in `decisions/ADR-001` addendum |
| Q8 | Fork / near-duplicate rule for the held-out list (report both, do not choose) | held-out list | engineer |
| Q9 | Is Loc-Bench held out of training? Its repos overlap Verified repos (django, sympy, sklearn, ...) | ADR-005 | engineer |
| Q10 | The "repos" figures 632 / 97 are folder counts; 154 folder names are truncated (`pylint`, `scikit`, `django` holding `django-helpdesk`). Distinct canonical repositories are unknown until query ids are read; two repositories may share one folder | held-out list | measure on Ada (next task) |
| Q11 | CORE-Bench chunk ids are random UUIDs with no path or line span, chunks are 4,096-char text windows, and each query scores against its own `filtered_corpus_id` candidate list (19k-25k ids for django) rather than the whole folder corpus. Chunk-to-CodeUnit mapping and the matching evaluation protocol need a decision | CodeUnit, ADR-004, evaluation | engineer |
| Q12 | CORE-Bench L3 labels are LLM-judged (paper); L2 labels are chunk-vs-patch alignment | RQ3 interpretation | note in report |
| Q13 | CodeUnit Q1: what do `calls` / `called_by` / `tests` / `configs` hold? Options: unit ids / qualified names / paths. Proposal: unit ids (unresolved targets dropped and counted in edge-recovery coverage); `configs` = repo-relative file paths | parser, graph | engineer, freeze |
| Q14 | CodeUnit Q2: `repo_id` form. Options: `owner/name` / `owner/name@commit` / folder name (unusable: truncated, Q10). Proposal: `owner/name` (compare case-folded), commit kept in the index manifest | held-out filter | engineer, freeze |
| Q15 | CodeUnit Q3: nested defs, lambdas, properties, decorators, class attributes. Flask at the flask-5014 base commit: 513 nested defs, 613 decorated, 16 property-like, 24 lambdas, 114 class attributes, `Flask` class 2,124 lines. Proposal: top-level functions, classes, methods only (nested folded into the parent, decorators in the span, lambdas and class attributes never units); class `source` (full vs header-only) is unresolved | parser, ADR-004 | engineer, freeze |
| Q16 | CodeUnit Q4: chunk link (ADR-004). Of 160 sampled L2/L3 positives (3 Verified repos), 111 overlap one function/method, 28 overlap 2+, 5 only a class, 16 no definition (module-level), 39 cut a unit at the window edge. Options: `chunk_id` field / derived mapping table / chunk-level only. Proposal: derived table built by the evaluation loader at the instance base commit, schema unchanged; module-level code needs an ADR-004 answer (a new unit type would change the schema) | evaluation, ADR-004 | engineer, freeze |
| Q17 | CodeUnit Q5: `last_modified`. Options: last-touching commit time / mtime / empty / snapshot time. Proposal: commit time (ISO-8601 UTC) when full history exists, else `""`; never mtime (breaks byte-identity) | reproducibility | engineer, freeze |
| Q18 | CodeUnit Q6: `is_test`. Options: path rule / name rule / framework markers. Proposal: file-level path rule (component `tests` or `test`, or `test_*.py`, `*_test.py`, `conftest.py`); `examples/` is not test | parser | engineer, freeze |
| Q19 | CodeUnit Q7: `tests` filled at parse time or by the graph extension? Proposal: graph extension (weeks 7-10); `[]` until then, and empty does not mean untested | graph | engineer, freeze |
| Q20 | CodeUnit Q8: `id` format. Options: `file::Qual.name` / `file:Qual.name` / both with a mapping. Proposal: `::` as in the master example, repo-relative posix path, deterministic `#<start_line>` suffix only on same-name collisions (the suffix rule is part of the question) | everything | engineer, freeze |
| Q21 | CORE-Bench evaluation by unit needs the checkout at each instance base commit; base commits were available only for Verified instances (SWE-bench parquet), unknown for the other sub-datasets. Which sub-datasets enter the evaluation? | evaluation, Q11 | engineer |

Resolved this block: Q2 (Ada reaches HF and GitHub; 6.5 to 8.9 MB/s on a 50 MB range request, see `docs/COMPUTE.md`), Q6 (home has
24 GB free; L2+L3 originals 17.0 GB, whole repository 32.2 GB).

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
