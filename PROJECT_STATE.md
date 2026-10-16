# Project State

> **Current truth only.** Not a history. History lives in `RESULTS.md` and the git log.
> **Hard cap: 200 lines.** If this file exceeds it, the fix is to *delete resolved content*,
> not to add a summary. See the maintenance rule at the bottom.

**Last updated:** 2026-10-12 · **Milestone:** M0 — scaffold only · **Tasks completed:** 0

---

## One-line status

Research design is locked (Master Project Document rev 16, 2026-10-11) and the repository scaffold
exists. **No code has been written.** Week 1 starts with the repository bootstrap (`docs/ROADMAP.md`).

## What is built

| Layer | State | Notes |
|---|---|---|
| Repo scaffold: folders, docs split from master, ADR stubs, specs | done | |
| Python package (`ril/`), `pyproject.toml`, `Makefile`, hooks | not started | `docs/ROADMAP.md` week 1 |
| CodeUnit schema (frozen) | not started | `specs/code_unit.md` is a draft of the master doc's schema; needs engineer sign-off |
| Held-out repository list | not started | `specs/held_out_repos.md`, needs Ada |
| Latency harness | **not built** | `specs/latency_harness.md`; commits are exempt from the latency rule until it exists |
| Parser / call graph / BM25 / dense / fusion / assemble | not started | |
| Training pipeline, supervision arms | not started | |
| Evaluation (CORE-Bench loaders, metrics), agent integration | not started | |

## Next task

Bootstrap the Python package: skeleton, `pyproject.toml`, `Makefile`, lint/test tooling and a
commit-hook stub — no research code. Then, in order: CodeUnit schema (`specs/code_unit.md`),
held-out repositories (`specs/held_out_repos.md`), latency harness (`specs/latency_harness.md`),
parse one real repository (`specs/parse_one_repo.md`), evidence for ADR-001…010 (`decisions/`).

## Blockers

None.

## Open questions

| # | Question | Blocks | Resolve by |
|---|---|---|---|
| Q1 | Which team member is Person A / B / C (owners in `docs/ROADMAP.md`)? | ownership columns | engineer, week 1 |
| Q2 | Can Ada's compute nodes reach Hugging Face / GitHub, and at what throughput? Drives how CORE-Bench and SweLoc are fetched | held-out repo job | probe from Ada while building the held-out list |
| Q3 | Does a docs-only commit need a fresh latency row, or may it reference the previous row? The professor said "before every commit" | commit hook design | engineer, before the latency harness closes |
| Q4 | GitHub remote(s) for the team repo. The engineer supplies them and performs every push; until then the repo has no remote | publishing only | engineer |
| Q5 | ADR-001…ADR-010 (training pool, quality signal, graph role, granularity, benchmark, encoder, scaffold, LLM, rerank, usable-by-others) | frozen config, RQ2 start | team, end of week 2 |
| Q6 | Disk budget on Ada for CORE-Bench L2/L3 corpora (9.4M + 2.6M chunks; the data card lists 32.2 GB for the whole package) vs `$HOME` quota | held-out repo job | measure on Ada before fetching |
| Q7 | Drift from the master doc: it lists SweLoc as released, but no public dataset release was found (collection scripts only; see ADR-001 addendum). Is SweLoc obtainable, or is the pool built with the published scripts? Also: Loc-Bench is 560 rows in `Loc-Bench_V1`, 660 in `Loc-Bench_V0.2` | ADR-001, pool filter | engineer; confirm in the ground-truth audit |

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
