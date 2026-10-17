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
