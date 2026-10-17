# ADR-011: RepoGraph schema, edge taxonomy and storage

- **Status:** Proposed — **not decided**. This ADR lists options, evidence and costs. No option is chosen.
- **Date:** 2026-10-17
- **Decided by:** _pending — engineer / team_
- **Related:** `specs/repo_graph.md` (DRAFT v0), `docs/GRAPH_DESIGN.md`, ADR-003 (graph role), ADR-012
  (edge-recovery definitions, planned), ADR-013 (CodeUnit v1, decision D4), ADR-004 (granularity),
  `docs/05_structural_signals.md`

## Context
Decision D4 (`specs/code_unit.md`) fixed that relations live in a separate typed edge store and that
the CodeUnit lists hold resolved ids only, as projections. What the store holds, how an edge records its
own reliability, which relations exist at all, and how the store is kept are not fixed. The papers read
disagree about which relations carry signal and none measures edge accuracy or reports graph-step latency
percentiles (`docs/GRAPH_DESIGN.md`, sections 2 and 3). The first parse and graph build needs a schema to
write against, but nothing in the schema should rule out any of the three roles under ADR-003.

## Alternatives considered
Each question below has its options in `specs/repo_graph.md`; the summary:

1. **Node kinds.** directory, file (the module unit, settled by D6), class, function/method, test (flag or
   kind), config artifact, document, and query-time issue and pull-request nodes. Options concern
   directories as documents, test as a flag or a kind, which files are configuration and documents, and
   section-level documents (Q-G3 to Q-G6).
2. **Edge families.** contain, import, invoke, inherit, override; tests, configures, documents;
   co_change (history at or before the snapshot commit); mentions (query time only). Options per family:
   derivation, resolver, granularity (file or unit for co_change), and whether a family is in the first
   stored artifact or exploratory (Q-G13, Q-G14).
3. **Edge record.** Required: type, src, dst, status in {resolved, ambiguous, unresolved, external},
   derivation, candidate set for ambiguous. Optional: site, target_text, count (Q-G7). No confidence
   scores in this version.
4. **Status boundary.** `external` against `unresolved` for names that resolve to nothing (Q-G8).
5. **Snapshots.** One graph per (repository, commit), or one graph with validity ranges (GREPO), or an
   incremental update of a stored graph (LARGER) (Q-G10).
6. **Storage.** S1 Parquet edge list with in-memory adjacency; S2 SQLite with in-memory cache; S3
   `networkx`; S4 `rustworkx` or another compiled library; S5 a graph database (KGCompass); S6 per-file
   sidecars with incremental update (LARGER); S7 canonical JSONL as interchange. Likely a combination of
   an interchange format and a read-side structure.
7. **Resolver per family.** Own `ast` resolver; assignment-graph points-to (PyCG); language-server
   resolution (SemNav); type-inference library (GREPO); LLM-proposed edges (CoSIL); combinations with
   the resolver recorded in `derivation` (Q-G13).

## Decision
_Pending._ Work that cannot wait proceeds behind a config flag marked `provisional: ADR-011` and never
enters `configs/frozen/`.

## Rationale
_Pending._ Inputs available now: `docs/GRAPH_DESIGN.md` (evidence matrix, roles, the contain-edge
disagreement and its settling ablation, leakage rules, storage measurement plan).

## Trade-offs
Recorded per option in the spec. The ones that cut across: a richer schema (more families, optional
fields, per-commit graphs) costs build time, storage and review effort and may never be used by the
chosen role; a smaller schema is cheaper but a missing family is a rebuild and a version bump after the
first index exists. A graph that keeps `ambiguous` and `unresolved` sites costs space and shows the
coverage honestly; dropping them (as ARISE and GREPO do) is smaller and hides the number that
explains a weak structural signal.

## Evidence class and the experiment that could change it
- **Evidence class.** Per claim, in `docs/GRAPH_DESIGN.md`: the paper results are *read in full*
  (notes in `knowledge/papers/`, each cited with a page); the cost and failure-mode statements for
  this project's own resolver and storage are *reasoned only*; nothing is *measured here* yet.
- **Cheapest experiments that could settle the open points**, each with its time-box:
  1. First parse and graph build on flask, requests and django: per-status counts per family (settles
     whether the projections are non-empty, hence D4, and gives the coverage table); inside that build.
  2. Exploratory samples of `tests`, `configures` and `co_change` edges (n >= 50 each, precision by
     reading the source; `co_change` counts for N in {2, 3, 5}); inside that build.
  3. Storage measurements S1 to S7 (build, load, peak memory, size, 1- and 2-hop expansion p50/p95/p99,
     update, determinism); inside that build, one afternoon of work after the graph exists.
  4. Pilot M (reach of L3 positives from L2 positives by edge subset, with a random-set control) and
     pilot E3 (edge-family ablation on a BM25 seed list with chance control): the settling experiments
     for the contain-edge disagreement and for which families deserve to be in the first artifact.
  5. Pilot E4 (data-fitted edge weights, cross-repository) tests the hypothesis that hand-set
     confidences can be replaced by measured ones.

## Evidence
`knowledge/papers/` notes: `locagent-2503.09089.md`, `kgcompass-2503.21710.md`, `larger-2605.16352.md`,
`spider-2512.16956.md`, `grepo-2602.13921.md`, `arise-2605.03117.md`, `cosil-2503.22424.md`,
`graphlocator-2512.22469.md`, `semnav-2609.31176.md`, `pycg-2103.00587.md`, `jarvis-2305.05949.md`,
`dypybench-2403.00539.md`, `total-recall-helm-2024.md`, `exploration-structure-2606.11976.md`,
`LANDSCAPE.md`. All read in full except where the scan lists a paper as abstract only.

## Related benchmarks
The first measurements are in the 2026-10-17 addendum (stages `parse`, `graph_build`, `graph_expand_1hop` and
`graph_expand_2hop`, through the latency harness). `mentions_extract` is not registered yet.

## References
See `docs/GRAPH_DESIGN.md`.

## Conditions to revisit
- The first graph build shows that few call sites resolve in the repository (the projections are nearly
  empty), or the exploratory precision of `tests` or `configures` is low.
- Storage measurements show the leading option exceeding the memory ceiling at the largest repository.
- ADR-003 settles a role that needs a field the schema lacks.
- A paper read later reports edge-type ablations on a fused retriever or a measured resolution rate.

## Addenda

### 2026-10-17 — First graph build: counts and storage measurements (no option chosen)

Evidence class: measured here (flask at the pallets__flask-5014 base commit, requests at psf__requests-6028, django at
django__django-16145; seed 0; resolver `own-ast-resolver/v0`; build config hashes in `configs/experiments/p_graph_first_build.yaml`).
Machines: the laptop (Apple M3, 8 GB, Python 3.11.14) and Ada (gnode002, Python 3.10.12, 128 GB node; jobs 25550 and others in
`docs/COMPUTE.md`). Numbers from the two machines are never merged. Logs: `results/logs/p_stats_*`, `p_graph_measure_*`;
tables: `results/tables/p_graph_status_counts.csv`, `p_graph_rule_counts.csv`, `p_storage_measurements.csv`,
`p_extrapolation.csv`; latency and throughput rows in `results/latency/*_log.csv` (query-set ids `graph-<repo>-<backend>-v1`, 200
queries of three seed units each in `configs/bench/query_sets/graph-<repo>-v1.txt`, batch size 1, warmup 5, 3 passes).

**What the first graph holds.** Units: flask 974 (80 module units), requests 678 (35), django 35,860 (2,751). Edges per family
(all statuses): flask 5,749, requests 3,775, django 224,155; the per-status table is in the CSV. Resolved `invoke` edges project to
`calls` lists that are non-empty for 45.6%, 66.4% and 62.0% of the non-module units (the D4 flip condition is not met).
Every `invoke` edge stores `site` and `target_text` (Q-G7 option "store all"; `provisional: ADR-011`); the unit-set hash is in the
metadata (Q-G11, `provisional: ADR-011`); `contain` edges are stored (Q-G9) and number about one per unit.

**Build cost** (laptop / Ada; one process, history pass included, peak resident memory of the build process):

| Repository | parse s | graph build s | history s | build peak RSS MB | artifacts on disk MB |
|---|---|---|---|---|---|
| flask | 0.10 / 0.23 | 0.20 / 0.65 | 0.09 / 0.11 | 55 / 48 | 3.1 |
| requests | 0.06 / 0.18 | 0.12 / 0.41 | 0.09 / 0.10 | 53 / 46 | 2.1 |
| django | 3.58 / 11.56 | 7.32 / 22.45 | 1.71 / 1.63 | 592 / 648 | 145.4 |

The graph artifacts (units, nodes, edges, metadata) are canonical JSONL: 3.1 MB (flask), 2.1 MB (requests), 145 MB (django, of which
`units.jsonl` carries the sources). History is one `git log --name-only` pass. Peak memory of the build process at django scale is
592 MB on the laptop and 648 MB on Ada, far below the 8 GB ceiling, so the django build fits the local box, as the pre-run
estimate said.

**Extrapolation from the two small repositories** (`results/tables/p_extrapolation.csv`; the estimate written down before the
django run is `results/logs/p_django_prediction_2026-10-17.json`): a two-point line through flask and requests against source lines
predicted a django build of 197.7 MB, 1.6 s parse, 4.5 s graph build and 0.6 s history; measured on the laptop 591.5 MB, 3.6 s, 7.3 s
and 1.7 s (1.6 to 3.0 times larger). Against units the line is better for time (0.8 times for parse and graph build) and still low for
memory (1.8 times). Two points fit badly; the order of magnitude and the conclusion (it fits locally) held.

**Expansion and storage, django** (200 queries of three seed units; the mean number of units reached within 1 and 2 hops is 19.7 and
434.9; warm rows, batch size 1, stages `graph_expand_1hop` and `graph_expand_2hop`; peak RSS from `VmHWM` of the query process on Ada
and from `ru_maxrss` on the laptop, including the interpreter and the library).

**Ada (gnode002, Xeon E5-2640 v4, Python 3.10.12)**

| Option | write s | size MB | load s | peak RSS after load / after queries MB | 1-hop p50 / p95 / p99 ms | 2-hop p50 / p95 / p99 ms | 2-hop cold p95 ms |
|---|---|---|---|---|---|---|---|
| S7 canonical JSONL + dict adjacency | 6.55 | 81.37 | 1.147 | 92 / 92 | 0.073 / 0.091 / 0.112 | 0.151 / 0.312 / 0.424 | 0.338 |
| S5 embedded graph database (kuzu) | 1.91 | 15.41 | 0.124 | 254 / 411 | 31.610 / 33.008 / 35.107 | 34.693 / 40.450 / 45.714 | 36.739 |
| S3 networkx | 0.36 | 10.83 | 0.244 | 97 / 97 | 0.076 / 0.097 / 0.111 | 0.167 / 0.375 / 0.470 | 0.416 |
| S1 Parquet + CSR arrays | 0.80 | 2.92 | 0.194 | 223 / 223 | 0.082 / 0.106 / 0.123 | 0.223 / 0.511 / 0.693 | 0.535 |
| S4 rustworkx | 0.42 | 10.83 | 0.156 | 71 / 71 | 0.083 / 0.110 / 0.127 | 0.233 / 0.544 / 0.764 | 0.567 |
| S6 per-file JSON sidecars | 8.74 | 76.72 | 1.586 | 92 / 92 | 0.091 / 0.102 / 0.116 | 0.151 / 0.324 / 0.455 | 0.452 |
| S2 SQLite, queried directly | 2.77 | 92.75 | 0.000 | 33 / 37 | 0.810 / 0.968 / 1.114 | 5.103 / 14.263 / 24.960 | 14.359 |
| S2 SQLite + in-memory adjacency | 2.70 | 92.75 | 0.418 | 102 / 102 | 0.073 / 0.088 / 0.111 | 0.146 / 0.292 / 0.394 | 0.310 |

**Laptop (Apple M3, Python 3.11.14)**

| Option | write s | size MB | load s | peak RSS after load / after queries MB | 1-hop p50 / p95 / p99 ms | 2-hop p50 / p95 / p99 ms | 2-hop cold p95 ms |
|---|---|---|---|---|---|---|---|
| S7 canonical JSONL + dict adjacency | 2.00 | 81.37 | 0.388 | 88 / 88 | 0.022 / 0.025 / 0.030 | 0.052 / 0.114 / 0.162 | 0.145 |
| S5 embedded graph database (kuzu) | 0.57 | 15.41 | 0.010 | 64 / 136 | 4.101 / 4.230 / 4.561 | 4.596 / 5.854 / 6.504 | 7.537 |
| S3 networkx | 0.11 | 10.83 | 0.088 | 93 / 94 | 0.024 / 0.027 / 0.033 | 0.057 / 0.135 / 0.176 | 0.161 |
| S1 Parquet + CSR arrays | 0.43 | 2.92 | 0.089 | 178 / 178 | 0.024 / 0.030 / 0.036 | 0.078 / 0.191 / 0.270 | 0.210 |
| S4 rustworkx | 0.19 | 10.83 | 0.053 | 69 / 70 | 0.026 / 0.034 / 0.047 | 0.088 / 0.229 / 0.319 | 0.261 |
| S6 per-file JSON sidecars | 2.58 | 76.72 | 0.314 | 90 / 90 | 0.022 / 0.025 / 0.029 | 0.053 / 0.116 / 0.164 | 0.148 |
| S2 SQLite, queried directly | 0.67 | 92.75 | 0.000 | 30 / 33 | 0.196 / 0.243 / 0.304 | 1.368 / 3.851 / 6.334 | 3.953 |
| S2 SQLite + in-memory adjacency | 0.73 | 92.75 | 0.153 | 98 / 98 | 0.022 / 0.025 / 0.029 | 0.052 / 0.113 / 0.162 | 0.141 |

flask and requests show the same ordering at smaller scale (`results/tables/p_storage_measurements.csv`: all three repositories,
both machines, warm and cold, p50/p95/p99). Cold rows reset the stage's own caches only (a SQLite connection or a database handle is
reopened per call); the in-memory options have nothing to reset, so their cold and warm rows agree.

**Incremental update of one file** (option S6: re-parse and re-resolve one file against the other files' unchanged summaries and
rewrite its sidecar; 30 files sampled with seed 0; p50 / p95 / p99 ms): laptop flask 1.0 / 11.1 / 38.0, requests 1.3 / 15.9 / 72.9,
django 0.5 / 14.4 / 31.0; Ada flask 5.0 / 41.6 / 137, requests 5.7 / 57.4 / 274, django 2.6 / 41.1 / 98.4. For scale, a full django
build takes 11 to 23 s. The measurement does not rebuild the files that import the changed one, so it is a lower bound for a real
incremental update (LARGER reports medians of 53 to 81 ms for its own, larger, update; `paper_reported`, `larger-2605.16352.md`).

**Determinism.** All six artifact files of every repository are byte-identical on rerun, on both machines. Across the two machines
(Python 3.11 and 3.10) the flask and requests files are byte-identical and django differs in 4 of 224,155 edge lines, because
`ast.unparse` writes `lambda :` in 3.10 and `lambda:` in 3.11 inside `target_text`.

**Reading, without a choice.** Every option that keeps the adjacency in memory answers a 2-hop expansion in well under a millisecond
at django scale; they differ in load time (0.16 to 1.6 s on Ada, the database 0.12 s), file size (2.9 MB for Parquet to 81 MB for JSONL) and resident
memory (71 MB for rustworkx to 254 MB for the embedded database). SQLite queried directly has no load cost and the smallest footprint
but is 25 to 50 times slower at 2 hops, with a heavy tail (p99 25 ms on Ada). The embedded graph database is about two orders of
magnitude slower per query and the largest in memory; it offers query-language flexibility the others do not (relevant to role C in
`docs/GRAPH_DESIGN.md`). None of these numbers includes a candidate cap, edge-type filters or personalised ranking, which a role-A
signal would add to the expansion, and none decides the interchange format, per-commit graphs (Q-G10) or the graph's role. Q38 in
the project state lists what the engineer decides from here.

**Edge-family counts that bear on the schema** (`results/tables/p_graph_status_counts.csv`): `invoke` edges are one per call site and
make up about 70% of django's edges. Django: invoke 160,479 sites (63,010 resolved, 31,668 ambiguous, 6,733 unresolved, 59,068
external), import 16,817 (13,414 resolved, 3,403 external), inherit 6,841 (6,506 resolved), override 3,513, contain 36,505. The
exploratory families in django: `tests` 17,454 edges, `configures` 10 edges; `co_change` file pairs changed together in at least 2,
3 and 5 commits (cap 50 files per commit): 25,378, 11,519 and 4,130.
