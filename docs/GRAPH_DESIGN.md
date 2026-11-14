# Knowledge-graph design: evidence, roles, options

Status: working design document for `specs/repo_graph.md` (DRAFT v0) and ADR-011. **It records options,
evidence and costs. It does not choose.** The graph's role is ADR-003; the graph's schema, edge
taxonomy and storage are ADR-011; how edge recovery is defined and reported is ADR-012.

Evidence labels: **read in full** (a note in `knowledge/papers/`, value `paper_reported`), **measured**
(a project run with a log), **reasoned** (no source, no run). Nothing below is **measured** unless it
says so. The first graphs were built on 2026-10-17 (flask, requests, django; ADR-011 and ADR-012 addenda) and the
sections written before that date still describe the options as they stood then. Page numbers are PDF pages of the version named in
each note.

## 1. Why a separate, versioned graph

The CodeUnit is frozen (v1) and carries four relation lists that hold resolved ids only (D4). Import,
inherit, contain, co-change and mention relations do not fit four lists, and the papers read disagree
about which relations carry signal (section 5), so the edge set must be able to change without touching
the unit type. The graph is therefore its own artifact with its own version constant, keyed by the
CodeUnit ids (D11), built per repository snapshot (D5). Every edge has a status so that "the resolver
found nothing" (`unresolved`) is never confused with "the target is outside the repository"
(`external`), and so that no resolution failure disappears from the counts.

## 2. What the papers did with graphs (read in full)

| Paper (note) | Graph role | Edge types used | Edge types ablated | Resolution measured | Latency |
|---|---|---|---|---|---|
| LocAgent (`locagent-2503.09089.md`) | agent tool: type-aware BFS plus BM25 entity search (Sec. 3.1-3.2, pp.4-6) | contain, import, invoke, inherit | only contain against all four (Table 6, p.9) | no | cost and rounds only (Table 5, p.9) |
| KGCompass (`kgcompass-2503.21710.md`) | signal: distance-decayed score picks 15 candidates; entity paths in the prompt (Sec. 3, pp.4-8) | containment, call, import, attribute reference; issue and PR mention links | no (graph on/off, entity path on/off; Tables 5-6, pp.15-16) | no | dollars and tokens (Table 3, p.12) |
| LARGER (`larger-2605.16352.md`) | signal inside an agent's search output (Sec. 4, pp.4-7) | contains, imports, invokes, inheritance; cross-artifact tests, documentation, configuration (Table 11, p.19) | no; components only (Table 3, p.9) | no; confidences fixed by provenance | seconds per instance including the LLM (Table 6, p.15); update ms (App. D.1, p.17) |
| SpIDER (`spider-2512.16956.md`) | signal added to a dense list under a fixed budget, with an LLM filter (Sec. 4.2, pp.5-6) | contains (default), invokes, imports, inherits tested | yes, one family at a time, one benchmark, single run (Table 3, p.8) | no; locality statistics of the ground truth (Table 6, p.30) | stated 5-10 s per query against under 1 s dense (A.14, pp.27-28) |
| GREPO (`grepo-2602.13921.md`) | learned: GNN reranker over anchors (Sec. 4-5, pp.3-8) | contain, call, inherit, previous/next version | yes, one at a time, single run (Table 4, p.8) | no; unresolved dropped, ambiguous all linked (App. A.1, A.3, pp.11, 15) | none for inference |
| ARISE (`arise-2605.03117.md`) | agent tool: navigation plus data-flow slice (Sec. 3, pp.4-5) | contains, imports, calls, inherits, definition-use; no test or configuration | tool tiers, not edge types (Tables 2-3, pp.7-8) | no; dynamic dispatch dropped by policy (Sec. 3.2, p.4) | build 1.7 s to 33 min per repository (Sec. 5.3, p.10) |
| CoSIL (`cosil-2503.22424.md`) | agent tool, LLM-built graphs, no index (Sec. II-B, pp.3-4) | import (module graph); invoke and inherit (function graph) | whole graphs, not edge types (Table IV, p.8) | no; edges are LLM output | tokens and dollars (Table VII, p.9) |
| GraphLocator (`graphlocator-2512.22469.md`) | agent tool over a layered graph, lazy dependency edges (Sec. 2.1, pp.4-5) | HasMember, ImportedBy, ExtendedBy, ImplementedBy, UsedBy | tools, not edges | no | tokens |
| SemNav (`semnav-2609.31176.md`) | agent tool plus retrieval-time neighbour bonus; edges resolved on demand by a language server | explicit resolved and unresolved edges (p.3) | online resolution on/off: -7.00 points File Hit@10 (p.6) | not as a rate | tokens only (Figure 3c, p.7) |

Reading across the table (evidence: read in full; the synthesis is inference):

- Two of the nine ablate edge types (SpIDER, GREPO); none measures how many edges its resolver gets
  right or misses; none reports a latency percentile for the graph step. The first project number in
  each of these columns would be new.
- Roles in the nine: five agent tools (LocAgent, ARISE, CoSIL, GraphLocator, SemNav), three signals
  or list expanders (KGCompass, LARGER, SpIDER), one learned (GREPO) (`LANDSCAPE.md`, "What the scan
  found", item 1).
- Resolution policies differ: drop dynamic dispatch (ARISE), drop unresolved and link all ambiguous
  (GREPO), let a language server resolve online (SemNav), let an LLM propose edges (CoSIL). The
  four-status record keeps enough information for a reader to apply any of these later.
- Backbone and benchmark dependence is large: ARISE's published-system rows score very differently under
  its backbone than in their own papers (`arise-2605.03117.md`, Relation to RQs), and CoSIL's
  function Top-1 gain of 0.230 gave no resolved-rate gain in one end-to-end comparison (94 against 96 of
  300; `cosil-2503.22424.md`, Table IX, p.10).

## 3. Edge families: evidence matrix

Full per-family cards (derivation, resolver, failure modes, leakage, cost) are in `specs/repo_graph.md`.
This matrix is the evidence only.

| Family | Ablated anywhere? | Strongest published number (paper_reported) | What no source shows |
|---|---|---|---|
| contain | LocAgent (all vs contain-only), GREPO (removed), SpIDER (alone) | LocAgent function Acc@10 66.42 contain-only against 66.06 without traversal and 71.53 full (Table 6, p.9); GREPO Hit@20 41.25 to 37.47 without contain (Table 4, p.8); SpIDER Python Recall@20 0.49 against dense 0.42 (Table 2, p.8) | which part of containment (directory, file, class) matters; effect on a fused retriever |
| import | CoSIL (module graph removed), SpIDER (alone) | CoSIL function Top-1 0.433 to 0.383 without the module graph (Table IV, p.8); SpIDER imports alone 0.44 (Table 3, p.8) | effect isolated from the LLM that builds the CoSIL graph |
| invoke | SpIDER (alone), GREPO (removed) | SpIDER Python invokes 0.56 against contains 0.49 and both 0.60 (Table 3, p.8); GREPO Hit@20 41.25 to 40.80 without call edges (Table 4, p.8) | effect at a given resolution coverage; cost without an LLM filter |
| inherit | GREPO (removed), SpIDER (alone) | GREPO Hit@20 41.25 to 40.30 (Table 4, p.8); SpIDER inherits alone 0.42, equal to dense (Tables 2-3, p.8) | whether the effect exists in a schema where inherit edges touch functions |
| override | none | none; no note lists it | everything |
| tests | no | LARGER uses a 0.75 confidence link (Table 11, p.19); no ablation | whether the link helps |
| configures | no | LARGER 0.5 (Table 11, p.19); no ablation | whether the link helps |
| documents | no | LARGER 0.6 (Table 11, p.19); documentation files missed in 73% of cases in one repository study (`exploration-structure-2606.11976.md`, Table 5, p.14) | whether the link helps |
| co_change | no | none measured; GREPO temporal anchors (a learned history prior): Hit@1 14.80 to 8.09 without (Table 4, p.8), with the candidate-source caveat | any measured effect of file-pair co-change |
| mentions | no | KGCompass: 32.7% of instances name a ground-truth file or function (Table 4, p.13) | effect of mention links in isolation |

Consequence for the project (inference): a project edge-type ablation on a fused retriever with latency
columns would not duplicate any of these (the LARGER note states the same for tests, documentation and
configuration links). The master statement that tests and configuration are "covered by nobody" does not
survive as worded (LARGER links them); the statement "no ablation shows the value of those links" does
(Q24).

## 4. Three roles of the graph

The roles are not exclusive in principle but they differ in what they change: A changes the candidate
list at query time, B changes the training data, C changes the agent. Each is a different experiment
and a different latency profile. Which one is in the frozen configuration is ADR-003.

### Role A: retrieval-time signal

- **Forms.** (i) Hop-decay score `gamma^dist` from the seed units, fused with BM25 and dense by rank
  fusion (master design, gamma about 0.5); (ii) personalised PageRank seeded at the query's top units;
  (iii) SpIDER-style expansion from the top-C dense centres to depth d, keeping neighbours that fall
  inside a larger dense list, replacing the lowest-ranked non-centre entries so the budget stays fixed
  (`spider-2512.16956.md`, Sec. 4.2, pp.5-6; Proposition 4.1, p.6: recall changes by admitted hits minus
  displaced hits over the number of edited functions, so it rises only if admitted precision exceeds the
  relevance of what is displaced).
- **Experiment that would show its value.** Pilot E3 (exploratory, planned) on BM25 seeds, then dense
  (E6): seeds alone against seeds plus expansion, with each edge family alone, leave-one-out and all;
  C in {1, 3, 5}, gamma in {0.3, 0.5, 0.7}, 1 or 2 hops; metrics delta nDCG@10 at L2 and delta Recall@100
  at L3; paired bootstrap intervals; a size-matched random expansion as chance control (a dense graph
  can look good by reaching everything); sweeps on non-Verified repositories, one pre-stated setting
  confirmed on Verified. In RQ1 form: `E-RQ1-DENSE-STRUCT` and `E-RQ1-ALL` (`docs/EXPERIMENTS.md`) with
  nDCG per millisecond.
- **Latency profile.** Per query, batch size 1, on the interactive path: seed lookup, adjacency read
  (1 hop, 2 hop), score computation, fusion. Registered stage names: `graph_expand_1hop`,
  `graph_expand_2hop`. No project number yet; the cost scales with degree, and containment makes
  module and class nodes hubs (siblings at 2 hops are 30% of Verified ground-truth function pairs,
  `spider-2512.16956.md`, A.3, pp.18-19), so a neighbour cap and p99 are the quantities to watch. The
  published expansion that reports a latency is the one with an LLM filter (stated 5-10 s against under
  1 s dense, A.14, pp.27-28); a filter-free expansion has no published latency.
- **Schema needs.** See the roles table in `specs/repo_graph.md`.
- **Constraint to resolve.** The experimental design holds the fusion rule fixed (rank-based RRF). A
  hop-decay *score* does not enter RRF directly; it must become a ranked list, or the expansion must
  edit the candidate list (Q-G2).

### Role B: training-time structure

- **Forms.** (i) Structural hard negatives: callers, callees, siblings and same-file units of the
  positive, instead of or besides negatives mined from a retriever's top list (SweRank mines hard
  negatives from the top M = 15 by a pretrained embedder after a consistency filter at K = 20;
  `swerank-2505.07849.md`, Sec. 3.3, pp.4-5); (ii) L3-style positives: units reached from the labelled
  positives through `tests` and `configures` edges, mimicking the broader context labels of CORE-Bench
  Level 3, which are produced by an agent's file opens judged by three votes (`core-bench-2606.11864.md`,
  Sec. 3.2.3, p.5; Algorithm 1, p.14); (iii) weights from graph distance (a soft analogue of FILTER and
  WEIGHT).
- **Precedent.** None found: the literature scan's query 10 (retrievers trained with graph-based or
  structural hard negatives) returned nothing beyond SweRank, CoRNStack and SpIDER (`LANDSCAPE.md`,
  search log #10). This is an absence in a limited search, not proof.
- **Experiments that would show its value.** Planned pilots that wait for the training stack:
  `E-PILOT-NEG` (random repository-local against teacher-mined against graph-structural negatives) and
  `E-PILOT-L3POS` (graph-derived test and configuration positives added to training), at tiny budget,
  reported with intervals and labelled exploratory; precondition: pilot M's measure of how many L3
  positives are tests or configuration, and how many are reachable by which edge families.
- **Latency profile.** None online: the encoder at inference is unchanged, so the query path carries no
  graph step unless role A is also used. Offline throughput is the quantity: graph build in units per
  second per repository and neighbour-sampling cost per training sample (samples per second). Not
  measured.
- **Risks to the experimental design (reasoned).** (a) False negatives: callers and siblings of a
  positive may be relevant; the literature on false negatives is for text retrieval (`rlhn-2505.16967.md`,
  `rethinking-negative-pairs-2310.08069.md`). (b) RQ2 varies supervision only: a graph-derived
  supervision source is itself a supervision change, so whether it is an additional arm, a component
  of every arm, or out of scope is a design decision (Q-G1). (c) Leakage: training graphs come from
  pool repositories at their instance base commits, and the repository-level disjointness test and the
  quality-signal-encoder test apply; a graph statistic fitted on held-out repositories must not be
  reused (`specs/repo_graph.md`, `co_change` card).
- **Schema needs.** Graphs for many (repository, commit) pairs, which makes the per-commit against
  validity-range question (Q-G10) a training question as much as a storage one.

### Role C: agent tool

- **Form.** LocAgent-style tools: entity search, type-aware traversal with hop limit and relation
  filter, entity retrieval (`locagent-2503.09089.md`, Sec. 3.2, p.6), exposed to the fixed agent as an
  RQ3 integration variant.
- **Experiment that would show its value.** RQ3 paired design with the scaffold and model held fixed
  (ADR-007, ADR-008): condition 1 retrieved list in context; condition 2 retrieved list plus graph tool;
  McNemar test with intervals; repeated runs per condition because run-to-run variation is large (CoSIL:
  86 against 96 resolved of 300 for the same pipeline, `cosil-2503.22424.md`, Table IX, p.10; ARISE: the
  4.7-point gain is 14 instances, one attempt, `arise-2605.03117.md`, Sec. 4.2, p.6). Precedents are
  small: LocAgent's graph traversal is worth 5.47 function points on top of search (Table 6, p.9), with
  all ablation cells single runs.
- **Latency profile.** Dominated by LLM rounds, not by graph lookups: LocAgent reports 6 rounds and
  0.05 dollars per instance for the 7B model and 9 rounds and 0.09 for the 32B (`locagent-2503.09089.md`,
  Table 5, p.9). A traversal call is a local lookup; the quantity that matters is resolved rate per
  agent wall-clock (`docs/experiments/B.md`, E-RQ3-AGENT), which the harness would attribute per tool
  call. Not measured.
- **Constraint (reasoned).** RQ3 holds the agent fixed and varies the retriever. A graph *tool* changes
  the agent's action space, so it is a different comparison from RQ3 as written; as a variant it needs
  its own label. Whether this variant is in scope at all is part of ADR-003.
- **Schema needs.** Name lookup, BFS with type filters, text rendering of a subgraph, status visible in
  the output.

## 5. Where the papers disagree: contain edges

| Source | Setting | Contain result (paper_reported) |
|---|---|---|
| LocAgent | fine-tuned 7B agent with BM25 entity search; 274 instances; one run | contain-only ties no traversal: function Acc@10 66.42 against 66.06 (full 71.53); "marginal" in the paper's words (`locagent-2503.09089.md`, Table 6, p.9; Sec. 5.6, p.10). Traversal as a whole is worth 5.47 points |
| SpIDER | dense seeds, LLM filter; Recall@20 | containment alone raises Recall@20 over the same dense list by 0.05 to 0.12; on Python 0.49 against 0.42; invoke alone is better (0.56) and costs about eight times the tokens (109.9K against 12.9K) (`spider-2512.16956.md`, Table 2-3, p.8) |
| GREPO | trained GNN reranker over anchors | removing contain edges is the largest edge-type drop: Hit@20 41.25 to 37.47; removing call edges 40.80 (`grepo-2602.13921.md`, Table 4, p.8) |

None of the three is a controlled test of the question "does containment carry signal when the seeds
are lexical or dense retrieval, without an LLM". The difference in the first two is explainable by what
supplies the seeds (inference, `spider-2512.16956.md` Discrepancies): in LocAgent the agent already
finds the neighbourhood by search; in SpIDER the seed list is dense and containment adds recall for
functions beyond the list.

**The ablation that would settle it here** (pilot E3, exploratory, planned):

1. Seeds: top-C units of BM25 (and later of a dense retriever on the same units). Budget: the expanded
   list has the same length as the seed list (SpIDER's fixed-budget rule), so that admission displaces.
2. Arms: seeds alone; each of directory-to-file, file-to-definition, class-to-method (the three
   parts of containment), invoke, import, inherit alone; leave-one-out from the full set; all; and a
   size-matched random expansion of the same units (chance control: same candidate counts, same
   files, then the whole repository).
3. Metrics: delta nDCG@10 at L2, delta Recall@100 at L3, per repository and pooled; paired bootstrap
   95% intervals; statement of what the unit-level qrels mapping lets this say (pilot M).
4. Tuning discipline: sweeps on non-Verified repositories; Verified only for one pre-stated setting.
5. Reading: if containment beats chance and equals the other families, the LocAgent number is a
   property of the agent; if containment equals chance, SpIDER's gain is the filter and the larger
   candidate pool, not the edges. Both outcomes are informative; none changes a decision by itself.

## 6. Resolution status and what is known about recovery

The record keeps the four statuses (`resolved`, `ambiguous`, `unresolved`, `external`) per site so
that the coverage table is a count, not an opinion. Recovery as a single percentage depends on the
definition, and the literature uses incompatible ones (read in full):

| Source | Ground truth | Edge scope | Reported |
|---|---|---|---|
| PyCG (`pycg-2103.00587.md`) | hand-built, five packages under 3.5k lines | external and module-level callers included | precision 99.2%, recall 69.9% (Table IV, p.9) |
| Jarvis (`jarvis-2305.05949.md`) | test traces plus manual additions, six applications | application functions and reachable library callees | 0.99 / 0.82 application-only; 0.35 / 0.60 application-centred with dependencies (Table V, p.10) |
| DyPyBench (`dypybench-2403.00539.md`) | executed edges of the test suites, 39 projects | all callees including builtin methods | 49% of dynamic edges in PyCG's graph; 92% of the missing edges miss the callee (Sec. 4.1.2, pp.11-12) |
| Total Recall (`total-recall-helm-2024.md`) | executed edges from fixed entry points (Java) | whole graph or core package | test-based baselines can mis-state precision and recall in either direction |

The master document's "expect 70-85% edge recovery" is not supported as a general figure by any of
them (`LANDSCAPE.md`, claims checked). Consequences for the graph design: the status of each site is
recorded so that the in-repository share, the external share and the unrecovered share can each be
reported; the graph build measures them on flask, requests and django before any number is quoted;
ADR-012 holds the competing definitions. Every result that uses the graph reports the coverage next to
it, so that a weak structural signal can be read against it.

No confidence scores are assigned. LARGER's fixed confidences (Table 11, p.19) and KGCompass's
per-hop decay of 0.6 (Eq. 1, p.5) are unmeasured hand settings. Hypothesis to test, not a design: a
per-family weight estimated from measured reach or precision (pilot E4, cross-repository: fitted on some
repositories, evaluated on others).

## 7. Leakage rules, collected

1. Every graph used for an evaluation instance is built from the repository at that instance's base
   commit and from nothing newer: no file, test, configuration, documentation or history reachable only
   after the fixing change.
2. `co_change` uses commits that are ancestors of the snapshot commit, chosen by ancestry and not by
   date.
3. `mentions` and any stored issue or pull-request node use only text available at the instance's creation
   time; nothing from the patch or the linked change.
4. Training graphs come from pool repositories only, at their own instance base commits; the
   repository-level disjointness test applies to every graph-derived statistic that is fitted and
   later evaluated (weights, thresholds, support counts).
5. A quality-signal encoder is never the encoder being trained; graph-derived supervision does not
   change that rule.
6. No edge is derived from the gold positives or from qrels.

## 8. Storage options and the measurement plan

Options (S1 to S7) are listed in `specs/repo_graph.md`. The first graph build measures, for each, on
flask, requests and django at their Verified base commits: build time; load time; peak resident memory
and size on disk; 1-hop and 2-hop expansion latency p50/p95/p99, warm and cold, batch size 1; incremental
update time for one changed file; byte-identical output on rerun; and an extrapolation to the largest
repository from the measured per-unit numbers. Hardware spec is recorded; numbers are not compared
across machines. The local box has 8 GB RAM and no GPU; anything near its ceiling goes to the cluster.
Reference scale (paper_reported, other systems, not predictions): median 134,000 nodes and 313,000
edges per repository including statement nodes (`arise-2605.03117.md`, Sec. 5.3, p.10); a Django
snapshot of 2,750 files and 27,867 functions (`kgcompass-2503.21710.md`, Sec. 4.1, p.8); LARGER's
incremental update of tens of milliseconds against a rebuild of minutes (`larger-2605.16352.md`,
App. D.1, p.17).

## 9. Questions the engineer must close for ADR-003

Each is a design question; none is answered here. They come with the nearest evidence.

**Evidence status after the graph-role measurement of 2026-10-29 (`docs/EXPERIMENTS.md` E-GRAPH-ROLE; ADR-003 addendum of the same date; measured, exploratory).**
Role A (retrieval-time signal): evidence for same-file expansion of the best first-stage units (L3 Recall@100 +6.5 to +7.7 on Verified-six, +11.3 to +13.2 on dev); **no evidence that edges add to it**
(stored graph minus score-ordered same-file expansion: -2.7 [-6.0, 0.8] and -2.0 [-5.2, 0.8] at Verified-six L3; non-contain-only 6 to 7 points below same-file; containment edges never leave their file).
Role B (training-time structure): no evidence. Role C (agent tool): no evidence. Flip experiment for A: stacked same-file plus non-contain-neighbour expansion at equal budget over dev, Verified-six and the
Pro ansible repository (ADR-003). Questions 1 and 2 below stay open for the engineer; the measurement bears on them as stated here.

1. **Which role or roles are in the frozen configuration** (A, B, C, or a combination), and which is
   only a demonstration feature. Evidence: section 4; no paper compares roles on one benchmark.
2. **How a graph signal enters a rank-fused stack.** The design fixes rank-based fusion. A hop-decay
   score has to become a ranked list, or the expansion edits the candidate list (SpIDER). The
   exchange identity (Proposition 4.1, p.6) says when an edited list loses.
3. **Whether graph-derived supervision (role B) is inside RQ2 or outside it.** RQ2 varies supervision
   strategy at matched optimisation budgets; a structural negative source is a supervision change.
4. **Whether the agent-tool variant (role C) belongs to RQ3**, which holds the agent fixed, or is a
   separate study.
5. **Status policy for a signal:** use resolved edges only (the CodeUnit projections), or also
   ambiguous edges split across their candidates, or all; this changes the signal's reach.
6. **Which edge families are in the first stored graph and which stay exploratory** until their
   precision is sampled (tests, configures, documents, co_change).
7. **What latency budget the graph step may use** relative to the pipeline's stages (set when the
   harness exists; the stage names are registered, the thresholds are not).
8. **Which recovery definition(s) are reported** (Q27, ADR-012).
9. **Scope of the claim.** Python only; the graph's absolute effect is not an agent-capability claim.

## 10. What is not known (open at the end of this design)

- Resolution coverage of any resolver on library-style repositories, in-repository only (no source).
- Precision of name-convention `tests` edges, `configures` edges, `documents` edges (no source).
- Any effect of `co_change` on retrieval (no measurement found).
- Whether containment carries signal over a lexical or dense seed list without an LLM (section 5).
- The latency of the graph step at p50/p95/p99 on any storage option.
- The share of L3 positives reachable through each edge family from the L2 positives, with the chance
  control (pilot M).

The first graph build and pilots M and E3 produce the first project numbers for these.
