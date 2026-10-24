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
- **Averaging (decision D17, 2026-10-18):** the primary number is the mean over queries with repository-clustered
  bootstrap intervals; the mean of folder means appears only in the table that reproduces the published BM25 rows (ADR-005).
- **Gold readings (decision D18, 2026-10-18, provisional):** a chunk's positive counts for every unit it overlaps; the reading
  without module-residual positives is primary for design decisions about the graph, the CORE-Bench-faithful reading (with
  them) is reported beside it (ADR-004).

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
| E-CLASS-SOURCE | RQ1 ext. (apparatus) | class unit `source` form (full, header, header plus method signatures; Q28, `provisional: ADR-013`) | units, ids, spans, gold mapping, BM25 parameters, the pilot-E3 grid and cache, seed 0, dev repositories for the sweep | n/a | BM25 and expansion nDCG@10 (L2) and Recall@100 (L3) per form, query-level and repository-clustered intervals, four gold readings; index size and build time | done (exploratory, 2026-10-23; rows `x1-class-source-*`; ADR-013 addendum). Dev rule kept `full` |
| E-AMBIG-POLICY | RQ1 ext. (apparatus) | policy for ambiguous `invoke` sites read from the stored graph (keep, drop, rebucket by receiver evidence, keep sets of at most three; Q35, Q36) | as E-CLASS-SOURCE, form `full` | n/a | retrieval effect per policy; edge precision and recall per policy by the dynamic oracle (flask) and Jedi (300 stratified sites of requests and streamlink) | done (exploratory, 2026-10-23; rows `x1-ambig-*`; ADR-011 addendum). Dev rule kept `drop` |
| E-L3-CENSUS | RQ1 ext., RQ2 (apparatus) | none (count of positives by kind, repository and file novelty) | pilot-E1 unit records; D9 path rule | n/a (bootstrap seed 0) | positives by kind; share of L3 positives in files without L2 positives, instance-bootstrap intervals | done (2026-10-23; rows `x1-l3-census`, `x1-l3-census-extended`): 438 cached instances, then all 540 Python L3 instances with base commits |
| E-POOL-CHECK | RQ2 (apparatus, pool) | none (measurement of the candidate pool `gangiswag/train_data` python) | the pool as published | n/a (sample seed 0) | directory structure, positives and functions per instance, (repository, PR) overlap with CORE-Bench and Verified | done (exploratory, 2026-10-18; `RESULTS.md` row `x-pool-check`) |
| E-POWER | RQ2, RQ3 (apparatus) | n, discordance, effect, run-to-run SD, per-query SD, correlation, seeds | alpha 0.05, power 0.8 | n/a (simulation seed 0) | power and minimum detectable effects (calculation, no data) | done (2026-10-18; row `x-power`) |
| E-CONTAM-PROBE | RQ2/RQ3 (apparatus, contamination) | shard slice (every 10th of 240), hash level (text, syntax tree) | probe set = functions of the 12 Verified repositories at 499 base commits | n/a | function-hash matches against CoRNStack `document`, by size of function; feasibility and cost of the full scan | done as a slice (exploratory, 2026-10-18; rows `x-contam-probe-slice`, `x-contam-throughput`) |
| E-DENSE-FUSION (was E-GRAPH-FUSION) | RQ1 ext. (apparatus), ADR-006, Q30 | encoder (CodeRankEmbed, Qwen3-Embedding-0.6B; `provisional: ADR-006`), cut (512, 1024 tokens; dev only), first stage (BM25, dense, RRF(BM25, dense) with k swept on dev, score-level BM25+dense), graph on top of the strongest first stage (edited list, graph as a third RRF list, score-level with weight swept on dev; core families and each family alone) | units and gold of the pilot-E3 cache, class form `full`, ambiguous sites `drop`, seeds are retrieved units, expansion at most 50 units, seed 0, dev repositories for every sweep, one stated setting on the Verified-six | n/a | nDCG@10 (L2) and Recall@100 (L3) at unit level (both D18 readings) and chunk level, query-level and repository-clustered intervals; graph cells against the first stage and size-matched chance controls; query-encode and flat-search latency p50/p95/p99 (CPU, GPU), encoding throughput and peak memory | running (2026-10-23; rows `x2-*`) |
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
(+1.8 [+1.0, +2.6]). The two controls behave differently, which is why both are reported: random units of the whole snapshot lower BM25 (for the size of the contain expansion by 2.5 nDCG@10 at L2 and 5.9
Recall@100 at L3: they displace BM25's ranks 6 to 55 with unrelated units), while random units of the seeds' files already gain at L3 (+6.8 for that size) because gold units cluster in
the seeds' files. Against random units of the seeds' files the gain of `core` is +2.0 [+1.2, +2.9] (L2) and +5.1 [+2.7, +7.5] (L3). (2) **Containment carries most of the signal.** Alone, `contain` is the one family
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

## E-POOL-CHECK, E-POWER, E-CONTAM-PROBE: pool, power and contamination measurements, done 2026-10-18

Configs `configs/experiments/x_pool_check.yaml`, `x_power.yaml`, `x_contam_probe.yaml`; logs `results/logs/x_pool_check_2026-10-18.json`, `x_power_2026-10-18.json`, `x_contam_probe_2026-10-18.json`;
tables `results/tables/x_pool_check_*.csv`, `x_power_*.csv`, `x_contam_probe_slice.csv`; rows `x-*` in `RESULTS.md`. Exploratory: they measure and calculate, they choose nothing (ADR-001 and the
others stay open). Licence: counts, ids and hashes only; no query, function or code text was kept.

### E-POOL-CHECK: what `gangiswag/train_data` (python) contains

Method: the member table of `train.zip` (listing of 2026-10-17), then one HTTP range request per instance directory for its query and qrels members (24,285 of 24,285 read, 0 fetch errors, 33 minutes at
12 threads, CPU only), and the corpus of a sample of 300 directories chosen by the order of sha256("0:<directory>"). Nothing else was downloaded. Overlap is by (canonical repository, PR number); the
reference sets are the CORE-Bench L2 and L3 query ids (the Rewrite folders carry the same ids) and the 500 Verified instances.

- **What a directory is.** One pull request: `<owner>__<name>-<PR>` with one query (the issue text, `metadata` = `repo` and `base_commit` only), a qrels file of binary positives (every row has score 1)
  and a corpus that lists the functions of the repository at the base commit. All 24,285 directories have exactly one query; the directory name agrees with the `repo` field in 24,285 of 24,285; the 24,285 (repository, PR) pairs are distinct over 2,448 repositories.
- **Positives.** 307,996 qrels rows in total: mean 12.68 per directory, median 4, 95th percentile 42, maximum 3,924; none has zero. The sample (300): mean 9.22, median 3; all 2,765 positive ids occur in their corpus.
- **Functions per instance (sample of 300).** Corpus size mean 1,047, median 410, 5th to 95th percentile 48 to 4,750, minimum 24, maximum 15,584; function ids are unique within a corpus in 300 of 300.
  Nine of the 300 corpora have at most 40 functions (these pass a top-40 rank filter whatever the model).
- **Is the 24,285 before or after the top-40 filter (S2)?** Not decidable from this data; the facts are: no rank, score or filter field exists anywhere (query metadata has two keys, corpus rows carry `_id`, `title`, `text`,
  `metadata` with no keys). The SweRank+ table counts 49,973 "instances" for the Python row (an instance being a query with one modified function as positive); the directories hold 307,996 positive rows, 6.2 times as many. This
  is what the data would look like if the directories were the unfiltered pull requests with all their modified functions and the table counted what survived the filter (49,973 of 307,996 is 16.2%); it is also what it would look like if a
  "table instance" were not a (query, function) pair. Neither reading is confirmed. The earlier SweRank paper's Figure 5a shows a filter keeping about 28% of the instances at K=20 (plot reading, `knowledge/papers/swerank-2505.07849.md`), so a 16% survival at K=40 would be unusual
  but those are different pools and teachers. Cheapest experiment that would settle it: rank the positives of about 50 small directories under SweRankEmbed-Small and count how many fall outside the top 40 (about 1 hour of encoding of a few thousand functions on CPU; not run, it needs the encoder and is a different job than a metadata check).
- **Creation dates.** None in the pool (`metadata` has `repo` and `base_commit`). The `created_at` values exist only for Verified (2013-01-25 to 2023-08-07, `knowledge/datasets/swe_bench_verified.md`); a date comparison would need a GitHub lookup of the pool's base commits, blocked without `GITHUB_TOKEN`.
- **Same-PR overlap (direct leakage).** 60 pairs with CORE-Bench L2, all in sub-datasets SWE-bench-Live (56) and SWE-Bench-plus-plus (4), over 18 repositories (cfn-lint 9, haystack 7, trimesh 7, weasyprint 6, faker 5, python-telegram-bot 5, streamlink 5, and eleven others with 1 or 2);
  0 with L3 (any sub-dataset), 0 with Verified (0 of 500 by (repository, PR), 0 of 500 by base commit), 0 with Multi-SWE-bench, SWE-bench-plus, Multilingual. With the owner ignored (sensitivity for renamed or moved repositories) 63 pairs. The Pro ids contain a hash, not a PR number, and cannot be compared this way (632 L2, 585 L3 ids).
  All 18 repositories are on the held-out list, so the repository-level filter removes these 60 pull requests; the check adds no instance beyond the filter, and it shows that without the filter 60 CORE-Bench L2 queries would have had their own pull request in the training pool.

### E-POWER: calculations, assumptions explicit

Two-sided, alpha 0.05, power target 0.8. Seed 0, `ril/evaluation/power.py` (`scripts/power_analysis.py`); the closed forms were checked by simulation (below). Nothing here chooses an n, a design or a number of runs.

**Paired resolved rate, exact McNemar.** n instances, two conditions; d = share of instances on which the two conditions disagree (discordance), effect = difference in resolved rate. P(only the second resolves) = (d + effect)/2, P(only the first) = (d - effect)/2.
The test is the exact binomial test on the disagreeing instances (doubled tail). The power depends on n, d and the effect only; the baseline resolved rate (0.2 to 0.6) only limits which (d, effect) pairs exist, and all 75 combinations of baseline 0.2 to 0.6, d 0.10 to 0.30 and effect 2 to 10 points are feasible (`x_power_mcnemar_feasibility.csv`). The minimum detectable effect is the smallest effect on a 0.25-point grid from which the power stays at or above 0.8 (the exact test's power is not monotone).

| n | discordance | power at 2 pts | 4 pts | 6 pts | 8 pts | 10 pts | minimum detectable effect (points, power 0.8) |
|---|---|---|---|---|---|---|---|
| 302 | 0.1 | 0.14 | 0.53 | 0.90 | 1.00 | 1.00 | 5.5 |
| 302 | 0.2 | 0.10 | 0.30 | 0.61 | 0.86 | 0.97 | 7.5 |
| 302 | 0.3 | 0.08 | 0.21 | 0.44 | 0.69 | 0.88 | 9.25 |
| 432 | 0.1 | 0.22 | 0.72 | 0.98 | 1.00 | 1.00 | 4.5 |
| 432 | 0.2 | 0.13 | 0.42 | 0.77 | 0.96 | 1.00 | 6.25 |
| 432 | 0.3 | 0.10 | 0.30 | 0.59 | 0.85 | 0.96 | 7.75 |
| 500 | 0.1 | 0.25 | 0.79 | 0.99 | 1.00 | 1.00 | 4.25 |
| 500 | 0.2 | 0.15 | 0.48 | 0.84 | 0.98 | 1.00 | 5.75 |
| 500 | 0.3 | 0.11 | 0.34 | 0.66 | 0.90 | 0.98 | 7.25 |

Reading: at n = 432 and a discordance of 0.20 the test detects a 6.25-point difference with 80% power and a 4-point difference with 42% power; at n = 302 a 4-point difference has 30% power. The discordance is not known before the runs (it is at least the effect and grows with run-to-run randomness); the row to read is chosen by the engineer's expectation, and the pilot runs of the agent give a first value.

**Run-to-run variation.** Read as the standard deviation (in points) of the overall resolved rate between repeated full passes of one condition; if ±2 to ±5 is meant as a half-range, the standard deviation is smaller and the tables scale linearly (minimum detectable difference = 2.80 x SD x sqrt(2/runs); runs needed = 2 x (2.80 x SD / effect)^2, rounded up; normal approximation, run noise only, the instance-sampling variance of the paired comparison is not added).

Minimum detectable difference between two conditions (points) with r runs per condition:

| run-to-run SD (points) | 1 run | 2 | 3 | 5 | 10 |
|---|---|---|---|---|---|
| 2 | 7.92 | 5.6 | 4.57 | 3.54 | 2.51 |
| 3 | 11.89 | 8.4 | 6.86 | 5.32 | 3.76 |
| 4 | 15.85 | 11.21 | 9.15 | 7.09 | 5.01 |
| 5 | 19.81 | 14.01 | 11.44 | 8.86 | 6.26 |

Runs per condition needed to detect an effect (points) at 80% power:

| run-to-run SD (points) | effect 2 pts | 4 | 6 | 8 | 10 |
|---|---|---|---|---|---|
| 2 | 16 | 4 | 2 | 1 | 1 |
| 3 | 36 | 9 | 4 | 3 | 2 |
| 4 | 63 | 16 | 7 | 4 | 3 |
| 5 | 99 | 25 | 11 | 7 | 4 |

**Paired bootstrap of nDCG@10.** Per-query scores of two retrievers with the same standard deviation and correlation rho; the 95% percentile bootstrap interval of the mean paired difference excludes zero; normal scores assumed (nDCG@10 is bounded and skewed, so these are approximations). Minimum detectable mean difference (nDCG@10 points, i.e. 0.01 = 1) at 80% power:

| n | per-query SD | rho 0.5 | rho 0.7 | rho 0.9 |
|---|---|---|---|---|
| 432 | 0.2 | 2.7 | 2.09 | 1.21 |
| 432 | 0.3 | 4.04 | 3.13 | 1.81 |
| 432 | 0.4 | 5.39 | 4.18 | 2.41 |
| 302 | 0.2 | 3.22 | 2.5 | 1.44 |
| 302 | 0.3 | 4.84 | 3.75 | 2.16 |
| 302 | 0.4 | 6.45 | 5.0 | 2.88 |

**Seeds.** Two arms with k training seeds each; the seed-to-seed standard deviation in the metric is the unit. Minimum detectable difference at 80% power (Monte Carlo, 200,000 draws per evaluation, bisection):

| seeds per arm | design | minimum detectable difference (seed SDs) |
|---|---|---|
| 3 | unpaired t | 3.07 |
| 3 | paired t, rho 0.5 | 3.26 |
| 3 | paired t, rho 0.8 | 2.06 |
| 5 | unpaired t | 2.03 |
| 5 | paired t, rho 0.5 | 1.69 |
| 5 | paired t, rho 0.8 | 1.06 |

With three seeds per arm and independent seeds, two arms must differ by about 3.1 seed standard deviations to be detected by a t-test; arms closer than that are indistinguishable at this sample size, which is the project's overlap-within-one-SD rule stated as a number.

**Validation.** Exact McNemar versus 20,000 simulated multinomial experiments at four cells: differences within 0.71 standard errors (|z| at most 0.71); the percentile paired bootstrap simulated at its analytic minimum (400 datasets x 1,000 resamples, three cells) gave power 0.825, 0.783, 0.825 for a target of 0.80 (within 1.4 standard errors). `tests/unit/test_power.py` also compares the closed form with full enumeration for small n.

### E-CONTAM-PROBE: feasibility, probe and a measured slice

**Corpus (metadata and stream measurements).** `cornstack-python-v1` (Nomic organisation on the Hub): 240 shards `shard-00000` to `shard-00239` `.jsonl.gz`, 307.6 GB compressed (0.74 to 1.35 GB each; the 38 shards and 49 GB of the earlier dataset note were a mistake from reading one listing page; corrected in `knowledge/datasets/cornstack.md`).
Row fields in every row measured: `query`, `document`, `document_rank`, `document_score`, `metadata`, `negatives` (100 or 101 strings), `negative_scores`; no repository field. A shard holds 100,000 rows in the 24 shards scanned, so the corpus is about 24 million rows (23.9 million if the last shard is short; extrapolation).

**Throughput (job 25862).** Streaming 200 MB of compressed stream (about 15,000 to 16,000 rows) and hashing the `document` of every row took 23.3 to 24.8 s on 2 CPUs (network 4.3 to 7.3 s, inflate 6 s, JSON parse and hashing 11 to 13 s). Whole shards in the scan ran 135 to 648 s each on 4 workers sharing a node (network read 26 to 502 s; the network share varied most).
That gives about 0.12 CPU-seconds per compressed MB, about 10 CPU-hours for the 307.6 GB (about 2.6 hours on 4 CPUs if the network keeps up). Hashing the 100 negatives of every row as well: 174 s for 50 MB (29 times the cost per MB of the documents alone; 388,413 negatives in 3,882 rows), about 300 CPU-hours: not feasible here and not run.
The full documents-only scan fits the compute policy but not the time of this session; a systematic slice was run instead.

**Probe set.** `ril/training/contamination_index.py` with the existing parser (`parse_file`): every function and method unit (D6) of every `.py` file of the CodeUnit discovery rules at the 499 distinct base commits of the 500 Verified instances (12 repositories), read from the git object store once per blob
(834,651 file versions seen, 57,705 distinct parsed, 29 unparseable, 81 excluded by the rules): 1,688,434 function occurrences, 277,268 distinct text hashes, 222,020 distinct syntax-tree hashes (about 30 minutes on 2 CPUs). Two hash levels: layout-normalised text (docstring and comments kept) and syntax tree (docstring, decorators, comments, layout and quoting ignored; names and statements kept).

**Slice result (documents only; shards 0, 10, ..., 230 = 24 of 240; 2,400,000 rows, 2,327,498 documents with a syntax-tree hash).** 14,614 documents (0.61%) have the syntax-tree hash of a Verified function; 170 of them also match at the text level (the corpus documents mostly lack the docstring, which is the query, so a text match including the docstring is rare). 4,968 distinct hashes;
4,158 of the 14,614 hits belong to hashes that occur in more than one of the 12 repositories. By size of the matched function (syntax-tree nodes): under 20 nodes 10,680 (73%); 20 to 49 1,575; 50 to 99 1,127; 100 or more 1,232 (8.4%). Hits per repository (a hash shared by several repositories counts for each): sympy 6,488, astropy 5,228, django 5,016, scikit-learn 4,377, pylint 3,022, requests 2,782, xarray 2,109, pytest 2,082, matplotlib 1,794, sphinx 382, flask 133, seaborn 54.
Extrapolating the 10% systematic sample ten-fold would give the order of 10^5 hits and 10^4 large ones, but the shards are not known to be randomly ordered; no corpus-wide rate is claimed.

**What a hit does and does not mean.** A hit says that a function with this exact syntax tree (names and statements equal) occurs as the `document` of a CoRNStack row; the function may come from the repository at a different commit than the Verified base commit (the probe set is the union over 499 snapshots), from a fork or vendored copy, or be a generic function that many repositories contain (73% of hits are very small functions; a quarter of hit records match several repositories).
It does not say that the (query, document) pair was in any model's training data, that the Verified issue was seen, or that the model memorised anything; the retriever trained on it (CodeRankEmbed) is not the project's encoder choice (ADR-006 open). A non-hit does not show absence: renamed or edited copies, functions in the unscanned 90% of shards and the negatives field are not covered. A defensible reading is limited to the larger hits: how many of the 1,232 hits of 100 or more nodes are Verified functions at the instances'
own base commits (not the union) was not computed.

Reproduce: `scripts/ada/README.md` ("Pool check and contamination probe"). The slice command is `contam_scan.sbatch` with `STRIDE=10`; `STRIDE=1` runs the full documents-only scan.

**Next (decision D23, 2026-10-18).** The full documents-only scan (`STRIDE=1`) runs in the background, with hits restricted to
functions at the instance's own base commit and above a size floor stated before the full result is read; counts per
repository. The probe is not part of the frozen evaluation: it supports the contamination statement of the report only, and a
hit is not proof that a pair was trained on (ADR-005 addendum).

## E-CLASS-SOURCE, E-AMBIG-POLICY, E-L3-CENSUS and the E-GRAPH-SIGNAL headline under decision D18: exploratory, done 2026-10-23

Configs `configs/experiments/x1_structure_dev.yaml` (hash `3041c6121f78`; the dev sweep and the two selection rules, written before
any run), `x1_headline_dev.yaml` (`7c42ce178063`), `x1_headline_confirm.yaml` (`063d649a918c`; the Verified setting, committed before
any Verified extras existed), `x1_l3_census.yaml` (`3244f8775b83`). Log `results/logs/x1_structure_2026-10-23.json` (job ids, hashes,
hardware, alignment checks), readers `results/logs/x1_oracle_flask_2026-10-23.json` and `x1_jedi_policy_2026-10-23.json`; tables
`results/tables/x1_*`. Code: `ril/parsing/ambiguity_policy.py`, the class-source forms in `ril/parsing/repository_parser.py`,
`ril/evaluation/{x1_prepare,x1_eval,policy_readers}.py`, `ril/analysis/{x1_tables,l3_census}.py`; jobs `scripts/ada/x1_prepare.sbatch`,
`x1_census.sbatch`. Licence: arrays, counts, ids and paths only.

**Protocol.** One extras file per instance (Ada, CPU; 355 dev and 83 Verified-six instances, no failures) holds the BM25 scores of
the issue text under each class-unit source form, the index size and build time of each form, every ambiguous `invoke` site with
its candidate set and receiver evidence, and four gold readings. The evaluation merges it with the pilot-E3 cache of the same
instance and refuses to score unless the `full`-form scores equal the cached BM25 scores and the resolved invoke pairs agree in
number (438 of 438 agree). It then runs the pilot-E3 grid unchanged (seeds, hop decay, the 50-unit cap, both list forms, both chance
controls), so a variant differs from pilot E3 only in the class text or in which ambiguous sites become edges. Variant `full`
with policy `drop` *is* pilot E3: under gold `units` it reproduces every pilot-E3 number (for example `contain` +4.1 [+2.9, +5.2]
nDCG@10 at L2 on dev, `core` -0.0 [-1.4, +1.6] at L2 on Verified). **Gold readings:** `units_all_nomod` (every overlapped unit, module
units removed) is primary (D18); `units_all` (CORE-Bench-faithful) is beside it; pilot M's mapping `units` (functions or methods a chunk
overlaps, else the class, else the module unit) continues pilot E3. **Averages:** mean over queries with two 95% intervals,
query-level (`micro`) and repository-clustered (`cluster`, D17). Dev has five repositories at L2 but only **two at L3** (openlibrary,
qutebrowser): a clustered interval over two clusters is not informative (it can be narrower than the query-level one) and the L3
text quotes the query-level interval. **Tuning discipline:** every variant ran on dev only; the selection rules were in the config
before the first run; Verified ran one stated setting. The `pol_rebucket_nofixture` variant is a dev-only sensitivity.

**Class-unit source forms (Q28).** `full` = the whole class span; `header` = the class span without its methods (decorators,
`class` line, docstring, every class-level statement wherever it stands); `header_sigs` = `header` plus each method's decorators
and `def` line(s). Ids, spans and every other field are identical across forms, so the unit count and the gold mapping are too.

Dev (351 L2, 155 L3 queries), difference against `full` (percentage points; query-level interval, clustered interval at L2):

| gold reading | ranking | `full` (L2 nDCG@10 / L3 Recall@100) | `header` L2 | `header` L3 | `header_sigs` L2 | `header_sigs` L3 |
|---|---|---|---|---|---|---|
| `units_all_nomod` (primary) | BM25 alone | 21.2 / 37.5 | -2.3 [-3.4, -1.3] (cl. [-3.3, -1.2]) | -2.9 [-3.6, -2.1] | -2.9 [-3.8, -2.0] (cl. [-4.1, -1.8]) | -2.2 [-2.9, -1.6] |
| `units_all_nomod` | `contain` expansion | 23.5 / 45.1 | -2.2 [-3.6, -0.8] | -0.9 [-2.3, +0.4] | -2.9 [-4.2, -1.7] | -0.7 [-1.8, +0.4] |
| `units_all_nomod` | `core` expansion | 22.2 / 47.4 | -2.0 [-3.1, -0.8] (cl. [-3.1, -0.8]) | -1.7 [-3.1, -0.5] | -2.7 [-3.9, -1.6] (cl. [-4.1, -1.6]) | -2.0 [-3.2, -1.0] |
| `units_all` | BM25 alone | 21.0 / 36.8 | -2.6 [-3.7, -1.6] | -2.6 [-3.3, -1.9] | -3.1 [-4.1, -2.2] | -2.0 [-2.6, -1.4] |
| `units_all` | `core` expansion | 22.5 / 48.8 | -2.0 [-3.2, -0.8] | -2.0 [-3.3, -0.7] | -2.7 [-3.8, -1.6] | -2.0 [-3.1, -1.0] |
| `units` (pilot M mapping) | BM25 alone | 15.8 / 35.6 | -0.3 [-1.1, +0.4] | +0.3 [-0.3, +0.8] | +0.3 [-0.4, +1.0] | +0.4 [-0.1, +0.8] |
| `units` | `contain` expansion | 19.9 / 44.5 | -1.4 [-2.5, -0.3] | +0.7 [-0.6, +2.1] | -1.3 [-2.4, -0.3] | +0.8 [-0.3, +1.9] |
| `units` | `core` expansion | 17.6 / 47.5 | -0.2 [-1.1, +0.7] | -0.7 [-2.0, +0.5] | -0.2 [-1.1, +0.7] | -0.9 [-2.0, +0.1] |

Expansion cells: C 5, gamma 0.5, 2 hops, list form. Per repository (`units_all_nomod`, BM25 alone and `core`), `full` is ahead or level
in all five dev repositories (streamlink level). **Selection rule result** (`results/tables/x1_dev_selection.json`): `full` stays; neither
header form is eligible (both are below `full` at L2 and L3). **Index size and build time** (dev, median per snapshot over 355
snapshots; `results/tables/x1_dev_sizes.csv`): 5,195 units (755 class units) in every form; source text 5.73 M characters (`full`),
3.70 M (`header`, -35%), 4.01 M (`header_sigs`, -30%); BM25 tokens 517,550 / 332,714 (-36%) / 359,494 (-31%); postings 207,739 /
164,846 (-21%) / 174,660 (-16%); index arrays 3.42 / 2.73 / 2.89 MB; parse plus index build p50 2.83 / 2.45 / 2.53 s, p95 5.01 / 4.37 /
4.75 s (Ada Xeon E5-2640 v4, four shards sharing six CPUs: indicative, not a latency row). The graph does not depend on the form.

**What it shows.** Under the readings that count a unit as gold whenever a positive chunk overlaps it (D18 part 1), the full class
text is better by 2 to 3 points at both levels, for BM25 alone and after expansion. Most of that is the reading: a class whose method
is gold is itself gold under `units_all`, and only the full form contains the method's text. Under pilot M's mapping, where a class is
gold only when a chunk touches no method, the three forms are not distinguishable for BM25 or `core` (all intervals include 0), and
`header` costs 1.4 points at L2 only through the containment expansion. So the Q28 answer depends on D18 part 1, and the cost of `full`
is about 55% more indexed tokens and 26% more postings for text that the method units already hold. **Does not show** anything about a
dense encoder (truncation makes long class units behave differently; X2), or about chunk-level evaluation.

**Ambiguous-site policies (Q35, Q36).** Applied to the `invoke` family when the graph is read (`ril/parsing/ambiguity_policy.py`):
`keep` every candidate of every ambiguous site; `drop` none (pilot E3 as run read resolved edges only); `rebucket` drop a site whose
receiver carries evidence of a non-repository object (literal or builtin container assigned, `*args`/`**kwargs` name, an annotation
naming only builtin or imported external types after removing `Optional`/`Union`/container wrappers, an un-annotated parameter of a test
or fixture function in a test file) and keep the rest; `max3` keep sites with at most three candidates. The evidence rules are this
project's syntactic reading of the four kinds named in Q35, not type inference. Ambiguous sites are common: median per dev snapshot
1,168 (haystack) to 5,306 (conan) ambiguous sites against 8,744 to 25,600 resolved; the evidence rules fire on 6% (haystack) to 40%
(qutebrowser, mostly fixture parameters) of them (`results/tables/x1_dev_ambiguous.csv`).

Retrieval effect, dev, `full` form, gold `units_all_nomod`, list form at the pilot-E3 cell, difference against `drop`:

| policy | `invoke` L2 | `invoke` L3 | `core` L2 | `core` L3 | `invoke+contain` L3 |
|---|---|---|---|---|---|
| `keep` | -0.2 [-0.6, +0.1] | -2.9 [-4.2, -1.4] | -0.1 [-0.3, +0.1] | -2.4 [-3.5, -1.3] | -3.3 [-4.6, -1.9] |
| `rebucket` | -0.1 [-0.4, +0.2] | -2.1 [-3.4, -0.8] | +0.0 [-0.2, +0.2] | -1.6 [-2.7, -0.5] | -2.1 [-3.4, -0.9] |
| `rebucket` without the fixture rule (dev only) | -0.3 [-0.6, +0.1] | -2.3 [-3.6, -1.0] | -0.1 [-0.3, +0.1] | -2.2 [-3.4, -1.2] | -3.2 [-4.5, -1.8] |
| `max3` | -0.0 [-0.3, +0.2] | -0.4 [-1.4, +0.6] | -0.0 [-0.2, +0.2] | +0.1 [-0.4, +0.7] | -0.4 [-1.4, +0.4] |

The ordering (`max3` = `drop` > `rebucket` > `keep` at L3; nothing moves L2) is the same under all four gold readings; in the
clustered intervals `rebucket` at L3 includes 0 (`core` [-3.2, +0.1]). **Selection rule result:** `drop` stays; no candidate is eligible.

Edge quality per policy, read by two readers that are not the build author:

| reader, measure | `drop` | `keep` | `rebucket` | `max3` |
|---|---|---|---|---|
| dynamic oracle (flask suite, 1,057 in-repository caller-callee pairs): precision of invoke pairs whose caller executed (lower bound) | 0.616 (506/821) [0.583, 0.649] | 0.315 (694/2,205) [0.296, 0.334] | 0.450 (619/1,377) [0.423, 0.476] | 0.476 (671/1,409) [0.450, 0.502] |
| oracle: recall of all pairs / without implicit-protocol dunders (n 1,057 / 854; D15) | 0.479 / 0.592 | 0.657 / 0.813 | 0.586 / 0.725 | 0.635 / 0.786 |
| oracle: precision of the ambiguous pairs the policy adds / drops | - / 0.136 | 0.136 (188/1,384) / - | 0.203 (113/556) / 0.091 (75/828) | 0.281 (165/588) / 0.029 (23/796) |

Site level. Oracle, executed lines of the library (coverage.py): an in-repository candidate was observed for 29 of 50 executed sites
with at most three candidates (0.58 [0.44, 0.71]) and 2 of 33 with more (0.06 [0.02, 0.20]); 4 of 650 executed `external` sites had an
in-repository callee of that name (0.006 [0.002, 0.016]); 197 of 263 executed resolved sites had their pair observed (0.75 [0.69,
0.80]). In the test files (judged at caller level; no line coverage there) fixture-parameter sites had a candidate observed as often
as sites without evidence (97/433 = 0.22 [0.19, 0.27] against 95/392 = 0.24 [0.20, 0.29]): **the fixture rule does not separate
in-repository from external receivers in flask** (a fixture often returns the repository's own object). Jedi 0.20.1 on 300 stratified
sites (requests and the dev repository streamlink, 150 each, `results/tables/x1_jedi_policy_sample.csv`): resolved sites agree 48/50
(0.96 [0.87, 0.99]); `external` 40/40 answered external; re-bucketed (evidence) sites 24/25 answered external (0.96 [0.80, 0.99];
literal 21/21, annotated 4/4, fixture 0/1 answered); sites with at most three candidates 30/58 answered inside the set (0.52 [0.39,
0.64]; requests 27/36, streamlink 3/22), with more than three 4/20 (0.20 [0.08, 0.42], 30 of 50 unanswered); `unresolved` sites were
in-repository for Jedi in 30/44 answered (0.68). **What it shows.** Adding ambiguous candidates raises oracle recall (0.48 to 0.66)
and lowers pair precision (0.62 to 0.32); `max3` keeps most of the recall gain (0.64) at the best precision of the three, and its
dropped pairs are almost all wrong (0.03 supported). In retrieval none of the policies helps: at L3 every added ambiguous edge costs
Recall@100 in proportion to how many wrong edges it adds, and L2 does not move. The receiver-evidence rules are precise for literals and
annotations (Jedi) but those are few; the fixture rule, which fires most, is not supported by the oracle. **Does not show:** a policy
for other edge uses (training negatives, an agent tool), or the boundary between `external` and `unresolved` beyond the counts above
(Jedi reads 68% of `unresolved` sites as in-repository: the resolver's recall limit, not a bucket error).

**L3 positive census.** Every located positive of the 438 cached instances (210 with L3 qrels; `results/tables/x1_census_cached_*.csv`),
by kind of the unit it maps to (decision D9 path rule first: a positive in a test file is a test unit whatever its structure):

| set | L3 positives | function | method | class | module residual | test unit | non-Python (docs / config / data) | Python not parsed |
|---|---|---|---|---|---|---|---|---|
| dev (155 instances) | 3,253 | 1,170 | 941 | 111 | 444 | 482 | 86 (6 / 30 / 50) | 19 |
| Verified six (55) | 1,342 | 178 | 849 | 20 | 62 | 203 | 30 (2 / 0 / 28) | 0 |
| all (210) | 4,595 | 1,348 (29.3%) | 1,790 (39.0%) | 131 (2.9%) | 506 (11.0%) | 685 (14.9%) | 116 (2.5% [1.4, 4.0]) | 19 |

L2 for comparison (438 instances, 2,792 positives): no test units, 74 non-Python (2.7% [1.9, 3.5]), 586 module residuals (21.0%).
**Novelty:** of the L3 positives of instances that also have L2 positives, 37.7% [32.9, 42.5] (instance bootstrap) lie in a file
that holds no L2 positive (dev 29.5% [24.8, 34.4], Verified six 57.5% [49.5, 64.4]); 184 of 210 instances have at least one. Of those
1,731 new-file positives, 685 are test units (40%), 559 methods, 344 functions, 65 module residuals, 41 non-Python. Per repository the
new-file share runs from 28.9% (openlibrary) to 61.5% (xarray). **What it shows.** Test code is the largest structure beyond the edited
files that L3 asks for (15% of L3 positives, 40% of those in new files); configuration and documentation are rare (30 configuration and
8 documentation positives in 4,595); the pilot sample's 0 of 141 non-Python positives was a small-sample zero, the rate is about 2.5%.
**Extension beyond the cached instances** (`x1_l3_census.yaml`; Ada jobs 35503 and 35518, 2.7 CPU-hours): the six other Verified
repositories with L3 qrels (django 136, sympy 51, sphinx 26, scikit-learn 21, pytest 10, pylint 3 instances) and SWE-bench Pro ansible
(83), the one further Python repository with L3 qrels (Live has no L3 folders; Multi-SWE-bench and Multilingual are not Python), mapped
with the pilot-E1 unit stage; every positive located. All 540 Python L3 instances of the sub-datasets with base commits (all 302 Verified,
155 dev, 83 ansible), 14,092 L3 positives (`results/tables/x1_census_extended_*.csv`):

| set | L3 positives | function | method | class | module residual | test unit | non-Python (docs / config / data) | in a file without L2 positives |
|---|---|---|---|---|---|---|---|---|
| all 540 | 14,092 | 2,570 (18.2%) | 6,710 (47.6%) | 467 (3.3%) | 1,192 (8.5%) | 2,887 (20.5%) | 245 = 1.7% [1.2, 2.4] (82 / 70 / 93) | 46.2% [43.0, 49.4] |
| Verified, all 12 repositories (302) | 8,893 | 1,034 | 4,843 | 243 | 454 | 2,248 (25.3%) | 71 = 0.8% [0.3, 1.6] (43 / 0 / 28) | 58.8% [55.6, 61.9] |
| dev (155) | 3,253 | 1,170 | 941 | 111 | 444 | 482 (14.8%) | 86 = 2.6% [1.7, 3.8] | 29.5% [24.8, 34.4] |
| ansible (83) | 1,946 | 366 | 926 | 113 | 294 | 157 (8.1%) | 88 = 4.5% [2.7, 6.7] (33 / 40 / 15) | 16.6% [12.7, 21.2] |

Of the 6,516 L3 positives in files without L2 positives, 2,887 are test units (44%), 2,384 methods, 778 functions, 241 module residuals,
103 non-Python. Django carries much of the Verified test share (1,459 of its 4,361 L3 positives are test units; 62.8% of its L3 positives
lie in new files). The extension strengthens the cached-instance reading: tests are the structure beyond the edited files that L3 asks
for (a fifth of all L3 positives, close to half of those in new files); configuration and documentation are under 2% everywhere,
highest in ansible (4.5%, a configuration-heavy project); the dev repositories have fewer new-file positives than Verified (29.5% against
58.8%), so a graph signal for L3 tuned on dev sees a different mix than the test set.

**The E-GRAPH-SIGNAL headline under D18** (`full` form and `drop` policy, as selected; C 5, gamma 0.5, 2 hops, list form; gold
`units_all_nomod`; query-level interval, clustered interval in brackets after it where it differs in sign):

| edge subset | dev L2 vs BM25 | dev L2 vs same-file | dev L3 vs BM25 | dev L3 vs same-file | Verified-6 L2 vs BM25 | Verified-6 L2 vs same-file | Verified-6 L3 vs BM25 | Verified-6 L3 vs same-file |
|---|---|---|---|---|---|---|---|---|
| contain | +2.4 [+1.3, +3.5] | +3.4 [+2.5, +4.5] | +7.7 [+5.4, +10.0] | +1.6 [+0.0, +3.1] | +2.8 [+0.5, +5.1] (cl. [-0.7, +4.4]) | +4.4 [+2.6, +6.3] | +7.2 [+3.0, +12.1] | +4.0 [+0.5, +7.9] (cl. [-0.3, +6.3]) |
| invoke | +0.4 [-0.5, +1.3] | +1.4 [+0.6, +2.3] (cl. [-0.1, +2.9]) | +7.3 [+5.4, +9.4] | +2.0 [-0.5, +4.4] | +0.8 [-0.8, +2.6] | +2.4 [+0.8, +4.2] | +1.6 [-0.8, +4.2] | -1.7 [-5.2, +1.4] |
| import | -1.4 [-1.9, -0.8] | -1.1 [-1.6, -0.6] | -0.8 [-1.6, +0.1] | -3.0 [-4.8, -1.4] | -0.3 [-1.4, +0.8] | +0.9 [-0.1, +2.0] | -2.0 [-4.0, -0.4] | -4.9 [-8.0, -2.2] |
| invoke+contain | +1.0 [+0.1, +2.0] | +2.1 [+1.3, +3.0] | +11.3 [+9.0, +13.9] | +4.8 [+2.2, +7.2] | +2.0 [-0.2, +4.3] | +3.4 [+1.6, +5.4] | +6.0 [+2.6, +10.4] | +2.2 [-1.7, +6.1] |
| core | +1.0 [+0.1, +1.9] | +2.1 [+1.3, +3.0] | +9.9 [+7.7, +12.3] | +3.9 [+1.5, +6.3] | +1.7 [-0.4, +3.9] | +3.1 [+1.3, +5.0] | +5.8 [+2.3, +9.9] | +2.1 [-1.7, +5.9] |
| all | +0.9 [+0.0, +1.9] | +2.0 [+1.1, +2.9] | +9.0 [+6.9, +11.3] | +2.8 [+0.4, +5.2] | +1.4 [-0.6, +3.4] | +2.7 [+1.0, +4.5] | +4.1 [+0.3, +8.6] | +0.5 [-3.4, +4.2] |
| all-minus-contain | +0.0 [-0.9, +0.9] | +1.3 [+0.4, +2.2] | +5.6 [+3.8, +7.5] | -0.0 [-2.4, +2.3] | +0.6 [-1.0, +2.4] | +2.3 [+0.9, +3.9] | +0.4 [-2.2, +3.1] | -2.7 [-5.7, -0.1] |

BM25 alone under this reading: dev 21.2 (L2, 351 queries) and 37.5 (L3, 155); Verified six 18.0 (83) and 31.8 (55). The full tables
(19 subsets, both list forms, every reading and both intervals) are `results/tables/x1_headline_{dev,confirm}_cells.csv`.
**What changes against the pilot-E3 statement.** (1) The containment result holds and is cleaner on Verified: under the primary
reading `contain` is above same-file chance at L2 on dev and Verified (+3.4, +4.4) and at L3 on Verified (+4.0 [+0.5, +7.9]); at L3
on dev it sits at the edge (+1.6 [+0.0, +3.1]), where pilot E3's `units_nomod` reading gave +1.2 [-0.4, +2.8]. The gain over BM25 at L2
is smaller than pilot E3 reported (dev +2.4 rather than +4.1) because the baseline is higher under every-overlapped-unit gold (21.2
rather than 15.8). (2) `core` and `all` remain not distinguishable from same-file chance at L3 on Verified. (3) Removing containment
leaves nothing above same-file chance at L3 (dev -0.0, Verified -2.7). (4) **Some orderings flip between the two D18 readings** (D18's
revisit condition), all among cells whose intervals overlap: at dev L3 against same-file chance `invoke` is ahead of `contain` without
module units (+2.0 [-0.5, +4.4] against +1.6 [+0.0, +3.1]) and behind it with them (+0.8 [-1.5, +3.2] against +2.8 [+1.3, +4.2]);
sign changes occur only for cells within about one point of zero (`tests`, `import+contain`, `co_change+contain` at dev L3, `co_change`
at Verified L2). The class-source and policy orderings above do not flip between the two D18 readings. Whether a flip among
indistinguishable cells reopens the primary reading is for the engineer (ADR-004). With six repositories, mostly matplotlib and
astropy, the clustered intervals on Verified include 0 for `contain` at L2 against BM25, `contain` at L3 against same-file chance and
`all` at L3 against BM25 (cl. [-0.3, +10.1]), where the query-level ones do not; D17's clustered interval is the more cautious reading.


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
