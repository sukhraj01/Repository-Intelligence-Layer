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
| A2b | RQ1 ext. (apparatus) | resolver typing options (return inference, merged locals, parameter defaults, all three) | repositories, parse, stored resolver rules | 0 | invoke sites by status; unknown-receiver sites; build seconds; trace recall and precision on flask | done 2026-11-05 (section A2b) |
| A1-DEV | RQ1 ext. (apparatus) | BM25 tokenizer (ref, split, split_noorig), then k1 x b on the chosen tokenizer; chunk level | dev folders of `configs/experiments/e1_bm25_dev3.yaml`, prefilter, metrics, stop list, stemmer | 0 | pooled nDCG@10 (protocol) with paired and clustered intervals; Recall@100; tokenise and build throughput; query p50/p95/p99 | chunk-level selection done 2026-11-05; fields and granularity open (section A1-DEV) |

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
reproduced the graph digest; with seven loads the nearest-rank p95 and p99 are the largest of the seven, so the p95 columns
of the table in `results/tables/a2c_edge_store.csv` are a maximum, not an estimate of a tail):

| repository | edges | raw JSONL | store | write | load, counts only | load, hashes (default) | load, deep | adjacency |
|---|---|---|---|---|---|---|---|---|
| requests | 4,163 | 1.1 MB | 68 KB | 0.19 s | 0.04 s | 0.04 s | 0.13 s | 0.004 s |
| flask | 5,892 | 1.5 MB | 90 KB | 0.17 s | 0.03 s | 0.03 s | 0.09 s | 0.002 s |
| click | 9,654 | 2.6 MB | 146 KB | 0.23 s | 0.05 s | 0.05 s | 0.16 s | 0.005 s |
| pytest | 39,145 | 11.2 MB | 627 KB | 0.93 s | 0.25 s | 0.24 s | 0.65 s | 0.02 s |
| django | 262,361 | 90.8 MB | 4.5 MB | 6.84 s | 1.98 s | 2.26 s | 5.31 s | 0.53 s |

Table `results/tables/a2c_edge_store.csv`, log `results/logs/a2c_edge_store_2026-10-31.json`.

**Reading.** Evidence class: measured. The store is 16 to 20 times smaller than the raw canonical JSONL, and hash checking
costs almost nothing over an unchecked load (django 2.26 s against 1.98 s); recomputing the digest costs 2.6 to 3.1 times an
unchecked load and 2.35 to 3.15 times a hash-checked load (p50 over the five repositories, ratios of the table above; django
2.7 and 2.35), so it is opt-in. Load time is JSON parsing of the edge records; a reader that needs only the adjacency of resolved
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

## A2b: resolver typing pilots, static and dynamic readings, done 2026-11-05

**Question.** Unknown-receiver calls are 80% of the ambiguous or unresolved sites (A2b-PREP). Do three typing
extensions of the resolver move them to `resolved`, and at what build cost?

**Pilots** (`ril.parsing.call_graph.ResolverOptions`, one factor each, then all three; all off is the stored resolver and
is byte-identical to it on all five checkouts, checked against the A2c graph digests): `infer_returns` (a call of an
in-repository function without a return annotation takes the value all its `return` statements agree on, `None` ignored,
generators and disagreeing returns left unknown; also for properties and `self.x = make()` attributes); `merge_locals` (a
local bound several times takes its one typed binding when the others are untyped or literals such as `None`);
`param_defaults` (an unannotated parameter takes the type of its default). Tests: `tests/unit/test_resolver_options.py`.

**Result, static** (the five A1-PILOT checkouts, one build per pilot, 2026-11-03; `results/tables/a2b_resolver_pilot_static.csv`,
totals in `results/tables/a2b_summary.json`):

| pilot | resolved sites, django | change | unknown-receiver sites, django | change | resolved, all five | build time, django |
|---|---|---|---|---|---|---|
| stored | 73,847 | - | 42,231 | - | 92,071 | 15.9 s |
| infer_returns | 74,286 | +439 | 41,604 | -627 | 92,566 | 16.4 s |
| merge_locals | 74,302 | +455 | 41,004 | -1,227 | 92,589 | 16.3 s |
| param_defaults | 73,867 | +20 | 42,216 | -15 | 92,091 | 17.0 s |
| all three | 74,837 | +990 | 40,270 | -1,961 | 93,204 | 16.9 s |

Across the five repositories the combined options resolve 1,133 more sites (+1.2% of resolved sites, 0.5% of all
invoke sites) and remove 4.3% of the unknown-receiver sites. Graph build time over the five repositories rises 7.1%
(19.3 s to 20.7 s), but with one build per pilot this is not separable from timing noise: `param_defaults`, which moves
20 sites, cost 7.5%. Correction (2026-11-05): the build-time column first written here (15.6 s to 17.0 s, "about 9%") came
from an earlier run, not the stored log; it now quotes the log.

**Why the gain is small: what the untyped receivers are** (combined options, 46,620 untyped receivers of attribute calls,
`untyped_receivers_combined_options` in the log): attribute chains on another object (`obj.a.b()`) 34.3%; attribute
chains on `self` (`self.x.y()`, the attribute's type unknown) 17.2%; locals assigned from an untyped value 14.7%; call
results 12.0%; unannotated parameters 9.2%; other locals 6.8%; subscripts 1.6%. Return inference reaches only the
call-result share, and only where the callee is in the repository. Most untyped receivers come from parameters and
attributes whose type is set by a caller elsewhere, so the next step that would reach them is propagating argument
types from call sites into parameters and `self` attributes (inter-procedural), not more local rules.

**Result, dynamic** (2026-11-05; `results/logs/a2b_resolver_pilot_dynamic_2026-11-05.json`, summary in
`results/tables/a2b_summary.json`). The flask test suite at 7ee9ceb (the pallets__flask-5014 base commit) run under
`scripts/ada/trace_pytest.py` on the local machine (Python 3.11, the repository's test pins plus werkzeug 2.2.3, jinja2
3.1.2, click 8.1.3, itsdangerous 2.1.2, markupsafe 2.1.2): 482 passed, 2 skipped, exit 0. Recall and precision from
`recovery_report`; 1,049 executed in-repository caller-to-callee pairs. The stored resolver reproduces the lead's reading
of 2026-10-17 on the cluster (`results/logs/p_flask_recovery_2026-10-17.json`: 1,057 pairs, Python 3.10, one more test
run) within a few pairs.

| pilot | resolved pairs | recovered (of 1,049) | recall, resolved | recall, resolved or ambiguous | precision lower bound (caller executed) | pairs added to stored |
|---|---|---|---|---|---|---|
| stored | 935 | 507 | 48.3% | 66.1% | 61.8% (of 820) | - |
| infer_returns | 936 | 507 | 48.3% | 66.1% | 61.8% (of 820) | 1 |
| merge_locals | 947 | 516 | 49.2% | 66.3% | 62.0% (of 832) | 12 |
| param_defaults | 935 | 507 | 48.3% | 66.1% | 61.8% (of 820) | 0 |
| all three | 948 | 516 | 49.2% | 66.3% | 62.0% (of 832) | 13 |

No option removes a resolved pair. The 13 pairs the combined options add, each read against the trace (`added_pairs` in the
log): 9 executed; 2 are instantiations whose target is the class (`Flask.test_client` to `FlaskClient`,
`Flask.test_cli_runner` to `FlaskCliRunner`), which the tracer records as the `__init__` call, and both `__init__` pairs are
among the 9; 1 has a caller the suite did not run (`examples/tutorial/tests/conftest.py::app` to `Flask.app_context`,
from return inference); 1 has an executed caller but no traced pair (`test_open_session_with_endpoint` to
`Scaffold.get`, from `@app.get("/")`): `Scaffold.get` is wrapped by the `setupmethod` decorator, so the trace sees the
call from the wrapper, and the source shows the call is real. By reading, none of the 13 is wrong. The misses are
unchanged by any option except instantiation without a site (17 to 15): implicit protocol dunders 199, no call site for
the callee's name 75, property access 40; only 25 misses have a call site present, which bounds what typing can add on
flask.

**Reading.** Evidence class: measured; the dynamic reading is one repository and one suite, so it checks correctness of
what moves rather than the size of the gain. What the options move is right: every added pair on flask is supported by the
trace or, read against the source, real, and precision does not fall. But the gain is small (recall +0.9 points on flask,
+1.2% resolved sites over five repositories), because the failures that dominate are not local typing failures: on flask
they are dunder, property and no-site calls, and over the five repositories most untyped receivers are attribute chains
and parameters set by callers. `merge_locals` carries almost all of the measured effect, `param_defaults` almost none.
Adopting the options changes resolver output, so it is a resolver-version decision for the lead (request RA-4 in
`docs/status/person_a.md`); the stored resolver stays the default meanwhile.

## A1-DEV: BM25 tokenisation and k1/b on the development folders, chunk level, done 2026-11-05

**Question.** Which BM25 setting does the development set choose for the tuned index: does identifier splitting (with or
without the whole identifier) beat the reference tokenisation of E1 on the benchmark's own task, and does k1 or b move
once the tokenizer is fixed? A1-PILOT showed both matter on a label-free local task; this is the selection on dev.

**Protocol, fixed before any run** (`configs/experiments/a_bm25_dev.yaml`; code `ril/analysis/rq1_bm25_dev.py`, tests
`tests/unit/test_rq1_bm25_dev.py`; cluster stage `scripts/ada/a_bm25_dev.sbatch`). Data: the development folders of
`configs/experiments/e1_bm25_dev3.yaml` (SWE-bench Pro openlibrary, qutebrowser, ansible at L2 and L3; SWE-bench-Live
conan, deepset, streamlink at L2), fetched into workstream A's own cluster account by `scripts/ada/a_fetch_dev.sbatch`.
Test folders are never read. Chunk level, whole-folder BM25 with the protocol reading of E1 (first 10,000 of the folder
ranking, then the query's candidates); documents and queries use the same tokenizer. Criterion: nDCG@10 pooled over all
dev queries, L2 and L3 together (as the E1 sweep). Stage 1: `ref`, `split`, `split_noorig` at k1 1.5 / b 0.75; the best
by the criterion is chosen only if its repository-clustered paired 95% interval against `ref` lies above 0, otherwise
`ref` stays. Stage 2: k1 in {0.9, 1.2, 1.5, 2.0} x b in {0.4, 0.6, 0.75, 0.9} on the chosen tokenizer; the best cell
replaces k1 1.5 / b 0.75 only under the same rule. Regression control: `ref` at k1 1.5 / b 0.75 on the five dev folders
of `configs/experiments/e1_bm25_reproduction.yaml` must reproduce the default row of `results/tables/e1_dev_sweep.csv`
exactly (510 queries, pooled nDCG@10 23.8244). Field weights and unit-versus-chunk granularity need unit texts at each
instance's base commit and are a later stage.

**Result** (`results/logs/a1_bm25_dev_2026-11-05.json`, `results/tables/a1_bm25_dev.csv`; cluster jobs 60143 and
60164, one u22 node, 2 CPUs, Python 3.10, 5.5 and 7.7 minutes). 680 dev queries (L2 and L3 pooled) over six repositories.

Regression control: `ref` at k1 1.5 / b 0.75 on the five E1 dev folders gives 510 queries and pooled nDCG@10 23.8244, the
E1 dev sweep's default row exactly.

Stage 1 (k1 1.5, b 0.75; differences against `ref` with query-level and repository-clustered intervals):

| tokenizer | nDCG@10 | L2 | L3 | Recall@100 | diff (queries) | diff (clustered) | tokenise chunks/s | query ms p50 / p95 / p99 |
|---|---|---|---|---|---|---|---|---|
| ref | 23.9 [22.2, 25.8] | 19.8 | 31.7 | 38.8 | - | - | 9,890 | 0.75 / 5.4 / 6.9 |
| split | 29.9 [27.9, 31.9] | 24.1 | 40.6 | 48.3 | +5.9 [+4.9, +7.0] | +5.9 [+3.3, +8.2] | 3,359 | 0.89 / 8.0 / 10.2 |
| split_noorig | 28.2 | 22.6 | 38.6 | 47.5 | +4.3 [+3.2, +5.3] | +4.3 [+2.1, +6.2] | 3,402 | 0.85 / 7.7 / 10.0 |

`split` is chosen by the rule. Every repository moves the same way (nDCG@10 `ref` to `split`: conan 9.9 to 10.8, deepset
19.1 to 27.2, ansible 24.3 to 29.4, openlibrary 26.8 to 35.8, qutebrowser 35.5 to 41.9, streamlink 7.0 to 9.4). Keeping the
whole identifier is better than dropping it (29.9 against 28.2), as in A1-PILOT.

Stage 2 (k1 x b on `split`; difference against k1 1.5 / b 0.75, clustered interval):

| k1 \ b | 0.4 | 0.6 | 0.75 | 0.9 |
|---|---|---|---|---|
| 0.9 | 26.5 (-3.4) | 27.8 (-2.1) | 28.7 (-1.1) | 29.5 (-0.3) |
| 1.2 | 27.2 (-2.6) | 28.5 (-1.3) | 29.5 (-0.4) | 30.2 (+0.3) |
| 1.5 | 27.8 (-2.1) | 29.1 (-0.8) | 29.9 (0) | 30.2 (+0.3) |
| 2.0 | 28.3 (-1.6) | 29.7 (-0.2) | **30.5 (+0.6)** | 30.3 (+0.5) |

The best cell, k1 2.0 / b 0.75, gains +0.6 [+0.3, +0.9] over queries and +0.6 [+0.1, +1.0] clustered, so the rule adopts
it. It lies on the edge of the grid (k1 2.0 is the largest value swept), so a larger k1 may do slightly better; extending
the grid now would be a second look chosen after seeing the first and is not done.

**Reading.** Evidence class: measured on dev; the cells were re-run on another account with the query-level rows stored
(`E-A1-TAKEOVER` in `docs/experiments/B.md`: every value equal, run files listed with SHA-256 in
`results/logs/a1_bm25_dev_run_files_2026-11-08.json`). The k1 2.0 cell is the best of 15 non-default cells of the grid, so
its interval is optimistic and the candidate is unconfirmed until it has been read inside the fused first stage.
Identifier splitting is the one large lever for BM25 on CORE-Bench code
chunks (+5.9 nDCG@10, every repository, clustered interval well above 0), consistent with A1-PILOT; k1 and b are a small
second-order adjustment. Cost: tokenising with splitting is about 3x slower (3,359 against 9,890 chunks per second),
index build is nearly unchanged, and query p95 rises from 5.4 to 8.0 ms in stage 1 (longer token lists); the stage 2
cells, run in a different job, give a p95 of about 6.7 to 7.0 ms for the same tokenizer, so differences of this size
between jobs are within node-to-node variation. Candidate setting: `configs/candidates/bm25_A.yaml` (`split`, k1 2.0,
b 0.75), to the lead as a request (ADR-004). Open: field weights and unit-versus-chunk granularity (unit texts needed),
then one reading of the Verified six with the single final setting.

