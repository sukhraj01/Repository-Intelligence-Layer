# Experiments: workstream A

Append-only log, entries by this workstream only. Rules, interpretation rules and the index of all entries are in
`docs/EXPERIMENTS.md`; the same rules apply here. Entry ids are unique across all experiment logs.

## Registry

| ID | RQ | What varies | Held fixed | Seeds | Primary outputs | Status |
|---|---|---|---|---|---|---|
| A1-PILOT | RQ1 ext. (apparatus) | BM25 identifier splitting and field weights (docstring-to-function task) | k1, b, stop list, stemmer, five local checkouts | 0 | MRR, Recall@10, nDCG@10 with clustered intervals; build and query latency | done 2026-10-31 (exploratory; section A1-PILOT) |
| A2a | RQ1 ext. (apparatus) | graph build: incremental update vs full rebuild | repositories, commits, resolver | 0 | equality of graph digests; seconds per commit p50/p95/p99 | done 2026-10-31 (section A2a) |
| A2c | RQ1 ext. (apparatus) | stored graph: versioned, hashed edge store vs raw JSONL; load check level | repositories, resolver, graph | 0 | round-trip equality; bytes; write and load seconds p50 | done 2026-10-31 (section A2c) |
| A2b-PREP | RQ1 ext. (apparatus) | none (census of invoke sites by status and resolver rule) | repositories, resolver | 0 | site counts per rule | done 2026-10-31 (section A2b-PREP) |
| A2b | RQ1 ext. (apparatus) | resolver typing options (return inference, merged locals, parameter defaults, all three) | repositories, parse, stored resolver rules | 0 | invoke sites by status; unknown-receiver sites; build seconds; trace recall and precision (pending) | static reading done 2026-11-03; dynamic pending (section A2b) |

## A1-PILOT: identifier splitting and field weights for BM25 on docstring-to-function retrieval, exploratory, done 2026-10-31

**Question.** Before the development-set runs on the cluster, does splitting identifiers (snake_case, camelCase, acronym and
digit boundaries) or weighting the name field move natural-language-to-code retrieval at unit level at all, and what does it
cost in index build and query latency?

**Task (local, label-free).** Five local checkouts (requests, flask, click, pytest, django at their default-branch heads;
commits in the log). Query = the first line of a function's or method's docstring (non-test units, at least 3 reference
tokens; at most 1,000 queries per repository, sampled with seed 0); the one relevant unit is that function. Every docstring
(module, class, function, nested) is removed from every unit's indexed text first, so the query text is never in the index.
All units of the snapshot are candidates (whole-snapshot retrieval, as in the benchmark). 2,649 queries in total.

**Conditions** (one factor each against `ref`; `split_fields` uses a name weight of 2 fixed before the run, not swept):
`ref` reference tokenisation of E1; `split` identifiers split, whole identifier kept; `split_noorig` split, whole identifier
dropped; `split_fields` `split` plus the name field twice and signature and path once. k1 1.5, b 0.75 for all
(`provisional: ADR-004`).

**Result** (pooled over the five repositories, query-weighted; MRR cut at rank 100; differences against `ref` with
paired query-level and repository-clustered 95% bootstrap intervals, 2,000 draws, seed 0):

| condition | MRR | Recall@10 | nDCG@10 | MRR diff (clustered) | Recall@10 diff (clustered) |
|---|---|---|---|---|---|
| ref | 18.7 [17.6, 20.0] | 32.5 | 21.3 | - | - |
| split | 27.6 | 47.1 | 31.4 | +8.9 [+6.9, +10.5] | +14.6 [+12.3, +17.8] |
| split_noorig | 26.8 | 46.9 | 30.8 | +8.1 [+6.2, +9.7] | +14.4 [+12.1, +18.1] |
| split_fields | 31.9 | 52.2 | 35.9 | +13.1 [+10.3, +15.9] | +19.7 [+17.6, +22.1] |

Every repository moves in the same direction (MRR `ref` to `split`: requests 30.2 to 36.7, flask 19.4 to 28.9, click 25.8
to 32.3, pytest 20.1 to 30.5, django 13.5 to 21.8). Cost: index build throughput falls from about 24,000-36,000 units/s
to 11,000-16,000 (`split`) and 9,000-12,000 (`split_fields`); query p50/p95/p99 is unchanged within noise (django, 41,221
units: `ref` 0.28 / 0.99 / 1.29 ms, `split` 0.27 / 1.01 / 1.19 ms, local CPU). Table `results/tables/a1_bm25_docstring_pilot.csv`,
log `results/logs/a1_bm25_docstring_pilot_2026-10-31.json`.

**Reading.** Evidence class: measured, exploratory. Splitting identifiers is a large and consistent gain on this task;
keeping the whole identifier besides its parts is 0.8 MRR above dropping it (no paired interval computed for that pair); weighting the name helps further. Limits: docstring summary
lines share vocabulary with the function's own name far more than issue reports do, so the size of the gain here is an upper
bound for the benchmark, not an estimate of it; the field weight is a single stated value; these are not development
repositories of the benchmark. Nothing is chosen from this pilot: the A1 one-factor runs on the development repositories
(and the E1 reproduction as the regression control) decide.

## A2a: incremental graph update against a full rebuild, done 2026-10-31

**Question.** Can the graph of a new commit be produced by re-reading only what the commit changed, with the result equal
byte for byte to a full rebuild, and what does a per-commit update cost against a full rebuild?

**Method.** `ril/parsing/incremental.py` keeps, per file, the units, the symbol summary and the import and invoke edges of the
previous build. An update re-parses files whose bytes, module name or package flag changed, rebuilds the structure edges
(contain, inherit, override) from the summaries, and re-resolves the call sites of a file only when it changed, imports
(directly or through a chain of imports) a module whose summary changed (summary compared without source positions, so a
change inside a function body reaches no other file), or uses an attribute name whose in-repository method set changed. The
D8 timestamps are updated from the commits between the two snapshots. `ril/bench/incremental_measure.py` takes the last 21
first-parent commits that touch Python files of each repository: the first is built in full, each of the next 20 is reached
by an incremental update and also built from scratch with `build_repository`; graph digest and unit bytes are compared.

**Resolver fix found by the equality check.** On requests the first runs disagreed on 3 of 5 commits: the resolver cached
the value of a lookup that had been cut short by a cycle (`str = str` in a `compat` module), so the edge of `from .compat import
str` depended on which file had been resolved first. Results computed under a cycle cut are no longer cached
(`ril/parsing/call_graph.py`). Effect on a full build: 2 of 4,163 edges change on requests (from `resolved` to `external`,
the re-exported builtin), 0 of 5,892 on flask and 0 of 262,361 on django; build time unchanged. Regression test:
`tests/unit/test_incremental_graph.py`. The resolver version string is unchanged (request to the lead).

**Result.** 20 updates per repository, every one equal to the full rebuild (100 of 100). Seconds per commit, nearest-rank
percentiles, local CPU (16 threads visible, one used), D8 history included in both columns:

| repository | files | units | full p50 / p95 / p99 | incremental p50 / p95 / p99 | speedup p50 (min) | share of files re-resolved p50 / p95 |
|---|---|---|---|---|---|---|
| requests | 37 | 753 | 0.35 / 0.39 / 0.40 | 0.25 / 0.29 / 0.30 | 1.4 (1.2) | 57% / 59% |
| flask | 83 | 1,009 | 0.48 / 0.53 / 0.55 | 0.08 / 0.38 / 0.39 | 5.3 (1.2) | 2.4% / 86% |
| click | 91 | 1,517 | 0.84 / 0.92 / 0.93 | 0.63 / 0.79 / 0.80 | 1.3 (1.05) | 87% / 90% |
| pytest | 274 | 6,834 | 4.71 / 5.54 / 5.61 | 0.60 / 3.36 / 3.56 | 7.6 (1.5) | 0.7% / 64% |
| django | 2,939 | 41,221 | 29.2 / 30.1 / 30.4 | 2.96 / 21.1 / 21.1 | 9.6 (1.3) | 0.07% / 71% |

Commits whose changes stay inside function bodies (no module summary changed: 8, 10, 7, 12 and 13 of the 20) take a median
of 0.09, 0.06, 0.19, 0.48 and 2.86 s; at django size the remainder is reading and hashing every file, the structure edges
and sorting 262,000 edges, not resolution. Table `results/tables/a2_incremental_update.csv`, per-commit rows (files changed,
re-parsed, re-resolved and why, stage times) in `results/logs/a2_incremental_graph_2026-10-31.json`.

**Reading.** Evidence class: measured. The gate (incremental equals full on at least five repositories at three commits
each) holds on every update measured. The speedup depends on what a commit touches: an edit inside function bodies
re-resolves one file, while a change to the symbols of a module that a package re-exports reaches every importer, which is
most of a small repository (requests, click). Finer dependencies (per imported name instead of per module) would cut that
further; not attempted. Times are wall clock, one process, warm file cache, local CPU, history read included.

## A2c: the stored graph as a versioned, hashed edge-list directory, done 2026-10-31

**Question.** Decision D16 fixes the read structure of the first stored graph (a typed edge-list file read into an
in-memory adjacency). What does a versioned, deterministic and verified version of that file cost to write and load?

**Format** (`ril/parsing/edge_store.py`, `EDGE_STORE_VERSION = 1`): a manifest, manifest.json (format and version, graph metadata
with schema, resolver and unit-set hash, node and edge counts, counts per family and status, graph digest, SHA-256 and size
of each data file) plus `nodes.jsonl.gz` and `edges.jsonl.gz` (the canonical graph bytes, gzip with a fixed header). The
same graph always writes the same bytes, whatever order its edges were built in. A load always checks format version and
counts; by default it also checks the file hashes; `deep` also recomputes the graph digest. A failed check raises
instead of returning a graph. Tests: `tests/unit/test_edge_store.py` (round trip, byte identity, tampered file, unknown
version).

**Result** (history off, seven loads per check level, nearest-rank p50, local CPU, warm file cache; every round trip
reproduced the graph digest):

| repository | edges | raw JSONL | store | write | load, counts only | load, hashes (default) | load, deep | adjacency |
|---|---|---|---|---|---|---|---|---|
| requests | 4,163 | 1.1 MB | 68 KB | 0.19 s | 0.04 s | 0.04 s | 0.13 s | 0.004 s |
| flask | 5,892 | 1.5 MB | 90 KB | 0.17 s | 0.03 s | 0.03 s | 0.09 s | 0.002 s |
| click | 9,654 | 2.6 MB | 146 KB | 0.23 s | 0.05 s | 0.05 s | 0.16 s | 0.005 s |
| pytest | 39,145 | 11.2 MB | 627 KB | 0.93 s | 0.25 s | 0.24 s | 0.65 s | 0.02 s |
| django | 262,361 | 90.8 MB | 4.5 MB | 6.84 s | 1.98 s | 2.26 s | 5.31 s | 0.53 s |

Table `results/tables/a2c_edge_store.csv`, log `results/logs/a2c_edge_store_2026-10-31.json`.

**Reading.** Evidence class: measured. The store is 16 to 20 times smaller than the raw canonical JSONL, and hash checking
costs almost nothing over an unchecked load (django 2.26 s against 1.98 s); recomputing the digest costs about 2.4 times a
load, so it is opt-in. Load time is JSON parsing of the edge records; a reader that needs only the adjacency of resolved
edges could store that projection separately (not done: D16 reads the typed edge list).

## A2b-PREP: where the resolver fails, by call-site rule, done 2026-10-31

The resolver-recall pilots of A2b need the dynamic oracle (D15), which runs a repository's own test suite under the call
tracer. That suite was not run on this machine (running a checked-out project's code locally is not permitted here), so
no recall number is reported. What can be measured statically is where the resolver fails today. Over the 232,474
`invoke` sites of the five checkouts of A1-PILOT (default-branch heads): 92,071 resolved, 89,168 external, 38,420
ambiguous, 12,815 unresolved. Of the 51,235 ambiguous or unresolved sites, **41,147 (80%)** are calls on a receiver of
unknown type (`unknown-receiver:name-match` 36,743 ambiguous, `unknown-receiver:too-many-name-matches` 4,404 unresolved);
next are attributes missing from a known class's MRO (3,934), calls through a local name (1,622), several module-level
definitions of one name (1,174) and attributes of a class with an unresolved base (1,113). Log
`results/logs/a2b_invoke_breakdown_2026-10-31.json`.

**Reading.** Of the three pilots the brief names, attribute and variable typing (constructor assignments, parameter
annotations, local assignments) targets the largest failure class; import-aware resolution and decorated or property calls
target classes of a few hundred to a few thousand sites. Order for the pilots once the oracle can run: typing first.

## A2b: resolver typing pilots, static reading, 2026-11-03 (dynamic reading pending)

**Question.** Unknown-receiver calls are 80% of the ambiguous or unresolved sites (A2b-PREP). Do three typing
extensions of the resolver move them to `resolved`, and at what build cost?

**Pilots** (`ril.parsing.call_graph.ResolverOptions`, one factor each, then all three; all off is the stored resolver and
is byte-identical to it on all five checkouts, checked against the A2c graph digests): `infer_returns` (a call of an
in-repository function without a return annotation takes the value all its `return` statements agree on, `None` ignored,
generators and disagreeing returns left unknown; also for properties and `self.x = make()` attributes); `merge_locals` (a
local bound several times takes its one typed binding when the others are untyped or literals such as `None`);
`param_defaults` (an unannotated parameter takes the type of its default). Tests: `tests/unit/test_resolver_options.py`.

**Result, static** (the five A1-PILOT checkouts, one build per pilot; `results/tables/a2b_resolver_pilot_static.csv`):

| pilot | resolved sites, django | change | unknown-receiver sites, django | change | resolved, all five | build time, django |
|---|---|---|---|---|---|---|
| stored | 73,847 | - | 42,231 | - | 92,071 | 15.6 s |
| infer_returns | 74,286 | +439 | 41,604 | -627 | 92,566 | 16.9 s |
| merge_locals | 74,302 | +455 | 41,004 | -1,227 | 92,589 | 16.6 s |
| param_defaults | 73,867 | +20 | 42,216 | -15 | 92,091 | 16.8 s |
| all three | 74,837 | +990 | 40,270 | -1,961 | 93,204 | 17.0 s |

Across the five repositories the combined options resolve 1,133 more sites (+1.2% of resolved sites, 0.5% of all
invoke sites) and remove 4.3% of the unknown-receiver sites, for about 9% more build time.

**Why the gain is small: what the untyped receivers are** (combined options, 46,620 untyped receivers of attribute calls,
`untyped_receivers_combined_options` in the log): attribute chains on another object (`obj.a.b()`) 34.3%; attribute
chains on `self` (`self.x.y()`, the attribute's type unknown) 17.2%; locals assigned from an untyped value 14.7%; call
results 12.0%; unannotated parameters 9.2%; other locals 6.8%; subscripts 1.6%. Return inference reaches only the
call-result share, and only where the callee is in the repository. Most untyped receivers come from parameters and
attributes whose type is set by a caller elsewhere, so the next step that would reach them is propagating argument
types from call sites into parameters and `self` attributes (inter-procedural), not more local rules.

**Dynamic reading: pending.** Recall and precision against the flask test-suite trace (D15) are not measured yet; the
trace needs the suite run, which is not done on this machine by the tooling. With the trace at
`data/processed/flask_trace.json`, `scripts/a_resolver_pilot.py --trace pallets/flask=<checkout at 7ee9ceb>=<trace>` adds
recall and the precision lower bound per pilot. A moved site is not a correct site until then.

**Reading.** Evidence class: measured (static only). The three local typing extensions are cheap, and each resolves
sites the stored resolver leaves to name matching, but together they reach a few percent of the failure class. Nothing is
adopted: the stored resolver stays as it is until the dynamic reading shows the moved sites are right.
