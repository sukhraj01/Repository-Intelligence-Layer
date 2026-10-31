# docs/ — index and reading order

The design is split from the Master Project Document by topic so a reader can load **only what
the task at hand needs**. This page says what each file is and when to read it.

| File | What it holds | Read when |
|---|---|---|
| `01_project_overview.md` | Identity table; system vs experiment | orienting a new contributor |
| `02_research_questions.md` | RQ1–RQ3, wording that must not drift, killed claims, the approved sentence | writing anything that states a claim |
| `03_literature_map.md` | Every bearing paper: what it established, why we are not it | defending novelty; related work |
| `04_data_and_ground_truth.md` | Datasets by stage, mining recipe, repo-level disjointness, label caveats | anything touching data |
| `05_structural_signals.md` | LocAgent schema, KGCompass, our test/config extension, graph-role fork | parser, call graph, structural signal |
| `06_core_bench.md` | Levels, the L1→L2 cliff, four findings, what it does not measure | evaluation; framing |
| `07_latency_and_profiling.md` | Professor's requirements, expected time distribution, profiling correctness | bench harness; any perf work |
| `08_experimental_design.md` | What "budget" means, 4 arms, held-identical block, statistics, threats, null-result reading | training, evaluation, RQ3 |
| `09_architecture.md` | CodeUnit, offline indexing, online retrieval, defaults, package layout | any implementation |
| `10_timeline_and_fallback.md` | 16-week plan, week-12 go/no-go, milestones, the pitch | planning; progress reviews |
| `11_references.md` | Corrected citations and links | writing the report |
| `12_open_decisions.md` | The 10 open decisions + week-1 deliverables, as written in the master | closing decisions |
| `ARCHITECTURE.md` | **Live** component design: interfaces, assumptions, limitations, changelog | changing any component boundary |
| `ROADMAP.md` | **Live** checkbox plan by week and owner (owners are named at the top) | planning; tick as work lands |
| `EXPERIMENTS.md` | **Live** experiment registry: rules, index of all entries, the lead's entries | planning or running an experiment |
| `experiments/A.md`, `experiments/C.md` | experiment logs of workstreams A and C (append-only, one writer each) | reading or adding an entry of that workstream |
| `DEVIATIONS.md` | **Live** departures from the master doc, DEV-001 onward, with rationale | before departing from the design |
| `REVIEW.md` | **Live** review standard: checks on every branch, the flag rules and their limits, re-deriving a number, proxies, hand-back and verdict | reviewing or handing back a branch |
| `GRAPH_DESIGN.md` | **Live** options, evidence and costs for the knowledge graph (does not choose) | graph schema, storage, roles |
| `COMPUTE.md` | Local box and Ada: environment, quotas, inherited lessons, job log | before any cluster or data work |
| `status/` | **Live** one status page per workstream (`status/person_a.md`), replaced at the end of each block | picking up or reviewing a workstream |
| `source/MASTER_PROJECT_DOCUMENT.md` | Verbatim copy of the whole master doc | only if a topic file is ambiguous |

## Documents outside `docs/`

| Where | What it holds |
|---|---|
| `../PROJECT_STATE.md` | what is true now, the next task, open questions |
| `../RESULTS.md` | every benchmark, one line each, append-only |
| `../results/ledger_a.md` | workstream A's result rows in the `RESULTS.md` format (one `ledger_*` file per workstream); merged into `RESULTS.md` by the maintainer |
| `../results/README.md` | what each directory under `results/` holds |
| `../decisions/` | ADR-001 to ADR-013 with their addenda; index in `decisions/README.md` |
| `../specs/` | acceptance contracts (`code_unit.md`, `held_out_repos.md`, `latency_harness.md`, `parse_one_repo.md`, `repo_graph.md`); index in `specs/README.md` |
| `../knowledge/` | paper notes (`knowledge/papers/`, with `LANDSCAPE.md`) and dataset cards (`knowledge/datasets/`) |
| `../configs/` | frozen, demo, bench and per-experiment configurations; `configs/README.md` |
| `../data/README.md` | what is tracked (`data/held_out/`) and what is rebuilt on the cluster |

## Two kinds of document

- **Derived copies (`01`–`12`, `source/`)** are generated from the master doc. Do not edit them to
  record progress. If one is wrong or stale, the *master* is wrong — record an Open question in
  `PROJECT_STATE.md` and the team fixes the master, then re-syncs.
  Exception (decision D14, 2026-10-18; DEV-010): where the master is factually wrong about an
  identifier or a figure, the copy is corrected in place with the inline marker "(corrected, see
  DEV-0nn)", and `DEVIATIONS.md` keeps the evidence. A re-sync must keep those corrections until the
  master carries them.
- **Live documents (`ARCHITECTURE`, `ROADMAP`, `EXPERIMENTS`, `DEVIATIONS`, `GRAPH_DESIGN`, `COMPUTE`,
  `status/`)** are owned by this repo and updated as work happens. They may depart from the master
  where measurement or a decision requires it; every departure is a `DEVIATIONS.md` entry.

## Re-syncing from the master

The master document lives outside this repository. Copies here were taken from **rev 16
(2026-10-11)**. When the master changes, re-split it, diff the result against these files, and note
what changed in the commit message.

## Reading order

Read two files carefully rather than twelve badly: start from `PROJECT_STATE.md`, then only the
topic files the task touches (table above).
