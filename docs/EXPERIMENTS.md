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
| E-GRAPH-L3 | RQ1 ext. | + test/config node and edge types | L3 eval set | n/a | L3 metrics; edge-recovery coverage | planned |
| E-RQ2-RAW | RQ2 | arm = RAW | everything in the held-identical block | 3 | retrieval metrics + budget table | planned |
| E-RQ2-FILTER | RQ2 | arm = FILTER (K-rank threshold) | as above | 3 | as above | planned |
| E-RQ2-WEIGHT | RQ2 | arm = WEIGHT (K-rank soft weight) | as above | 3 | as above | planned |
| E-RQ2-CURRICULUM | RQ2 | arm = CURRICULUM (easy→hard) | as above | 3 | as above | planned |
| E-RQ2-CTRL-SUBRAW | RQ2 | RAW subsampled to FILTER's pool size, equal updates | as above | 3 | separates "less data seen more often" from quality | planned |
| E-RQ2-SEC-QQ | RQ2 (secondary) | best arm at 100/80/60/40% of pool | as above | 3 | quantity–quality curve (replicates SweRank §5.3.1 at repo level) | planned — only if core completes |
| E-RQ2-SEC-POSNEG | RQ2 (ablation) | degrade positive side vs negative side | as above | 3 | positive- vs negative-quality effect | planned — only if core completes |
| E-RQ3-AGENT | RQ3 | retriever = RAW / FILTER / WEIGHT / CURRICULUM | agent scaffold, base LLM, temperature, seed, instances | 1 per instance (paired) | resolved rate + CI; McNemar; retrieval-vs-reasoning breakdown; resolved rate per agent wall-clock | planned — gated on week-12 go/no-go |

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
