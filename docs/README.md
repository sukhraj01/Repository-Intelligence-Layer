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
| `ROADMAP.md` | **Live** checkbox plan by week and owner | planning; tick as work lands |
| `EXPERIMENTS.md` | **Live** experiment registry: IDs, protocol, status | planning or running an experiment |
| `DEVIATIONS.md` | **Live** departures from the master doc, with rationale | before departing from the design |
| `COMPUTE.md` | Local box and Ada: environment, quotas, inherited lessons | before any cluster or data work |
| `source/MASTER_PROJECT_DOCUMENT.md` | Verbatim copy of the whole master doc | only if a topic file is ambiguous |

## Two kinds of document

- **Derived copies (`01`–`12`, `source/`)** are generated from the master doc. Do not edit them to
  record progress. If one is wrong or stale, the *master* is wrong — record an Open question in
  `PROJECT_STATE.md` and the team fixes the master, then re-syncs.
- **Live documents (`ARCHITECTURE`, `ROADMAP`, `EXPERIMENTS`, `DEVIATIONS`, `COMPUTE`)** are
  owned by this repo and updated as work happens.

## Re-syncing from the master

The master document lives outside this repository. Copies here were taken from **rev 16
(2026-10-11)**. When the master changes, re-split it, diff the result against these files, and note
what changed in the commit message.

## Reading order

Read two files carefully rather than twelve badly: start from `PROJECT_STATE.md`, then only the
topic files the task touches (table above).
