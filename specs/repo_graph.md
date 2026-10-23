# Spec: RepoGraph (typed edge store)

**Status: DRAFT v0** (2026-10-17; `REPO_GRAPH_SCHEMA_VERSION = "v0-draft"`; ADR-011, Proposed).
This spec lists options, evidence and costs. **It makes no design choice.** Every place where a choice
is needed is marked **Open** and collected in "Open design questions". It evolves independently of the
CodeUnit: the CodeUnit is FROZEN v1 (`specs/code_unit.md`, ADR-013) and refers to the graph only
through the projections described under "Settled".

Reasoning, the per-paper evidence and the experiments that would settle the open points are in
`docs/GRAPH_DESIGN.md`. Papers are cited as `<note>, <table or section>, p.<pdf page>` where `<note>` is
a file in `knowledge/papers/`; every such value is `paper_reported`, never `measured`. Nothing in this
spec is a measurement of this project: the first graph build (`specs/parse_one_repo.md`) produces the
first ones.

## Purpose

A separately versioned store of typed relations between the entities of one repository snapshot:
directories, files, definitions, tests, configuration and documentation artifacts, and (at query time
only) the issue text. It serves three possible roles (retrieval-time signal, training-time structure,
agent tool; `docs/GRAPH_DESIGN.md`, "Three roles") and the choice among them is ADR-003, not this spec.
The spec's job is to make the store rich enough that no role is ruled out by the schema, while keeping
every edge honest about how it was obtained.

## Version constant and compatibility

- `REPO_GRAPH_SCHEMA_VERSION` is a string constant owned by the graph module, recorded with every graph
  artifact. It is bumped by this spec's change control, never by a CodeUnit change.
- A graph artifact also records the `CODEUNIT_SCHEMA_VERSION` of the units whose ids it uses, the
  `repo_id` (D5), the snapshot commit, and the resolver names and versions that produced its edges.
- **Open (Q-G11):** whether a unit-set hash is recorded so that a graph can be rejected when its units
  were rebuilt differently.

## Inputs and outputs

- **Input:** the CodeUnits of one repository at one snapshot commit (`specs/code_unit.md`), the file
  tree at that commit, and (for `co_change` only) the commit history reachable from that commit.
- **Output:** the typed edge store for that snapshot; the CodeUnit projections `calls`, `called_by`,
  `tests`, `configs` (resolved ids only); a per-status edge count table per edge family (so that
  resolution coverage is always reported next to any result that uses the graph).
- **Query-time overlay (not stored in the snapshot graph):** nodes and `mentions` edges for the issue
  text of one query (see "Node kinds").

## Settled (engineer's decisions of 2026-10-17, D4 to D11; not reopened here)

- Relations live in a separate typed edge store; `CodeUnit.calls`, `called_by`, `tests` hold resolved
  CodeUnit ids and `configs` holds repository-relative file paths, all as projections of this store
  (D4). Ambiguous and unresolved edges stay in the store with a status and are never dropped silently.
- Unit ids are the stable keys of code nodes (D11). `repo_id` is `owner/name`, case-folded; the
  snapshot commit lives in the container that holds the units and the graph, not in the unit (D5).
- The module unit (one residual `module` unit per file) is the file node of the graph (D6).
- `CodeUnit.tests` is filled by the graph build, not at parse time; `[]` means "not computed" (D10).
- `co_change` uses history at or before the snapshot commit only (brief; compatible with D8).
- Confidence scores are not assigned in this version (see "Edge record").

Readings made while writing this spec, to be confirmed by the engineer (Q-G12): the direction of the
`tests` projection (for a unit `u`, `tests(u)` is the set of test-unit ids with a resolved `tests`
edge to `u`) and that `configs(u)` is the set of paths of configuration artifacts with a resolved
`configures` edge to `u` or to the file of `u`.

## Node kinds

Code nodes reuse CodeUnit ids. Non-code nodes need ids of their own; the id forms below are
proposals, not decisions.

| Kind | What it is | Id | Source of the node | Notes and options (Open unless stated) |
|---|---|---|---|---|
| `directory` | a directory of the snapshot | repo-relative posix path with trailing `/` | file tree | used by LocAgent, SpIDER, GREPO, LARGER, ARISE (`locagent-2503.09089.md`, Sec. 3.1, p.4; `spider-2512.16956.md`, Sec. 4.1, p.4; `grepo-2602.13921.md`, Sec. 4.1, p.4; `larger-2605.16352.md`, Sec. 3, p.3; `arise-2605.03117.md`, Sec. 3.2, p.4). Whether directories carry any retrieval document is Open (Q-G3). |
| `file` | a Python file | the module unit's id (`path::<module>`, D6) | module unit | settled by D6; the file node is a unit, so a file is retrievable at unit level. SpIDER creates a file node only when the file holds a definition (`spider-2512.16956.md`, A.6, p.20); here every Python file has a module unit. |
| `class` | a class definition | CodeUnit id | `unit_type = class` | top-level classes only (D6); nested classes fold into their parent, so a nested class is not a node (consequence of D6, recorded in Q-G4). |
| `function` / `method` | a top-level function or a method | CodeUnit id | `unit_type = function` or `method` | nested functions fold into the parent (D6). Invokes from a nested function are attributed to the enclosing unit (Open, Q-G4). |
| `test` | test code | Option A: no separate kind; a code node with `is_test = true` (D9). Option B: a distinct kind `test` assigned by the graph build. | CodeUnit flag, or graph build | Open (Q-G5). Option A costs nothing and follows D9 (a file-level path rule that agrees with pytest collection on three repositories, `specs/code_unit.md` D9); option B lets a test unit be a node whose kind is derived from a naming or collection rule finer than the file. |
| `config` | a configuration artifact (`setup.py`, `setup.cfg`, `pyproject.toml`, `tox.ini`, `*.ini`, `*.yaml`, `*.yml`, `*.toml`, `MANIFEST.in`, CI files) | repo-relative path | file tree | non-Python artifacts have no CodeUnit, so they are artifact nodes. Which file names count is Open (Q-G6). `CodeUnit.configs` holds the same paths (D4). |
| `document` | a documentation artifact (`*.rst`, `*.md`, `*.txt` under `docs/` or the root) | repo-relative path | file tree | LARGER links documents (`larger-2605.16352.md`, Table 11, p.19); the CORE-Bench L3 judge sees non-code chunks (pilot M reports the kinds of L3 positives). Granularity (file or section) is Open (Q-G6). |
| `issue` | the text of the query | `query:<query_id>` | the benchmark row | **query-time only**, never stored in an index. |
| `pr` | a linked pull request | `query:<query_id>/pr:<n>` | benchmark metadata | **query-time only**. Prior issues and pull requests as stored nodes (KGCompass) are an option with a leakage rule (see the `mentions` card). |

Node attributes shared by all kinds: `id`, `kind`, `path` (empty for query-time nodes), `repo_id`. No
node carries a score.

## Edge record (all families)

Every edge carries the following fields. They are the minimum; further fields are listed as options.

| Field | Meaning | Required |
|---|---|---|
| `type` | one of the families below | yes |
| `src` | node id of the source | yes |
| `dst` | node id of the target when the status is `resolved`; otherwise see "Status" | yes |
| `status` | `resolved`, `ambiguous`, `unresolved` or `external` | yes |
| `derivation` | how the edge was obtained: resolver name and version, rule name, and the evidence kind (for example `ast-call`, `import-statement`, `name-convention`, `git-history`) | yes |
| `candidates` | for `ambiguous` edges, the full candidate set of node ids the resolver could not choose between, in a deterministic order | when `status = ambiguous` |
| `site` | file and line of the syntactic site that produced the edge (call site, import statement, mention span) | option (Q-G7) |
| `target_text` | the unresolved or external target as written (`self.helper`, `requests.get`) | option; needed for `unresolved` and `external` to be auditable (Q-G7) |
| `count` | number of syntactic sites collapsed into the edge | option (Q-G7) |

**Not in this version: confidence scores.** LARGER assigns fixed confidences by edge provenance by
hand (same-file 1.0, explicit import 0.95, resolved import 0.9, inheritance 0.9, test link 0.75,
documentation 0.6, configuration 0.5; `larger-2605.16352.md`, Table 11, p.19) and reports no ablation of
edge types and no measurement of edge accuracy (same note, "What it did not establish"). KGCompass
uses a decay `beta` = 0.6 per hop chosen by an unreported exploration (`kgcompass-2503.21710.md`, Eq. 1,
p.5; Sec. 4.3, p.9). These are hypotheses to test, not inputs: data-fitted edge weights are pilot E4
(planned), and any weight must be derived from measured reach or precision, never set by hand.

### Status

| Status | Definition | `dst` | Notes |
|---|---|---|---|
| `resolved` | the resolver mapped the site to exactly one node of the snapshot | that node | the only status that enters the CodeUnit projections (D4) |
| `ambiguous` | the resolver found two or more in-repository candidates and could not choose | empty | `candidates` holds the set. GREPO gives an edge to every candidate (`grepo-2602.13921.md`, App. A.3, p.15); ARISE drops the site (`arise-2605.03117.md`, Sec. 3.2, p.4). Here the site is kept as one edge with a candidate set, so either policy can be applied later by a reader. |
| `unresolved` | the site is expected to point inside the repository but no resolver rule produced a target (dynamic dispatch, `getattr`, decorator-wrapped call, unknown receiver type) | empty | counted as unrecovered in coverage reports. ARISE and GREPO drop these silently (`arise-2605.03117.md`, Sec. 3.2, p.4; `grepo-2602.13921.md`, App. A.1, p.11); here they stay visible. |
| `external` | the target is outside the repository: standard library, builtin, or a third-party distribution | empty | not "unrecovered". `target_text` or a qualified external name records the target. Builtin-type methods (for example `list.append`) are external; DyPyBench found 59% of the callees missing from PyCG's graph to be methods of builtin types (`dypybench-2403.00539.md`, Sec. 4.1.2, p.12). |

How the status is derived is part of the edge's `derivation`: it records the resolver and the rule
(for example "name resolved through the caller's import alias map; one in-repository match"). The
boundary between `unresolved` and `external` (a name that resolves to nothing may be an uninstalled
third-party dependency) is **Open (Q-G8)**: options are a standard-library name list plus the
declared requirements of the repository, an environment with the dependencies installed, or marking
the boundary case `unresolved` and reporting it separately.

Counting rule used by every coverage report: a coverage table lists, per edge family and per
repository, the number of sites in each of the four statuses. A share such as "recovered" is only ever
stated together with its definition (ADR-012 holds the competing definitions; none is chosen here).

## Edge families

Each card gives: what the edge means; how it can be derived (options); resolver; known failure modes;
who used it; leakage rules; cost. Costs are qualitative here: nothing is measured yet in this project.
Paper values are `paper_reported`.

### contain

- **Meaning.** Structural parent to child: directory to directory or file, file (module unit) to
  top-level definition, class to method.
- **Derivation.** From the file tree and the syntax tree. No resolution step; always `resolved`.
- **Failure modes.** Hub nodes: a module with hundreds of children makes every pair of its units two
  hops apart (SpIDER: two functions in one class are 2 hops apart, in different files 4 or more;
  `spider-2512.16956.md`, Sec. 4.2, p.5). On Verified, 30% of ground-truth function pairs are siblings
  at two hops (1,171 of 3,869) and 48% are cross-file at 6 or more containment hops (1,851 of 3,869;
  same note, A.3, pp.18-19). KGCompass's "multi-hop" counts mostly reflect file hubs (inference in
  `kgcompass-2503.21710.md`, Discrepancies).
- **Who used it.** LocAgent (all four types, contain-only ablation; `locagent-2503.09089.md`, Table 6,
  p.9), SpIDER (default and best-cost setting, depth 4; `spider-2512.16956.md`, Table 3, p.8), GREPO
  (ablated, `grepo-2602.13921.md`, Table 4, p.8), KGCompass, LARGER, ARISE, GraphLocator.
- **Leakage.** None beyond the snapshot rule: built from the base commit only.
- **Cost.** Linear in the number of units; the cheapest family. Edge count is about one per unit.
- **Open.** Whether directory-to-file and file-to-definition edges are one family or two (the
  ablation in "Where the papers disagree" can separate them), and whether `contain` is stored or
  derived on the fly from unit ids (Q-G9).

### import

- **Meaning.** A module imports a module or a definition. LocAgent: file to function or class
  (`locagent-2503.09089.md`, Sec. 3.1, p.4). CoSIL: module to module (`cosil-2503.22424.md`,
  Sec. II-B, pp.3-4).
- **Derivation.** `ast` `Import` and `ImportFrom` nodes; resolution against the file tree
  (absolute and relative imports, packages, `__init__` re-exports, `__all__`, star imports,
  conditional and function-level imports, `TYPE_CHECKING` blocks).
- **Resolver.** Options: own `ast` resolver; PyCG-style assignment graph (`pycg-2103.00587.md`,
  Sec. III, pp.3-7); a language-server resolver (SemNav uses go-to-definition on demand;
  `semnav-2609.31176.md`, Method details, p.3). Choice is Open (ADR-011, resolver per family).
- **Failure modes.** Dynamic imports (`importlib`, `__import__`) and `sys.path` manipulation are
  unresolved; third-party imports are `external`. In SpIDER's schema import edges touch function nodes
  only in Python and so "cannot surface new functions" (`spider-2512.16956.md`, Table 3 caption, p.8);
  the same note finds import edges add nothing (Python Recall@20 0.44 against 0.49 for containment,
  Table 3, p.8). That is a statement about SpIDER's schema; an import edge to the module unit is a
  different object.
- **Who used it.** LocAgent, KGCompass (`kgcompass-2503.21710.md`, Sec. 3.1, p.5), CoSIL (module graph;
  removing it lowers function Top-1 from 0.433 to 0.383 and file Top-1 from 0.613 to 0.540;
  `cosil-2503.22424.md`, Table IV, p.8), LARGER, ARISE, GraphLocator, SpIDER.
- **Leakage.** Snapshot only.
- **Cost.** One pass over import statements; resolution adds a file-tree lookup. Cheap relative to
  `invoke`.

### invoke

- **Meaning.** A definition calls or instantiates another definition (an invoke to a class is an
  instantiation; `locagent-2503.09089.md`, Sec. 3.1, p.4). Module-level calls have the module unit as
  caller (PyCG does the same; `pycg-2103.00587.md`, Method details, p.7).
- **Derivation.** Call sites from `ast`; the target is resolved by one of: lexical lookup in scope
  plus import alias map (ARISE keeps only unambiguous direct and qualified `module.function()` calls;
  `arise-2605.03117.md`, Sec. 3.2, p.4); an assignment-graph points-to analysis (PyCG); a type-inference
  library at each call site joined to definitions by (path, line), dropping builtin and external
  targets and giving an edge to every ambiguous candidate (GREPO; `grepo-2602.13921.md`, App. A.1 and
  A.3, pp.11, 15); a language server (SemNav); an LLM reading the node (CoSIL; edges never compared
  with an oracle, `cosil-2503.22424.md`, "What it did not establish"); a dynamic trace (oracle, not an
  indexing option: DyPyBench needed 215 minutes per project on average; `dypybench-2403.00539.md`,
  Sec. 4.1.2, p.10).
- **Failure modes.** `getattr`/`setattr`, `eval`, decorators, monkey patching, duck typing, methods of
  builtin types, functions stored in lists or dicts (PyCG limits, p.7; Jarvis residual false negatives,
  `jarvis-2305.05949.md`, Method details, p.9). Edge-recovery figures differ by definition and
  ground truth: PyCG precision 99.2% and recall 69.9% on five packages under 3.5k lines with a hand
  ground truth including external callees (`pycg-2103.00587.md`, Table IV, p.9); Jarvis 0.99 and 0.82 on
  an exhaustive application-only scenario, 0.35 and 0.60 application-centred with dependencies
  (`jarvis-2305.05949.md`, Table V, p.10); 49% of executed edges present in PyCG's graph on 39
  projects (`dypybench-2403.00539.md`, Sec. 4.1.2, p.11). They are not comparable; ADR-012 collects the
  definitions. No source reports in-repository-only recovery for library-style repositories.
- **Who used it.** LocAgent, KGCompass, CoSIL, SpIDER (best single edge family: Python Recall@20 0.56
  against 0.49 for containment, at 109.9K against 12.9K tokens per instance, a cost of the LLM filter;
  `spider-2512.16956.md`, Table 3, p.8), GREPO (removing call edges changes Hit@20 41.25 to 40.80;
  `grepo-2602.13921.md`, Table 4, p.8), LARGER, ARISE, GraphLocator, SemNav.
- **Leakage.** Snapshot only.
- **Cost.** The dominant graph-build cost in the papers that report one: ARISE reports 96% to 99% of
  build time in its data-flow pass (a statement-level pass this project does not plan;
  `arise-2605.03117.md`, Sec. 5.3, p.10); PyCG averages 0.77 s and 61.2 MB on five small packages
  (`pycg-2103.00587.md`, Table V, p.10). No figure exists for this project's resolver; the first graph
  build measures it for flask, requests and django.

### inherit

- **Meaning.** Class to base class.
- **Derivation.** Base-class expressions of `ClassDef`, resolved like names (import alias map, same
  module, qualified).
- **Failure modes.** Dynamic bases, `six.with_metaclass`, bases built by calls, aliases. Externally
  defined bases are `external`.
- **Who used it.** LocAgent, GREPO (removing inherit edges: Hit@20 41.25 to 40.30;
  `grepo-2602.13921.md`, Table 4, p.8), SpIDER (no gain, Python Recall@20 0.42 against dense 0.42;
  `spider-2512.16956.md`, Table 2 and Table 3, p.8), CoSIL, KGCompass (not stated), ARISE, LARGER.
- **Leakage.** Snapshot only.
- **Cost.** Negligible.

### override

- **Meaning.** A method overrides a method of a base class (method to method).
- **Derivation.** Not an independent observation: derived from `inherit` and method names, so its
  quality is bounded by `inherit`. Method resolution order for multiple inheritance (PyCG handles it;
  `pycg-2103.00587.md`, Sec. III, p.7).
- **Who used it.** None of the notes read lists `override` as a separate edge type (searched in the
  graph and call-graph notes); it is the project's own proposal. Value for dispatch: an `invoke` to a base method
  could be linked to its overriders, which is a way to expand `ambiguous` and `unresolved` virtual-call
  sites; this is a hypothesis, untested.
- **Leakage / cost.** Snapshot only; negligible once `inherit` exists.

### tests

- **Meaning.** A test unit exercises a unit under test.
- **Derivation options.** (a) name convention (`test_foo` to `foo`, `TestFoo` to `Foo`, test file
  `test_x.py` to module `x.py`); (b) static: the test body invokes the unit (needs `invoke`
  resolution, so it inherits that family's recall); (c) imports of the module under test from a test
  file; (d) dynamic: coverage contexts per test (needs the repository's dependencies installed and the
  tests run; DyPyBench: 215 minutes per project on average to collect dynamic call graphs;
  `dypybench-2403.00539.md`, Sec. 4.1.2, p.10). Choice is Open; D10 only fixes that the graph build
  fills `CodeUnit.tests`.
- **Failure modes.** Fixtures, parametrisation, shared helpers under `tests/` (the `is_test` rule flags
  helper modules that pytest does not collect from; `specs/code_unit.md` D9), tests that call a unit
  indirectly, names that do not follow convention.
- **Who used it.** LARGER (tested-by with confidence 0.75, `larger-2605.16352.md`, Table 11, p.19; no
  ablation of the link, Table 3, p.9; unclear whether the headline runs enable it, App. D.1, p.17).
  ARISE has no test relation (`arise-2605.03117.md`, Sec. 3.2, p.4). No other note records one.
- **Leakage.** The snapshot is the base commit, so tests added by the fixing change are absent, which
  is correct. A `tests` edge must never be derived from the patch. If the CORE-Bench L3 labels
  include test files (pilot M reports the share), `tests` edges give structural access to labelled
  material: that is the intended use, and also the reason the edge must be built from the snapshot
  alone.
- **Cost.** Static options are cheap given `invoke`; the dynamic option costs a test run per
  repository and an environment. Precision is measured by the exploratory sample in the first graph
  build (n >= 50, labelled exploratory).

### configures

- **Meaning.** A configuration artifact refers to a unit or a module (an entry point, a plugin
  registration, a settings module, a CI command).
- **Derivation options.** Module paths and `module:function` entry points named in `setup.py`,
  `setup.cfg`, `pyproject.toml`, `tox.ini`, `*.ini`, `*.yaml`; dotted names in strings; imports from
  `setup.py`.
- **Failure modes.** Names in strings resolve only by matching text to the file tree; many configuration
  files name no code at all; generated configuration.
- **Who used it.** LARGER (confidence 0.5; same caveats as `tests`; `larger-2605.16352.md`, Table 11,
  p.19). Not in the other notes.
- **Leakage.** Snapshot only; a configuration file changed by the fixing patch is read at the base
  commit.
- **Cost.** Cheap (text matching); precision unknown, measured by the exploratory sample.

### documents

- **Meaning.** A documentation artifact refers to a unit or module (a code identifier in prose, a
  directive such as `.. autofunction::`).
- **Derivation options.** Directive parse for rst; identifier matching for backticked names in md and
  rst; heading-to-module matching.
- **Failure modes.** Common words that are also identifiers (high ambiguity); versioned docs that
  describe a different commit.
- **Who used it.** LARGER (confidence 0.6; `larger-2605.16352.md`, Table 11, p.19). In the
  co-change literature scan, documentation files were the category missed most (73% for `docs/docsite/`
  gold files; `exploration-structure-2606.11976.md`, Table 5, p.14), which is a reason to consider the
  family and not evidence that it helps.
- **Leakage.** Snapshot only.
- **Cost.** Cheap; precision unknown.

### co_change

- **Meaning.** Two files (or two units) changed in the same commits more often than chance.
- **Derivation.** From `git log` of commits that are ancestors of the snapshot commit. File-pair counts
  with a minimum support N (pilot values N in {2, 3, 5}: counts only, no precision claim yet). Unit
  granularity needs line-level history (`git log -L` style) and is far more expensive; Open.
- **Failure modes.** Large refactor and merge commits create dense false couplings; squash merges hide
  structure; renames break path history (follow renames or not is Open); bots and formatting commits.
- **Who used it.** No note reports a co-change edge in a measured system. GREPO's temporal anchors come
  from a transformer over commit-history neighbours, trained on the training split, with a candidate
  source role (`grepo-2602.13921.md`, App. K, pp.34-36; removing them: Hit@1 14.80 to 8.09, Hit@20
  41.25 to 28.78, Table 4, p.8; the note warns the drop includes the loss of a candidate source).
  Exploration Structure proposes co-change and measures nothing (`exploration-structure-2606.11976.md`,
  Conclusion, p.18). The scan found no measurement of co-change for localization with language-model
  agents (`LANDSCAPE.md`, "Dead ends").
- **Leakage (critical).** Use only commits that are ancestors of the snapshot commit, selected by
  ancestry, not by timestamp (clock skew and rebased history make dates unreliable). The fixing change
  and everything after it must be unreachable. For training graphs the same rule applies per instance
  base commit. A co-change statistic fitted across repositories (for example a weight) must not be
  fitted on held-out repositories (`specs/held_out_repos.md`).
- **Cost.** One history traversal per repository; D8's per-file last-commit lookup is the same kind of
  query, and its cost on the largest repository is measured in the first parse build. Not measured yet.

### mentions

- **Meaning.** The issue text refers to an entity (file path, class, function, dotted name, error
  message string).
- **Derivation options.** Template or regular-expression extraction over issue text (KGCompass,
  `kgcompass-2503.21710.md`, Sec. 3.1, p.5); fuzzy name matching and dense search of rewritten queries
  (GREPO anchors, `grepo-2602.13921.md`, Sec. 4.3, p.5); LLM extraction of named functions (LocAgent
  difficulty analysis, App. C.1.2, p.16).
- **Query time only.** The edge belongs to the query overlay, not to the stored snapshot graph. The
  issue node is the origin of path scoring in KGCompass (`kgcompass-2503.21710.md`, Eq. 1, p.5).
- **Failure modes.** Many issues name no file or function: 67.3% of SWE-bench Lite instances name
  neither (`kgcompass-2503.21710.md`, Table 4, p.13), so `mentions` seeds exist for about a third of
  them; stack traces name frames, not causes.
- **Leakage.** The issue text is the query; nothing from the patch, the linked pull request's diff, or
  comments posted after the issue's creation time. If earlier issues and pull requests are stored as
  nodes (KGCompass), only artifacts older than the instance's `created_at` are kept (24.0% of mined
  artifacts were dropped by that filter; `kgcompass-2503.21710.md`, Sec. 3.1, p.5). GREPO restricts the
  input to the issue title and first message (`grepo-2602.13921.md`, Sec. 4.2, p.5).
- **Cost.** Per query, in the order of a text scan of the issue plus name lookups; part of the query
  path, so it carries a latency stage (`mentions_extract`, to be registered in the harness).

## Three roles and what each needs from the schema

The experiments, latency profiles and the evidence are in `docs/GRAPH_DESIGN.md`, "Three roles". The
schema needs are:

| Role | Needs from the store | Not needed |
|---|---|---|
| **A. retrieval-time signal** (hop decay, personalised PageRank, SpIDER-style expansion from top dense centres) | adjacency by unit id in both directions with per-type and per-status filters; hop distance; a way to cap neighbours per node (SpIDER caps invoke exploration at 100 neighbours per query, `spider-2512.16956.md`, Table 3 caption, p.8; LARGER caps 20 per file, `larger-2605.16352.md`, App. E.3, p.20); in-memory read path with no per-query disk access | edge text, `site`, source of non-code artifacts |
| **B. training-time structure** (structural hard negatives; L3-style positives from tests and configuration neighbours; weights from graph distance) | graphs for the pool repositories at each training instance's base commit (or a shared graph with validity ranges, Q-G10); neighbour sampling by type and distance; a guarantee that neighbours exist at the instance's commit; deterministic sampling given a seed | online latency; query-time overlay |
| **C. agent tool** (LocAgent-style traversal) | entity lookup by name and by id; type-aware BFS with hop limit and relation filters; rendering of a subgraph as text (tree format beat row, incident, DOT and JSON on 37 hard instances; `locagent-2503.09089.md`, Table 9, p.16); `ambiguous` and `unresolved` edges visible to the agent with their status (SemNav keeps explicit resolved and unresolved edges, `semnav-2609.31176.md`, Method details, p.3) | numeric scores; cached adjacency beyond one repository |

Common to all: stable node ids, one snapshot per graph artifact, deterministic serialization
(byte-identical on rerun for the same inputs and seed, as for the CodeUnit canonical form).

The questions the engineer must close in ADR-003 for the graph to be specified further are listed in
"Open design questions" (Q-G1, Q-G2) and in ADR-011.

## Storage options (to be measured in the first graph build; none chosen)

| Option | Description | Evidence |
|---|---|---|
| S1 | typed edge list in Parquet plus in-memory adjacency (CSR arrays) built at load | none in the papers; project-internal option |
| S2 | typed edge table in SQLite with indexes on (type, src) and (type, dst) plus in-memory adjacency cache | none in the papers |
| S3 | `networkx` multigraph, in memory | none in the notes read (no paper names its in-memory structure) |
| S4 | `rustworkx` or another compiled graph library | none; wheel availability for Python 3.11 on the local box and on the cluster to be checked |
| S5 | a graph database | KGCompass stores its graph in one (`kgcompass-2503.21710.md`, Sec. 4.3, p.9) |
| S6 | per-file sidecar files, updated incrementally per commit | LARGER (`larger-2605.16352.md`, Sec. 4.4, pp.6-7; App. D.1, pp.17-18): median alignment update 53 ms (pandas), 78 ms (transformers), 81 ms (scikit-learn) against 254, 123 and 51 s for a full rebuild (the update is incremental on a stored graph; the rebuild is from scratch) |
| S7 | canonical JSONL edge file (sorted keys, compact separators, as the CodeUnit canonical form) as the interchange format, with any of the above as a read-side structure | project-internal; makes byte-identity testable |

These are not exclusive: an interchange format plus a read-side structure is the likely shape, and
that is one more thing to decide. Measurements for each option, on flask, requests and django at
their Verified base commits: build time, load time, peak resident memory, size on disk, 1-hop and
2-hop expansion latency p50/p95/p99 (warm and cold), incremental update time, byte-determinism, and
the extrapolation to the largest repository from the measured numbers. Reference scale from the
papers (not this project's): ARISE reports a median graph of 134,000 nodes and 313,000 edges per
repository with statement nodes (`arise-2605.03117.md`, Sec. 5.3, p.10); KGCompass's Django snapshot
has 2,750 files and 27,867 functions (`kgcompass-2503.21710.md`, Sec. 4.1, p.8). The local box has 8 GB
RAM and no GPU, so the memory projection from measured per-unit numbers is made before any larger
build (project rule).

## Where the papers disagree: contain edges

LocAgent's ablation limited to `contain` is level with no traversal (function Acc@10 66.42 against
66.06, full 71.53; `locagent-2503.09089.md`, Table 6, p.9; single run, 274 instances, one instance is
about 0.37 points). SpIDER's default is containment only and raises Recall@20 over the same dense list
(+0.05 to +0.12; `spider-2512.16956.md`, Abstract, p.1; Table 2, p.8), while its own edge table has
invoke ahead of containment in every language (Python 0.56 against 0.49; Table 3, p.8). GREPO's
largest edge-type drop is for contain (Hit@20 41.25 to 37.47; `grepo-2602.13921.md`, Table 4, p.8).
The settings differ (agent with BM25 search and a fine-tuned 7B model; dense seeds plus an LLM filter;
a trained GNN reranker over anchors); the value of containment appears to depend on what supplies the
seeds (`spider-2512.16956.md`, Discrepancies). This project does not decide which is right.

**Ablation that would settle it at this project's scale** (planned as pilot E3, exploratory): same
seeds (BM25 first, then dense), same budget, expansion over each edge family alone, leave-one-out and
all; `contain` split into directory-to-file, file-to-definition and class-to-method; ΔnDCG@10 at L2
and ΔRecall@100 at L3 with paired bootstrap intervals against the seeds alone and against a
size-matched random expansion; per repository; tuned on non-Verified repositories, confirmed on
Verified with one pre-stated setting. Full design in `docs/GRAPH_DESIGN.md`.

## Open design questions

| # | Question | Options | Needed by |
|---|---|---|---|
| Q-G1 | Graph role(s) in the frozen configuration | signal; agent tool; training-time structure; combinations (ADR-003) | frozen config |
| Q-G2 | How a graph signal enters a rank-fusion stack that is fixed to RRF | graph-derived ranked list as an extra RRF input; score added before fusion (conflicts with the fixed rank-based fusion rule); expansion that edits the candidate list as SpIDER does | ADR-003 |
| Q-G3 | Do directories carry any retrieval document | none (pure structure); path text only | node kinds |
| Q-G4 | Attribution of nested definitions' edges to the enclosing unit | attribute to enclosing unit (follows D6); keep nested defs as nodes (needs a CodeUnit change) | resolver |
| Q-G5 | `test` as a kind or as a flag | flag `is_test` only; separate kind | node kinds |
| Q-G6 | Which files are `config` and `document`; granularity of documents | by name list; by extension; file vs section | node kinds |
| Q-G7 | Optional edge fields (`site`, `target_text`, `count`) | store all; store only for non-resolved; store none | edge record |
| Q-G8 | Boundary between `external` and `unresolved` | stdlib list plus declared requirements; installed environment; report the boundary case separately | status |
| Q-G9 | `contain` stored or derived | stored; derived from ids | storage |
| Q-G10 | One graph per (repository, commit) or one graph with validity ranges | per-commit; temporal graph as in GREPO (`grepo-2602.13921.md`, App. A.4, p.16); incremental update as in LARGER | storage, training role |
| Q-G11 | Unit-set hash recorded in the graph | yes; no | compatibility |
| Q-G12 | Confirm the projection readings under "Settled" | **decided 2026-10-18 (D20): confirmed** | CodeUnit projections |
| Q-G13 | Which resolver per family | own `ast`; PyCG-style; Jedi or language server; combination with status per resolver | ADR-011, ADR-012 |
| Q-G14 | Which families are in the first graph artifact and which stay exploratory | **decided 2026-10-18 (D19): contain, import, invoke, inherit, override in; tests, configures, co_change built but off by default** | ADR-011 |
| Q-G15 | Edge-recovery definition(s) reported | **decided 2026-10-18 (D15): dynamic-oracle recall with and without implicit callees, beside the call-site breakdown with each denominator named** (ADR-012 addendum) | reporting |

### Decided on 2026-10-18 (engineer decisions D15, D16, D19, D20; reasoning in the ADR-011 and ADR-012 addenda)

- **Read structure (D16):** a typed edge-list file read into an in-memory adjacency; no graph database. The file format
  (Parquet or canonical JSONL) and per-commit graphs (Q-G10) stay open.
- **First stored families (D19):** `contain`, `invoke`, `import`, `inherit`, `override`. The `tests`, `configures` and
  `co_change` builders stay and are off by default; `documents` and `mentions` are not built.
- **Projections (D20):** the readings under "Settled" are confirmed. With D19, `tests(u)` and `configs(u)` are `[]`
  (not computed) in the first stored graph.
- **Recovery reporting (D15):** see Q-G15.
- **Still open, to be settled by measurement (D24):** Q-G8 and Q-G13 (the `ambiguous` and `external` policies, Q35 and Q36)
  and Q-G1, Q-G2 (graph role, entry into fusion; Q30). The `ambiguous` policies (keep, drop, rebucket by receiver evidence, keep
  sets of at most three) are applied by a reader (`ril/parsing/ambiguity_policy.py`), the stored edge record is unchanged; first
  measurements 2026-10-23 in the ADR-011 addendum (`docs/EXPERIMENTS.md` E-AMBIG-POLICY). Still open.

## Acceptance criteria (for the spec, as a draft)

- [x] Node kinds, edge families (derivation, resolver, failure modes, users with note references,
      leakage, cost), edge record with status, derivation and candidate set, and the absence of
      confidence scores are written down.
- [x] The three roles, their schema needs, the storage options and the contain-edge disagreement with
      the settling ablation are written down.
- [x] No design choice is made; every choice is a marked open question.
- [x] The first graph build filled the per-status coverage table for flask, requests and django and the exploratory
      samples for `tests` and `configures` (n = 60 each, precision by reading) and the `co_change` counts
      (`results/tables/p_*.csv`, first build of 2026-10-17; ADR-012). The resolver used is the project's own `ast` resolver,
      recorded in every graph's metadata as `own-ast-resolver/v0` (`provisional: ADR-011`, Q-G13).
- [ ] (Next) A v0-to-v1 freeze needs the engineer's decisions on Q-G1 to Q-G15 and an ADR-011 status of
      Accepted. The storage measurements now exist (ADR-011 addendum).

## Change control

This spec is DRAFT v0 and may change freely until a freeze. After a freeze, a change to a field, a
status meaning, an edge family or an id form needs an ADR, a `REPO_GRAPH_SCHEMA_VERSION` bump, and a
rebuild plan for stored graphs. None of it touches `CODEUNIT_SCHEMA_VERSION` unless a projection
changes shape, in which case the CodeUnit change control applies as well.
