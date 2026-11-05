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

## Index of entries

One row per entry in every experiment log (an entry with a section but no registry row is listed too). Entry ids are unique across `docs/EXPERIMENTS.md`, `docs/experiments/A.md`,
`docs/experiments/B.md` and `docs/experiments/C.md`; `python -I scripts/check_docs.py` fails on a duplicate id or on a citation that resolves to nothing.
The lead adds the row for a new entry at merge time (the pull request text carries the row).

| Entry id | Owner | File | Status | Date |
|---|---|---|---|---|
| E-LAT-HARNESS | lead | `docs/EXPERIMENTS.md` | planned |  |
| E-LAT-STAGES | lead | `docs/EXPERIMENTS.md` | planned |  |
| E-RQ1-DENSE | lead | `docs/EXPERIMENTS.md` | planned |  |
| E-RQ1-DENSE-BM25 | lead | `docs/EXPERIMENTS.md` | planned |  |
| E-RQ1-DENSE-STRUCT | lead | `docs/EXPERIMENTS.md` | planned |  |
| E-RQ1-ALL | lead | `docs/EXPERIMENTS.md` | planned |  |
| E-GRAPH-BUILD | lead | `docs/EXPERIMENTS.md` | done | 2026-10-17 |
| E-GRAPH-REACH | lead | `docs/EXPERIMENTS.md` | done | 2026-10-17 |
| E-BM25-REPRO | lead | `docs/EXPERIMENTS.md` | done | 2026-10-18 |
| E-LABEL-NOISE | lead | `docs/EXPERIMENTS.md` | done | 2026-10-18 |
| E-PILOT-LEAK | lead | `docs/EXPERIMENTS.md` | done | 2026-10-29 |
| E-PILOT-K | lead | `docs/EXPERIMENTS.md` | done | 2026-10-29 |
| E-PILOT-NEG | lead | `docs/EXPERIMENTS.md` | done | 2026-10-29 |
| E-PILOT-L3POS | lead | `docs/EXPERIMENTS.md` | planned |  |
| E-PILOT-POOL | lead | `docs/EXPERIMENTS.md` | planned |  |
| E-GRAPH-SIGNAL | lead | `docs/EXPERIMENTS.md` | done | 2026-10-18 |
| E-GRAPH-WEIGHTS | lead | `docs/EXPERIMENTS.md` | done | 2026-10-18 |
| E-RECENCY | lead | `docs/EXPERIMENTS.md` | done | 2026-10-18 |
| E-CLASS-SOURCE | lead | `docs/EXPERIMENTS.md` | done | 2026-10-23 |
| E-AMBIG-POLICY | lead | `docs/EXPERIMENTS.md` | done | 2026-10-23 |
| E-L3-CENSUS | lead | `docs/EXPERIMENTS.md` | done | 2026-10-23 |
| E-POOL-CHECK | lead | `docs/EXPERIMENTS.md` | done | 2026-10-18 |
| E-POOL-RANKS | lead | `docs/EXPERIMENTS.md` | done | 2026-10-25 |
| E-TRAIN-STACK | lead | `docs/EXPERIMENTS.md` | done | 2026-10-25 |
| E-GRAPH-ROLE | lead | `docs/EXPERIMENTS.md` | done | 2026-10-29 |
| E-PILOT-CURVE | lead | `docs/EXPERIMENTS.md` | done | 2026-10-29 |
| E-PILOT-ARMS | lead | `docs/EXPERIMENTS.md` | done | 2026-10-31 |
| E-PILOT-ARMS2 | lead | `docs/EXPERIMENTS.md` | done | 2026-10-31 |
| E-PILOT-NOISE | lead | `docs/EXPERIMENTS.md` | gate N0 and stage N1 done (two seeds; third seed at r = 0.4 added) | 2026-11-01 |
| E-PILOT-NOISE-SIB | lead | `docs/EXPERIMENTS.md` | done; sanity (i) not passed, reading not answered | 2026-11-02 |
| E-MINE-PILOT | lead | `docs/experiments/B.md` | code built and tested offline; live runs blocked (no token) | 2026-11-02 |
| E-MINED-PILOT | lead | `docs/experiments/B.md` | done (six runs, two seeds; exploratory) | 2026-11-03 |
| E-MINE-STORE | lead | `docs/experiments/B.md` | done (pilot; the full run is not started) | 2026-11-05 |
| E-MINE-FULL | lead | `docs/experiments/B.md` | running (launched 2026-11-05, account C) | 2026-11-05 |
| E-LABEL-AUDIT-SHEET | lead | `docs/experiments/B.md` | sheets built, nobody has read any pair | 2026-11-05 |
| E-STORED-ANALYSIS | B | `docs/experiments/B.md` | done | 2026-11-02 |
| E-C1-EVAL | C | `docs/experiments/C.md` | done (apparatus; synthetic fixtures only) | 2026-10-30 |
| E-C2-RAW-PR | C | `docs/experiments/C.md` | done (synthetic plumbing; harness superseded by the lead's miner, D97) | 2026-10-30 |
| E-C3-AGENT-PILOT | C | `docs/experiments/C.md` | done (apparatus; synthetic execution) | 2026-10-30 |
| E-C4-RQ3 | C | `docs/experiments/C.md` | done (apparatus; synthetic fixtures) | 2026-10-30 |
| E-C1-LAUNCH | C | `docs/experiments/C.md` | done (offline preparation) | 2026-10-31 |
| E-COLAB-SETUP | C | `docs/experiments/C.md` | done (offline preparation) | 2026-10-31 |
| E-C1-COLAB-DEV | C | `docs/experiments/C.md` | done (operator_reported; not independently rerun) | 2026-10-31 |
| E-POWER | lead | `docs/EXPERIMENTS.md` | done | 2026-10-18 |
| E-CONTAM-PROBE | lead | `docs/EXPERIMENTS.md` | done | 2026-10-18 |
| E-CONTAM-SCAN | lead | `docs/EXPERIMENTS.md` | done | 2026-10-29 |
| E-CONTAM-EDITED | lead | `docs/EXPERIMENTS.md` | done | 2026-10-29 |
| E-DEV-ANSIBLE | lead | `docs/EXPERIMENTS.md` | done | 2026-10-29 |
| E-DENSE-FUSION (was E-GRAPH-FUSION) | lead | `docs/EXPERIMENTS.md` | done | 2026-10-23 |
| E-ENCODER-NUMBERS | lead | `docs/EXPERIMENTS.md` | done | 2026-10-29 |
| E-GRAPH-L3 | lead | `docs/EXPERIMENTS.md` | planned |  |
| E-RQ2-RAW | lead | `docs/EXPERIMENTS.md` | planned |  |
| E-RQ2-FILTER | lead | `docs/EXPERIMENTS.md` | planned |  |
| E-RQ2-WEIGHT | lead | `docs/EXPERIMENTS.md` | planned |  |
| E-RQ2-CURRICULUM | lead | `docs/EXPERIMENTS.md` | planned |  |
| E-RQ2-CTRL-SUBRAW | lead | `docs/EXPERIMENTS.md` | planned |  |
| E-RQ2-SEC-QQ | lead | `docs/EXPERIMENTS.md` | planned |  |
| E-RQ2-SEC-POSNEG | lead | `docs/EXPERIMENTS.md` | planned |  |
| E-RQ3-AGENT | lead | `docs/EXPERIMENTS.md` | planned |  |
| A1-PILOT | A | `docs/experiments/A.md` | done | 2026-10-31 |
| A2a | A | `docs/experiments/A.md` | done | 2026-10-31 |

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
| E-PILOT-LEAK | RQ2 (pilot, needs the training stack) | small encoder trained with versus without the instances of held-out and renamed repositories (the D1 rename-resolved overlap, 89 repositories in the candidate pool) | encoder, budget, seed, remaining pool, evaluation set | 3 | Verified nDCG@10 and Recall@100 of both encoders, paired; the difference is the leakage inflation | done (exploratory, 2026-10-29; rows `t2-leak-*`): 292 held-out directories in place of 292 others change nothing measurable on dev or on Verified-six (labelled: uses test repositories deliberately) at this budget; no Verified-six repository is in the pool |
| E-PILOT-K | RQ2 (pilot) | consistency filter K in {10, 20, 40, none} and teacher in {CodeRankEmbed, SweRankEmbed-Small, BM25, agreement of two}, at a tiny budget | encoder, matched optimization budget, pool, seed | 3 | retrieval metrics per cell with intervals; kept share per cell | done (exploratory, 2026-10-29; rows `t2-k-*`): 63 updates of RAW move CodeRankEmbed +8.3 dev L2 nDCG@10 and +11.0 L3 Recall@100; no FILTER, WEIGHT or CURRICULUM cell beats RAW at L3, strict cells (K = 10, BM25 at any K, agreement at K = 10) are 0.6-1.6 points below it; nothing decided |
| E-PILOT-NEG | RQ2 (pilot) | negatives: random repository-local, teacher-mined, graph-structural (callers, siblings, same-file units) | positives, budget, pool, seed | 3 | retrieval metrics; false-negative rate of each negative source on a labelled sample | done for random / top-M / positive cut (exploratory, 2026-10-29; rows `t2-neg-*`): positive cut +1.1 [0.35, 1.9] dev L3 Recall@100 (dense), top-M indistinguishable from random; structural factor not run (waits for Q30) |
| E-PILOT-L3POS | RQ2 (pilot) | graph-derived test and configuration positives added to training | everything else, budget | 3 | L3 Recall@100 and L2 nDCG@10, paired with the run without them | planned: the training stack exists (E-TRAIN-STACK, 2026-10-25). What this would decide: whether the L3-style positive (E-GRAPH-REACH, E-GRAPH-SIGNAL) is learnable from structure, i.e. whether an L3 arm is worth a place in RQ2 |
| E-PILOT-POOL | RQ2 (pilot) | training pool (SweLoc-style candidate pool, own PR-mined set, CodeSearchNet) at a fixed number of updates | encoder, budget, seed, filter | 3 | retrieval metrics per pool; unique examples seen | planned: the training stack exists (E-TRAIN-STACK, 2026-10-25); waits for ADR-001. What this would decide: which pool the frozen configuration uses, and how much of an arm difference is a pool difference |
| E-GRAPH-SIGNAL | RQ1 ext. (apparatus) | edge-family subset (19), seeds C (1, 3, 5), decay gamma (0.3, 0.5, 0.7), hops (1, 2), way of forming the scored list (edited list, ranked list fused by RRF) | reference BM25 over the units of the snapshot (module unit in), seeds are retrieved units, expansion limited to 50 units, seed 0, dev repositories for every sweep | n/a | change in nDCG@10 (L2) and Recall@100 (L3) against BM25 alone and against size-matched random expansions, paired 95% intervals | done (exploratory pilot, 2026-10-18; `RESULTS.md` rows `e3-*`; ADR-003 addendum) |
| E-GRAPH-WEIGHTS | RQ1 ext. (apparatus) | one weight per edge family fitted from data (pilot M reach table; leave-one-repository-out from E3 expansions) against the hand-set decay | as E-GRAPH-SIGNAL at C 5, 2 hops | n/a | paired difference against the hand-set decay, dev and three disjoint Verified repositories | done (exploratory pilot, 2026-10-18; rows `e4-*`) |
| E-RECENCY | RQ1 ext. (apparatus) | weight and time constant of a recency prior from `last_modified` (D8) added to BM25 | as E-GRAPH-SIGNAL | n/a | paired change against BM25 | done (exploratory pilot, 2026-10-18; rows `e5-*`) |
| E-CLASS-SOURCE | RQ1 ext. (apparatus) | class unit `source` form (full, header, header plus method signatures; Q28, `provisional: ADR-013`) | units, ids, spans, gold mapping, BM25 parameters, the pilot-E3 grid and cache, seed 0, dev repositories for the sweep | n/a | BM25 and expansion nDCG@10 (L2) and Recall@100 (L3) per form, query-level and repository-clustered intervals, four gold readings; index size and build time | done (exploratory, 2026-10-23; rows `x1-class-source-*`; ADR-013 addendum). Dev rule kept `full` |
| E-AMBIG-POLICY | RQ1 ext. (apparatus) | policy for ambiguous `invoke` sites read from the stored graph (keep, drop, rebucket by receiver evidence, keep sets of at most three; Q35, Q36) | as E-CLASS-SOURCE, form `full` | n/a | retrieval effect per policy; edge precision and recall per policy by the dynamic oracle (flask) and Jedi (300 stratified sites of requests and streamlink) | done (exploratory, 2026-10-23; rows `x1-ambig-*`; ADR-011 addendum). Dev rule kept `drop` |
| E-L3-CENSUS | RQ1 ext., RQ2 (apparatus) | none (count of positives by kind, repository and file novelty) | pilot-E1 unit records; D9 path rule | n/a (bootstrap seed 0) | positives by kind; share of L3 positives in files without L2 positives, instance-bootstrap intervals | done (2026-10-23; rows `x1-l3-census`, `x1-l3-census-extended`): 438 cached instances, then all 540 Python L3 instances with base commits |
| E-POOL-CHECK | RQ2 (apparatus, pool) | none (measurement of the candidate pool `gangiswag/train_data` python) | the pool as published | n/a (sample seed 0) | directory structure, positives and functions per instance, (repository, PR) overlap with CORE-Bench and Verified | done (exploratory, 2026-10-18; `RESULTS.md` row `x-pool-check`) |
| E-POOL-RANKS | RQ2 (apparatus, pool, quality signal) | teacher (SweRankEmbed-Small, CodeRankEmbed, BM25; stored-text sensitivity), K in {10, 20, 40} | sample: 160 directories, 20 per stratum of corpus-size quartile x held-out flag, seed 0; cut 1,024 tokens, float16; rank among non-positive functions | n/a (sample and bootstrap seed 0) | positive-rank distributions, shares outside the top K, directories with no positive in the top K, pool estimates against SweRank+ Table 1, teacher agreement, full-pool cost | done (exploratory, 2026-10-25; rows `x3-*`): qrels not filtered per positive (39% outside the SweRankEmbed-Small top 40); directories selected with respect to SweRankEmbed-Small (0 of 160 without a top-10 positive vs 19.3% on never-filtered Verified); filter vs teacher fit not decidable |
| E-TRAIN-STACK | RQ2 (apparatus) | none (validation of the training path: reader, hooks, loss, budget, checkpoints, evaluation hook) | synthetic pool for the tests; 24 real pool directories (seed 0) for the cluster check; every training value a test value, `provisional: ADR-001, ADR-002, ADR-006` | n/a (seed 0) | arms-only-through-hooks identity (bit-identical batches, gradients, parameters); exact resumption; evaluation hook against the X2 dev tables; checkpoint footprint | done (2026-10-25; rows `t1-*`): identity holds; the hook reproduces 18 of 18 X2 dev rows (values and clustered intervals); no retrieval result |
| E-POWER | RQ2, RQ3 (apparatus) | n, discordance, effect, run-to-run SD, per-query SD, correlation, seeds | alpha 0.05, power 0.8 | n/a (simulation seed 0) | power and minimum detectable effects (calculation, no data) | done (2026-10-18; row `x-power`; RQ3 grid and published-swap reading added 2026-10-29, row `h-rq3-power`) |
| E-CONTAM-PROBE | RQ2/RQ3 (apparatus, contamination) | shard slice (every 10th of 240), hash level (text, syntax tree) | probe set = functions of the 12 Verified repositories at 499 base commits | n/a | function-hash matches against CoRNStack `document`, by size of function; feasibility and cost of the full scan | done as a slice (exploratory, 2026-10-18; rows `x-contam-probe-slice`, `x-contam-throughput`) |
| E-CONTAM-SCAN | RQ2/RQ3 (apparatus, contamination), D23 | size floor 20 nodes (50 and 100 as sensitivity), fixed from the slice before the result | all 240 CoRNStack python shards, `document` field; probe = functions at each Verified instance's own base commit | n/a | hit counts and shares per repository with Wilson intervals | done 2026-10-29 (exploratory; rows `x4-contam-scan`) |
| E-CONTAM-EDITED | RQ2/RQ3 (apparatus, contamination), D23 flip experiment | same floors as E-CONTAM-SCAN (20 primary, 50 and 100) | the functions each Verified reference patch edits (before and after the patch), against the hits of E-CONTAM-SCAN | n/a | share of edited functions in the corpus against two comparators, with repository-clustered intervals | done 2026-10-29 (exploratory; rows `x5-contam-edited`) |
| E-DEV-ANSIBLE | RQ2 (dev tables), D32 / Q47 | none (apparatus: a third dev L3 repository) | Pro ansible, L2 and L3, unit level, role dev | n/a | cache, text stores and gold readings for the dev evaluation | done 2026-10-29 (no metric computed) |
| E-DENSE-FUSION (was E-GRAPH-FUSION) | RQ1 ext. (apparatus), ADR-006, Q30 | encoder (CodeRankEmbed, Qwen3-Embedding-0.6B; `provisional: ADR-006`), cut (512, 1024 tokens; dev only), first stage (BM25, dense, RRF(BM25, dense) with k swept on dev, score-level BM25+dense), graph on top of the strongest first stage (edited list, graph as a third RRF list, score-level with weight swept on dev; core families and each family alone) | units and gold of the pilot-E3 cache, class form `full`, ambiguous sites `drop`, seeds are retrieved units, expansion at most 50 units, seed 0, dev repositories for every sweep, one stated setting on the Verified-six | n/a | nDCG@10 (L2) and Recall@100 (L3) at unit level (both D18 readings) and chunk level, query-level and repository-clustered intervals; graph cells against the first stage and size-matched chance controls; query-encode and flat-search latency p50/p95/p99 (CPU, GPU), encoding throughput and peak memory | done (exploratory, 2026-10-23 to 2026-10-25; rows `x2-*`; ADR-006 and ADR-003 addenda) |
| E-ENCODER-NUMBERS | RQ1 ext. / RQ2 (apparatus), ADR-006, D25, D31 | encoder (CodeRankEmbed 1,024 tokens k 100, Qwen3-Embedding-0.6B 512 tokens k 20, both as selected on dev; `provisional: ADR-006`), class-unit text (`full`, `header`; dev) | everything of E-DENSE-FUSION; for the training-step measurement the D31 batch shape (32 x (1+1), float16 autocast, gradient checkpointing, 512 tokens) | n/a (one measurement, seed 0) | paired RRF difference with query-level and repository-clustered intervals (dev; Verified-six as a final-test-style reading), header against full, training-step throughput and peak memory, query-encode and flat-search latency p50/p95/p99 | done (exploratory, 2026-10-29; rows `e7-*`; ADR-006 addendum) |
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

**Third dev L3 repository (decision D32, 2026-10-29).** Pro `ansible/ansible` (83 instances with L3 qrels, already mapped by E-L3-CENSUS) is added as a `dev` folder in `configs/experiments/e1_bm25_dev3.yaml` (see E-DEV-ANSIBLE); the original configuration above is unchanged so its hash and every earlier run stay valid. Verified stays the test set.

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

#### E-POWER update 2026-10-29: RQ3 table on a wider grid, with a normal form beside the exact one

Code `ril/analysis/rq3_power.py` (tests `tests/unit/test_rq3_power.py`), wrapper `scripts/rq3_power.py`, table `results/tables/h_rq3_power.csv`; calculation, no data, no randomness (seed 0 recorded), CPU, local. Same model as above (paired, two-sided, alpha 0.05, power 0.8). **Exact** = the doubled-tail binomial test on the disagreeing instances, minimum detectable effect on a 0.25-point grid from which power stays at 0.8 (it reproduces the 2026-10-18 cells above exactly). **Normal** = the large-sample form, (b - c)/n with variance d/n under the null and (d - e^2)/n under the effect; it is optimistic by 0.2 to 0.5 points at n of 302 to 900 because the exact test is conservative on discrete counts.

Minimum detectable effect, percentage points (exact / normal):

| n | discordance 10% | 15% | 20% | 30% |
|---|---|---|---|---|
| 302 | 5.50 / 5.08 | 6.50 / 6.22 | 7.50 / 7.18 | 9.25 / 8.80 |
| 432 | 4.50 / 4.25 | 5.50 / 5.21 | 6.25 / 6.01 | 7.75 / 7.36 |
| 600 | 3.75 / 3.61 | 4.75 / 4.42 | 5.25 / 5.10 | 6.50 / 6.25 |
| 900 | 3.25 / 2.95 | 3.75 / 3.61 | 4.50 / 4.17 | 5.25 / 5.11 |

What n each effect would need (exact, power 0.8): 6 points at discordance 15%: about 350 instances; 5 points at 14%: about 470; 3 points at 14%: about 1,300 (at 10%: about 920); 2 points at 14%: about 2,850; 1.2 points at 14%: about 7,800. For comparison, the unit-level Verified sets have 432 (L2) and 302 (L3) queries (D12); 600 and 900 are hypothetical (dev instances added, or a second benchmark); the agent has not been run, so the discordance is unmeasured.

Width of an effect estimate (95% half-width of the paired difference in points, approximately 1.96 x sqrt(d / n)): n = 432 gives 3.0 / 3.7 / 4.2 / 5.2 at discordance 10 / 15 / 20 / 30%; n = 900 gives 2.1 / 2.5 / 2.9 / 3.6. An interval at n = 432 and d = 15% therefore cannot separate effects closer than about 3.7 points from zero, and a run-to-run SD of the agent (above) widens it further.

**What published retrieval swaps imply (read in full; `knowledge/papers/codegrep-2608.05886.md`).** Only one source reports a resolved rate for retrieval swaps behind a fixed agent on a Verified-sized set: on all 500 Verified instances with a fixed open-source agent and one run per configuration, no retrieval 25.8%, BM25 top-2 25.2%, a dense code-embedding model top-2 25.8%, and the paper's own trained retriever 27.0% (Table 3; `paper_reported`). The differences are -0.6, 0.0 and +1.2 points, i.e. -3, 0 and +6 instances of 500, with no seed, interval or paired test in the paper. Per-instance overlaps are in its text for two pairs (94 instances resolved by both the baseline and BM25; 96 by both the baseline and the paper's retriever; `paper_reported`); with the totals above they give 35 and 32 instances resolved by only one condition (BM25 pair) and 33 and 39 (retriever pair), a discordance of 13.4% and 14.4% (derived by this project from `paper_reported` counts; exact McNemar p = 0.81 and 0.56). Two things follow, labelled inference: (i) published retrieval swaps behind a fixed agent are of the order of 0 to 1 point, below every cell of the table above (the smallest is 2.95 points at n = 900 and discordance 10%); (ii) the one discordance that can be derived, about 14%, lies in the 10 to 20% rows. The other papers read in full report no resolved rate for retrieval swaps (the agent-retrieval benchmark states that it makes no claim about patch success, and the explorer study correlates upstream metrics with resolved rate across 14 explorers, not across retrievers with a fixed agent). No paper read in full reports a paired per-instance resolved-rate difference with an interval for a retrieval swap.

**Question for the engineer (nothing decided; Q45).** Is RQ3 a hypothesis test (McNemar, "does the better retriever resolve more instances, yes or no") or an effect estimate with an interval ("by how much, with what uncertainty")? The number that decides it is the smallest resolved-rate difference between two arms that you would call worth reporting as a positive RQ3 result. If it is 5 to 6 points or more, a test is feasible at the Verified sizes (n = 432: minimum detectable effect 5.5 to 6.25 points at discordance 15 to 20%; n = 302: 6.5 to 7.5). If it is 3 points or less, a test needs about 1,300 instances or more at 14% discordance, which neither Verified set offers, and RQ3 can honestly be only an estimate whose interval (about +/- 3 to 4 points at n = 432) will probably include zero; the published swaps (0 to 1 point) sit in that second regime. A null at n = 432 is then reported as "no difference larger than about 4 points detectable", with the retrieval-versus-reasoning failure breakdown, never as "no effect". The discordance itself needs one agent pilot (Q45).

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


## E-DENSE-FUSION: dense retrieval, BM25+dense fusion and the graph on top, exploratory, done 2026-10-25

**What it measures.** The first dense numbers of the project: two encoders on the same unit texts as the BM25
pilots, fused with BM25, and the graph expansion of pilot E3 on top of the strongest first stage, in three forms.
Nothing here is a decision; ADR-006 (encoder) and Q30 (graph role, how a graph signal enters fusion) stay open.

**Setup.** Units, gold readings and edge pairs of the pilot-E3 cache (class form `full`, ambiguous sites dropped);
355 dev instances (five development repositories) for every sweep, the 83 Verified-six instances for one stated
setting per configuration. Encoders (`ril/retrieval/dense_encoder.py`, `provisional: ADR-006`): CodeRankEmbed
(137M, its own query prefix) and Qwen3-Embedding-0.6B (instruction on the query only, in the model repository's
`Instruct: <task>\nQuery:<issue>` form with the task sentence "Given a GitHub issue, retrieve the code units
(functions, methods, classes or modules) that have to be changed to resolve it"; the report gives the format but
no instruction for code). Truncation: queries (with prefix or instruction) and documents cut at the same number of
tokens of each encoder's tokenizer, beginning kept; 512 and 1024 compared on dev only. Flat exact inner-product
index over L2-normalised vectors. Float16 on one RTX 2080 Ti (agreement with float32: cosine >= 0.99998 on 64
units). Fusion: RRF `sum 1/(k + rank)` with k swept on dev; score-level `alpha * mm(BM25) + (1 - alpha) * mm(dense)`
with alpha swept on dev. Graph on top: seeds = top-C of the first stage; hop-decay expansion (at most 50 units) over
core families and each alone; forms: edited list, graph list as a third RRF list (same k), score level
`(1 - w) * first_score + w * g`; chance controls of the same size (whole snapshot, files of the seeds). Metrics:
nDCG@10 (L2) and Recall@100 (L3), mean over queries with query-level and repository-clustered bootstrap intervals
(2,000 draws, seed 0); D18 readings `units_all_nomod` (primary) and `units_all`. Chunk level: filter-first ranks
of the CORE-Bench chunks of the same folders. Configurations (sha256, 12 characters): `x2_first_dev` abf0ba1e339e,
`x2_graph_dev` f0dcbd370e66, `x2_graph_headline_dev` c0a2002b0b4e, `x2_first_confirm` 4fff5dc4f7de,
`x2_graph_confirm` e09d169f6680, `x2_chunks_confirm` afb83c2bf13e; every selection rule was committed before the
numbers it selects from existed, every confirmation before its Verified scores were read. Run log
`results/logs/x2_dense_fusion_2026-10-25.json`; tables `results/tables/x2_*`.

**Dev selections (stated rules).** Cut: CodeRankEmbed 1024 (dense alone at L2 +1.1 [+0.4, +1.9] over 512), Qwen3
512 (+0.5 [-0.1, +1.1], rule keeps the cheaper cut). RRF k: 100 (CodeRankEmbed), 20 (Qwen3). Strongest first stage:
RRF(BM25, Qwen3-Embedding-0.6B, k 20). Graph cell: score level, C 5, gamma 0.7, 2 hops, w 0.5 (w 0.5 is the edge
of the grid). Chunk-level k: 100 and 20.

**Results (unit level, `units_all_nomod`; points, mean over queries, query-level interval; under `units_all` the selections and every
Verified ordering are the same; on dev CodeRankEmbed alone is level with BM25 at L3, -0.2 rather than -3.5).**

| | dev L2 nDCG@10 | dev L3 R@100 | Verified-six L2 | Verified-six L3 |
|---|---|---|---|---|
| BM25 | 21.2 | 37.5 | 18.0 | 31.8 |
| CodeRankEmbed (1024) alone | 18.2 | 34.0 | 17.9 | 33.6 |
| Qwen3-Embedding-0.6B (512) alone | 24.7 | 46.7 | 17.0 | 39.1 |
| RRF BM25 + CodeRankEmbed, vs BM25 | 24.0, +2.9 [+1.2, +4.6] | 43.0, +5.5 [+4.0, +7.2] | 23.0, +5.1 [+1.4, +8.8] | 38.0, +6.2 [+2.9, +9.7] |
| RRF BM25 + Qwen3, vs BM25 | 28.3, +7.2 [+5.4, +8.9] | 47.1, +9.6 [+8.0, +11.5] | 24.9, +6.9 [+3.6, +10.5] | 41.5, +9.7 [+6.8, +12.7] |
| RRF Qwen3 vs RRF CodeRankEmbed | +4.3 [+3.0, +5.7] | +4.1 [+2.9, +5.4] | +1.9 [-1.7, +5.5] | +3.4 [+0.9, +6.3]; clustered [-1.1, +5.7] |

Chunk level (filter-first): BM25 19.3 / 41.7 (dev), 13.4 / 33.0 (Verified-six); RRF with Qwen3 +9.4 [+7.5, +11.4] /
+14.1 [+12.3, +16.2] (dev) and +8.6 [+4.1, +13.2] / +16.1 [+12.0, +20.2] (Verified-six); RRF with CodeRankEmbed +3.9
/ +10.4 (dev, k 20 row) and +5.3 [-0.4, +10.8] / +11.4 [+6.9, +16.1] (Verified-six). At chunk level and at L3 the
Qwen3 encoder alone is level with its RRF (dev L3 -0.5 [-2.3, +1.1]).

**Graph on top of RRF(BM25, Qwen3) (stated cell; `units_all_nomod`).** Dev: core +1.9 [+0.9, +2.8] (L2) and +10.7
[+8.8, +12.8] (L3) over the first stage; over the same-file control +0.9 [-0.0, +1.7] and +2.5 [+0.2, +4.5]; over the
whole-snapshot control +5.9 and +17.6. `contain` alone carries it (+3.4 / +11.8; over same-file +2.3 [+1.5, +3.1] /
+3.8 [+2.0, +5.5]); `invoke` alone +5.5 at L3 but below same-file chance; `import` lowers L2. The three forms give
overlapping best cells on dev (core: edited list +1.4 / +10.7, third RRF list +1.5 / +9.9, score level +1.9 /
+10.7). Verified-six: core +0.2 [-1.8, +2.2] (L2) and +4.4 [+0.5, +8.8] (L3; clustered [+0.8, +7.8]) over the
first stage; over the same-file control +1.4 [-2.3, +5.1] at L3 (not distinguishable from same-file chance); over
the whole-snapshot control +11.4 [+8.1, +15.2].

**Cost (per hardware spec, `results/latency/`).** Query encoding, batch 1, warm p50 / p95 / p99: on the 2080 Ti,
CodeRankEmbed 18.5 / 19.5 / 20.6 ms and Qwen3 45.2 / 46.6 / 47.6 ms (512); on 4 threads of a Xeon E5-2640 v4,
378 / 937 / 957 ms and 1,533 / 3,591 / 3,628 ms. Flat exact search of 100 (CPU, numpy): 0.40 / 0.44 / 0.47 ms
(CodeRankEmbed, 768 dimensions) and 0.51 / 0.58 / 0.61 ms (Qwen3, 1,024) at the dev median snapshot of 5,195 units;
4.95 / 5.12 / 5.26 ms and 5.98 / 6.19 / 6.38 ms at the django scale of 35,860 units; on the GPU 0.27 and 0.33 ms at
django scale. Encoding throughput: whole dev runs at 512 tokens 201 (CodeRankEmbed) and 84 (Qwen3) unit texts per
second on the GPU; a fixed 128-text sample on 4 CPU threads 2.2 and 0.67 texts per second. Peak GPU memory while
encoding: 1.4 / 4.4 GB (CodeRankEmbed at 512 / 1024) and 2.3 / 4.6 GB (Qwen3); CPU resident peak after loading 1.7
and 4.0 GB, up to 2.5 and 6.3 GB after encoding a 1024-token sample. GPU-hours: 2.84 (jobs 36104, 38109).

**What it does not show.** Zero-shot encoders only; one seed per cell (sampling over queries is the only interval);
dev L3 has two repositories, so its clustered interval is not informative (Q47); Verified-six L3 has 55 queries.
The graph cell was selected at the edge of its weight grid. The latency query set is built from a development
repository's code words with issue-like lengths (median 220 tokens), not from issues; its files stay out of the
tracked tree (raw code words) and are pinned by sha256 in `results/logs/x2_query_sets.json`. Chunk-level CodeRankEmbed was
scored at 512 tokens only (a 1024-token chunk encoding exists, unscored). Class-source forms and the `max3` policy
were not read on the dense first stage (the per-form unit hashes are prepared on the cluster).

## E-ENCODER-NUMBERS: four numbers for the encoder choice (ADR-006), exploratory, done 2026-10-29

**What it measures.** Four numbers that ADR-006 turns on, on existing runs plus one short GPU measurement. Nothing is decided; the
engineer settles ADR-006. Configuration `configs/experiments/e7_encoder_numbers.yaml` (hash `6aaef4fd84df`), training-step
configuration `e7_train_step_qwen3.yaml` (`7485fdfc6c5f`; CodeRankEmbed control `t1_validate_cre.yaml`, `8ac6819f9ba6`), seed 0.
Code `ril/evaluation/e7_encoders.py`, `ril/analysis/e7_tables.py`, `scripts/e7_run.py`, `scripts/ada/e7_measure.sbatch`; tables
`results/tables/e7_*.csv`; run log `results/logs/e7_encoder_numbers_2026-10-29.json`; rows `e7-*` in `RESULTS.md`. Values are
percentages (nDCG@10 at L2, Recall@100 at L3, mean over queries), differences points, intervals 95% bootstrap (2,000 draws), both
query-level and repository-clustered. Encoders as selected on dev in E-DENSE-FUSION and held fixed here: CodeRankEmbed at 1,024
tokens with RRF k 100, Qwen3-Embedding-0.6B at 512 tokens with k 20 (class form `full`, ambiguous sites dropped).

**(a) Paired difference RRF(BM25, Qwen3) minus RRF(BM25, CodeRankEmbed)** (`units_all_nomod`, then `units_all`).

| set | level | queries / repositories | CodeRankEmbed RRF | Qwen3 RRF | difference [query-level] | [repository-clustered] | `units_all` difference [query-level] |
|---|---|---|---|---|---|---|---|
| dev | L2 nDCG@10 | 351 / 5 | 24.04 | 28.32 | +4.29 [+2.95, +5.74] | [+2.22, +6.55] | +3.62 [+2.40, +4.89], cl. [+1.76, +5.18] |
| dev | L3 Recall@100 | 155 / 2 | 43.00 | 47.08 | +4.08 [+2.85, +5.37] | [+3.78, +4.41] (two clusters) | +3.12 [+1.94, +4.36] |
| Verified-six | L2 nDCG@10 | 83 / 6 | 23.03 | 24.88 | +1.85 [-1.67, +5.50] | [-2.01, +5.93] | +1.67 [-1.79, +5.29], cl. [-2.15, +5.79] |
| Verified-six | L3 Recall@100 | 55 / 6 | 38.04 | 41.48 | +3.43 [+0.87, +6.33] | [-1.07, +5.68] | +2.89 [+0.60, +5.44], cl. [-1.19, +4.69] |

Verified-six is a final-test-style reading: both configurations were fixed on dev before any Verified score was read, nothing was
chosen on Verified, and this session chooses nothing on it. Per repository (`units_all_nomod`, difference in points, queries in
brackets): dev L2 conan +4.07 (87), haystack +4.66 (72), openlibrary +1.93 (80), qutebrowser +8.47 (75), streamlink +0.67 (37), all five
positive; dev L3 openlibrary +3.78 (81), qutebrowser +4.41 (74). Verified-six L2: astropy -0.41 (22), matplotlib +4.89 (32), seaborn
-5.42 (2), flask +19.60 (1), requests +7.81 (8), xarray -3.59 (18); L3: astropy -2.59 (11), matplotlib +6.11 (24), seaborn -5.13 (1),
flask +3.33 (1), requests +4.68 (5), xarray +3.79 (13). Dense alone, Qwen3 minus CodeRankEmbed: dev +6.42 [+4.79, +8.19] (L2) and
+12.71 [+10.25, +15.12] (L3); Verified-six -0.87 [-5.28, +3.39] (L2) and +5.54 [+2.09, +9.57], cl. [+0.57, +9.17] (L3). The
numbers reproduce the E-DENSE-FUSION table (+4.3 / +4.1 / +1.9 / +3.4). Not read: a third dev repository at L3 (D32, session X5);
Verified-six L3 has 55 queries from 6 repositories, three of them with at most one query.

**(b) Dense class-unit text `full` against `header`, dev** (`units_all_nomod`; 351 L2 and 155 L3 queries, same cut and k as in (a),
nothing re-tuned per form; value for `full`, then `header` minus `full` with query-level and clustered interval).

| ranking | `full` L2 / L3 | `header` L2 | `header` L3 |
|---|---|---|---|
| BM25 alone | 21.17 / 37.47 | -2.34 [-3.44, -1.29], cl. [-3.31, -1.22] | -2.89 [-3.63, -2.10] |
| CodeRankEmbed alone | 18.24 / 34.00 | -1.79 [-2.66, -1.00], cl. [-4.17, -0.76] | -0.50 [-1.06, +0.05] |
| Qwen3 alone | 24.66 / 46.71 | -1.57 [-2.34, -0.83], cl. [-2.01, -1.15] | -1.13 [-1.65, -0.58] |
| RRF(BM25, CodeRankEmbed) | 24.04 / 43.00 | -1.90 [-2.84, -0.99], cl. [-3.04, -0.45] | -1.97 [-2.72, -1.23] |
| RRF(BM25, Qwen3) | 28.32 / 47.08 | -1.86 [-2.84, -0.88], cl. [-2.82, -0.69] | -2.06 [-2.79, -1.34] |

Under `units_all` the signs and sizes agree (RRF: CodeRankEmbed -1.98 / -1.66, Qwen3 -1.99 / -1.75; dense alone -1.34 / -0.38 and
-1.24 / -1.00). BM25 alone reproduces the Wave 3 rows (-2.3, -2.9). So with a dense encoder at these cuts `full` is ahead of
`header` in every cell and no interval is above zero; the one interval that includes zero is CodeRankEmbed alone at L3 (-0.50).
Truncation is the stated reason `full` might lose: 4.4% (CodeRankEmbed, 1,024) and 8.9% (Qwen3, 512) of all units are cut at the
median instance (all 438 cached instances; the share for class units alone was not computed). Per D25 this is reported, nothing is
switched; the reading dependence found for BM25 (a class is gold whenever one of its methods is, and only the full text
contains the method) applies to the dense scores in the same way and was not separated here. Only dev; no Verified number was read for this part.

**(c) Training step of Qwen3-Embedding-0.6B at the D31 shape** (one 2080 Ti, 11,264 MiB, 10.57 GiB usable to torch; CUDA gate
passed in every job; float16 autocast, gradient checkpointing, 512 tokens, AdamW as the training path builds it; 3 warmup + 10 timed
updates on a throwaway model; jobs 46134, 46180, 46183, 0.07 GPU-hours in all).

| model | shape (batch x (positives + negatives)) | result |
|---|---|---|
| CodeRankEmbed (control, same job) | 32 x (1+1) | 12.24 and 12.35 examples/s (2.61 and 2.59 s per update), peak 6,880 MiB (two jobs; T1 job: 12.06, 6.9 GB) |
| CodeRankEmbed | 8 x (1+1) | 11.77 examples/s, 0.68 s per update, peak 3,369 MiB |
| Qwen3-Embedding-0.6B | 32, 16, 8, 4, 2, 1 x (1+1) | out of memory at every shape (peak at failure 10,227 to 10,541 MiB; for 16, 8 and 4 in job 46134 the peaks carry over from the earlier shape, the clean single-shape runs of 4, 2, 1 in job 46183 fail the same way) |

Memory probe (job 46183, one short document, activations negligible): 595,776,512 parameters; float32 weights 2,272.7 MiB;
after one backward pass (weights + gradients) 4,561.7 MiB; AdamW's default multi-tensor update runs out of memory at the first
optimizer step (peak 10,599.7 MiB reached before the failure); with the per-tensor update (`foreach=False`) the step completes with
9,107.1 MiB resident (four copies of the weights) and a 10,599.7 MiB peak, leaving about 1.7 GiB for everything else. So the batch
size is not what fails: float32 weights, gradients and both AdamW moments of this model fill an 11 GB card on their own. Not
measured: any throughput for Qwen3 (no shape ran). Reasoned, not measured: the activation share of CodeRankEmbed at 32 x (1+1) is
6.7 GiB (6,880 MiB) minus its 2.0 GiB of weights, gradients and moments, i.e. 4.7 GiB; scaled by layers times width (28 x 1,024 against
12 x 768, a factor of about 3) it would be of the order of 14 GiB, so the step would need of the order of 24 GiB in all, at least a 24 GB card, and its speed
would be between the encoding-throughput ratio (2.4, E-DENSE-FUSION) and the parameter ratio (about 4.3) slower than CodeRankEmbed's
12 examples/s. Changes that might fit the card (8-bit optimizer states, half-precision master weights, low-rank adapters, a smaller
batch with gradient caching) alter the training recipe held identical across arms, are design choices, and were not tried. `sinfo`
shows no card above 11 GB that account A can use: `ihub`, `plafnet2` and `rrc` (3080 Ti, 3090 cards) refuse the `research` account;
the unlabelled `u22` nodes expose no card type. The D31 check is therefore: none reachable, so nothing was run on one.

**(d) Query latency next to the retrieval gain** (per hardware spec: GPU 2080 Ti, CPU 4 threads of a Xeon E5-2640 v4; batch 1, warm,
p50 / p95 / p99 in ms, issue-like query set of 100 queries, 295 warm timings; rows in `results/latency/latency_log.csv`, stages
`query_encode` and `dense_search`, taken from E-DENSE-FUSION, no new latency run).

| | CodeRankEmbed (1,024) | Qwen3 (512) | ratio of p50 |
|---|---|---|---|
| query encode, GPU | 18.07 / 19.28 / 22.15 | 45.17 / 46.59 / 47.63 | 2.5 |
| query encode, GPU, cold | 18.26 / 21.62 / 24.52 | 45.32 / 47.13 / 48.83 | 2.5 |
| query encode, CPU | 411.5 / 1,265 / 2,555 | 1,533 / 3,591 / 3,628 | 3.7 |
| flat search, CPU, dev median snapshot (5,195 units) | 0.40 / 0.44 / 0.47 | 0.51 / 0.58 / 0.61 | 1.3 |
| flat search, CPU, 35,860 units | 4.95 / 5.12 / 5.26 | 5.98 / 6.19 / 6.38 | 1.2 |
| RRF vs BM25, dev L2 / L3 | +2.9 [+1.2, +4.6] / +5.5 [+4.0, +7.2] | +7.2 [+5.4, +8.9] / +9.6 [+8.0, +11.5] | |
| RRF vs BM25, Verified-six L2 / L3 | +5.1 [+1.4, +8.8] / +6.2 [+2.9, +9.7] | +6.9 [+3.6, +10.5] / +9.7 [+6.8, +12.7] | |
| Qwen3 minus CodeRankEmbed (a), Verified-six L2 / L3 | | +1.85 [-1.67, +5.50] / +3.43 [+0.87, +6.33] | |
| extra query encode per query for the extra gain, p50 | | GPU +27.1 ms, CPU +1,122 ms | |

For scale, a 1,024-token CodeRankEmbed cut costs the same GPU time as 512 (18.5 against 18.1 ms) but on the CPU its p95 and p99 rise
(937 to 1,265 and 957 to 2,555 ms); Qwen3 at 1,024 is 46.5 ms on the GPU and 1,520 / 3,996 / 7,266 ms on the CPU. The latency requirement
(the project's latency protocol) is p50/p95/p99 per component; whether 45 ms or 1.5 s of query encoding fits an interactive budget is the
engineer's to state; no budget is recorded in the repository.

**What it does not show.** One seed; zero-shot encoders, so (a) and (b) say nothing about the encoders after fine-tuning (the
comparison that matters for RQ2); dev L3 has two repositories; the training-step measurement is a throwaway model for 13 updates and
says nothing about convergence; the 4.7 GiB activation figure and the 24 GB card class are reasoning from one other model.
Dead ends: job 46134 ran four Qwen3 shapes in one process (the shape list was not split), job 46180 lost the commas of its shape list
in `--export` and its first probe crashed at the optimizer step; both are kept in the run log with their notes.

## E-POOL-RANKS: teacher ranks of the candidate pool's positives and the pool's filter state, exploratory, done 2026-10-25

**What it measures.** Whether the 24,285 directories of `gangiswag/train_data` python (E-POOL-CHECK) are before or after the
consistency filter of SweRank+ (keep a positive only if it ranks in the top 40 of its repository under SweRankEmbed-Small;
`knowledge/papers/swerank-plus-2512.20482.md`), and how the K-rank quality signal of ADR-002 is distributed in this pool under three
teachers. Nothing is decided; ADR-001 (pool) and ADR-002 (quality signal) stay open.

**Setup.** Configuration `configs/experiments/x3_pool_ranks.yaml` (hash `755b27136e9d`; the main part, including three readings (below), stated before any rank was read, the reference
comparison added after the main ranks and before any reference rank). Sample: corpus-size quartile (uncompressed corpus bytes of every directory, edges 122,227 / 359,103 /
974,092 bytes) times held-out flag (list v2, core plus Loc-Bench tier, aliases including the rename cache: 3,485 of 24,285 directories),
20 directories per stratum by the order of sha256("0:<directory>"), 160 directories, 118 repositories, 1,522 positives, 188,566 functions
(sample file sha256 in the run log). Each directory was read by HTTP range request; nothing but ids, ranks, counts and timings left the
cluster. Teachers: SweRankEmbed-Small (revision `745d2a06`, the SweRank+ filter teacher), CodeRankEmbed (revision `3c4b6080`, the
SweRank filter teacher) and BM25 (reference form, `provisional: ADR-004`); dense teachers at 1,024 tokens (the published SweRank
mining script's length), float16, the model's query prefix. Rank, as in the published SweRank construction scripts (read
2026-10-25; each positive is a separate instance whose candidates are the positive and every non-positive function, so the other
positives of the same pull request are not competitors): 1 + non-positive functions with a strictly higher score (`rank_all`, which
counts the other positives too, is in the tables). Text: the function code with the stored id line removed (as the published mining
script encodes it); sensitivity stated in advance: SweRankEmbed-Small on the stored `<id>\n<code>` text (`@pool`). Pool estimates
weight each stratum's sample ratio by its pool positives or directories; intervals are 95% stratified bootstrap (2,000 draws,
instances resampled within strata, seed 0); for 0 or 2 of 160 the exact binomial interval is given. Code
`ril/training/pool_ranks.py`, `pool_rank_jobs.py`, `ril/analysis/x3_tables.py`, `scripts/pool_ranks.py`; jobs in `scripts/ada/README.md`;
log `results/logs/x3_pool_ranks_2026-10-25.json`; tables `results/tables/x3_pool_ranks_*.csv`; rows `x3-*` in `RESULTS.md`.
1.24 GPU-hours (jobs 38202, 38213, 38291, 38292, 38295, 38296; `docs/COMPUTE.md`).

**Positive ranks** (1,522 positives of the sample; median and quartiles of `rank`):

| teacher | p25 | median | p75 | p95 | max |
|---|---|---|---|---|---|
| SweRankEmbed-Small | 1 | 10 | 98.8 | 448 | 7,911 |
| SweRankEmbed-Small, stored text | 1 | 3 | 94.8 | 404 | 7,936 |
| CodeRankEmbed | 7 | 38.5 | 154 | 688 | 7,560 |
| BM25 | 7 | 33 | 120.8 | 714 | 7,188 |

**Shares outside the top K** (pool estimates; sample values in `x3_pool_ranks_topk.csv`):

| teacher | positives outside top 10 | top 20 | top 40 | directories with no positive in top 10 | top 20 | top 40 (sample count of 160) |
|---|---|---|---|---|---|---|
| SweRankEmbed-Small | 50.4% [34.2, 59.1] | 45.2% [29.3, 54.2] | 39.4% [24.1, 48.0] | 1.7% [0.2, 3.9] | 1.3% [0.0, 3.5] | 1.3% (2; exact [0.15, 4.4]) |
| SweRankEmbed-Small, stored text | 43.3% [26.2, 52.0] | 40.0% [23.7, 49.0] | 34.9% [19.3, 43.4] | 0 | 0 | 0 (0 of 160; exact upper 2.3%) |
| CodeRankEmbed | 69.4% [57.2, 75.8] | 61.6% [48.6, 68.8] | 52.7% [37.9, 60.7] | 15.3% [8.8, 22.2] | 10.0% [5.2, 15.9] | 4.3% [1.6, 8.0] (9; exact [2.6, 10.4]) |
| BM25 | 71.3% [59.9, 78.6] | 63.5% [51.0, 71.8] | 53.4% [40.5, 62.0] | 23.2% [16.4, 31.0] | 15.1% [9.4, 21.1] | 13.4% [8.0, 19.6] (23; exact [9.3, 20.8]) |

**Against the SweRank+ Table 1 Python row** (24,285 PRs, 49,973 instances; `paper_reported`). Pool estimate of the positives inside the
top K (the instance count a SweRank-style positive-level filter would give from these directories):

| teacher | K = 10 | K = 20 | K = 40 |
|---|---|---|---|
| SweRankEmbed-Small | 152,783 [125,891, 202,589] | 168,809 [141,025, 217,902] | 186,531 [160,311, 233,797] |
| SweRankEmbed-Small, stored text | 174,614 [147,788, 227,173] | 184,667 [157,014, 235,010] | 200,660 [174,432, 248,435] |
| CodeRankEmbed | 94,137 [74,664, 131,790] | 118,269 [95,988, 158,448] | 145,839 [121,145, 191,143] |
| BM25 | 88,465 [65,884, 123,512] | 112,426 [87,016, 150,796] | 143,689 [117,119, 183,415] |

Simple count rules over all 307,996 qrels rows (exploratory, no teacher) do not give 49,973 either: one positive per directory 24,285,
at most two 42,667, at most three 57,413; positives of directories with at most 5 / 10 positives 34,769 / 63,727; distinct
(repository, function id) pairs 226,468; no positive lies in a test file (D9 path rule), so a test-function exclusion is not the gap.

**Teacher agreement per positive** (Spearman of ranks, instance-clustered bootstrap; Cohen's kappa of top-K membership):
SweRankEmbed-Small and CodeRankEmbed 0.855 [0.791, 0.896], kappa 0.64 at K = 20 (597 both inside, 267 only under SweRankEmbed-Small,
12 only under CodeRankEmbed, 646 neither) and 0.69 at K = 40; each dense teacher and BM25 0.53 [0.33, 0.67] and 0.53 [0.35, 0.65],
kappa 0.36 at K = 20; the two text forms of SweRankEmbed-Small 0.899 [0.835, 0.929], kappa 0.85 at K = 20.

**By repository and held-out flag** (sample, descriptive; no interval). Of 118 sampled repositories, the share with no positive in the
top 40 is 0.9% (SweRankEmbed-Small), 5.9% (CodeRankEmbed), 13.6% (BM25); the share with every positive inside is 59%, 47%, 38%. Median
rank in held-out against kept directories: 7 vs 14 (SweRankEmbed-Small), 31.5 vs 49 (CodeRankEmbed), 35 vs 32 (BM25); by size
quartile the dense teachers' outside-top-40 shares range 26-45% and 32-59% (`x3_pool_ranks_groups.csv`, `x3_pool_ranks_repositories.csv`).

**The three readings stated in advance.**
(a) *If the directories are only PRs with at least one positive kept by the SweRank+ filter, the share of directories with no positive in
the SweRankEmbed-Small top 40 is near 0.* Observed 2 of 160 (code text) and 0 of 160 (stored text, even at K = 10): consistent.
(b) *If the qrels are the unfiltered modified functions and Table 1 counts the kept ones, the estimate of positives inside the
SweRankEmbed-Small top 40 is near 49,973.* Observed 186,531 [160,311, 233,797] (200,660 for the stored text): not consistent; even at
K = 10 and under every teacher the estimate is above 49,973 with its interval.
(c) *If the qrels themselves were filtered, nearly every positive is inside the SweRankEmbed-Small top 40.* Observed 39.4% [24.1, 48.0]
outside (34.9% for the stored text): ruled out.

**Reference: the same teachers on a never-filtered set** (stated in the configuration before it was run). The authors' export of
SWE-bench Verified in the same directory format (`swe_bench_verified.zip` of the same dataset repository; 457 of 500 directories carry
qrels) was never consistency-filtered and its repositories are outside SweRankEmbed-Small's training pool (SweRank excludes SWE-bench
repositories). Share of directories with no positive in the top K, plain sample shares with exact intervals
(`x3_pool_ranks_reference.csv`):

| teacher | K | pool sample (160) | Verified export (457) | pool, 1,000-2,999 functions | Verified, 1,000-2,999 functions | pool, 1 positive | Verified, 1 positive |
|---|---|---|---|---|---|---|---|
| SweRankEmbed-Small, stored text | 10 | 0 [0, 2.3] | 19.3% [15.7, 23.2] | 0 of 34 [0, 10.3] | 25.0% [13.6, 39.6] | 0 of 34 [0, 10.3] | 18.6% [14.6, 23.2] |
| SweRankEmbed-Small, stored text | 40 | 0 [0, 2.3] | 9.4% [6.9, 12.5] | 0 of 34 [0, 10.3] | 12.5% [4.7, 25.3] | 0 of 34 [0, 10.3] | 9.8% [6.8, 13.4] |
| CodeRankEmbed | 10 | 16.9% [11.4, 23.6] | 35.7% [31.3, 40.3] | 23.5% [10.8, 41.2] | 45.8% [31.4, 60.8] | 23.5% [10.8, 41.2] | 35.5% [30.4, 40.9] |
| CodeRankEmbed | 40 | 5.6% [2.6, 10.4] | 17.5% [14.1, 21.3] | 14.7% [5.0, 31.1] | 33.3% [20.4, 48.4] | 5.9% [0.7, 19.7] | 20.4% [16.2, 25.1] |

Reading: on never-filtered issues the same teacher with the same text leaves about one directory in five without a positive in its top
10; in the pool not one of 160 is (also within matched snapshot size and positive count). Under the independent CodeRankEmbed the pool is
easier than Verified as well (a third to a half of the no-positive share), so part of the gap is a difference between the two sets (repositories,
issue style); the remainder, a share that goes to zero only under SweRankEmbed-Small, is specific to that model.

**Conclusion (what is certain, what is not).**
- Certain within this sample: the positive-level consistency filter of SweRank+ has not been applied to the qrels. Under the filter's
  own teacher, in either text form, a third or more of the positive rows rank outside the top 40, and far more than 49,973 positives
  rank inside it. So the directories' positives are the unfiltered modified functions (or a superset that no filter we can reproduce
  explains), and a RAW arm at the positive level is available from this pool.
- Certain: Table 1's 49,973 is not the count of these directories' positives surviving a top-K filter under the released teachers for
  any K in {10, 20, 40}; the directories are not the paper's instance set, and the paper's count cannot stand in for the size of a
  FILTER arm built from them.
- Measured, with the reference: the directories are a set selected with respect to SweRankEmbed-Small. No sampled directory lacks a
  positive in its stored-text top 10, against 19.3% [15.7, 23.2] of never-filtered Verified directories under the same teacher and
  settings, and the gap is larger than under the independent CodeRankEmbed. This is what a PR-level consequence of the SweRank+ filter
  (keep a PR if one of its positives passes; the published SweRank script cuts at rank 10) would produce.
- Not decidable here: whether that selection is a filter applied to the pool or the fit of the released SweRankEmbed-Small to these pull
  requests. The same picture arises without any filter if the released checkpoint has been trained on them: it was
  fine-tuned on the SweRank training data (Python PRs of popular PyPI repositories, the same authors' collection), and on this pool it
  ranks positives far better than its own base model (median 10 against 38.5; 267 against 12 positives inside the top 20 under one
  teacher only). Inference: a PR-level filter removes the PRs whose every positive fails; how many those were is not recoverable from
  the directories; on the Verified reference the same rule would remove 9.4% (top 40) to 19.3% (top 10) of PRs. Held-out-repository directories (14% of the pool) show the same no-positive share under SweRankEmbed-Small as the rest (1 of 80 each).
- Cheapest experiment that would separate filter from fit: creation dates of the pool's PRs against the release date of the
  SweRankEmbed-Small checkpoint (needs `GITHUB_TOKEN`, D2). PRs created after it cannot have been in its training data; if they too
  never lack a top-10 positive, the pool was filtered; if they behave like the Verified reference, the selection is the checkpoint's fit.
  A token-free variant: the pool's 2,448 repositories against SweRank's own 3,387 (not released; the authors' code may list them).

**What each case means for the RQ2 arms** (evidence for ADR-001 and ADR-002, no decision).
- *Directories unfiltered* (all collected PRs): RAW = every positive of the surviving repositories; FILTER, WEIGHT and CURRICULUM are
  computed from a teacher's K-rank on the same positives; the four arms come from one pool as designed.
- *Directories filtered at PR level by SweRankEmbed-Small* (qrels unfiltered, as measured): RAW is available at the positive level but
  is "RAW given that the PR has at least one easy positive"; the hardest PRs (every positive failing) are missing in unknown number.
  RAW-versus-FILTER contrasts measured on this pool then understate the noise RAW carries, so an effect found would be conservative and
  a null would not exclude an effect on a fully raw pool; the limitation would be stated with the result. FILTER, WEIGHT and CURRICULUM
  stay buildable.
- *Qrels filtered per positive* (the case in which RAW would not exist in this pool): ruled out by (c).
- In every case, SweRankEmbed-Small is a doubtful K-rank teacher for this pool: if it was trained on these PRs, its rank of a positive
  is a training fit, not an independent quality signal (ADR-002's rule that the quality encoder is separately pretrained is about the
  trained model; this is the same concern for the teacher). CodeRankEmbed (pretrained only) disagrees with it on 279 of 1,522 positives
  at K = 20. Which teacher and K define FILTER stays with ADR-002 and E-PILOT-K.

**Full-pool feature table: cost from measured throughput.** Pool functions: 24.72 GB of corpora times 0.001152 functions per byte (the
pool check's simple random sample of 300) = 28.5 million function texts; within-repository dedup (texts repeat across a repository's
snapshots): 16 repositories in four bins of directories per repository, distinct/all 0.998 (1 directory), 0.300 (2-9), 0.148 (10-49),
0.058 (50+), weighted by the bins' shares of pool bytes 0.117 (conservative, each bin's largest per-repository ratio: 0.239). Measured
encode rate on one RTX 2080 Ti at 1,024 tokens, float16: 278 texts/s (SweRankEmbed-Small), 275 (CodeRankEmbed), 260 (stored text).
Encoding alone would take 3.3 GPU-hours per dense teacher with dedup; the GPU is held for the whole loop, so the estimate uses a wall-time
model fitted to the five measured GPU runs (wall = 0.000203 s per function processed + 0.00355 s per text encoded; fits each run within
2%): 4.9 GPU-hours per dense teacher with dedup (8.3 conservative; 29.7 without dedup), both teachers about 9.7 (16.6 conservative); 4.15 GB of compressed corpora to stream (about 12 minutes at the measured 6 MB/s from Hugging Face). BM25 for the whole
pool (no dedup): 160 directories took 124 s for 188,566 functions on one process, so about 5.2 CPU-hours, about 1.3 hours in four shards.
Commands: `x3_dense.sbatch` with `SELECT=all SHARD="i n"` and `x3_pool_full.sbatch` (BM25), resumable per directory, then
`scripts/pool_ranks.py tables`; the estimate fits block 2's 24 GPU-hours; not run.

**What this does not show.** 160 directories: the pool-level estimates of positive counts have wide intervals (the positive count per
directory is heavy-tailed, 1 to 3,924). One cut (1,024 tokens) and float16 on one GPU type; the authors' text form, cut and precision for
the SweRank+ filter are not stated. Ranks count ties in the positive's favour (27% of BM25 positives tie with at least one function,
mostly at score 0). The dedup ratio rests on 16 repositories; the conservative figure bounds it from that sample only.

## E-TRAIN-STACK: the training stack and its validation, 2026-10-25

**What it is.** Apparatus for RQ2, not an experiment with a result: the path from pool directories to a scored checkpoint, with the
arms entering only through three hooks (`ril/training/README.md`). Every training value (budget, learning rate and schedule, batch
shape, negative policy, loss form, temperature, base encoder) is a configuration value marked `provisional: ADR-001, ADR-002, ADR-006`;
none has a code default, and a provisional configuration is refused under `configs/frozen/`. The negative policy is held identical
across arms (DEV-012, Q46).

**Tests (local, CPU, synthetic pool; `make test`, `make test-all`).** (1) Arms only differ through the hooks: FILTER at K = infinity,
WEIGHT with weights all 1 and CURRICULUM with a constant difficulty give batches, first gradients and trained parameters bit-identical to
RAW's; away from the identity, WEIGHT changes only the weights, FILTER and CURRICULUM change the batches; configurations that differ
outside the `arm` section are refused (`tests/unit/test_arms_only_differ_through_hooks.py`). (2) End to end on the tiny model: archive
-> reader (held-out drop, feature-table coverage) -> BM25 mining -> FILTER -> 12 updates; a run stopped after 6 updates and resumed
equals the uninterrupted run bit for bit (plan hash and parameters); result directory and run log written; evaluation hook paired
against an untrained baseline; unit and chunk levels agree where the synthetic chunks are the units
(`tests/integration/test_training_end_to_end.py`). (3) Same seed, same run; other seed, other run (`tests/reproducibility/test_training_repro.py`).
(4) Leakage check (d) passes again: the training package reaches no evaluation, analysis or bench code (it did not before this
session: the pool-rank jobs imported the GPU gate from evaluation code; the gate moved to `ril/util/gpu.py`).

**Cluster validation (CPU only, 0 GPU-hours; jobs 38730, 38731; log `results/logs/t1_training_stack_2026-10-25.json`).**
- *Selection* (held-out list v2 with the rename cache, the E-POOL-RANKS feature table): 24,285 directories listed, 3,485 held out (the
  count X3 measured), 20,720 outside the table, 80 kept, 24 drawn by the seeded order; 24 streamed by range request in 17 s, 0 errors.
- *Tiny model* (`configs/experiments/t1_validate_tiny.yaml`, hash `74d02bf3`): FILTER at K = 40 under CodeRankEmbed at the positive
  level kept 131 of 301 positives (43.5%) and 23 of 24 examples; 30 updates at batch 8 = 240 example visits, 23 unique, 10.4 effective
  epochs (the reuse that FILTER brings at matched updates, in miniature). Its retrieval numbers are not a result (hashed bag of words,
  24 training instances).
- *Evaluation hook* on the X2 development preparation, paired against CodeRankEmbed at 512 tokens: the BM25, CodeRankEmbed and RRF
  (k = 60) rows reproduce `results/tables/x2_first_dev.csv` and `x2_chunks_dev.csv` exactly, values and repository-clustered intervals,
  18 of 18 rows (L2 nDCG@10 and L3 Recall@100, both D18 readings and chunk level; e.g. dev L2 nDCG@10 under the primary reading: BM25
  21.17 [13.55, 27.85], CodeRankEmbed 17.16, RRF 23.56). The hook is therefore the X2 measurement applied to a new variant.
- *CodeRankEmbed path* (`configs/experiments/t1_validate_cre.yaml`, hash `8ac6819f`): 4 updates on the CPU, stopped after 2 and resumed
  from the step checkpoint, half-precision final model (274 MB) reloaded and used to encode; 4.5 s per update (batch 2, 128 tokens, 4
  threads). One step checkpoint with optimizer state plus the final model: 1.8 GB, which is what `$HOME` has free (`docs/COMPUTE.md`).

**Training throughput and memory on one RTX 2080 Ti** (job 38747, account A, 0.12 GPU-hours; stage `train_step` rows in
`results/latency/throughput_log.csv`, workloads `train-coderankembed-b<B>-n<N>-p<P>-t<T>[-amp_fp16][-gc]-v1`; 3 warmup and 10 timed
updates per shape on a throwaway model, one process per shape). CodeRankEmbed at 512 tokens fits only 4 examples with one positive
and one negative (8 documents) in float32 (9.2 GB peak, 7.1 examples/s) and in float16 autocast (8.1 GB, 13.8 examples/s); with
autocast plus gradient checkpointing, batch 32 with one positive and one negative fits (64 documents, 6.9 GB, 12.1 examples/s, 2.65 s
per update), batch 16 with two positives and three negatives (76 documents, 7.6 GB, 6.3 examples/s), and batch 8 at 1,024 tokens
(5.8 GB, 4.9 examples/s). For scale: the SweRank recipe's batch 64 with 15 hard negatives is 1,024 documents per update; at the measured
rate of about 24 documents/s under checkpointing, 20,000 updates of batch 32 x (1 + 1) would take about 15 GPU-hours per run (inference
from these rows; a larger or gradient-cached batch would cost more). Batch shape, precision and checkpointing are `provisional: ADR-002`;
nothing is chosen here.

**What this does not show.** Nothing about which arm, teacher, K, negative policy or budget is better; the `sentence-transformers`
path was trained for 4 updates on the CPU and measured for 13 updates per shape on the GPU, not run to convergence.

## E-PILOT-K, E-PILOT-NEG, E-PILOT-LEAK: smoke pilots, exploratory (stated 2026-10-25, before any training run)

**Purpose.** Evidence for ADR-002 (quality signal, K, teacher, negative policy) and ADR-001 (the held-out filter's effect) at a
tiny budget; effect sizes at this budget may not transfer to the RQ2 budget, and nothing here decides anything.

**Held identical across every condition** (`configs/experiments/t2/*.yaml`, one file per condition and seed; every value a
pilot value, `provisional: ADR-001, ADR-002, ADR-006`): base CodeRankEmbed (pinned revision) at 512 tokens, float16 autocast with
gradient checkpointing; batch 32 x (1 positive + 1 hard negative) plus in-batch negatives (Q53); multi-positive InfoNCE
(`sum_in_numerator`, batch normaliser, temperature 0.05); AdamW lr 2e-5 (SweRank's small-retriever value), weight decay 0.01,
7 warmup updates then linear decay, clip 1.0; **63 optimizer updates** in every run (one pass over selection A's 2,000
examples at batch 32: 2,016 visits); the final model in half precision; evaluation by the X2 hook on the development
repositories, units only (decision D12's level; chunks skipped for budget), RRF k = 60 with BM25 beside the dense column.
Seeds 0 and 1 per condition (training seed; the selection is fixed). Teacher ranks: one pass over the example cache per teacher
(CodeRankEmbed, SweRankEmbed-Small at 1,024 tokens, float16; BM25), with E-POOL-RANKS's rank definition; feature table
the feature table of selection A (untracked; ids hashed as in E-POOL-RANKS).

**Pool.** Selection A: the first 2,000 directories outside the held-out list (v2 with the rename cache) by sha256("0:<directory>");
cached with 0 fetch errors, 2,000 examples. Selection L (E-PILOT-LEAK only): the first 2,000 directories of the whole listing by
the same order, held-out repositories included: 292 held-out directories in place of A's last 292. No Verified-six repository
has a directory in the pool (92 held-out repositories occur in it, none of them in Verified-six; two development repositories
do: haystack 140 and streamlink 109 directories), so on Verified-six the pilot can see only indirect leakage.

**Conditions.**
- E-PILOT-K: RAW (`t2_k_raw`); FILTER at the positive level, K in {10, 20, 40}, under CodeRankEmbed, SweRankEmbed-Small, BM25 and
  the agreement of CodeRankEmbed and BM25 (a positive is kept if it is inside the top K under both); WEIGHT (power form
  min(1, (20 / K-rank)^1), floor 0.1, example K-rank under CodeRankEmbed); CURRICULUM (easy to hard by the example K-rank under
  CodeRankEmbed, 4 quantile buckets). Negatives `random_repo` in every cell. Q52: every cell whose teacher includes CodeRankEmbed
  has `teacher_equals_base` true (recorded per run).
- E-PILOT-NEG (RAW arm in every cell): `random_repo` (= `t2_k_raw`), `teacher_top_m` (M = 15, CodeRankEmbed miner, the base
  checkpoint), `teacher_top_m_poscut` (M = 15 after dropping candidates scored at or above 0.95 x the best positive's score:
  reference positive `max`).
- E-PILOT-LEAK: `t2_k_raw` (selection A) against `t2_leak_in` (selection L), both evaluated on the development repositories and on
  Verified-six, the latter labelled "uses test repositories deliberately, for the leakage effect; not a final number".
- Run order (reverse priority for dropping if the 20 GPU-hour cap is reached): RAW with its Verified-six evaluation, FILTER
  cells, NEG, LEAK, then WEIGHT and CURRICULUM.

**Readings stated in advance** (tables by `scripts/t2_tables.py pilots configs/experiments/t2_pilots.yaml`, method in
`ril/analysis/t2_tables.py`). Primary numbers: dev L2 nDCG@10 and L3 Recall@100 under the D18 primary reading, dense column (the
trained encoder alone), RRF column beside. Effect = condition minus reference, seed means, paired over queries; 95% intervals over
queries and over repositories (D17). A cell is called different from its reference only if its query-level interval excludes 0
**and** its effect is larger than the reference's own seed-0-to-seed-1 difference on the same queries; otherwise
indistinguishable at this budget. With about 15 contrasts x 2 levels, one or two intervals excluding 0 are expected by chance.
Every condition is also shown against the untrained base (does 63 updates move the model at all). Two seeds give one
seed-to-seed difference per condition: they can show an effect larger than one retraining's change, not a seed standard
deviation, and the intervals carry query sampling only.

**Results (2026-10-29; 36 runs, all finished; tables `results/tables/t2_pilot_*_{effects,seeds,runs}.csv`, teacher tables
`t2_teacher_{shares,agreement}.csv`, log `results/logs/t2_pilots_2026-10-29.json`, result directories `results/rq2/t2_*/`).**
Dev, D18 primary reading, percentage points; effect vs RAW, seed means, [query-level 95% interval]; "noise" = RAW seed 1 minus
seed 0 on the same queries (dense: L2 0.78, L3 0.26; RRF: L2 0.15, L3 -0.11). Flag "beyond" = interval excludes 0 and |effect| > noise (the
stated rule).

| cell | positives kept | examples kept | dense L2 nDCG@10 | dense L3 Recall@100 | RRF L3 Recall@100 |
|---|---|---|---|---|---|
| base (untrained) | | | 17.16 | 33.93 | |
| RAW (vs base) | 100% | 100% | 25.44 (+8.28 [6.77, 9.80]) | 44.97 (+11.03 [9.12, 12.98]) | 47.37 (+4.74 [3.65, 5.91]) |
| FILTER CodeRankEmbed K10 / 20 / 40 | 22.5 / 31.3 / 42.0% | 82 / 91 / 96% | -0.49 / -0.17 / -0.30 | **-0.77** [-1.45, -0.08] / +0.01 / -0.25 | **-0.63** / -0.10 / -0.30 |
| FILTER SweRankEmbed-Small K10 / 20 / 40 | 45.0 / 50.9 / 57.9% | 96 / 98 / 100% | +0.48 / +0.08 / +0.11 | **-0.98** [-1.70, -0.33] / **-0.58** / -0.30 | -0.24 / -0.21 / +0.05 |
| FILTER BM25 K10 / 20 / 40 | 22.3 / 30.9 / 44.7% | 74 / 83 / 90% | -0.61 / -0.23 / -0.54 | **-1.13** [-1.71, -0.58] / -0.63 / **-1.61** [-2.30, -0.99] | **-0.94** / **-0.54** / **-0.79** |
| FILTER agreement CodeRankEmbed+BM25 K10 / 20 / 40 | 12.5 / 19.9 / 31.0% | 61 / 75 / 86% | **-0.80** [-1.39, -0.23] / -0.21 / +0.13 | **-1.16** / -0.56 / **-0.41** | **-0.76** / -0.20 / -0.36 |
| WEIGHT (CodeRankEmbed, power, K 20) | 100% | 100% | -0.32 [-0.59, -0.08] | **-0.43** [-0.72, -0.15] | -0.11 |
| CURRICULUM (CodeRankEmbed, 4 buckets) | 100% | 100% | -0.31 | **-0.68** [-1.15, -0.27] | -0.25 |
| NEG teacher top-15 (CodeRankEmbed miner) | | | -0.21 [-0.98, 0.52] | +0.35 [-0.71, 1.49] | -0.72 [-1.61, 0.05] |
| NEG top-15 after the 0.95 positive cut | | | +0.63 [0.11, 1.13] | **+1.10** [0.35, 1.90] | -0.18 |
| LEAK: selection L (292 held-out dirs) vs A, dev | | | +0.18 [-0.25, 0.57] | +0.16 [-0.21, 0.53] | +0.07 |
| LEAK, Verified-six (uses test repositories deliberately, for the leakage effect; not a final number) | | | +0.51 [-0.46, 1.59] (L2 n = 83) | -0.25 [-0.90, 0.34] (n = 55) | -0.45 [-0.83, -0.10] |

Bold: beyond the stated rule. Every flagged FILTER, WEIGHT and CURRICULUM cell is negative and the same sign in both seeds except
SweRankEmbed-Small K20 at L3 (seeds +0.22, -1.38); the one positive flag among the arm cells is RRF L2 under SweRankEmbed-Small K10
(+0.66 [0.18, 1.16]). About 60 arm contrasts were made, so two or three flags would be expected by chance; the pattern (strict filters,
and BM25 at every K, lower L3) is more than that, the size (about 1 point) is not. L2 and repository-clustered intervals in
`t2_pilot_k_effects.csv`.

**Cost.** Per run: 63 optimizer updates, 2,016 example visits, 0.046-0.047 GPU-hours of training loop (about 2.8 minutes); unique
examples seen = examples kept (FILTER 1,229-1,992; RAW, WEIGHT, CURRICULUM, NEG, LEAK 2,000), effective epochs 1.008 (RAW) to 1.64
(agreement K10): at matched updates a strict filter re-visits its kept examples, as designed. Whole run including the dev evaluation
about 22 minutes (about 0.37 GPU-hours; the evaluation encodes the trained model's dev unit texts at about 50 texts/s, a quarter of
X2's rate); with the Verified-six evaluation about 42 minutes. Teacher passes 2.20 GPU-hours (both dense teachers over 1.95 million
functions), BM25 2 CPU-minutes. Session total 16.87 GPU-hours of block 2 (jobs 39098, 39100, 39101, 39188, 39212; `docs/COMPUTE.md`).
The positive-cut cell had 70 of 2,016 visits with no eligible negative (shortfall). Q52: `teacher_equals_base` is true for every
cell whose teacher includes CodeRankEmbed (FILTER CodeRankEmbed and agreement, WEIGHT, CURRICULUM) and for the NEG miner; those cells
do not behave differently from the SweRankEmbed-Small and BM25 cells at the same K (e.g. L3 K10: -0.77, -0.98, -1.13).

**Teachers on selection A** (2,000 directories, 25,318 positives): positives inside the top 10 / 20 / 40: CodeRankEmbed 22.6 / 31.3 /
42.0%, SweRankEmbed-Small 45.0 / 50.9 / 57.9%, BM25 22.3 / 30.9 / 44.7%; directories with no positive inside the top 10:
17.9% [16.2, 19.6], 4.3% [3.5, 5.2], 26.2% [24.3, 28.1] (Wilson). Spearman per positive: CodeRankEmbed~SweRankEmbed-Small 0.854
[0.818, 0.884], CodeRankEmbed~BM25 0.706 [0.65, 0.75], SweRankEmbed-Small~BM25 0.667 [0.60, 0.72]; kappa of top-20 membership 0.57, 0.48,
0.43. SweRankEmbed-Small again ranks the pool's positives far better than the others (E-POOL-RANKS, Q50).

**What this would change in the plan (evidence, not decisions).** ADR-002: no difference between RAW and any consistency filter,
weight or curriculum cell is detectable at 63 updates. That is a statement about the budget (about 0.3% of a planned run; RAW alone does move the encoder
well away from its base, so the budget trains, but it is not shown to separate the arms), not a finding about filtering: it does not say that filtering fails or helps. The strict cells sit about 1 L3
point below RAW, which fewer unique positives per update explains without any claim about label quality; the positive-aware cut is the
only setting that moved L3 upward, which bears on Q46 (the negative policy held identical across arms). ADR-001: the held-out
filter's removal of 14.6% of the pool shows no difference detectable at 63 updates on dev or Verified-six; whether it is hygiene
for the claim only or changes numbers at larger budgets is not shown; the direct case (held-out development repositories in training)
is in this pair only at about 30 directories and showed nothing detectable either.

**What it does not show.** Two seeds: one seed-to-seed difference per condition, not a standard deviation; the intervals carry query
sampling only. 63 updates is about 0.3% of the master's 20,000; a filter's benefit (less label noise) may need many epochs to show and
its cost (fewer unique positives, more repetition) dominates early. Dev has five repositories and two of them carry the L3 queries
(Q47). One base, one batch shape (32 x (1 + 1)), one learning rate, units only (no chunk level). The structural negative factor and
the RQ2 arms at their real budget are not run.

## E-CONTAM-SCAN: full documents-only contamination scan, exploratory, done 2026-10-29

Decision D23 (ADR-005 addendum). Config `configs/experiments/x4_contam_scan.yaml` (hash `87ac11b7293b`), committed (`b9680b3`) **before** the full result was read, with the floor chosen from the 24-shard slice only. Log `results/logs/x4_contam_scan_2026-10-29.json`, table `results/tables/x4_contam_scan_by_repo.csv`, row `x4-contam-scan`; jobs in `results/logs/ada_jobs.csv` (account A). Not part of the frozen evaluation.

**Floor and why.** 20 syntax-tree nodes (`ast.walk` count of the matched function); 50 and 100 as sensitivity readings, all stated before the result. In the slice, the share of hit documents whose hash occurs at the base commits of more than one of the 12 repositories (a generic function) was 39% below 20 nodes, 2% at 20 to 29 and 1% or less above; 15 and 10 nodes would have left 3% and 27%. 73% of the slice hits were under 20 nodes.

**What was scanned.** All 240 shards, 23,881,192 rows (every row had a `document`), 306.6 GB of compressed stream; negatives not scanned. Shard jobs 45620 and 45621 (4 workers each, 2 h 13 min and 2 h 06 min) plus 45774 for the one shard (87) whose three attempts hit transient name-resolution failures. Measured cost: 17.9 worker-hours summed over shards (the earlier 10 CPU-hour estimate counted CPU only; the rest was waiting on the network), 4.7 GB peak RSS on the first job (estimate was 1.5 GB from the slice; 8 GB requested was enough). The base-commit hashes (500 instances, 7,397,591 function entries at or above 20 nodes) came from job 45623 (32 min, 1.4 GB). No hit record was truncated (`any_hits` equals the records for all 240 shards) and no hit lacked a syntax-tree hash.

**Result, all hits.** 150,198 documents (0.63%) match a Verified function by syntax-tree hash (slice: 0.61%); 32,714 distinct hashes. By size of the matched function: under 20 nodes 106,777 (71%), 20 to 49 16,290, 50 to 99 13,021, 100 or more 14,110.

**Result, restricted.** Hash must be a function at an instance's own base commit of that repository and at or above the floor (a document counts for each repository whose instances contain the hash; the ALL row counts a hash once):

| floor (nodes) | hit documents | distinct probe functions | of them in the corpus (Wilson 95%, descriptive) |
|---|---|---|---|
| 20 (primary) | 43,421 | 194,187 | 26,530 = 13.7% (13.5-13.8) |
| 50 | 27,131 | 138,509 | 18,391 = 13.3% (13.1-13.5) |
| 100 | 14,110 | 84,409 | 10,435 = 12.4% (12.1-12.6) |

Per repository at the primary floor (instances; distinct functions above the floor; functions in the corpus with Wilson interval; hit documents; median share of an instance's functions above the floor that match, range over instances): astropy 22; 20,449; 22.3% (21.7-22.9); 5,050; 28% (20-34%). django 231; 38,826; 17.6% (17.3-18.0); 14,696; 22% (20-24%). matplotlib 34; 16,013; 12.8% (12.3-13.3); 3,417; 19% (16-21%). seaborn 2; 2,146; 14.3% (12.8-15.8); 423; 14%. flask 1; 714; 4.1% (2.8-5.8); 377; 4%. requests 8; 1,219; 26.5% (24.1-29.0); 1,679; 33% (25-37%). xarray 22; 11,241; 8.5% (8.0-9.1); 1,031; 7% (6-17%). pylint 10; 7,498; 7.7% (7.2-8.4); 740; 7% (6-18%). pytest 19; 10,407; 7.0% (6.5-7.5); 772; 5% (3-16%). scikit-learn 32; 18,809; 18.6% (18.1-19.2); 7,720; 18% (16-31%). sphinx 44; 10,732; 6.0% (5.6-6.5); 677; 4% (4-14%). sympy 75; 56,208; 10.7% (10.5-11.0); 7,382; 15% (12-22%). The full table, with the 50 and 100 floors, is in the CSV.

**What this says.** Every one of the 500 instances has at least one matching function at every floor, so "does the instance have a hit" carries no information; the share of an instance's own functions that occur in the corpus does (4% to 33% by repository median at floor 20, higher in repositories whose corpus snapshot is close to the base commits). The restriction to the instance's own base commit removes nothing at repository level (the probe was built from exactly those snapshots, so the repository rows equal the union-probe counts; a first version of the tables compared the two and was dropped as vacuous); it matters per instance, which is how the shares above are computed. Floors 50 and 100 change the counts; by share of functions in the corpus, requests and astropy lead and pytest, sphinx and flask trail at all three floors, while the middle ranks (django, scikit-learn, seaborn, matplotlib, sympy, pylint, xarray) swap neighbours.

**What a hit does not say.** A hit is a function-level match: a function with this exact syntax tree occurs as the `document` of a CoRNStack row. It is not proof that the (query, document) pair was trained on, that the Verified issue or its patch was seen, or that any model memorised anything; the corpus may contain the function from a different commit, a fork or a vendored copy, and a retriever trained on the corpus is not the project's encoder choice (ADR-006 open). A non-hit does not show absence (renamed or edited copies, negatives not scanned, no gold-patch matching). Functions are not independent draws, so the intervals are descriptive; the two- and one-instance repositories (seaborn, flask) carry no instance-level interval worth reading.

**The D23 flip experiment (edited functions among the hits)** was run on 2026-10-29, see E-CONTAM-EDITED below.

Reproduce: `scripts/ada/README.md` ("Pool check and contamination probe"); tables by `contam_probe.py tables`; code `ril/analysis/x4_tables.py`, `ril/training/contamination_index.py::instance_hashes`, tests `tests/unit/test_x4_tables.py`.

## E-DEV-ANSIBLE: SWE-bench Pro ansible as a third development repository, done 2026-10-29

Decision D32 (Q47): dev L3 had two repositories (openlibrary, qutebrowser), so its repository-clustered interval was not informative. Pro `ansible/ansible` (83 instances with L3 qrels, unit records already made by E-L3-CENSUS) becomes a dev folder. Verified remains the final test set and is not touched. This is apparatus: no metric was computed and no setting was chosen from it.

**Configuration.** `configs/experiments/e1_bm25_dev3.yaml` is `e1_bm25_reproduction.yaml` copied unchanged (17 folders, same BM25 parameters, metrics, bootstrap, seed 0, same dev and test roles) plus one folder: dataset `SWE-bench_Pro`, folder `instance_ansible__ansible`, repo `ansible/ansible`, levels L2 and L3, `units: true`, role `dev`. The original file is untouched, so the hashes of earlier runs hold. The instance-cache hash (`prepare_hash`) does not depend on the folder list, so no existing cache is invalidated.

**What was built (CPU, account A, job 46142, 43 min, 3.5 GB peak of 12 GB requested).** The 83 unit records of the census were linked in; `ansible` has 12,530 units at the base commit of the first instance. Pilot-E3 instance cache for the 83 instances (`~/ril_e/e3_cache_ansible/`, 25 MB, same arrays as the other dev files including the D18 gold readings without module units), the unit-text stores (`texts_units/ansible__ansible.s{0,1,2}.jsonl`, 199 MB), 87 L2 and 83 L3 query texts, the chunk-text store (`texts_chunks/ansible__ansible.jsonl`, 86 MB) and the per-instance unit-hash arrays (`prep/units/`, 83 files) were added next to the existing X2 files in `~/ril_x2/prep` and the cache files copied (new files only) into `~/ril_t1/work/e3_cache/`. Nothing existing was overwritten. Working clones were node-local. Dense vectors for ansible do not exist: the X2 baseline encodings predate it, so a baseline column for ansible is absent until the encoder is run on the new stores; a checkpoint evaluation encodes the stores itself.

**Check.** `stores_for` on the new configuration returns the four ansible stores; a cache file has role `dev`, levels L2 and L3 and the same array names as a qutebrowser file; 83 of 83 unit-hash files and cache copies exist.

**To include it in an evaluation.** Pass `--e1-config configs/experiments/e1_bm25_dev3.yaml` (instead of `e1_bm25_reproduction.yaml`) to the checkpoint evaluation, with `--prep ~/ril_x2/prep`, `--e3-cache ~/ril_t1/work/e3_cache` and `--data-root ~/ril_x2/raw` (links to `~/ril_e/raw`, which now links the two ansible folders). Dev tables built with `roles` = `dev` then carry ansible as a third L3 repository (5 dev L2 repositories become 6 with ansible; 2 dev L3 repositories become 3). Numbers produced with the old configuration and with this one are not comparable pooled; an interval over three repositories is still wide.

## E-CONTAM-EDITED: are the patched functions among the contamination hits, exploratory, done 2026-10-29

The flip experiment of decision D23 (ADR-005 addendum). Config `configs/experiments/x5_contam_edited.yaml` (hash `89d73965f4af`; the floors and scan come from E-CONTAM-SCAN, hash `87ac11b7293b`), written before the result was read. Log `results/logs/x5_contam_edited_2026-10-29.json`, table `results/tables/x5_contam_edited.csv`, row `x5-contam-edited`, jobs 46133 (first run, tables later superseded: its comparison pooled (instance, function) pairs, which weights long-lived functions by the number of instances and was dropped) and 46147 (final) in `results/logs/ada_jobs.csv`; CPU only, account A, 1 min 47 s, 0.41 GB peak. Not part of the frozen evaluation.

**Protocol.** For each of the 500 Verified instances the reference patch (Python sections only; the test patch is not used) is applied to the base-commit files with `git apply` in a scratch directory. An *edited* function is a function or method unit (nested definitions fold into the parent) whose line span contains an old-file line the patch touches (a removed or changed line; for a pure insertion the two old lines around it, as in E-LABEL-NOISE). Its *pre* version is the unit at the base commit, its *post* version the unit with the same file, qualified name and occurrence index after the patch; it is *changed* when the post syntax-tree hash differs from the pre hash. A *match* is a syntax-tree hash that occurs as the `document` of a corpus row (E-CONTAM-SCAN). Distinct hashes within a repository, pooled over the 12 repositories. Comparators: all other base-commit functions of the same repositories above the floor (the 13.7% of E-CONTAM-SCAN, here without the edited ones), and the unedited functions of the same patched files (same files, so a closer match in age and activity). Differences carry a repository-clustered percentile bootstrap interval (2,000 draws, seed 0, D17); single shares carry Wilson intervals that are descriptive (functions are not independent draws).

**Extraction.** The patch applied in 500 of 500 instances; no file failed to parse before or after. 886 edited functions (one without a syntax-tree hash); 25 instances edit no function or method (for example patches that touch only module-level lines); 108 functions are added by patches (not edited functions; reported separately).

**Result at the primary floor (20 nodes), measured.**

| group (distinct functions) | matched / n | share (Wilson 95%, descriptive) | difference to edited-pre, pts (repo-clustered 95%) |
|---|---|---|---|
| edited, as at the base commit | 70 / 783 | 8.9% (7.1-11.1) | |
| all other base-commit functions | 26,490 / 193,479 | 13.7% (13.5-13.8) | edited minus other -4.8 [-9.7, -0.8] |
| unedited functions of the same patched files | 3,419 / 13,347 | 25.6% (24.9-26.4) | edited minus same-file -16.7 [-21.0, -12.1] |
| post-patch version of the changed edited functions | 101 / 728 | 13.9% (11.6-16.6) | post minus other +0.2 [-3.8, +2.9]; post minus same-file -11.7 [-16.7, -7.0] |

Instances: 460 have an edited function above the floor; 52 of them (11.3%, 8.7-14.5) have at least one that matches. Of the 719 changed edited functions that have a post version and a pre size above the floor, 17 match in both versions, 27 only before the patch, 83 only after, 592 in neither (9 more are removed by the patch). Functions added by patches: 6 of 78 match (not interpretable at this size). Floors 50 and 100: edited 55 / 631 = 8.7% and 31 / 479 = 6.5% against 13.3% and 12.4% for the other functions; post versions 13.9% (88 / 633) and 12.8% (62 / 484). By size at floor 20 (edited minus other): 20-49 nodes 9.9% against 14.6% (-4.8 [-14.1, +1.1]), 50-99 nodes 15.8% against 14.7% (+1.1 [-6.0, +10.3]), 100 or more 6.5% against 12.4% (-5.9 [-10.1, -3.6]). By repository (edited matched / edited): django 34 / 334, sympy 17 / 143, pylint 6 / 18, scikit-learn 5 / 52, matplotlib 3 / 55, astropy 2 / 29, requests 2 / 9, xarray 1 / 34, pytest 0 / 36, sphinx 0 / 68, seaborn 0 / 4, flask 0 / 1; django and sympy hold 73% of the matches and 61% of the edited functions.

**What this says.** The patched functions are not over-represented among the hits. As they stand at the base commit they match less often than the other functions (8.9% against 13.7%, interval excludes zero but is wide with 12 repositories) and clearly less often than the unedited functions of the same files (25.6%); the fixed versions match at about the all-function rate (13.9% against 13.7%, difference +0.2 with an interval from -3.8 to +2.9). Reading (inference, not tested): the corpus is sampled from repository states later than most base commits, in which a fixed bug no longer has its old form, and edited functions are by selection recently active code, so the unedited neighbours in the same files are the longer-lived ones; this explains the direction without any reference to training, but the corpus snapshot dates were not checked. The condition of D23 under which a per-repository sensitivity row would be considered (a large share of edited functions in the corpus, concentrated in a few repositories) is not met: the share is below the all-function rate; pylint (6 / 18) is the only repository above it and has 18 functions.

**What a hit does not say.** A hit is an exact syntax-tree match of a function, not proof that the issue, the patch or the (query, document) pair was in any model's training data; a post-patch match is what any corpus taken after the fix would contain. A non-hit does not show absence (renamed or edited copies, negatives not scanned, no semantic matching). The result bears on the contamination statement only: it gives no ground to a per-repository sensitivity row and no ground to the claim that the evaluation is clean.

Reproduce: `contam_probe.py edited` and `edited-tables` through `scripts/ada/contam_edited.sbatch` (from `$HOME`, needs `~/ril_c/work/verified_patches.json`, built locally from the Verified table's `patch` column and copied over, untracked); summary CSV `python scripts/x5_tables.py results/logs/x5_contam_edited_2026-10-29.json results/tables/x5_contam_edited.csv`; code `ril/evaluation/contamination_edited.py`, `ril/analysis/x5_tables.py`, tests `tests/unit/test_x5_edited.py`.


## E-GRAPH-ROLE: is the graph a retrieval signal beyond same-file expansion? Exploratory, done 2026-10-29

**What it measures.** Q49 and the first half of the graph-role question of ADR-003: on the two fused first stages of X2, does expansion over graph
edges add anything to what taking more units of the files already found adds, at the same candidate budget? Nothing is decided; the graph role
(Q30) stays open.

**Setup.** Inputs unchanged: the E3 cache with the D18 readings (class form `full`, ambiguous call sites dropped, D19 families), the X2 dense
scores, the X2 cell (score level, C 5, gamma 0.7, two hops, graph weight 0.5, cap 50), no new tuning. First stages: RRF(BM25, Qwen3-Embedding-0.6B at
512 tokens, k 20, alpha 0.2) and RRF(BM25, CodeRankEmbed at 1024 tokens, k 100, alpha 0.4), the settings X2 stated for each. Candidate sources
(`ril/evaluation/s1_graph_role.py`): a none (first-stage score); b graph as stored (contain, import, invoke, inherit); c same-file expansion ordered
by first-stage score; d same-file expansion in random order (3 draws); e graph over non-contain edges only (import, invoke, inherit); f contain only;
and a control added after the first run (the numbers of that run had been read; declared in the configuration notes): `topm`, the next best
first-stage units with no file constraint. c, d and topm are size-matched to each of b, e, f and take the same graph-score values in the same order, so
the only difference between a graph variant and its counterparts is which units get the boost. The expansion sizes are in
`results/tables/s1/*_sizes.csv` (about 50 for b, 44 to 50 for e and f). Dev: 351 L2 and 155 L3 queries (five and two repositories); Verified-six: 83 and 55
(six repositories). Gold `units_all_nomod` (D18 primary), `units_all` beside it. Metrics nDCG@10 (L2), Recall@100 (L3), mean over queries, 2,000 bootstrap
draws seed 0, query-level interval `q` and repository-clustered interval `cl.` (D17). **Dev L3 has two repositories, so its clustered interval is not
informative (Q47); the Verified-six clustered interval is the cautious one.** Verified is read as a final-test style reading; no choice is made from it.
Configurations (sha256, 12 characters): `s1_graph_role_qwen3` cac71c9811d4, `s1_graph_role_cre` d457d884b16e, `_qwen3_sens` 58fdd0b5993a, `_cre_sens`
3f2b238712e5. Run log `results/logs/s1_graph_role_2026-10-29.json`; tables `results/tables/s1/`; job 46171 (CPU, 8.1 min, 195 MB), 0 GPU-hours.

**Results, RRF(BM25, Qwen3), Recall@100 at L3 (points; difference to the first-stage score `none`; `q` query-level, `cl.` clustered).**

| source | dev L3 (none 47.6) | Verified-six L3 (none 42.1) |
|---|---|---|
| b graph as stored | +10.3 [8.3, 12.3] | +3.8 [0.8, 7.4], cl. [1.0, 6.7] |
| c same-file by score | +11.3 [9.0, 13.6] | +6.5 [3.3, 10.1], cl. [1.7, 8.2] |
| d same-file random | +8.2 [6.1, 10.6] | +2.0 [-0.8, 5.2], cl. [1.2, 3.2] |
| topm (no file constraint) | +0.1 [-0.5, 0.7] | -0.1 [-1.7, 2.2] |
| e non-contain only | +3.9 [2.4, 5.5] | -0.5 [-2.0, 1.1], cl. [-1.9, -0.04] |
| f contain only | +11.3 [9.0, 13.7] | +4.9 [1.6, 8.7], cl. [2.1, 9.5] |
| **b minus c** | -1.0 [-2.9, 0.8] | -2.7 [-6.0, 0.8], cl. [-6.5, 3.9] |
| b minus d | +2.0 [-0.2, 4.1] | +1.7 [-1.7, 5.3], cl. [-1.9, 4.0] |
| e minus c | -6.2 [-8.6, -4.0] | -7.0 [-10.2, -4.1], cl. [-9.0, -2.9] |
| f minus b | +1.1 [-0.9, 3.0] | +1.1 [-0.8, 3.4], cl. [-1.3, 5.6] |

RRF(BM25, CodeRankEmbed), Verified-six L3 (none 37.8): b +5.7 [2.5, 9.2], c +7.7 [4.0, 12.2], d +2.5 [-0.2, 5.4], e +0.4 [-1.5, 2.3], f +5.0 [1.7, 8.9];
b minus c -2.0 [-5.2, 0.8], cl. [-6.4, 0.6]; e minus c -7.3 [-11.6, -3.5]. Dev L3 (none 42.1): b +12.2, c +13.2, b minus c -1.0 [-3.3, 1.2]. At L2
(nDCG@10) the graph (b) minus same-file by score is +0.6 [-0.2, 1.4] (Qwen3 dev), +1.7 [0.1, 3.4] (Qwen3 Verified, cl. [-0.4, 2.9]), +0.7 [0.0, 1.6] (CodeRankEmbed
dev), +1.4 [-0.3, 3.2] (CodeRankEmbed Verified, cl. [0.2, 3.1]): small, point estimates all positive; the clustered interval includes 0 for the two Qwen3 pairs and excludes it for the two CodeRankEmbed pairs (cl. [0.1, 1.3] dev, [0.2, 3.1] Verified). Non-contain
only at L2 is below same-file by score on dev (-1.3 [-2.2, -0.4] Qwen3) and level on Verified. The full tables (both readings, every pair) are in `s1_graph_role_*_compare.csv`.
Under `units_all` no ordering above flips (b minus c at L3: -0.2 to -2.3, e minus c: -5.7 to -7.8; contain only minus same-file by score on Qwen3 dev L3 +1.3 [cl. 0.3, 2.4]).
Weight sensitivity (dev, `_sens` configurations, w 0.2 / 0.5 / 0.8): b minus c at L3 is -1.0 to -1.3 at every weight and e minus c -3.6 to -6.3; nothing depends on the edge-of-grid 0.5.

**Reachability** (RRF(BM25, Qwen3); L3 gold units that the first stage leaves outside its top 100: dev 2,935 units in 149 queries, 2 repositories; Verified-six 1,926 units in 52
queries, 6 repositories; `s1_graph_role_*_reach.csv` has both first stages, both readings, top-5 and top-100 sources and every family). Share reached from the top 5 units *and not in a file
of any of them*, by hop limit (dev / Verified-six, clustered intervals in the csv): non-contain edges 2.2% / 0.9% in 1 hop, 8.3% [4.1, 10.3] / 8.4% [5.9, 14.9] in 2 hops (244 and 161
units); by family at 2 hops invoke 6.6% / 5.5%, import 1.3% / 2.3%, inherit 0.2% / 0.4%. All edges together (contain included) reach 13.5% / 15.8% not in the source files;
containment alone reaches none outside the sources' files (0 of 855 and 385 reached units): in this graph a containment edge never leaves its file, so contain-only expansion is a
tree-restricted same-file expansion. The files of the top 5 units hold 45.4% / 32.5% of those gold units. From the top 100 units: non-contain 2 hops not in a source file 3.4% / 4.3%; the files
of 100 sources hold 91.7% / 89.7%. CodeRankEmbed: 8.2% / 7.8% (top 5, non-contain, 2 hops, not same-file), same-file 47.6% / 25.5%.

**What it says (evidence class: measured, exploratory, one stated cell, 55 Verified L3 queries in six repositories, two dev L3 repositories, zero-shot encoders, random baselines from 3 draws).**
(1) The L3 gain of the graph over the first stage is real and is reproduced (+3.8 / +5.7 Verified, +10.3 / +12.2 dev), but a same-file expansion ordered by the first-stage score gets at least as much
(+6.5 / +7.7, +11.3 / +13.2). The part of that gain that is "other units of the files already found" is the whole of it that can be separated at this sample; the unordered same-file control (d) that earlier
waves used as chance understated what a file-level baseline reaches. (2) Taking the next best units of the ranking with no file constraint gives nothing at Recall@100 (topm +0.1 / -0.1), so the same-file
effect is not a top-of-ranking re-weighting. (3) Edges that leave the file: non-contain-only expansion reaches 8% of the missed L3 gold units from the top 5 in two hops, yet as an expansion
of 46 to 50 units it adds +3.9 / +5.7 on dev and nothing on Verified, and is 6 to 7 points below same-file by score on both. (4) Containment-only carries the whole effect here; it equals
the stored graph within the intervals. (5) At L2 the graph is ahead of same-file by score by 0.6 to 1.7 points in every pair; the evidence is inconsistent across first stages (clustered intervals above 0 for CodeRankEmbed only).
**Not shown:** that edges add nothing (b minus c at Verified L3 has an interval of about -6 to +4 points); the paired standard deviation implied is about 12 points, so a 2-point difference needs
roughly 300 L3 queries for 80% power (reasoned estimate), against 155 dev and 55 Verified. Ranking by hop-decay score rather than by first-stage score, a second budget, and graph-ordered same-file are not tried.

**Flip experiment for "the graph is a retrieval signal" (not run; time-box about 1 hour of code and 10 minutes of CPU, no GPU).** Stacked expansion at the same total budget: fill with same-file units by
first-stage score, then replace the lowest-scored 10 and 25 of them with the best non-contain neighbours (hop-decay order) of the seeds, and compare with the unreplaced same-file list. If the replaced
list beats the unreplaced one at L3 with a repository-clustered interval above 0 on dev plus Verified-six plus the Pro ansible L3 repository (D32; its cache exists as `e3_cache_ansible`, dense scores would
have to be produced), the graph carries retrieval signal that files do not. If it is level or below, the retrieval role reduces to file-level expansion and the graph's retrieval role is a demonstration feature.

**Reproduce.** `scripts/ada/s1_graph_role.sbatch` (`scripts/ada/README.md`); code `ril/evaluation/s1_graph_role.py`, `ril/analysis/s1_tables.py`, tests `tests/unit/test_s1_graph_role.py`; rows `s1-*` of `RESULTS.md`.

## E-PILOT-CURVE: how many updates move the encoder beyond seed noise? Exploratory, done 2026-10-29

Status: exploratory pilot (outside the pre-registered RQ tables). Config hashes 70f4195c (seed 0) and 6c520027 (seed 1)
(`configs/experiments/t3/t3_curve_raw_s{0,1}.yaml`), evaluation set `configs/experiments/e1_bm25_dev3_curve.yaml`. Hardware:
RTX 2080 Ti (11 GB), account A, jobs 46876 and 46879 (`docs/COMPUTE.md`). Every number below is `measured` and traces to
`results/rq2/t3_curve_raw/*/step_*/` and `results/tables/t3_curve/`.

**Question.** At what number of optimizer updates does the encoder move beyond seed noise, and does it keep moving?

**Setup.** RAW (no filter, unit weights, random order), CodeRankEmbed base, random repository-local negatives (D28 primary),
batch 32 x (1+1), float16 autocast, gradient checkpointing, 512 tokens (D31), learning rate 2e-5 with 7 warm-up updates
and the linear decay of a **3,000-update schedule**, held-out filter on, 2 seeds (0, 1). Pool: the first 5,000 directories
outside the held-out list in the seeded order (selection A's 2,000 plus the next 3,000; `held_out_directories_selected` = 0),
so 2,000 updates x 32 = 64,000 example visits = 12.8 passes over the pool (the 63-update smoke pilots were one pass over 2,000).
The encoder is evaluated inside each run at 0, 100, 300, 1000 and 2000 updates on the dev subset below; the half-precision
copy and the encoded stores are deleted after each evaluation.

**Deviations from the brief, and why (budget; the engineer decides whether to extend).**
1. The runs **stop after 2,000 updates**; the 3,000-update point was not run. The first attempt (job 46827, 0.80 GPU-hours,
   cancelled) measured one evaluation of the full dev set at 43 minutes (229 unit texts/s over 590k texts). Six such evaluations
   plus 3,000 updates per seed would have cost about 6.5 GPU-hours per seed against 6.2 left of the block.
2. The evaluation uses the **dev subset** openlibrary and qutebrowser (L2 and L3) and streamlink (L2): 192 L2 queries in 3
   repositories and 155 L3 queries in **2 repositories**. Conan, haystack and ansible (64% of the encoding time) are dropped,
   so **D32 (ansible as a third dev L3 repository) is not honoured in the curve**; ansible was evaluated only at step 0
   (full set, job 46827), where it cannot show movement. Step 0 for the curve is the untrained encoder's per-query rows from that
   full-set evaluation restricted to the same queries (identical for both seeds by construction).
3. With 2 L3 repositories the repository-clustered interval is degenerate (it can be narrower than the query-level one);
   read the query-level interval as "queries only, not repositories". With 3 L2 repositories it is coarse.

**Definition of "beyond seed noise", written before any curve was seen** (session record of 2026-10-29, before the first
training job; implemented unchanged in `ril/analysis/t3_tables.py`). Metric: dense-only column, reading `units_all_nomod`
(D18), L2 nDCG@10 and L3 Recall@100 in percentage points. `M(s)` = mean over the two seeds of the change from step 0, paired over
queries; `G(s)` = seed 0 minus seed 1 at the same update count (one retraining's difference; two seeds give no standard
deviation). *Moved beyond seed noise at s*: the repository-clustered 95% interval of `M(s)` excludes 0 and the smaller of the
two seeds' own changes exceeds `|G(s)|`. *Keeps moving* across a step: the clustered interval of the increment `M(s_next) -
M(s)` excludes 0 and `|increment| > |G(s_next)|`. *Knee* (per level) = the smallest checkpoint from which no later increment
keeps moving; N for the next pilot = the larger of the two levels' knees, capped at 2,000. *No movement*: not moved at the last
checkpoint on both levels (then the arms pilot must not run). Note the rule uses the absolute value of the increment (a
decrease counts as movement).

**Curve** (percentage points; dense column; `units_all_nomod`; the RRF(BM25, dense) column beside it; all intervals 95%
bootstrap over 2,000 draws, queries and whole repositories):

L2 nDCG@10, dense column, units_all_nomod; 192 queries, 3 repositories; step 0 = 19.0

| updates | level (mean of 2 seeds) | change from step 0, M [query-level 95%] | M [repository-clustered 95%] | seed 0 / seed 1 change | seed gap G (s0 - s1) [query-level] | increment from previous step [query-level] | increment [clustered] |
|---|---|---|---|---|---|---|---|
| 100 | 29.5 | +10.5 [+8.3, +12.7] | +10.5 [+4.9, +12.6] | +11.2 / +9.9 | +1.3 [-0.0, +2.7] | +10.5 [+8.3, +12.7] | +10.5 [+4.9, +12.6] |
| 300 | 29.1 | +10.1 [+7.8, +12.3] | +10.1 [+6.5, +11.3] | +10.3 / +9.9 | +0.4 [-0.8, +1.7] | -0.4 [-1.4, +0.5] | -0.4 [-1.3, +1.6] |
| 1000 | 30.0 | +11.1 [+8.7, +13.4] | +11.1 [+7.6, +12.1] | +11.8 / +10.3 | +1.5 [-0.1, +3.1] | +1.0 [-0.1, +2.1] | +1.0 [+0.3, +1.6] |
| 2000 | 29.0 | +10.1 [+7.6, +12.3] | +10.1 [+7.0, +11.5] | +10.2 / +9.9 | +0.3 [-1.1, +1.6] | -1.0 [-2.1, +0.1] | -1.0 [-1.6, -0.6] |

L2 nDCG@10, rrf column, units_all_nomod; 192 queries, 3 repositories; step 0 = 26.9

| updates | level (mean of 2 seeds) | change from step 0, M [query-level 95%] | M [repository-clustered 95%] | seed 0 / seed 1 change | seed gap G (s0 - s1) [query-level] | increment from previous step [query-level] | increment [clustered] |
|---|---|---|---|---|---|---|---|
| 100 | 32.0 | +5.2 [+3.6, +6.8] | +5.2 [+2.8, +7.7] | +5.9 / +4.5 | +1.4 [+0.4, +2.5] | +5.2 [+3.6, +6.8] | +5.2 [+2.8, +7.7] |
| 300 | 31.6 | +4.8 [+3.1, +6.5] | +4.8 [+3.1, +7.2] | +5.2 / +4.3 | +0.9 [-0.1, +2.0] | -0.4 [-1.2, +0.5] | -0.4 [-0.7, +0.7] |
| 1000 | 31.7 | +4.9 [+3.1, +6.7] | +4.9 [+2.9, +7.4] | +5.5 / +4.3 | +1.2 [+0.1, +2.3] | +0.1 [-0.8, +1.0] | +0.1 [-0.2, +0.4] |
| 2000 | 31.3 | +4.5 [+2.7, +6.3] | +4.5 [+2.4, +7.2] | +4.6 / +4.3 | +0.3 [-0.7, +1.4] | -0.4 [-1.1, +0.3] | -0.4 [-0.6, -0.2] |

L3 Recall@100, dense column, units_all_nomod; 155 queries, 2 repositories; step 0 = 34.0

| updates | level (mean of 2 seeds) | change from step 0, M [query-level 95%] | M [repository-clustered 95%] | seed 0 / seed 1 change | seed gap G (s0 - s1) [query-level] | increment from previous step [query-level] | increment [clustered] |
|---|---|---|---|---|---|---|---|
| 100 | 45.1 | +11.1 [+9.1, +13.2] | +11.1 [+10.9, +11.3] | +11.9 / +10.4 | +1.4 [+0.6, +2.4] | +11.1 [+9.1, +13.2] | +11.1 [+10.9, +11.3] |
| 300 | 44.8 | +10.9 [+8.6, +13.3] | +10.9 [+10.7, +11.0] | +12.2 / +9.5 | +2.6 [+1.5, +3.8] | -0.3 [-1.0, +0.4] | -0.3 [-0.3, -0.2] |
| 1000 | 45.3 | +11.4 [+8.9, +14.1] | +11.4 [+10.5, +12.4] | +12.7 / +10.1 | +2.6 [+1.4, +4.0] | +0.5 [-0.4, +1.5] | +0.5 [-0.6, +1.7] |
| 2000 | 45.3 | +11.3 [+8.9, +14.0] | +11.3 [+10.3, +12.4] | +11.5 / +11.1 | +0.4 [-0.5, +1.4] | -0.1 [-0.8, +0.7] | -0.1 [-0.2, +0.0] |

L3 Recall@100, rrf column, units_all_nomod; 155 queries, 2 repositories; step 0 = 42.6

| updates | level (mean of 2 seeds) | change from step 0, M [query-level 95%] | M [repository-clustered 95%] | seed 0 / seed 1 change | seed gap G (s0 - s1) [query-level] | increment from previous step [query-level] | increment [clustered] |
|---|---|---|---|---|---|---|---|
| 100 | 47.5 | +4.8 [+3.6, +6.1] | +4.8 [+3.5, +6.0] | +5.2 / +4.5 | +0.7 [+0.0, +1.4] | +4.8 [+3.6, +6.1] | +4.8 [+3.5, +6.0] |
| 300 | 47.4 | +4.8 [+3.5, +6.1] | +4.8 [+3.6, +5.9] | +5.3 / +4.3 | +1.0 [+0.4, +1.8] | -0.0 [-0.6, +0.5] | -0.0 [-0.1, +0.0] |
| 1000 | 47.7 | +5.1 [+3.7, +6.5] | +5.1 [+4.4, +5.7] | +5.5 / +4.6 | +0.9 [+0.2, +1.7] | +0.3 [-0.3, +0.8] | +0.3 [-0.2, +0.8] |
| 2000 | 47.6 | +5.0 [+3.7, +6.5] | +5.0 [+4.9, +5.1] | +5.0 / +5.0 | -0.1 [-0.9, +0.7] | -0.1 [-0.5, +0.4] | -0.1 [-0.6, +0.5] |

Entries A1-PILOT and A2a are kept in `docs/experiments/A.md` (registry rows and sections).

**Result.**
- *Moved beyond seed noise*: yes at every checkpoint, both levels, both columns. At 100 updates (the first checkpoint) the
  dense column is +10.5 [+8.3, +12.7] nDCG@10 (L2, queries only; clustered [+4.9, +12.6]) and +11.1 [+9.1, +13.2] Recall@100
  (L3), each seed's own change (9.9 to 11.9) above the seed gap (1.3 to 1.4). For comparison the 63-update smoke pilot
  reported +8.3 / +11.0 on a different (larger) dev set and a different pool size (E-PILOT-K); not a like-for-like pair.
- *Keeps moving*: no, in the sense of improving. After 100 updates the change from step 0 stays between +10.1 and +11.4 on
  both levels; every increment is within 1.0 point and the seed gap at the same update count is 0.3 to 2.6 points, the same
  size. The only increment whose clustered interval excludes 0 and exceeds the gap is the L2 step 1000 to 2000, **-1.0**
  [-1.6, -0.6] (clustered, 3 repositories; query-level [-2.1, +0.1]): a decrease, with a one-seed gap of 0.3.
- *Rule as written*: both levels moved; L3 knee 100; L2 knee 2000 (the -1.0 step counts as movement because the rule uses the
  absolute value); so the pre-registered N = 2,000 (the cap), with `still moving between 1,000 and 2,000` flagged on L2.
- *Sensitivity readings added after seeing the curves (labelled as such, not the pre-registered rule)*: with the query-level
  interval, or counting only improvements (either interval), no increment keeps moving and the knee is the first checkpoint, 100
  updates, on both levels, so N = 100. The rule's outcome is therefore decided by one -1.0 step on three repositories.
- RRF column: +4.5 to +5.2 (L2), +4.8 to +5.1 (L3), the same shape (all of it from the dense component, which is where
  the training acts).

**Reading.** Evidence for the next pilot: on this pool and recipe the encoder has moved by about 10 to 11 points on the dense
column by 100 updates and does not improve measurably over the next 1,900 (increments within +-1.0, changes of the size of
the seed gap). The knee is at or before 100 updates; the first checkpoint cannot resolve earlier. The 3,000-update point is not
measured, so "no movement at 3,000" and "still moving at 3,000" are both untested. Limits: the checkpoints of one run sit at
learning-rate values of a 3,000-update schedule (about 97%, 90%, 67%, 33% of the peak at 100, 300, 1000, 2000), so a run
of N updates that decays to zero at N is not this curve; two seeds; 2 L3 repositories; a dev subset chosen by cost after the
first evaluation was seen, not by results (the choice was made before any trained checkpoint was evaluated). Not evidence that
a supervision signal helps or not: RAW only, so the arms pilot (T4) is where a difference between supervision signals would
show, and its size N is the engineer's decision between 100 (these sensitivity readings) and 2,000 (the rule as written).
Budget note: block 2 has 24 - 17.00 - 5.14 = 1.86 GPU-hours left, so ten 2,000-update runs do not fit; at N = 100 a run costs about 0.05
GPU-hours of training plus a 10-minute evaluation (about 0.2 GPU-hours).


Sections A1-PILOT and A2a: see `docs/experiments/A.md`.

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

## E-PILOT-ARMS: can a different supervision change anything at all? Exploratory, done 2026-10-31

Status: exploratory pilot, outside the pre-registered RQ tables. Configurations `configs/experiments/t4/t4a_*` (stage 1, 24 runs) and `t4b_*` (stage 2, 6 runs), each with its hash in `results/tables/t4/t4{a,b}_runs.csv`. Evaluation set and metrics as in E-PILOT-CURVE (`configs/experiments/e1_bm25_dev3_curve.yaml`); the untrained encoder's values are the step-0 rows of the learning curve. Account A, RTX 2080 Ti, jobs in `docs/COMPUTE.md`. Code: `ril/analysis/t4_tables.py`, `scripts/t4_tables.py`, `scripts/ada/t4_runs.sbatch`.

**Question.** After the RAW learning curve (about +10 L2 nDCG@10 and +11 L3 Recall@100 by 100 updates, flat to 2,000), does a different supervision change the level or the speed of reaching it, and how much of the gain is supervision at all?

**Fixed before any result (stage 1).** N = 100 updates on the schedule of 3,000 (warm-up 7, linear decay), which is the schedule the 100-update point of the curve had (`budget.stop_after`); D28 primary negatives; CodeRankEmbed base; seeds 0, 1, 2. Cells: RAW; NOISE (positives replaced by random functions of the same repository); FILTER K = 20 (positive level) under BM25, SweRankEmbed-Small and CodeRankEmbed (teacher equals base); WEIGHT (power, K = 20, p = 1, floor 0.1, CodeRankEmbed); CURRICULUM (4 quantile buckets, CodeRankEmbed) forward and reversed. The self-teacher with a warm-up is not run: ADR-002 names it as a candidate experiment, not as a specification. Pool: selection A (2,000 directories) because the K-rank rows of all three teachers exist for it; the curve used 5,000 directories. Stage 2 trigger: a non-RAW, non-NOISE cell with a paired-difference interval that excludes 0 at either level, or a RAW seed gap above 1.0 point. Intervals: repository-clustered where the level has at least three repositories (L2), query-level otherwise (L3, two repositories). Ansible L3 is left out: its 274k unit texts take about 20 minutes to encode per run, 24 runs would cost about 8 GPU-hours.

**Stage 1 (measured).** Table in `RESULTS.md` row `t4a-arms-stage1`. RAW gains +10.7 (L2) and +11.9 (L3) over the untrained encoder. No cell is above RAW at either level; the cells sit 0.1 to 1.4 points below it (several intervals exclude 0, all on the negative side); the reversed curriculum is level with RAW. NOISE stays at the untrained encoder, so its share of the RAW gain is about 0 (-2.4% and +2.9%, wide intervals): in this design the gain is not adaptation to the data format. NOISE is a weak control (random same-repository positives carry no consistent signal in either direction) and says nothing about a partly-correct signal. Trigger (i) met, (ii) not met (RAW seed gap 0.62 and 0.91).

**Stage 2 (measured).** Cells chosen by the largest absolute paired difference over the two levels, rule fixed before stage 2: FILTER (CodeRankEmbed teacher) and CURRICULUM (a near tie with FILTER under BM25 at L3: 1.01 against 1.05); RAW, N = 1,000 on the same schedule, seeds 0 and 1. At 1,000 updates the differences to RAW are +0.3 and +0.6 (L2), +0.2 and +0.4 (L3), intervals include 0 except one clustered L2 interval ([+0.02, +2.61], three repositories) and a degenerate two-repository L3 interval. The differences seen at 100 updates (all below RAW) do not persist; they also do not turn into gains.

**Limits (stated, not repaired).** (1) Pool of 2,000 examples: 1,000 updates is 16 passes, and RAW itself falls 3.0 (L2) and 2.4 (L3) points from 100 to 1,000 updates here, where the curve on 5,000 directories stayed flat; stage 2 mixes supervision with repeated passes. (2) Three L2 repositories, two L3 repositories: the clustered intervals are not reliable and the query-level ones carry query sampling only. (3) Two seeds in stage 2. (4) Dev subset, one encoder, one K, one weight form, one bucket count: "different supervision" is the five settings tried, not the space. (5) Teacher equals base for WEIGHT, CURRICULUM and one FILTER cell. (6) RAW at 100 updates here is not the curve's RAW (other pool, 1.6 passes against 0.64). Nothing here is a decision; the answer to "can supervision change anything" is, for these settings and this data, "not upward at 100 or 1,000 updates, and not detectably at either".


## E-PILOT-ARMS2: do the supervision arms differ from RAW at a matched pool and at matched unique examples? Exploratory, done 2026-10-31

Status: exploratory pilot, outside the pre-registered RQ tables. Configurations `configs/experiments/t5/t5a_*` (stage 1) and `t5b_*` (stage 2), hashes in `results/tables/t5/t5a_unique.csv` and `t5b_unique.csv`; tables `results/tables/t5/t5a_{effects,seeds,unique}.csv`, `t5b_{effects,unique}.csv`; logs `results/logs/t5a_tables.json`, `t5b_tables.json`. Account A, RTX 2080 Ti, jobs 50335, 50356 (stage 1, seeds 0 and 1) and 50942 (stage 2, seed 0); code `ril/analysis/t5_tables.py`, `scripts/t5_tables.py`, `scripts/ada/t5_runs.sbatch`.

**Question.** In E-PILOT-ARMS a smaller pool (2,000 examples, 1.6 passes in 100 updates, FILTER about 3) confounded passes with quality. On the 5,000-directory pool (62,238 positives, 0 held-out), does any supervision signal change the result at 100 updates, against RAW on the full pool and against RAW on a random subset of the size of the filtered pool (D43)?

**Set-up.** CodeRankEmbed base, 100 updates of the 3,000-update schedule (warm-up 7, linear), batch 32, random repository-local negatives, loss and optimizer as in E-PILOT-CURVE. Cells: RAW; RAW on a random subset of 4,592 examples (draw 0; the median of the three FILTER K=20 pool sizes, BM25 4,169, CodeRankEmbed 4,592, SweRankEmbed-Small 4,924 of 5,000); FILTER K=20 (positive level) with each teacher; WEIGHT (power, k=20, floor 0.1) and CURRICULUM (4 buckets), both with CodeRankEmbed as teacher (teacher equals base for these and for FILTER CodeRankEmbed). Seeds 0 and 1. Evaluation: dense column, gold reading `units_all_nomod`, five dev repositories without ansible (L2: openlibrary, qutebrowser, conan, haystack, streamlink, 351 queries; L3: openlibrary and qutebrowser, 155 queries). Ansible was not evaluated in any cell: its 274k unit texts serve L2 and L3 alike and cost 20 minutes a run, which did not fit the budget. Untrained base from the learning curve's step-0 rows (job 46827, same code and queries; ansible dropped). Percentage points; L2 interval repository-clustered over 5 repositories, L3 query-level over 2.

**Unique examples (D42).** Every cell trained on 3,200 example visits (the planner counts the 101st batch it builds, 3,232) and saw 3,232 distinct examples: no cell repeats an example and none falls below the common count. Pool drawn from / effective epochs: RAW, WEIGHT, CURRICULUM 5,000 / 0.646; subsample and FILTER CodeRankEmbed 4,592 / 0.704; FILTER BM25 4,169 / 0.775; FILTER SweRankEmbed-Small 4,924 / 0.656. Data order is the same for RAW and WEIGHT (same pool, same seeded permutation); the other cells differ in pool or ordering by construction.

**Stage 1 (means over seeds 0 and 1; per-seed values in `t5a_seeds.csv`).** Untrained base to RAW: +9.59 (L2), +11.13 (L3).

| cell | L2 nDCG@10 (seeds) | L3 Recall@100 (seeds) | d to RAW L2 / L3 | d to subsample L2 / L3 |
|---|---|---|---|---|
| RAW | 26.76 (27.18, 26.34) | 45.10 (45.82, 44.38) | | +0.33 [-0.90,+1.62] / -1.31 [-2.02,-0.60] |
| subsample (draw 0) | 26.43 (27.04, 25.82) | 46.41 (46.92, 45.89) | -0.33 [-1.62,+0.90] / +1.31 [+0.60,+2.02] | |
| FILTER BM25 | 26.23 (26.38, 26.08) | 45.71 (45.96, 45.46) | -0.53 [-2.30,+1.23] / +0.61 [-0.19,+1.42] | -0.20 [-0.89,+0.45] / -0.70 [-1.45,+0.05] |
| FILTER SweRankEmbed-Small | 26.20 (25.95, 26.45) | 45.31 (45.87, 44.75) | -0.56 [-1.36,+0.36] / +0.21 [-0.27,+0.67] | -0.23 [-1.20,+0.66] / -1.10 [-1.88,-0.32] |
| FILTER CodeRankEmbed | 26.15 (25.87, 26.44) | 45.33 (45.31, 45.36) | -0.60 [-1.59,+0.52] / +0.24 [-0.50,+1.01] | -0.28 [-1.38,+0.66] / -1.07 [-1.76,-0.35] |
| WEIGHT | 26.47 (26.89, 26.04) | 44.82 (45.52, 44.12) | -0.29 [-0.58,-0.01] / -0.28 [-0.54,-0.02] | +0.04 [-1.34,+1.31] / -1.59 [-2.40,-0.78] |
| CURRICULUM | 26.53 (26.77, 26.29) | 45.97 (46.43, 45.51) | -0.23 [-1.27,+0.59] / +0.87 [+0.20,+1.56] | +0.10 [-0.35,+0.67] / -0.44 [-1.02,+0.21] |

RAW seed gap 0.84 (L2), 1.45 (L3). Intervals carry query sampling only; with two seeds and one subsample draw they are descriptive. No cell is above RAW at both levels. The subsample is above RAW at L3 and level at L2, which one draw and two seeds cannot separate from seed noise (RAW's own gap is 1.45); the FILTER cells with the two stronger teachers are below the subsample at L3. Quality beyond quantity (beating the subsample) is not seen. Minimum detectable difference at three seeds from the observed variance (80% power, 5%): L2 1.4 (query sampling binds; seed SD 0.52), L3 1.7 (seed SD 0.73 binds); the differences observed here are smaller than both.

**Stage-2 trigger (fixed in the brief, read literally; `results/logs/t5a_tables.json`).** (i) met: WEIGHT against RAW has intervals excluding 0 at L2 and L3 in the same direction (below RAW); FILTER SweRankEmbed-Small and CodeRankEmbed against the subsample exclude 0 at L3 with the same sign at L2. (ii) met: RAW seed gap 1.45 at L3. The third seed of stage 1 was not run, because 2.64 GPU-hours more would have left no budget for stage 2.

**Stage 2 (1,000 updates, seed 0 only; partial by budget).** The brief's plan (RAW, subsample and the two cells with the largest absolute difference, WEIGHT and FILTER SweRankEmbed-Small, two seeds) costs about 8.5 GPU-hours at 1.06 per run; 4.03 were left, so RAW, the subsample and WEIGHT ran at seed 0 (3.18 GPU-hours). RAW L2 28.36, L3 46.65 (base +11.20 / +12.69). WEIGHT 28.14 / 46.62: -0.22 [-0.47,-0.01] / -0.03 [-0.37,+0.33] against RAW. Subsample 25.23 / 44.95: -3.13 [-4.29,-1.98] / -1.70 [-2.71,-0.71] against RAW; WEIGHT against the subsample +2.91 [+1.79,+3.98] / +1.67 [+0.74,+2.65]. At 1,000 updates RAW sees 5,000 distinct examples (6.4 passes) and the subsample 4,592 (7.0 passes), so the subsample is flagged as below the common unique count. One seed and one draw: the sign of the subsample gap here is the opposite of stage 1 at L3, which shows how little one draw settles.

**Reading.** At matched updates on the 5,000-directory pool, no K-rank signal (filter, weight, order) moves the result beyond what RAW's own seed gap covers; WEIGHT is a fraction of a point below RAW at both levels and equal at 1,000 updates. No evidence that quality beats quantity, with the bound stated above. Limits: two seeds (one in stage 2), one subsample draw (three were configured, `t5a_sub_d{1,2}_*`, not run), ansible not evaluated, dev repositories only, one encoder, one K, one weight form, three of four cells with teacher equal to base. Nothing here is a decision.

## E-PILOT-NOISE: when label noise is present at a known rate, do FILTER and WEIGHT recover what RAW loses? Exploratory, stated 2026-11-01 (before any run)

Status: exploratory pilot, outside the pre-registered RQ tables. Code `ril/training/noise.py` (injection, ledger, ranks of noised positives), `score_job` in `ril/training/train_jobs.py` (per-function teacher scores), arm `ORACLE_CLEAN` and the `match_clean` subsample in `ril/training/supervision.py`; unit tests `tests/unit/test_noise_injection.py`. Decisions D44 to D48 (engineer, 2026-11-01).

**Question.** The 5,000-directory pool looks pre-selected by a retriever (0 of 160 sampled directories lack a positive in SweRankEmbed-Small's top 10, against 19.3% on never-filtered data), and no supervision cell was above RAW or the size-matched subsample on it (E-PILOT-ARMS, E-PILOT-ARMS2). Here the pool's cleanliness is made a controlled variable: noise is injected at a known rate and the question is whether FILTER and WEIGHT recover quality that RAW loses, and what share of the best possible recovery (ORACLE-CLEAN) they reach. A method that fails here has no case anywhere; a method that works here and not on the public pool says the public pool is the reason.

**Design (fixed before any run).** Pool: the 5,000 directories of D41. For each training pair independently with probability r, the positive set is replaced by the same number of functions drawn uniformly from the other (non-positive) functions of the same snapshot, which is one repository (D45). One uniform draw per pair, keyed by the seed and the instance id, decides noising, so the realisation is the same for every cell of a seed, independent of pool order, and nested across rates; the true positives are masked (neither positive nor negative), as in the NOISE control (D38). The indicator is stored per pair in a ledger outside the examples and is read only by ORACLE-CLEAN and by the size-matched subsample's size. Rates r in {0, 0.2, 0.4}; r = 0 reuses the E-PILOT-ARMS2 RAW cells (not rerun). Cells at each r > 0 (D46): RAW; FILTER K = 20 with BM25 and with SweRankEmbed-Small as teacher; WEIGHT (power form, k = 20, floor 0.1, as E-PILOT-ARMS2) with the SweRankEmbed-Small K-rank; ORACLE-CLEAN (RAW on the pairs with the indicator off); RAW-subsampled to ORACLE-CLEAN's size. N = 100 updates of the 3,000-update schedule, D31 shape, D28 negatives, CodeRankEmbed base, seeds 0, 1, 2. Evaluation as in E-PILOT-ARMS2 stage 1 (five dev repositories, L2 and L3, ansible excluded). CURRICULUM is not run. Teacher ranks (D48): the stored rank files hold only the ranks of the true positives and the top 64 mined scores, so a rank of a replacement cannot be read from them; every function of every snapshot is scored once per teacher (`scripts/train.py score`) and ranks are computed from those scores with the published definition (1 + non-positive functions scored strictly higher, non-positive taken as of the pair as the arm sees it).

**Pre-registered reading (D47).** (i) Noise sanity: RAW degrades with r; if not, the noise is too weak to test anything: report and stop. (ii) ORACLE-CLEAN recovers RAW's loss; if not, the unrecoverable part is not noise. (iii) A method "works" when its paired difference to RAW has an interval excluding 0 in the positive direction on both levels (L2 repository-clustered, L3 query level), and it is reported as a fraction of the ORACLE-CLEAN recovery (its difference to RAW divided by ORACLE-CLEAN's). A method that does not beat RAW at r = 0.4 is reported as failing, with the minimum detectable difference at three seeds from the observed variance. (iv) The size-matched subsample is the control for FILTER: FILTER must beat it to claim quality beyond quantity. Gate N0: if the K-rank signal separates injected from clean pairs with AUC below 0.6, stop and report: the filter has nothing to find.

**Result of N0 (measured, exploratory; `results/logs/n0_separation_51459.json`, RESULTS rows `n0-separation-bm25`, `n0-separation-srs`).** Per-function scores exist for all 5,000 directories (4,905,357 functions) under BM25 and SweRankEmbed-Small; the earlier rank files could not give the rank of a replacement positive (D48 answered: not stored, scored again, 2.17 GPU-hours, inside the 3.5 allowed). Reproduction: the ranks of the true positives recomputed from the stored scores equal the feature table's in 62,237 of 62,238 cases for BM25 and in 59,255 (95.2%, largest difference 13 ranks) for SweRankEmbed-Small; the difference is float16 batch composition in the dense encoder, not a definition change. Separation, three seeds (noise realisations) at each of r = 0.2 and 0.4, K = 20, pair-level rank = minimum over the pair's positives:

| teacher | AUC injected vs clean (pair) | AUC (positive) | injected pairs a FILTER drops | clean pairs a FILTER drops |
|---|---|---|---|---|
| BM25 | 0.827 to 0.843 | 0.68 to 0.73 | 62 to 65% | 16.6 to 17.0% |
| SweRankEmbed-Small | 0.973 to 0.977 | 0.80 to 0.84 | 69.5 to 71.2% | 1.4 to 1.6% |

The gate (AUC below 0.6 means stop) is passed by a wide margin: the signal has something to find. Two cautions that bear on how N1 will read. (1) The public pool was built with SweRankEmbed-Small in the loop (0 of 160 sampled directories lack a positive in its top 10), so on clean pairs its median pair-rank is 1; the teacher is well placed to filter this pool, and a large FILTER effect at N1 would be partly that. (2) BM25 drops 17% of clean pairs at K = 20, so its FILTER shrinks the pool even without noise. Both are visible in the table above and in the unique-example table N1 would produce. Evidence class: measured.

**Stage N1 was not run (budget rule of the brief).** Cost per 100-update run is 0.377 GPU-hours (E-PILOT-ARMS2: 2.64 for 7 cells). Thirty-six runs (2 rates x 6 cells x 3 seeds) cost 13.6; the brief aborts the stage above 11, and 12.68 remain under the raised cap of 60 (47.32 used). The configurations (`configs/experiments/n1/`), the job (`scripts/ada/n1_runs.sbatch`, one job per seed and rate, 2.3 GPU-hours), the tables (`scripts/n1_tables.py`) and the noise arms are built, unit-tested locally and the torch tests pass on the cluster (36 passed); nothing was trained. **Open question for the engineer (design: it changes the seed count or the cap):** (a) run seeds 0 and 1 for both rates, 24 runs, 9.05 GPU-hours (fits both limits; the interval at two seeds is descriptive and the third seed, 4.5 more, needs the cap or limit raised); (b) raise the stage limit to 14 and run all 36 (13.6 of the 12.68 left: also needs the cap raised to about 62); (c) run r = 0.4 only, three seeds, 18 runs, 6.8, and decide r = 0.2 afterwards. Recommendation: (a), because the pre-registered decision (a method works at r = 0.4) is visible at two seeds with the minimum detectable difference reported, and the third seed then buys power only where a method is near the edge. Cheapest check that could change this: none needed; the run costs are measured. Not decided by a session.

**Engineer decisions after N0 (2026-11-01).** D49: N1 runs seeds 0 and 1 at both rates (r = 0.2 and 0.4), 24 runs, 9.05 GPU-hours. The design is reduced from three seeds to two because the full 36 runs (13.6 GPU-hours) exceed the 11 GPU-hour stage limit and the 12.68 left under the cap, and because the r = 0 anchor (E-PILOT-ARMS2 RAW cells) exists only for seeds 0 and 1, so these are the two seeds that pair with it. The minimum detectable difference at two seeds, from the observed variance, is reported next to every comparison; intervals at two seeds are descriptive. D50: the N0 choices stand (true positives masked in noised pairs, WEIGHT uses the SweRankEmbed-Small signal, one subsample draw). SweRankEmbed-Small shaped the public pool, so the SweRankEmbed-Small FILTER and WEIGHT cells are favoured by the separation gate; the BM25 FILTER cell is the one not favoured, and every conclusion below states which teacher it rests on. D51 (fixed before results): after the 24 runs, if at r = 0.4 any method's paired difference to RAW has the positive sign on both levels but an interval including 0 on either, run seed 2 at r = 0.4 for RAW, ORACLE-CLEAN and that method's cell(s) only (at most 2.3 GPU-hours); otherwise do not run it. The N2 trigger (D47 iii, a method works at r = 0.4) stands.

**N1 cost check (measured, 2026-11-01; job 51971, seed 0, r = 0.4, one GPU on one node).** The first cell (RAW) took 27.7 minutes from job start including setup, the second (ORACLE-CLEAN) 26.9 minutes, so about 0.45 GPU-hours per run against the 0.377 of E-PILOT-ARMS2 (different node, so the figure is not transferable). A job of six cells is about 2.7 GPU-hours and the 24 runs of D49 about 10.8, above the 9.5 GPU-hour abort limit of the brief. Rule followed literally (R6): the other three jobs (seed 0 r = 0.2, seed 1 r = 0.4, seed 1 r = 0.2) were NOT submitted. Job 51971 was left running because its cells are needed under every option. **Open question for the engineer (design: it changes the stage limit or the cells):** (a) raise the stage limit to 11 and run the three remaining jobs (total 10.8; cap 60 holds, 47.32 + 10.8 = 58.1); (b) keep 9.5 and drop one job, for example seed 1 at r = 0.2 (8.1 GPU-hours), so r = 0.2 has one seed only; (c) drop the two cells of least interest per job (for example BM25 FILTER, which drops 17% of clean pairs). Recommendation: (a), a 1.3-hour overrun of a limit that was set from an estimate now known to be low. Cheapest check: none; the cost is measured.

**Decisions D52, D53 (engineer, 2026-11-01).** Option (a): the N1 stage limit is raised from 9.5 to 11 GPU-hours and the Block 2 cap from 60 to 62 so that the D51 third seed still fits. Job 51971 completed (2.71 GPU-hours); the other three jobs were submitted.

**Result of N1 (measured, exploratory; two seeds, not three, D49).** Jobs 51971, 52143, 52144 (account A) and 52385 (account C): seeds 0 and 1 at r = 0.2 and 0.4, six cells each, 24 runs of 100 updates, 9.43 GPU-hours (0.45 per run on the first node, 0.37 on the others; the stage limit was raised to 11 by D52). Tables `results/tables/n1/n1_{effects,seeds,unique}.csv`, log `results/logs/n1_tables.json`, per-run config hashes in `n1_unique.csv`; command `python scripts/n1_tables.py results results/rq2/t3_curve_raw/2026-10-29_3909db9c/step_00000/query_rows.csv results/tables/n1 results/logs/n1_tables.json`. Values are L2 nDCG@10 points (repository-clustered 95% interval) and L3 nDCG@10 points (query-level interval), dense reading `units_all_nomod`, paired against the same seed. The r = 0 anchor is the E-PILOT-ARMS2 RAW cells, reused. With two seeds the intervals describe the dev repositories and queries, not seed-to-seed replication.

D47 (i), noise sanity: RAW degrades against the clean anchor at both rates and both levels: r = 0.2: -1.72 [-2.35, -0.89] L2, -1.11 [-1.59, -0.62] L3; r = 0.4: -3.67 [-4.85, -1.97] L2, -2.32 [-3.21, -1.42] L3. Passed. D47 (ii): ORACLE-CLEAN against RAW is positive at both rates and levels (r = 0.2: +0.92 [0.42, 1.62] L2, +2.24 [1.45, 3.01] L3; r = 0.4: +2.87 [1.66, 4.24] L2, +3.33 [2.22, 4.45] L3), i.e. 53% and 78% of RAW's L2 loss and above the loss at L3 (202% and 144%). Passed. Caution: at r = 0.4 ORACLE-CLEAN and the size-matched subsample have only 3,054 and 3,017 distinct examples for 3,232 draws (repeats, flagged in `n1_unique.csv`), as does FILTER-BM25 on seed 1; the other cells see 3,232 distinct examples.

D47 (iii), difference to RAW, with its share of the ORACLE-CLEAN recovery (L2 / L3), and (iv) whether the interval against the size-matched subsample also excludes 0 on both levels:

| rate | method (teacher) | vs RAW L2 | vs RAW L3 | share of oracle recovery L2 / L3 | works (iii) | beats subsample (iv) |
|---|---|---|---|---|---|---|
| 0.4 | FILTER K=20 (BM25) | +2.23 [1.01, 3.38] | +1.74 [0.75, 2.80] | 0.78 / 0.52 | yes | yes |
| 0.4 | FILTER K=20 (SweRankEmbed-Small) | +3.04 [1.49, 4.74] | +2.96 [1.88, 4.02] | 1.06 / 0.89 | yes | yes |
| 0.4 | WEIGHT (SweRankEmbed-Small) | +1.76 [0.86, 2.51] | +0.71 [0.20, 1.22] | 0.61 / 0.21 | yes | no (L3 vs subsample +0.68 [-0.18, 1.68]) |
| 0.2 | FILTER K=20 (BM25) | +1.00 [-0.74, 2.88] | +2.08 [1.08, 3.10] | 1.09 / 0.93 | no (L2 includes 0) | no |
| 0.2 | FILTER K=20 (SweRankEmbed-Small) | +1.55 [0.67, 2.65] | +1.67 [0.87, 2.51] | 1.68 / 0.75 | yes | yes |
| 0.2 | WEIGHT (SweRankEmbed-Small) | +0.78 [0.29, 1.24] | +0.69 [0.34, 1.04] | 0.85 / 0.31 | yes | no (L3 vs subsample +0.06 [-0.51, 0.66]) |

The size-matched subsample against RAW: r = 0.2 -0.18 [-0.83, 0.60] L2, +0.64 [0.05, 1.23] L3; r = 0.4 +0.12 [-0.25, 0.45] L2, +0.03 [-0.90, 0.83] L3. Minimum detectable difference at two seeds from the observed variance (the larger of the seed bound and the query bound; nDCG points): r = 0.2 1.56 L2, 2.77 L3; r = 0.4 2.15 L2, 1.86 L3 (pooled seed SD 0.51, 0.99, 0.77, 0.66; 6 degrees of freedom each). Differences below these values (WEIGHT at both rates, FILTER-BM25 at r = 0.2 L2, FILTER at L3 r = 0.2) have intervals that exclude 0 or not by the query bootstrap alone and are not separable from seed noise at this sample size.

**Reading, by teacher.** (1) Rests on the BM25 teacher (the one the separation gate does not favour): FILTER K=20 beats RAW and the size-matched subsample at r = 0.4 on both levels, with about 78% (L2) and 52% (L3) of the oracle recovery; at r = 0.2 it does not clear the bar on L2. (2) Rests on the SweRankEmbed-Small teacher, which shaped the public pool and is therefore favoured: FILTER beats RAW and the subsample at both rates and recovers about all (r = 0.4: 106% L2, 89% L3) of the oracle's gain; WEIGHT improves on RAW but not beyond the subsample at L3, with 21 to 31% of the L3 oracle recovery, and its differences at L3 are below the minimum detectable difference. (3) Known same-repository noise at 40% costs RAW about 3.7 (L2) and 2.3 (L3) nDCG points and a filter on a rank signal recovers most of it; this is a statement about injected noise of this kind with a teacher separating it at AUC 0.83 to 0.97, not about the public pool, which on the evidence of Waves 5 and 6 carries no recoverable noise of that kind for these cells. Python only; two seeds; one noise realisation per seed; one subsample draw.

**Triggers.** D51 (third seed at r = 0.4): not fired, since every paired difference to RAW at r = 0.4 has an interval excluding 0 on both levels. N2 (add r = 0.1 for a method that works at r = 0.4): fired, since three methods work at r = 0.4; NOT run. Open question for the engineer (design: scope and cost): the brief's "that method" is ambiguous with three working methods and its "about 2 GPU-hours" matches none of them. (a) FILTER-BM25 (the teacher not favoured by the gate) + RAW + ORACLE-CLEAN, seeds 0 and 1: 6 runs, 2.7 GPU-hours; (b) all three methods + RAW + ORACLE-CLEAN, seeds 0 and 1: 10 runs, 4.5 GPU-hours (ledger 56.69 of the cap 62; 61.2 after); (c) as (a) with seed 0 only, 1.35. Recommendation: (a). The r = 0.1 configurations do not exist yet (`configs/experiments/n1/` holds r = 0.2 and 0.4).

**Addendum 2026-11-02: third seed at r = 0.4 (measured, exploratory; D58).** Not the sibling-noise option of the Wave 8 list: a third seed of the uniform-noise headline. D58: Block 2 cap raised from 62 to 66 GPU-hours (60.41 used). D59: seed 2, r = 0.4 only, all six cells, configurations `configs/experiments/n1/n1_r40_*_s2.yaml`, one job (53271, account A, 2.40 GPU-hours, same command as the other N1 jobs). r = 0.2 stays at two seeds. The r = 0 anchor still has seeds 0 and 1 only, so the comparison with the clean anchor (D47 i) pairs those two seeds; all contrasts with RAW and with the subsample use three seeds. Tables `results/tables/n1/` and `results/logs/n1_tables.json` were rebuilt with `python scripts/n1_tables.py results results/rq2/t3_curve_raw/2026-10-29_3909db9c/step_00000/query_rows.csv results/tables/n1 results/logs/n1_tables.json --mdd-seeds 40=3` (the `--mdd-seeds` option is new; before it the minimum detectable difference assumed two seeds). The r = 0.2 reading is identical to the two-seed one.

**What changed (said first).** No method changes sign against RAW and no method-against-RAW interval changes whether it excludes 0. Two comparisons do change status: (1) the size-matched subsample against RAW at L3 was +0.03 [-0.90, 0.83] (interval includes 0) and is now -1.02 [-2.17, -0.13] (excludes 0, negative; L2 -0.23 [-0.56, 0.03]); (2) WEIGHT against the subsample at L3 was +0.68 [-0.18, 1.68] (includes 0) and is now +2.17 [1.15, 3.44] (excludes 0), so WEIGHT now also meets D47 (iv) at both levels. Both come from the seed-2 subsample run being low (one subsample draw per seed); read them as the subsample's seed variance, not as a property of WEIGHT. Shares of the ORACLE-CLEAN recovery fall for every method because the oracle's own gain over RAW falls less than the methods' (oracle +2.87 / +3.33 to +2.67 [1.28, 3.91] / +2.97 [1.92, 4.00]).

Difference to RAW at r = 0.4, nDCG@10 points, L2 (repository-clustered interval) / L3 (query-level interval), share of the ORACLE-CLEAN recovery L2 / L3, two seeds beside three seeds:

| method (teacher) | two seeds L2 | two seeds L3 | share (2 seeds) | three seeds L2 | three seeds L3 | share (3 seeds) | beats subsample (3 seeds) |
|---|---|---|---|---|---|---|---|
| ORACLE-CLEAN | +2.87 [1.66, 4.24] | +3.33 [2.22, 4.45] | n/a | +2.67 [1.28, 3.91] | +2.97 [1.92, 4.00] | n/a | n/a |
| FILTER K=20 (BM25) | +2.23 [1.01, 3.38] | +1.74 [0.75, 2.80] | 0.78 / 0.52 | +1.82 [0.36, 2.86] | +1.19 [0.25, 2.12] | 0.68 / 0.40 | yes (+2.05 / +2.22) |
| FILTER K=20 (SweRankEmbed-Small) | +3.04 [1.49, 4.74] | +2.96 [1.88, 4.02] | 1.06 / 0.89 | +3.01 [1.13, 4.26] | +2.57 [1.59, 3.56] | 1.13 / 0.87 | yes (+3.24 / +3.60) |
| WEIGHT (SweRankEmbed-Small) | +1.76 [0.86, 2.51] | +0.71 [0.20, 1.22] | 0.61 / 0.21 | +1.87 [0.81, 2.67] | +1.14 [0.57, 1.67] | 0.70 / 0.38 | yes (+2.10 / +2.17), was no at L3 |
| size-matched subsample | +0.12 [-0.25, 0.45] | +0.03 [-0.90, 0.83] | n/a | -0.23 [-0.56, 0.03] | -1.02 [-2.17, -0.13] | n/a | n/a |

D47 (i) and (ii) still pass: RAW against the clean anchor (seeds 0 and 1 only) -3.52 [-4.90, -1.55] L2, -1.86 [-2.71, -0.97] L3 (two-seed values -3.67 / -2.32); ORACLE-CLEAN recovers 76% of that L2 loss. Teacher caveat unchanged: the SweRankEmbed-Small cells are favoured; the BM25 FILTER cell is the one not favoured, and its share falls to 0.68 (L2) and 0.40 (L3), with its lower interval limits at 0.36 and 0.25.

Minimum detectable difference at three seeds, r = 0.4, nDCG points. (a) Table method of the two-seed entry (larger of the seed bound and the query bound; observed pooled seed SD 0.63 L2, 0.96 L3, 12 degrees of freedom): 1.78 (L2), 2.18 (L3), against 2.15 and 1.86 at two seeds. (b) Variance components as in E-STORED-ANALYSIS (code of branch `b/stored-analysis`, not merged here; `results/tables/n1/n1_r40_mdd_three_seeds.csv`, intervals from 300 repository resamples): query level 1.40 [1.20, 2.53] (L2) and 2.20 [1.70, 2.93] (L3); with the repository term 2.16 [1.64, 2.98] (L2) and 4.88 [3.34, 6.97] (L3). At two seeds the same method gives 1.65 / 2.59 and 2.34 / 5.06. Reading: FILTER-BM25 against RAW at L3 (+1.19) is below the L3 minimum detectable difference both ways and WEIGHT's L3 gain (+1.14) likewise; their intervals exclude 0 by the query bootstrap alone, which does not cover seed or repository variation. FILTER-SweRankEmbed-Small (+3.01 L2, +2.57 L3) and the oracle exceed the query-level values; only at L2 do they exceed the with-repository value for FILTER-SweRankEmbed-Small. The repository term rests on five dev repositories.

**Addendum 2026-11-03 (append-only correction, decision O4 / D71).** Wherever the entry above says "L3 nDCG@10" it means L3 **Recall@100**: the `metric` column of every stored Wave 6 and Wave 7 table is `recall100` for L3, and the tables are the source. L2 is nDCG@10. Numbers are unchanged.

## E-PILOT-NOISE-SIB: does the noise result survive when the noise is a neighbour of the true positive? Exploratory, stated 2026-11-02 (before any run)

Status: exploratory pilot, outside the pre-registered RQ tables; continues E-PILOT-NOISE. Code: kind `sibling` in `ril/training/noise.py`, configurations `configs/experiments/n8/`, jobs `scripts/ada/n8_separation.sbatch` and `n8_runs.sbatch`, tables `scripts/n1_tables.py` with `--prefix n8`. Decisions D54 to D57 (engineer, 2026-11-02).

**Question.** E-PILOT-NOISE injected noise by replacing a pair's positives with random functions of the same repository; a teacher's rank separates that noise from clean pairs with AUC 0.83 (BM25) and 0.97 (SweRankEmbed-Small). Noise in real pull-request labels is different: the edited function is a neighbour (same file, same class) of the one the issue is about, and neighbours score high under any retriever, so a rank-based filter may not find them. E-PILOT-NOISE says FILTER works when noise is findable; this entry asks whether it still works when the noise is the plausible kind, and so how far that result transfers.

**Design (fixed before any run).** D54: same pool, same seeds, same noised pairs as E-PILOT-NOISE at r = 0.4 (the uniform draw that decides whether a pair is noised is the same), but the replacement is the same number of non-positive functions of the same file(s) as the true positives; if those files hold fewer than that many, the same class, then the same directory, then the uniform draw of E-PILOT-NOISE. A level is used only when it holds at least as many non-positives as the pair has positives. The class level is a subset of the file level, so it can only be reached when the file level is empty and its share is zero by construction; it is reported anyway. The share of noised pairs per level is recorded in the noise summary of every run. The indicator is stored in the ledger and never visible to any arm; the true positives of a noised pair are masked, as in E-PILOT-NOISE. r = 0.2 and r = 0.1 are not run. D55: cells RAW; FILTER K = 20 with BM25; FILTER K = 20 with SweRankEmbed-Small; ORACLE-CLEAN; RAW subsampled to ORACLE-CLEAN's size. WEIGHT is not run (weaker in E-PILOT-NOISE). N = 100 updates of the 3,000-update schedule, D31 shape, D28 negatives, CodeRankEmbed base, seeds 0 and 1, the same noise realisation for every cell of a seed: 10 runs. The uniform-noise r = 0.4 cells of E-PILOT-NOISE (seeds 0 and 1) are the comparison anchor and are not rerun; the r = 0 anchor is again the E-PILOT-ARMS2 RAW cells. D57: ranks of the replacement positives are computed from the per-function scores stored for E-PILOT-NOISE (no GPU cost); if a replacement lacks a stored score the run stops (the code raises) and nothing is rescored.

**Pre-registered reading (D56).** (i) Sanity: RAW degrades under sibling noise against the r = 0 anchor, else stop. (ii) ORACLE-CLEAN recovers the loss, else stop. (iii) First, the separation: AUC of each teacher's K-rank for noised against clean pairs (pair level, minimum over the pair's positives), and the share of noised pairs a FILTER at K = 20 drops. Expectation stated now: both lower than under uniform noise (0.83 and 0.97; 62 to 65% and 69.5 to 71.2% dropped). If the AUC is below 0.6 for both teachers the runs still go ahead; that is the finding. (iv) A method "works" when its paired difference to RAW has an interval excluding 0 in the positive direction on both levels (L2 repository-clustered, L3 query level), reported as a fraction of the ORACLE-CLEAN recovery and compared with its fraction in E-PILOT-NOISE at r = 0.4 (FILTER-BM25 0.78 / 0.52, FILTER-SweRankEmbed-Small 1.06 / 0.89, L2 / L3). (v) The minimum detectable difference at two seeds is reported. Reading rule for the write-up: if FILTER's share of recovery falls clearly below its E-PILOT-NOISE share, the E-PILOT-NOISE result is an upper bound that holds for findable noise only, and the unfiltered-set design must include a noise audit; if it stays, the claim extends to plausible noise. "Clearly below" is not defined further here; the numbers and intervals are reported and the reading is the engineer's. Teacher caveat of E-PILOT-NOISE stands: SweRankEmbed-Small shaped the public pool, so its cells are favoured; the BM25 cells are the ones not favoured.

**Result of S0 (measured, exploratory; `results/logs/n8_separation_52619.json`, job 52619, CPU; RESULTS rows `n8-separation-bm25`, `n8-separation-srs`).** Same 5,000 directories, seeds 0 and 1, r = 0.4, K = 20, pair-level rank = minimum over the pair's positives. Noised pairs per seed: 1,946 and 1,983 (the pairs of E-PILOT-NOISE). Replacement level (share of noised pairs): file 0.915 / 0.910, class 0 (by construction), directory 0.065 / 0.070, uniform 0.020 / 0.020 (seeds 0 / 1). Every replacement had a stored score (D57 holds; nothing rescored).

| teacher | AUC noised vs clean, sibling | AUC, uniform (E-PILOT-NOISE) | noised pairs a FILTER drops, sibling | uniform | clean pairs dropped, sibling |
|---|---|---|---|---|---|
| BM25 | 0.773 / 0.788 | 0.827 to 0.843 | 50.4 / 52.8% | 62 to 65% | 17.0% |
| SweRankEmbed-Small | 0.941 / 0.940 | 0.973 to 0.977 | 43.4 / 43.7% | 69.5 to 71.2% | 1.4 to 1.6% |

D56 (iii) expectation (both lower than under uniform noise) holds for both teachers; the largest change is the share of noised pairs a FILTER drops with the SweRankEmbed-Small teacher (about 70% to 43%), while the AUC stays high (0.94). Median pair rank of noised pairs: 21 / 23 (BM25), 16 (SweRankEmbed-Small), against 3 and 1 for clean pairs. The AUC gate of 0.6 is passed by both teachers. Evidence class: measured.

**Result of S1 (measured, exploratory; two seeds).** Jobs 52622 (seed 0) and 52685 (seed 1), account A, five cells each, 10 runs of 100 updates, 3.73 GPU-hours (0.37 per run; the first run's cost was checked before seed 1 was submitted, limit 5.0). Tables `results/tables/n8/n8_{effects,seeds,unique}.csv`, log `results/logs/n8_tables.json`, per-run config hashes in `n8_unique.csv`; command `python scripts/n1_tables.py results results/rq2/t3_curve_raw/2026-10-29_3909db9c/step_00000/query_rows.csv results/tables/n8 results/logs/n8_tables.json --rates 40 --prefix n8 --cells raw filter_bm25 filter_srs oracle sub --stem n8 --label E-PILOT-NOISE-SIB`. Values are nDCG@10 points (L2 repository-clustered 95% interval, L3 query-level interval), dense reading `units_all_nomod`, paired against the same seed; the r = 0 anchor is the E-PILOT-ARMS2 RAW cells.

**D56 (i), sanity: NOT passed.** RAW under sibling noise against the clean anchor: -1.01 [-1.77, 0.06] L2 and -0.52 [-1.14, 0.12] L3; both intervals include 0. Under uniform noise at r = 0.4 the same contrast is -3.67 [-4.85, -1.97] and -2.32 [-3.21, -1.42]. The pre-registered rule is "else stop": no further runs were made (none were pending; all ten had run). **D56 (ii), partly not passed:** ORACLE-CLEAN against RAW is +0.22 [-0.82, 1.41] L2 and +1.54 [0.74, 2.27] L3, so it recovers only at L3; its share of RAW's loss is 0.22 (L2) and 2.96 (L3), and with a loss that is not distinguishable from 0 these shares are not interpretable.

Because (i) failed, the statements below are descriptive and do not carry the reading of D56 (iv); they are reported so that nothing is hidden, not as a finding that FILTER works or fails under sibling noise. Difference to RAW, L2 / L3, with the share of the ORACLE-CLEAN recovery and the E-PILOT-NOISE share at r = 0.4 (uniform):

| method (teacher) | vs RAW L2 | vs RAW L3 | share of oracle recovery L2 / L3 | E-PILOT-NOISE share L2 / L3 | works (D56 iv) |
|---|---|---|---|---|---|
| FILTER K=20 (BM25) | -0.31 [-2.14, 1.56] | +0.87 [0.16, 1.56] | -1.41 / 0.56 | 0.78 / 0.52 | no (L2 includes 0) |
| FILTER K=20 (SweRankEmbed-Small) | +0.79 [-0.17, 1.74] | +1.12 [0.36, 1.86] | 3.59 / 0.73 | 1.06 / 0.89 | no (L2 includes 0) |

The size-matched subsample against RAW: -0.28 [-1.42, 0.62] L2, +0.50 [-0.01, 1.01] L3. FILTER against the subsample: BM25 -0.04 [-1.28, 1.54] / +0.36 [-0.42, 1.18]; SweRankEmbed-Small +1.06 [-0.48, 2.28] / +0.62 [-0.23, 1.45]. All FILTER and subsample cells see 3,232 distinct examples except ORACLE-CLEAN and the subsample (3,054 and 3,017 distinct for 3,232 draws, seed 0 / 1; repeats flagged in `n8_unique.csv`). Minimum detectable difference at two seeds from the observed variance: 2.00 (L2) and 1.93 (L3) points (seed bound 1.18 / 1.93, query bound 2.00 / 1.04; pooled seed SD 0.42 / 0.69, 5 degrees of freedom each) (D56 v). Every L2 difference to RAW above is below that value, and the L3 differences of FILTER are below 1.93 as well, so none is separable from seed noise at this sample size.

**Reading (evidence class: measured, two seeds, one noise realisation per seed, one subsample draw).** (1) Under this construction of sibling noise at r = 0.4, RAW loses about 1.0 (L2) and 0.5 (L3) nDCG points against the clean pool, about a quarter of the 3.7 and 2.3 it loses under uniform noise, and the loss is not distinguishable from 0 at two seeds. The plausible explanation is that a neighbour of the edited function is often itself a relevant document (the loss function sees a near-miss as positive); this is inference, not tested here. (2) Because the noise this cheaply replaced does little harm to RAW, the comparison that D56 was built to make (does FILTER's share of the recovery fall below its E-PILOT-NOISE share) has no usable denominator: ORACLE-CLEAN's recovery at L2 is +0.22. The shares in the table are therefore printed but not interpreted. (3) What can be said: the separation is weaker for sibling noise (the share of noised pairs a FILTER drops falls from 62 to 65% to 50 to 53% for BM25 and from about 70% to 43% for SweRankEmbed-Small) but the SweRankEmbed-Small AUC stays at 0.94, which is a statement about the teacher's rank, not about training. (4) The D56 reading rule (is the E-PILOT-NOISE result an upper bound for findable noise only) is NOT answered by this run: its premise, that RAW degrades, did not hold at this noise and sample size. The E-PILOT-NOISE claim is neither extended nor limited by it. Python only.

**Not decided here; open for the engineer (design).** Options that would make the question answerable, none run: (a) a stronger sibling noise (r = 0.8, or replacement restricted to non-positive functions that do not co-occur with the positives in any pull request), so that RAW degrades; (b) a third and fourth seed at r = 0.4 (about 3.7 more GPU-hours for two) to narrow RAW's loss, whose point estimate is -1.0 / -0.5 and whose lower bound is within 0.1 of 0; (c) keep it as a finding: at the plausible-noise level tested, the label noise does not hurt RAW measurably, which would itself bear on whether the unfiltered set needs a noise audit. Not decided by a session. Cheapest check that could change this: (b) with two more seeds on RAW and ORACLE-CLEAN only (4 runs, about 1.5 GPU-hours); the ledger is 60.41 of 62.
