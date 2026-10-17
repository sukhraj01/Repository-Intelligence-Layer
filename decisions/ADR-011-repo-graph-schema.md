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
None yet; the latency harness is not built. Stage names to register: `parse`, `graph_build`,
`graph_expand_1hop`, `graph_expand_2hop`, `mentions_extract`.

## References
See `docs/GRAPH_DESIGN.md`.

## Conditions to revisit
- The first graph build shows that few call sites resolve in the repository (the projections are nearly
  empty), or the exploratory precision of `tests` or `configures` is low.
- Storage measurements show the leading option exceeding the memory ceiling at the largest repository.
- ADR-003 settles a role that needs a field the schema lacks.
- A paper read later reports edge-type ablations on a fused retriever or a measured resolution rate.

## Addenda
