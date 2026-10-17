# Experiments

Live registry. One row per planned experiment; status updated as work happens. The *design* of each
is in `08_experimental_design.md` (RQ2/RQ3) and `02_research_questions.md` (RQ1); this file adds IDs
and bookkeeping. Nothing here changes what is controlled — that is a design decision.

## Rules every experiment follows

- **Config:** a file in `configs/experiments/<exp_id>.yaml`, hashed; the hash is stored with the result.
- **Result directory:** `results/<rq>/<exp_id>/<YYYY-MM-DD>_<confighash8>/` containing `config.yaml`,
  `results.json`, `hardware.json`, and a log under `results/logs/`.
- **Seeds:** ≥3 per RQ2 arm; report mean ± SD; if two arms overlap within one SD, say indistinguishable.
- **Always:** baseline comparison, confidence intervals, slices, interpretation, latency columns.
- **RQ2 extras recorded per run:** GPU-hours, unique examples seen, effective epochs, optimizer updates.
- **A one-line summary goes in `RESULTS.md` the moment a run finishes.**
- **Statuses:** `planned` → `config-ready` → `running` → `done` → `interpreted` (or `cut`, with reason).

## Registry

| ID | RQ | What varies | Held fixed | Seeds | Primary outputs | Status |
|---|---|---|---|---|---|---|
| E-LAT-HARNESS | — | — | fixed query set | n/a | p50/p95/p99 per stage per commit | planned |
| E-LAT-STAGES | RQ1 | pipeline stage | repo, queries, hardware | n/a | per-stage time attribution; rerank share | planned |
| E-RQ1-DENSE | RQ1 | signals: dense only | encoder, eval set, metric code | n/a | nDCG@10, MRR, Recall@10, latency | planned |
| E-RQ1-DENSE-BM25 | RQ1 | dense + BM25 | as above | n/a | as above | planned |
| E-RQ1-DENSE-STRUCT | RQ1 | dense + structural | as above | n/a | as above | planned |
| E-RQ1-ALL | RQ1 | dense + BM25 + structural | as above | n/a | as above; nDCG per ms (Pareto) | planned |
| E-GRAPH-BUILD | RQ1 ext. (apparatus) | repository (flask, requests, django); storage option; recovery definition | Verified base commits, seed 0, resolver `own-ast-resolver/v0` | n/a | per-status edge counts; recovery under definitions (a)-(d); exploratory precision of `tests` and `configures`; build and expansion cost per storage option | done (exploratory, first build of 2026-10-17; `RESULTS.md` rows `p-*`; ADR-011 and ADR-012 addenda) |
| E-GRAPH-REACH | RQ1 ext. (apparatus) | edge subset (19), control (3: same files, whole repository, whole repository of the same unit kind) | flask, requests, seaborn Verified instances (L2 11, L3 7) at their base commits, seed 0, 200 control draws per positive, 2,000 bootstrap draws, resolver `own-ast-resolver/v0` | n/a | chunk match rate and failure reasons; span categories against the first label sample; L3 positives by kind; share of new L3 positives within 1, 2, 3 hops of the L2 units and unreachable, with chance control and 95% bootstrap intervals | done (exploratory pilot, 2026-10-17; `RESULTS.md` rows `m-*`; ADR-004 and ADR-003 addenda) |
| E-BM25-REPRO | RQ1 ext. (apparatus) | BM25 granularity (chunk, unit), module unit in or out of the index, protocol reading (cut at 10,000 before the candidate filter, or candidates only), k1/b (dev sweep) | reference tokenisation and scoring, seed 0, 2,000 bootstrap draws; dev and test repositories fixed in the config before the runs | n/a | nDCG@10 and Recall@100 with 95% intervals; agreement with the published BM25 rows | done (exploratory pilot, 2026-10-18; `RESULTS.md` rows `e1-*`; ADR-004 addendum) |
| E-LABEL-NOISE | RQ1 ext. (apparatus) | label set (all, content-cleaned, edit-overlap, both) and treatment of removed positives (kept as not relevant, or dropped from the list) | rankings of E-BM25-REPRO | n/a | score changes on the same queries with paired intervals; first-rank changes; whether a comparison changes verdict | done (exploratory pilot, 2026-10-18; `RESULTS.md` rows `e2-*`) |
| E-GRAPH-L3 | RQ1 ext. | + test/config node and edge types | L3 eval set | n/a | L3 metrics; edge-recovery coverage | planned |
| E-RQ2-RAW | RQ2 | arm = RAW | everything in the held-identical block | 3 | retrieval metrics + budget table | planned |
| E-RQ2-FILTER | RQ2 | arm = FILTER (K-rank threshold) | as above | 3 | as above | planned |
| E-RQ2-WEIGHT | RQ2 | arm = WEIGHT (K-rank soft weight) | as above | 3 | as above | planned |
| E-RQ2-CURRICULUM | RQ2 | arm = CURRICULUM (easy→hard) | as above | 3 | as above | planned |
| E-RQ2-CTRL-SUBRAW | RQ2 | RAW subsampled to FILTER's pool size, equal updates | as above | 3 | separates "less data seen more often" from quality | planned |
| E-RQ2-SEC-QQ | RQ2 (secondary) | best arm at 100/80/60/40% of pool | as above | 3 | quantity–quality curve (replicates SweRank §5.3.1 at repo level) | planned — only if core completes |
| E-RQ2-SEC-POSNEG | RQ2 (ablation) | degrade positive side vs negative side | as above | 3 | positive- vs negative-quality effect | planned — only if core completes |
| E-RQ3-AGENT | RQ3 | retriever = RAW / FILTER / WEIGHT / CURRICULUM | agent scaffold, base LLM, temperature, seed, instances | 1 per instance (paired) | resolved rate + CI; McNemar; retrieval-vs-reasoning breakdown; resolved rate per agent wall-clock | planned — gated on week-12 go/no-go |

## E-GRAPH-REACH (exploratory pilot, done 2026-10-17)

Config `configs/experiments/m_chunk_unit_reach.yaml` (hash `23c173e6c4f8`), log `results/logs/m_chunk_unit_reach_2026-10-17.json`,
tables `results/tables/m_*.csv`. Ran on Ada (CPU, one 2-CPU job of under a minute, `scripts/ada/m_chunk_unit_reach.sbatch`); a second
independent run gave identical records apart from timing and host name. Licence: CORE-Bench is non-commercial share-alike, so only
counts, ids, paths and line numbers are stored; no chunk text.

**Protocol.** For each Verified instance of flask (1), requests (8) and seaborn (2) in the L2 sample folders (L3: 1, 5, 1) the base
commit is checked out; every positive chunk (qrels) is located in the files by exact text, then trimmed text, then unified line
endings, then collapsed whitespace; all locations are kept. The first location's line span is mapped to the frozen units (D6) by line
overlap. The graph of the snapshot (contain, import, invoke, inherit, override; exploratory tests, configures and co_change) gives hop
distances from the L2 units of the instance to each L3 positive whose units are not L2 units ("new"). Edge subsets read the resolved
edges as undirected, except `invoke_fwd` (L2 unit calls the target) and `invoke_rev` (target calls the L2 unit); `inherit` includes
`override`; `import` and `co_change` join file units, so `*_contain` subsets add the containment tree; `all` uses co-change support 3.
**Control:** for every new positive with k units, random sets of k units (200 draws, seeded per instance, chunk and control) from the
same files, the whole repository, and the units of the same type and test flag; the L2 units are never drawn. Reported: observed share
within 1, 2, 3 hops, share with no path, chance share, their difference and ratio, with 95% percentile bootstrap intervals over
positives and over instances (2,000 draws).

**Results (measured, n small).**
- Match: 160 of 160 positives (19 L2, 141 L3) found, all by exact text, each at one location; no failure of any kind (no empty chunk, no
  missing file, no base commit missing). Wave 1's check that every list chunk of 11 instances occurs in its snapshot agrees.
- Span categories against the first label sample (111 / 28 / 5 / 16 of the same 160 positives): the first sample's rule recomputed on
  the whole chunk span gives 112 / 27 / 5 / 16 (one flask L3 positive differs; the first sample matched the first 200 characters, which
  can sit in two files); the frozen units give 118 / 21 / 5 / 16 (nested definitions fold into their parent, so six chunks that span a method
  and a nested function become one unit). Matching only the first 200 characters would give 119 / 5 / 20 / 16. The residual share that
  justifies the module unit reproduces exactly: 16 of 160 (10.0%; L3 13 of 141, L2 3 of 19); 2 more chunks touch residual lines besides a
  definition.
- L3 positives by kind (141): method 101, function 12, class 5, module residual 13, test unit 10 (7 methods, 3 functions), non-Python
  artifact 0 (docs, configuration, data), unmatched 0. In this sample L3 holds no documentation or configuration positive.
- Reach population: 126 of 141 L3 positives are new Python positives with a defined control (15 coincide with an L2 unit, 12 of those
  141 are text-identical to an L2 positive); 7 instances (flask 19, requests 79, seaborn 28).
- Reach, all new positives (observed share; chance share for random units of the same files; excess with positive-bootstrap interval):
  see the table below. Reading in one line: nearly everything is near the L2 units because it sits in the same files and directories;
  the excess over same-file chance is concentrated in `invoke` (both directions), about 13 points within 3 hops (6 to 20 points over
  positives, 5 to 27 over instances) and a factor of 1.8 at one hop; `contain` and `import` add nothing over same-file chance, `inherit`
  reaches 5 of 126 positives (4 within one hop; chance near zero), `tests`, `configures` and `co_change` add nothing measurable.

| subset | within 1 hop: observed | chance, same files | excess [95% positives] | within 3 hops: observed | chance, same files | excess [95% positives] (instances) | chance, whole repo same kind | excess [95%] |
|---|---|---|---|---|---|---|---|---|
| invoke, both ways | 0.119 | 0.065 | +0.054 [+0.003, +0.110] | 0.397 | 0.266 | +0.131 [+0.062, +0.200] (+0.049, +0.266) | 0.098 | +0.299 [+0.214, +0.380] |
| invoke, L2 unit calls target | 0.064 | 0.037 | +0.026 [-0.014, +0.069] | 0.095 | 0.064 | +0.031 [-0.018, +0.083] | 0.015 | +0.080 [+0.033, +0.137] |
| invoke, target calls L2 unit | 0.056 | 0.029 | +0.027 [-0.009, +0.067] | 0.119 | 0.067 | +0.052 [+0.005, +0.109] (+0.010, +0.124) | 0.024 | +0.095 [+0.043, +0.155] |
| import | 0.008 | 0.021 | -0.013 [-0.029, +0.007] | 0.127 | 0.139 | -0.012 [-0.052, +0.032] | 0.058 | +0.069 [+0.031, +0.110] |
| inherit (with override) | 0.032 | 0.001 | +0.031 [+0.007, +0.062] | 0.040 | 0.001 | +0.038 [+0.008, +0.077] | 0.001 | +0.038 [+0.007, +0.077] |
| contain | 0.040 | 0.043 | -0.003 [-0.040, +0.040] | 0.421 | 0.433 | -0.013 [-0.062, +0.040] | 0.146 | +0.275 [+0.200, +0.357] |
| tests (exploratory) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| configures (exploratory) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| co_change, support 3 (exploratory) | 0.032 | 0.024 | +0.008 [-0.010, +0.033] | 0.032 | 0.027 | +0.005 [-0.013, +0.030] | 0.008 | +0.024 [+0.004, +0.051] |
| invoke + contain | 0.159 | 0.099 | +0.060 [-0.003, +0.125] | 0.849 | 0.690 | +0.159 [+0.102, +0.214] (+0.052, +0.264) | 0.298 | +0.551 [+0.472, +0.616] |
| core five families | 0.167 | 0.113 | +0.054 [-0.010, +0.122] | 0.881 | 0.782 | +0.099 [+0.050, +0.147] (-0.011, +0.204) | 0.497 | +0.384 [+0.312, +0.454] |
| all families minus contain (exploratory) | 0.159 | 0.101 | +0.058 [+0.005, +0.119] | 0.698 | 0.514 | +0.184 [+0.111, +0.252] (+0.064, +0.292) | 0.314 | +0.385 [+0.301, +0.463] |
| all families (exploratory) | 0.198 | 0.135 | +0.064 [-0.001, +0.130] | 0.936 | 0.826 | +0.111 [+0.061, +0.165] (+0.049, +0.190) | 0.591 | +0.345 [+0.276, +0.412] |

Within two hops, by kind (function 10, method 90, class 5, module residual 11, test unit 10 new positives) and by repository (flask
19, requests 79, seaborn 28) the same pattern holds with wide intervals (`m_reach.csv`, groups `kind` and `repo:`); the invoke excess is
present in flask (0.26 observed within 3 hops against 0.01 by chance) and requests (0.43 against 0.27) and absent in seaborn (0.39
against 0.43).

**What it does and does not show.** It shows, for these three repositories, that (i) a chunk-to-unit mapping by text is exact and
unambiguous on Verified (D7 stands: the flip condition was a low match rate), (ii) the module unit is needed for 10% of the sample
(D6 stands), (iii) L3 positives in this sample are code units (7% tests, no documentation or configuration), and (iv) the structural
nearness of L3 positives to L2 positives is mostly file and directory locality, with a call-graph excess over that locality. It does not
show that graph expansion improves retrieval: the seeds are the gold L2 units, not retrieved ones (an upper bound on what a perfect first
stage could seed); the neighbourhood sizes and so the precision cost are not measured here (E3 does that); resolved `invoke` edges
cover 28% to 72% of call sites depending on the denominator (ADR-012), and instantiation edges end at the class, not its `__init__`,
so reach is an underestimate for call edges; L3 labels are model judgements over agent browsing (paper), not structural truth; positives
within an instance are correlated and there are 7 instances, so the instance interval is the honest one; three repositories do not
license any statement about others (seaborn shows no excess); the `tests`, `configures` and `co_change` rows are exploratory
(sampled precision in ADR-011) and `tests` reaches nothing because the L2 units here are not the direct target of any test edge.
Nothing here settles an edge taxonomy, a graph role or a granularity; those stay with the engineer (ADR-003, ADR-004, ADR-011).

## Development and test repositories (tuning discipline, set 2026-10-18)

Verified is the final test set for RQ1 and RQ3, so sweeps run on development repositories that share no repository with it.
Base commits were looked for in the datasets' own metadata (dataset pages fetched 2026-10-18; coverage counts the CORE-Bench queries whose
instance id occurs in that metadata with a `base_commit`, `results/logs/e_bm25_repro_noise_2026-10-18.json`):

| CORE-Bench sub-dataset | metadata source | base commits found (L2 queries; L3 queries) | Python repositories |
|---|---|---|---|
| SWE-bench Pro | `ScaleAI/SWE-bench_Pro` (`base_commit`) | 632 of 632; 585 of 585 | 3 (ansible, openlibrary, qutebrowser) |
| SWE-bench Live | `SWE-bench-Live/SWE-bench-Live` (`base_commit`) | 1,623 of 1,623; no L3 | most of 213 |
| SWE-Bench++ | `TuringEnterprises/SWE-Bench-plus-plus` (`base_commit`) | 442 of 442; no L3 | mixed languages |
| SWE-bench Multilingual | `SWE-bench/SWE-bench_Multilingual` (`base_commit`) | 276 of 276; 248 of 248 | none: its repositories are in other languages |
| Multi-SWE-bench | per-repository JSONL of `ByteDance-Seed/Multi-SWE-bench` (not fetched) | not measured | none among the 35 folders of this benchmark |
| SWE-bench+ (6 Python repositories) | none readable: its ids are not in `princeton-nlp/SWE-bench` (0 of 207) and the dataset page of the SWE-bench+ authors is not served | 0 of 207 | 6 |

So four of the five non-Verified sub-datasets give base commits from their own metadata (Q21 / D12: unit-level evaluation beyond Verified is
possible for Pro, Live and Pro's L3; Multilingual and Multi-SWE-bench contain no Python repository, so there is no "Multilingual-Python" set).
**Chosen dev repositories** (mid-size, pure Python projects, none in Verified; split fixed in `configs/experiments/e1_bm25_reproduction.yaml`
before any run, covered by its hash): Pro `internetarchive/openlibrary` (81 instances, L2 and L3) and `qutebrowser/qutebrowser` (75, L2 and L3);
Live `conan-io/conan` (90), `deepset-ai/haystack` (72), `streamlink/streamlink` (37), L2 only. 355 instances, 355 L2 and 155 L3 queries; corpora 6k to 20k chunks
per folder (L2 total 96 MB). Pro's `ansible` (213 MB) and the Live repositories that are also Verified repositories (matplotlib, xarray, sphinx, pylint) were
left out. **Test:** the 12 Verified repositories for the chunk-level reproduction; six of them (flask, requests, seaborn, xarray, matplotlib, astropy; 83 L2
and 55 L3 instances) for the unit-level runs. The fallback split of Verified in halves was not needed.

## E-BM25-REPRO (E1) and E-LABEL-NOISE (E2): exploratory pilots, done 2026-10-18

Configs `configs/experiments/e1_bm25_reproduction.yaml` (hash `638fb270c360`) and `e1_bm25_full_l2.yaml` (hash `583649ab5d04`), log
`results/logs/e_bm25_repro_noise_2026-10-18.json`, tables `results/tables/e1_*.csv`, `e2_*.csv`. All on Ada (CPU, `u22`, gnode002; clones
28 min, chunk stage 2.5 min, unit stage 49 min with a 3.8 GB peak, all 632 L2 folders 63 min; Python 3.10.12), one rerun of the 24 test folders
with identical ranks. Licence: records hold ranks, ids, paths, line numbers and counts; no corpus, query or source text.

**Method.** BM25 as the released toolkit does it (`ril/retrieval/bm25_index.py`): lower-case tokens `\b\w\w+\b`, a 33-word English stop list, Snowball English
stemming, Lucene-variant scoring with k1 = 1.5, b = 0.75 (`provisional: ADR-004`, the reference defaults), checked against the reference library
(`bm25s`) on identical ranking. Chunk level: index over the folder corpus, rank for each query, cut at 10,000, keep the query's candidate list
(`filtered_corpus_id`), binary gain; both this reading ("protocol") and ranking only the candidates ("filter-first") are recorded for each positive,
with the best and worst rank a tie could take. Unit level: for every instance, the base commit is checked out, units are parsed (D6, module unit included),
positives are located and mapped (D7), and BM25 ranks the units of that snapshot with the issue text, with and without the module units in the index
and for two gold readings (Q39): `units` (the functions or methods a chunk overlaps, else classes, else the module unit; pilot M's mapping) and `units_all`
(every overlapped unit including the class and the module unit). E2 label sets: `clean_content` drops positives whose lines are only imports, only comments or
docstrings, or that lie in a documentation file; `edit_overlap` keeps positives whose lines overlap a base-commit line the reference patch edits (units: gold
units that overlap an edited line); `clean_both`. A removed positive either stays in the list as not relevant (`neg`) or leaves it (`ignored`). Intervals are
percentile bootstraps over queries (2,000 draws, seed 0); for averages of averages the queries are resampled inside each folder.

**E1, chunk level: the loader and the metric reproduce the published BM25 rows (paper_reported 11.9 / 46.7 and 22.2 / 33.9 on Verified L2 and L3, 13.0 / 38.8 on L2).**
The match depends on the averaging convention, which the card does not state:

| set | convention | queries | nDCG@10 [95%] | Recall@100 [95%] | paper_reported |
|---|---|---|---|---|---|
| Verified 12 folders, L2 | mean over folders | 432 | 11.94 [9.42, 14.58] | 46.74 [42.23, 50.98] | 11.9 / 46.7 |
| Verified, L2 | mean over queries | 432 | 14.29 [12.15, 16.82] | 42.92 [38.94, 46.93] | |
| Verified, L3 | mean over folders | 302 | 22.19 [19.52, 24.99] | 33.89 [30.78, 36.70] | 22.2 / 33.9 |
| Verified, L3 | mean over queries | 302 | 22.08 [19.62, 24.75] | 28.79 [26.20, 31.42] | |
| all 632 L2 folders | mean of the 7 sub-dataset means of folder means | 5,061 | 13.00 [12.11, 13.99] | 38.82 [37.55, 40.11] | 13.0 / 38.8 |
| all L2 | mean over folders | 5,061 | 12.93 [12.47, 13.39] | 36.59 [35.88, 37.26] | |
| all L2 | mean over queries | 5,061 | 13.28 [12.77, 13.78] | 36.27 [35.34, 37.14] | |

The four Verified numbers and the L2 average match the published rows to the printed decimal under "mean over folders" (and, for L2, "mean over sub-datasets of the
mean over folders"); the query-weighted mean differs in Recall@100 by 2.5 points over all of L2 and by 3.8 (L2) and 5.1 (L3) on Verified, because small folders such as requests and flask have high recall
and a single query each. Sub-dataset L2 values (folder means): Pro 19.5 / 38.0, Live 14.8 / 44.4, SWE-Bench++ 12.6 / 32.3, Multi-SWE-bench 12.3 / 37.2, SWE-bench+ 15.0 / 48.4,
Verified 11.9 / 46.7, Multilingual 5.0 / 24.8 (`e1_aggregation.csv`). Not run: the L3 average of the card (20.5 / 30.1; Multi-SWE-bench and Multilingual L3 folders). Qrels note: 1,676 of the
52,712 L2 qrels rows repeat a (query, chunk) pair already listed (Multi-SWE-bench 1,319), so there are 51,036 distinct positives; the toolkit scores sets, as we do.
Protocol versus filter-first: identical nDCG@10 and Recall@100 on every group (difference 0.00); 17% to 40% of positives lie beyond rank 10,000 of the folder ranking, which
cannot matter at k <= 100 but would for Recall@1000. Ties (equal scores) move Recall@100 by under 0.2 points. Our six-repository sample (flask, requests, seaborn) cannot test a
632-folder average: 11 L2 queries give 10.5 / 71.2 with intervals spanning 3 to 21 and 50 to 91.

**E1, development repositories and the k1/b sweep (dev only).** On the 355 L2 and 155 L3 dev queries the defaults give nDCG@10 19.3 [16.7, 21.8] / 41.8 (L2) and 34.3 [30.6, 38.0] / 41.7
(L3); Pro 27.7 / 44.9, Live 12.7 / 39.4 at L2. Sweep of k1 in {0.9, 1.2, 1.5, 2.0} x b in {0.4, 0.6, 0.75, 0.9} on the 510 dev queries (criterion stated before the run: pooled nDCG@10):
the surface is flat (23.8 at the default; best cell k1 = 2.0, b = 0.75 at 24.2, paired +0.41 [+0.03, +0.80], at the edge of the grid; b = 0.4 is worse by 1.2 to 2.4). The best cell was run
once on the Verified folders: L2 nDCG@10 +0.27 [-0.01, +0.57], L3 +0.70 [+0.30, +1.10] (Recall@100 +0.03 and +0.72) against the default. Confirmation is weak and the grid edge is unexplored; the
defaults are kept for the other runs. No value is recommended.

**E1, unit level (mean over queries; empty gold impossible here, every row has a located positive).** Six Verified repositories (83 L2, 55 L3 queries) and the dev set (353 L2, 155 L3):

| set | gold | index | nDCG@10 [95%] | Recall@100 [95%] |
|---|---|---|---|---|
| Verified 6, L2 | `units` | with module | 16.1 [10.4, 22.3] | 43.8 [34.8, 53.3] |
| Verified 6, L2 | `units` | without module | 17.5 [11.7, 23.4] | 46.5 [37.6, 55.8] |
| dev, L2 | `units` | with module | 15.8 [13.7, 18.1] | 33.1 [30.0, 36.1] |
| dev, L2 | `units` | without module | 15.2 [13.1, 17.3] | 31.1 [28.1, 34.1] |
| dev, L3 | `units` | with module | 31.5 [27.8, 35.3] | 35.6 [32.3, 39.0] |
| dev, L3 | `units` | without module | 31.1 [27.6, 34.8] | 33.5 [30.4, 36.6] |

With and without the module unit, on the same gold (paired, with minus without): the module unit lets residual-line gold be found; dev L2 nDCG@10 +0.68 [+0.16, +1.27] and Recall@100 +2.00 [+0.68, +3.25]
(353 queries, two of which have only module gold), L3 +0.37 [-0.46, +1.22] and +2.11 [+1.13, +3.12]. When the gold has no module unit it is only a distractor and costs nDCG@10 -0.53 [-0.90, -0.21] (dev L2),
-1.91 [-2.76, -1.14] (dev L3), Recall@100 -1.8 and -1.4. On the six Verified repositories the effect is not distinguishable from zero for the first reading (-1.36 [-3.77, +0.79] nDCG@10) and negative for the distractor reading
at L3 (-5.3 [-7.7, -3.2]); the `units_all` reading gives the same signs. Unit-level and chunk-level scores are not on one footing (different candidate sets and gold counts) and are
reported side by side, not as a comparison of quality: the paired unit-minus-chunk difference on the same queries is +2.7 [-1.1, +6.8] nDCG@10 on the six Verified repositories and -3.4 [-5.2, -1.7] on the dev set.

**E2, label noise (L2).** Positives located in the snapshot: import-only 12.7% of dev L2 positives (332 of 2,615) and 6.2% of the Verified-six ones (11 of 177); comment- or docstring-only 2.6% and 1.1%; documentation files 0.2% and 0;
24.4% (dev) and 19.8% (Verified-six) of L2 positives overlap no line the patch edits (context windows around the edit). Rescored on the same queries (protocol reading, removed positives kept as not relevant;
`ignored` gives the same within 0.3 points):

| set | label set | queries kept | nDCG@10 | Recall@100 | change in nDCG@10 [95%] | change in Recall@100 |
|---|---|---|---|---|---|---|
| dev (355) | all | 355 | 19.3 | 41.8 | | |
| dev | content-cleaned | 355 | 20.7 | 47.3 | +1.40 [+0.86, +1.99] | +5.5 |
| dev | edit-overlap | 354 | 20.0 | 46.2 | +0.71 [+0.06, +1.30] | +4.2 |
| dev | both | 353 | 21.7 | 52.4 | +2.36 [+1.50, +3.24] | +10.5 |
| Verified 6 (83) | all | 83 | 13.4 | 44.2 | | |
| Verified 6 | content-cleaned | 83 | 14.0 | 46.8 | +0.62 [+0.06, +1.35] | +2.5 |
| Verified 6 | edit-overlap | 83 | 14.5 | 48.4 | +1.13 [-0.39, +3.13] | +4.2 |
| Verified 6 | both | 83 | 14.9 | 50.3 | +1.48 [-0.06, +3.52] | +6.1 |

Rank changes: the first-ranked positive moves for 9 of 355 (content) and 30 to 38 (edit) dev queries, median shift 0; scores rise mostly because the removed noisy positives were hard to find (import blocks have little text
to match). At unit level the same rules raise Recall@100 by 1.3 (content) and 10.4 (edit overlap) points on the dev set. Do conclusions flip? Of 24 tests per set (three comparisons x four label sets x two metrics; `e2_conclusions.csv`):
protocol minus filter-first never differs from zero; "unit-level is below chunk-level" on the dev set stays negative under every label set (Recall@100 becomes indistinguishable under edit overlap); the benefit of the module unit
(positive on dev, both metrics) becomes indistinguishable from zero under content cleaning and under both rules (the import-only positives it served are removed), and on the six Verified repositories the module-unit Recall@100
difference turns negative under content cleaning (-4.3 [-8.9, -0.2]) from indistinguishable. The verdict changes in three places only: the module-unit effect on the dev set (both metrics, under content cleaning and under both rules), the dev
unit-below-chunk Recall@100 difference (under edit overlap) and the Verified-six module-unit Recall@100 (under content cleaning); the first and the
third depend on whether import-only positives count as labels.

**What these do and do not show.** They show that our loader, tokeniser, BM25 and metric reproduce the benchmark's published BM25 numbers to the printed decimal, so later numbers can be read on the same ruler, provided the averaging
convention is stated (it moves Recall@100 by up to 5 points); that the k1/b surface is flat on the dev set; that the module unit buys reachability of residual-line gold at a small cost to everything else; and that
roughly one L2 positive in eight (dev) is an import block and one in four to five lies away from the edit. They do not show a granularity choice (ADR-004): unit and chunk metrics have different candidate sets and gold counts, Q39's
gold readings give the same signs but are two readings of an open definition, and the six Verified repositories give wide intervals (83 queries, a few repositories dominate). The dev set is a convenience sample of five projects
(Pro and Live data; Live labels come from a different pipeline, not checked here), so its levels do not transfer to Verified. The edited-line reading of the patch counts the neighbours of a pure insertion and takes base-commit
coordinates; the import/comment classifier is syntactic, and one author's reading of "noise" (a docstring-only chunk can be the right place for a documentation fix) is not a verdict on the labels. Nothing here is a decision.

## Pre-registered interpretation rules

Fixed in advance so results cannot be re-read after the fact:

- **Null result:** if nDCG differs across arms but resolved rate does not, the finding is "retrieval
  metrics are a leaky proxy for agent utility", supported by the failure-mode breakdown. It is not
  reframed as a positive. Three readings are reported together: agent robust to ordering; reasoning
  is the binding constraint; sample too small.
- **RQ3 power:** with n≈30 the binomial SE near a 30% resolve rate is ~8.4 pp. State the detectable
  effect size up front; report arms differing by ~3 pp as indistinguishable.
- **RQ2 claims** are about *which interventions matter and in what combination*, not about inventing
  an intervention.
