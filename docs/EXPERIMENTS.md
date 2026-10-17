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
| E-PILOT-LEAK | RQ2 (pilot, needs the training stack) | small encoder trained with versus without the instances of held-out and renamed repositories (the D1 rename-resolved overlap, 89 repositories in the candidate pool) | encoder, budget, seed, remaining pool, evaluation set | 3 | Verified nDCG@10 and Recall@100 of both encoders, paired; the difference is the leakage inflation | planned: waits for the training stack. What this would decide: whether current-name resolution (D1) matters for any reported number or is only hygiene, i.e. whether the pool filter's rename step has to be in the frozen configuration |
| E-PILOT-K | RQ2 (pilot) | consistency filter K in {10, 20, 40, none} and teacher in {CodeRankEmbed, SweRankEmbed-Small, BM25, agreement of two}, at a tiny budget | encoder, matched optimization budget, pool, seed | 3 | retrieval metrics per cell with intervals; kept share per cell | planned: waits for the training stack. What this would decide: whether the FILTER and WEIGHT arms' K and teacher are sensitive settings, and which teacher can serve as the separately pretrained quality signal (ADR-002) |
| E-PILOT-NEG | RQ2 (pilot) | negatives: random repository-local, teacher-mined, graph-structural (callers, siblings, same-file units) | positives, budget, pool, seed | 3 | retrieval metrics; false-negative rate of each negative source on a labelled sample | planned: waits for the training stack and the graph role (Q30). What this would decide: whether graph-derived supervision belongs inside RQ2, and whether mined negatives carry label noise that FILTER would have to handle |
| E-PILOT-L3POS | RQ2 (pilot) | graph-derived test and configuration positives added to training | everything else, budget | 3 | L3 Recall@100 and L2 nDCG@10, paired with the run without them | planned: waits for the training stack. What this would decide: whether the L3-style positive (E-GRAPH-REACH, E-GRAPH-SIGNAL) is learnable from structure, i.e. whether an L3 arm is worth a place in RQ2 |
| E-PILOT-POOL | RQ2 (pilot) | training pool (SweLoc-style candidate pool, own PR-mined set, CodeSearchNet) at a fixed number of updates | encoder, budget, seed, filter | 3 | retrieval metrics per pool; unique examples seen | planned: waits for the training stack and ADR-001. What this would decide: which pool the frozen configuration uses, and how much of an arm difference is a pool difference |
| E-GRAPH-SIGNAL | RQ1 ext. (apparatus) | edge-family subset (19), seeds C (1, 3, 5), decay gamma (0.3, 0.5, 0.7), hops (1, 2), way of forming the scored list (edited list, ranked list fused by RRF) | reference BM25 over the units of the snapshot (module unit in), seeds are retrieved units, expansion limited to 50 units, seed 0, dev repositories for every sweep | n/a | change in nDCG@10 (L2) and Recall@100 (L3) against BM25 alone and against size-matched random expansions, paired 95% intervals | done (exploratory pilot, 2026-10-18; `RESULTS.md` rows `e3-*`; ADR-003 addendum) |
| E-GRAPH-WEIGHTS | RQ1 ext. (apparatus) | one weight per edge family fitted from data (pilot M reach table; leave-one-repository-out from E3 expansions) against the hand-set decay | as E-GRAPH-SIGNAL at C 5, 2 hops | n/a | paired difference against the hand-set decay, dev and three disjoint Verified repositories | done (exploratory pilot, 2026-10-18; rows `e4-*`) |
| E-RECENCY | RQ1 ext. (apparatus) | weight and time constant of a recency prior from `last_modified` (D8) added to BM25 | as E-GRAPH-SIGNAL | n/a | paired change against BM25 | done (exploratory pilot, 2026-10-18; rows `e5-*`) |
| E-GRAPH-FUSION | RQ1 ext. (apparatus) | dense encoder (CodeRankEmbed) and rank fusion BM25 + dense + graph | as above | n/a | as above | not run (CPU cost, open question Q42); code and tests exist (`ril/evaluation/e6_dense.py`, fusion arms of `e3_eval.py`) |
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

## E-GRAPH-SIGNAL (E3), E-GRAPH-WEIGHTS (E4), E-RECENCY (E5): exploratory pilots, done 2026-10-18

Configs in `configs/experiments/` (evaluation hashes in `results/logs/e_graph_signal_2026-10-18.json`): dev sweeps `e3_graph_signal.yaml` (`b0f36a22dd45`),
`e4_fitted_weights.yaml` (`4d633970aed5`), `e5_recency_prior.yaml` (`2eefba8d3a70`); Verified confirmations `e3_graph_signal_confirm.yaml` (`06e3ff78e1a0`),
`e4_fitted_weights_confirm.yaml` (`956ad364cdbf`), `e5_recency_prior_confirm.yaml` (`eaa5ce62950e`); instance cache hash `70b481631de4`. Tables:
`results/tables/e3_*.csv`, `e4_*.csv`, `e5_*.csv`. The cache (checkout, units, typed graph with history, BM25 scores, edge pairs, gold unit indices read from the pilot-E1 records)
was built on Ada (CPU, `u22`, 438 instances, about 90 minutes summed over four shards; `scripts/ada/e3_prepare.sbatch`); its BM25 ranks agree with pilot E1's unit ranks in
12,924 of 12,924 comparisons. The evaluation (`scripts/e3_run.py eval`, a few minutes) ran on the cache files locally. Licence: arrays and counts only, no text.

**Protocol (E3).** For each instance and level the units of the snapshot (module units included) are ranked by BM25 on the issue text. The top C units with a positive score are
the seeds (never gold). Over the chosen edge families (resolved edges, read as undirected; `inherit` includes `override`; `co_change` has support 3; `tests`, `configures`, `co_change`
are exploratory families) a breadth-first search gives every reached node its hop distance d <= h; a unit's score is the best over seeds of (seed score / best score) x gamma^d; at most
50 units are kept (an implementation limit so that a hub does not flood the list; not tuned). Two ways to form the scored list are run side by side and neither is chosen (open question
Q30): **list**, the BM25 list is edited (seeds, then the expansion in score order, then the rest of BM25), and **rrf**, the expansion (seeds as hop 0) is a second ranked list fused with
the BM25 list by reciprocal rank fusion (k = 60). **Controls** of the same expansion size, three draws per query: random units of the snapshot (`rand_whole`) and random units of the
seeds' files (`rand_files`, topped up from the snapshot when those files are small). Subsets: each family alone; import, invoke and co_change with the containment tree; all families
minus one; `core` (contain, import, invoke, inherit); `all`. Grid: C 1, 3, 5 x gamma 0.3, 0.5, 0.7 x 1 or 2 hops (gamma only reorders a 1-hop expansion, so those cells coincide).
Gold reading `units` (Q39) is primary; `units_all` and `units_nomod` (`units` without module units) are sensitivities; a query without gold under a reading is not scored under it. Mean
over queries (micro) and mean of the repository means (macro) are in every table (Q40); intervals are 95% percentile bootstraps over queries (2,000 draws, one set of resamples per group,
so comparisons are paired). **Tuning discipline:** every sweep ran on the dev repositories (Pro openlibrary and qutebrowser; Live conan, haystack, streamlink; 353 L2 and 155 L3 queries).
The evaluation refuses to touch a test instance unless the specification is a single-setting confirmation, and the setting was written to the config (and committed) before any test instance
was prepared or scored. **Selection criterion (stated before the confirmation run):** the cell maximising (L2 nDCG@10 gain + L3 Recall@100 gain) / 2 over BM25 for subset `core`, gold `units`,
micro average: C 5, gamma 0.5, 2 hops, for both list forms. That cell sits at the edge of the grid (largest C and hops), so a larger C or more hops may do better; not explored.

**E3 results at the chosen cell, list form, gold `units`, micro (percentage points; 95% interval).** BM25 alone: dev 15.8 nDCG@10 (L2) and 35.6 Recall@100 (L3); Verified six 16.1 and 30.7
(83 L2 and 55 L3 queries). "Same-file" is the chance control that keeps the file locality of the seeds (random units of the seeds' files).

| edge subset | dev L2 vs BM25 | dev L2 vs same-file random | dev L3 vs BM25 | dev L3 vs same-file random | Verified-6 L2 vs BM25 | Verified-6 L2 vs same-file | Verified-6 L3 vs BM25 | Verified-6 L3 vs same-file |
|---|---|---|---|---|---|---|---|---|
| contain | +4.1 [+2.9, +5.2] | +4.3 [+3.2, +5.4] | +9.0 [+6.7, +11.4] | +2.2 [+0.7, +3.8] | +1.7 [-0.3, +4.1] | +2.9 [+1.1, +5.0] | +7.0 [+3.0, +11.5] | +3.6 [+0.4, +6.8] |
| import | -0.7 [-1.2, -0.3] | -1.0 [-1.5, -0.5] | -0.1 [-1.0, +0.8] | -2.3 [-4.0, -0.9] | -1.2 [-2.1, -0.4] | -0.2 [-0.7, +0.2] | -2.4 [-4.6, -0.6] | -5.4 [-8.6, -2.7] |
| invoke | +0.7 [-0.1, +1.5] | +0.9 [+0.1, +1.7] | +7.2 [+5.3, +9.3] | +1.3 [-1.1, +3.6] | -0.3 [-1.6, +1.1] | +0.8 [-0.2, +2.0] | +1.0 [-1.7, +3.7] | -2.0 [-5.6, +1.2] |
| inherit | -0.4 [-0.7, -0.1] | -0.1 [-0.4, +0.1] | -0.0 [-0.2, +0.2] | -0.3 [-0.6, -0.0] | -0.1 [-0.5, +0.3] | +0.2 [-0.3, +0.8] | -0.3 [-0.6, -0.0] | -1.1 [-2.0, -0.3] |
| tests | -0.9 [-1.6, -0.4] | -1.0 [-1.5, -0.3] | +2.0 [+1.0, +3.0] | +0.1 [-1.1, +1.3] | -0.6 [-1.8, +0.7] | +0.4 [-0.2, +1.4] | +0.3 [-1.2, +1.9] | -1.4 [-4.5, +1.2] |
| configures | -0.2 [-0.4, -0.1] | -0.1 [-0.2, -0.0] | -0.2 [-0.4, +0.0] | -0.3 [-0.6, +0.0] | -0.2 [-0.5, +0.0] | -0.0 [-0.1, +0.0] | -0.2 [-0.6, +0.0] | -0.4 [-1.0, +0.0] |
| co_change | -0.4 [-0.7, -0.1] | -0.3 [-0.6, -0.1] | -0.6 [-1.2, +0.0] | -1.8 [-3.3, -0.5] | -0.2 [-1.0, +0.6] | +0.3 [-0.0, +0.9] | -2.2 [-4.0, -0.8] | -3.1 [-5.8, -0.4] |
| invoke+contain | +1.9 [+1.1, +2.7] | +2.0 [+1.2, +2.9] | +12.8 [+10.4, +15.5] | +5.7 [+3.2, +8.1] | +0.7 [-1.1, +2.9] | +1.7 [+0.1, +3.7] | +5.0 [+1.4, +8.9] | +1.3 [-2.2, +4.7] |
| core | +1.8 [+1.0, +2.6] | +2.0 [+1.2, +2.9] | +11.9 [+9.6, +14.4] | +5.1 [+2.7, +7.5] | -0.0 [-1.4, +1.6] | +0.6 [-0.5, +2.1] | +4.4 [+1.1, +8.1] | +1.0 [-2.7, +4.5] |
| all | +1.7 [+1.0, +2.5] | +2.0 [+1.1, +2.8] | +11.2 [+9.0, +13.5] | +4.4 [+2.1, +6.9] | -0.2 [-1.5, +1.3] | +0.6 [-0.5, +1.9] | +3.1 [-0.6, +7.2] | -0.2 [-3.8, +3.2] |
| all-minus-contain | +0.4 [-0.4, +1.2] | +0.9 [+0.1, +1.6] | +6.9 [+5.0, +9.0] | +0.8 [-1.7, +3.1] | -0.3 [-1.7, +1.2] | +0.7 [-0.0, +1.8] | -0.3 [-2.9, +2.4] | -3.6 [-6.9, -0.7] |
| all-minus-invoke | +2.1 [+1.3, +3.0] | +2.2 [+1.3, +3.2] | +9.6 [+7.5, +11.9] | +3.0 [+0.6, +5.5] | +0.0 [-1.3, +1.6] | +0.8 [-0.4, +2.3] | +2.9 [-0.8, +6.9] | -1.6 [-5.7, +2.0] |

The ranked-list (rrf) form gives the same Recall@100 at L3 and smaller nDCG@10 gains at L2 (contain +1.9 [+1.2, +2.6] on dev and +0.5 [-1.0, +2.1] on Verified against BM25; `core` +1.7 and
+0.6); the full tables are in the CSV files. Expansion sizes at the cell (dev, mean units added per query): contain 40 (L2) and 44 (L3), invoke 45 and 43, import 23 and 19, tests 17 and 8,
co_change 9, inherit 4 and 3, configures 1; share of the added units that are gold: 6% (contain, L2), 3% (invoke, L2), 14% and 13% at L3 (`e3_dev_setting_expansion.csv`).

**What E3 shows, at this scale.** (1) Graph expansion from retrieved seeds improves BM25 on the dev repositories, mostly at L3 Recall@100 (`core` +11.9 [+9.6, +14.4]) and less at L2 nDCG@10
(+1.8 [+1.0, +2.6]). A random expansion of the same size is not neutral: it is not a null, because 50 added units push BM25's own tail down only slowly, which is why the controls matter. Against
random units of the seeds' files the gain of `core` is +2.0 [+1.2, +2.9] (L2) and +5.1 [+2.7, +7.5] (L3). (2) **Containment carries most of the signal.** Alone, `contain` is the one family
clearly above same-file chance at L2 (+4.3 [+3.2, +5.4]) and above it at L3 (+2.2 [+0.7, +3.8]); removing it from `all` costs 1.3 [0.7, 2.1] nDCG@10 (L2) and 4.2 [2.7, 5.9] Recall@100
(L3) on dev, and 3.4 [1.5, 5.8] Recall@100 (L3) on Verified (L2 on Verified: +0.1 [-0.7, +1.2], not distinguishable). The order is contain > invoke > the rest. `invoke` alone is only
slightly above same-file chance at L2 (+0.9 [+0.1, +1.7]) and not at L3 (+1.3 [-1.1, +3.6]), but it adds to `all` at L3 on dev (+1.6 [+0.4, +2.8]) and not on Verified (+0.2 [-0.6, +1.2]);
`import`, `inherit`, `tests`, `configures` and `co_change` are at or below zero at L2 and below same-file chance at L3 (co_change -3.1 [-5.8, -0.4] on Verified; `tests` gains +2.0 [+1.0, +3.0]
over BM25 at L3 on dev but equals same-file chance). This is the direction of SpIDER's observation (exploration mainly along containment) and not of LocAgent's ablation (containment weak),
**for this graph, these seeds and this metric**; see the limits. (3) The confirmation on the Verified six has the same direction and is smaller: `contain` is above same-file chance (+2.9
[+1.1, +5.0] at L2, +3.6 [+0.4, +6.8] at L3) but its gain over BM25 at L2 is +1.7 [-0.3, +4.1], and `core` and `all` are not distinguishable from same-file chance at L3 (+1.0 [-2.7, +4.5], -0.2
[-3.8, +3.2]); with 83 and 55 queries, mostly matplotlib and astropy, the intervals are wide. Per repository (dev, `e3_dev_setting_compare.csv`): `contain` gains on every repository at L2
except streamlink (-0.4 against BM25 on 37 queries); the `invoke` gain at L3 is large in openlibrary (+9.6) and absent against same-file chance in qutebrowser (+4.7 against BM25, -1.9 against chance).

**Sensitivities.** Gold `units_all`: contain +3.8 [+2.6, +5.0] and +8.9 [+6.6, +11.1] over BM25, +4.9 and +2.8 over same-file chance. Gold without module units (`units_nomod`; module units are
the import-only positives, 12.7% of dev L2 positives, Q41): contain +2.8 [+1.7, +3.9] and +8.1 [+5.8, +10.5] over BM25, +2.9 [+1.9, +4.0] over same-file chance at L2, and **+1.2 [-0.4, +2.8] at
L3, no longer distinguishable**: part of the L3 containment gain is the module unit of a file entering the list. Macro (repository-mean) averages differ from the micro ones by at most 0.5
points. Gamma matters little (cells with the same expansion set coincide for one hop); larger C and two hops are better on dev (`e3_dev_grid_compare.csv`).

**E3 does not show** that graph expansion belongs in the retrieval stack or in which role (Q30, ADR-003): the effect is measured on BM25 seeds only (a stronger first stage leaves less to
gain), over 50 added units that displace BM25's ranks 6 to 55, in a list form chosen for the pilot; beating the random controls says the structure is better than nothing, not better than a
second retriever. It does not show a general statement about containment: with these units (a class's source holds its methods; the module unit is the residual of a file; a seed method reaches
its class, then the file) containment is a file and class locality signal, the controls remove only the file part of that, `invoke` edges cover 28% to 72% of call sites (ADR-012) so its weakness
may be a recall limit of the resolver, and the dev repositories are five projects whose labels come from two different pipelines. The L3 gain is a gain on model-judged positives. The design note (`docs/GRAPH_DESIGN.md` section 5) proposed a fixed-length budget (the expanded list as long as the seed list) and the three
parts of containment (directory to file, file to definition, class to method) as separate arms; neither was run (here up to 50 units are added, and containment is one family), so the
SpIDER-style fixed-budget reading of the question is still open. Nothing here chooses an edge taxonomy, a graph role or a fusion method.

**E4, fitted weights.** One weight per edge family, multiplied along the path; the best family of every fit gets the hand-set 0.5, so a fit differs from the hand-set run only in the relative
weights (`results/tables/e4_fitted_weights.csv`). `fit_reach` uses the share of new L3 positives within two hops of the L2 units over each family alone (pilot M; flask, requests, seaborn): contain
0.5, invoke 0.37, import 0.13, inherit 0.06, co_change 0.04, tests and configures 0. `fit_excess` uses the excess over same-file chance: invoke 0.5, inherit 0.16, contain 0.16, co_change 0.02,
import, tests, configures 0. `loro_<repo>` is fitted on the other four dev repositories from the E3 expansions (share of the added units that are gold) and is evaluated only on the repository it
was not fitted on. All fits were fixed before they were scored. Dev (353 L2, 155 L3), `all` families, list form, C 5, 2 hops, paired difference against the hand-set 0.5: `fit_reach` +2.1 [+1.3,
+3.0] nDCG@10 (L2) and +1.1 [-0.2, +2.3] Recall@100 (L3); the cross-repository leave-one-out fit +2.2 [+1.4, +3.1] and +0.3 [-1.1, +1.7]; `fit_excess` -1.0 [-1.7, -0.4] and -1.4 [-3.1, +0.1].
`fit_reach` was confirmed on the three Verified repositories that were not used for the fit (astropy, matplotlib, xarray; 72 L2, 48 L3 queries): +2.0 [+0.4, +3.9] and +1.6 [-0.2, +4.2] against
the hand-set 0.5 for `all`, +1.8 [+0.4, +3.7] and +0.2 [-0.8, +1.4] for `core`. **Shows:** weighting containment above the other families helps at L2 (about 2 points of nDCG@10, in the dev data,
in a cross-repository fit and on three unseen repositories) and does not change L3; the excess-over-chance fit, which gives containment little weight, is worse. **Does not show:** that fitted
weights beat a tuned hand-set weighting (the hand-set run gives every family 0.5 and was not tuned per family; a hand-set contain-heavy vector may do as well, and the weight vectors of the two
good fits are close), or anything about weights fitted on a larger or different population. The reach fit rests on 7 instances, so the E4 Verified rows leave out their repositories.

**E5, recency prior.** Score = BM25 / best BM25 + lam x exp(-age / tau); age is the snapshot commit's time minus the last commit time of the file at or before the snapshot (D8; 98 of 2.9 million
snapshot units have no history; a stamp after the snapshot raises, and `tests/leakage/test_recency_leakage.py` checks the history of an older checkout of a repository that has later commits).
Dev grid lam 0.02, 0.05, 0.1, 0.2, 0.5 x tau 30, 90, 365 days: the gains are small and peak at lam 0.2, tau 30 days (selection criterion as for E3): nDCG@10 +0.83 [+0.22, +1.41] and Recall@100
+2.27 [+1.09, +3.63] at L2; +2.53 [+1.20, +3.88] and +2.37 [+1.02, +3.70] at L3; lam 0.5 loses the gain and short time constants beat long ones. On the Verified six the stated setting gives
nDCG@10 +1.48 [-0.67, +4.01] (L2) and +1.37 [-0.83, +3.52] (L3) and Recall@100 -0.26 [-4.74, +4.50] and -0.19 [-2.61, +1.91]: the same sign for nDCG@10, not distinguishable from zero.
**Shows:** at our scale a recency prior moves BM25 by a point or two on repositories whose fixes land in recently touched files, with a direction that survives on Verified for nDCG@10 and no
more. **Does not show** the temporal-anchor effect of GREPO (which anchors on issue time, a different quantity and benchmark); the prior uses the age of a file, not of a unit, and the dev
repositories are active projects. No setting is recommended.

**E6 (CodeRankEmbed on the same units; BM25 + dense + graph by rank fusion): not run.** Allowed only on CPU. Measured (job 25855, 4 CPUs of `u22`): 0.85 code chunks of 1,500 characters per second
(about 340 tokens per second). The dev snapshots hold about 52,000 distinct unit texts (6,400 to 14,800 per repository, mean 900 to 1,700 characters; job 25857, six spread snapshots each), so the
dev set alone is roughly 30 hours of CPU encoding at the model's own 512-token cut, and any shorter cut or smaller model would be a different, lower-fidelity experiment. Nothing was substituted;
the alternatives are recorded as an open question (Q42). What exists: `ril/evaluation/e6_dense.py` (unit texts to cosine scores, a store keyed by the text hash, tested with a stand-in encoder),
the `fusion` arms of `e3_eval.py` (dense alone, BM25 + dense by RRF, the graph on top of the fusion, with the same chance controls; tested on random scores) and
`scripts/ada/e6_probe.sbatch` (environment; the model's repository code needs `transformers` 4.44.2 and runs its own modelling code, `trust_remote_code`).

**Latency.** Real stages through the harness (`ril/bench/retrieval_measure.py`; query sets `retrieval-<repo>-v1` of 200 queries made of identifier words, batch size 1, local Apple M3): `bm25` p50
0.040 ms on 974 units (flask), 0.037 on 678 (requests), 0.202 on 35,860 (django); `graph_expand_2hop` p50 / p95 / p99 0.110 / 0.214 / 0.521 ms (flask), 0.145 / 0.192 / 0.216 (requests), 0.463 /
1.394 / 2.421 (django); `graph_expansion` (BM25 plus 2-hop expansion from three seeds, at most 50 units) 0.149 / 0.259 / 0.561, 0.170 / 0.220 / 0.241 and 1.140 / 2.135 / 2.854 ms (warm). These
are stage costs of this implementation on one machine; none is a regression claim.

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
