> **Derived copy** of the team's Master Project Document (rev 16, dated 2026-10-11).
> The master doc is the source of truth. If this file and the master disagree, the master wins; record the drift as an Open question in `PROJECT_STATE.md` instead of silently editing here.

# Repository Intelligence Layer — Master Project Document

2026-10-11 ·

*Consolidated record of everything established across the research-design sessions. Supersedes all earlier proposal drafts.*

## Project identity

RIL is a repository-level code retrieval layer for LLM coding agents, plus a controlled study of whether the retriever's training supervision affects whether the agent actually resolves the issue.

| Field | Value |
|---|---|
| Project | Repository Intelligence Layer (RIL) |
| Lead | Sukhraj Singh |
| Team | 3 members |
| Institution | IIIT Hyderabad |
| Course | NLP semester project (also targeting placements) |
| Duration | 16 weeks |
| Status | Research design locked; implementation not started |
| Language scope | Python only |

The professor has approved the direction and raised three requirements: establish the ground truth before anything else, consider knowledge graphs for structural information, and engage seriously with CORE-Bench as the setting. A standing fourth requirement applies to all his projects: latency and throughput analysis, profiled per component, recorded before every commit.

## System versus experiment

Two things are being built, and only one of them is the contribution. Stating this first prevents the single most likely objection — "code search already exists".

**The system (engineering).** A retrieval layer over a repository: function-level indexing, lexical plus dense plus structural signals, rank fusion, context assembly under a token budget. Not novel on its own. It is the apparatus, and for placement purposes it is also the portfolio artifact.

**The experiment (the research).** Several retrievers that differ only in training supervision, one fixed agent, and a measurement of whether the difference survives to task resolution. This is what a reviewer judges.

The two pull against each other and the project must hold both. A good experiment freezes the retrieval stack so only one variable moves; a good product tunes it however it takes. Resolution: build and tune RIL properly first, freeze a configuration before the supervision runs begin, and keep the frozen config separate from the demo config.

## Research questions

Three questions in a chain: what signals work, how supervision changes the retriever, and whether that change reaches the agent.

**RQ1 — Which retrieval signals contribute to repository-level code retrieval?**

Incremental ablation measuring what lexical and structural signals add to a dense baseline: dense only, dense + BM25, dense + structural, all three. Not lexical-only or structural-only, because neither is a system anyone would build. Role: foundation, not headline. Report nDCG@10, MRR, Recall@10, and latency per configuration.

**RQ2 — How does training supervision quality and composition affect repository-level retrieval under matched optimization budgets?**

Core controlled experiment. Four arms — raw, filtering, weighting, curriculum — trained for the same number of optimizer updates at matched batch size and schedule. Compute cost, unique examples seen, and effective epochs are reported, not controlled. Secondary: the quantity–quality tradeoff. Ablation: positive-side versus negative-side quality.

**RQ3 — Does improving retriever supervision translate into improved coding-agent performance?**

The main scientific payoff and the only place a causal claim is available. Four retrievers from RQ2, one fixed agent scaffold, one fixed base model, fixed temperature and seed, same instances. Outcome: resolved rate. Critical diagnostic: for every failure, whether the gold-patch file was in the retrieved context — this splits retrieval failures from reasoning failures and is what makes a null result publishable.

### Wording that must not drift

The RQ2 heading says *matched optimization budgets*, not *fixed training budgets*. The two are different experiments and the distinction is the methodological claim. See Experimental design.

## What the literature audit changed

The audit ran across six-plus search rounds and repeatedly narrowed the claim. This section exists so nobody on the team re-inflates it later.

### Claims that were killed

| Original claim | Killed by |
|---|---|
| "We discovered that training data noise hurts code retrieval" | Sun et al., ICSE 2022 — measured it, filtered, +19.2% MRR |
| "We invented filtering / weighting / curriculum for code retrieval" | Each exists separately (Sun 2022; Li et al. 2023; CodeR 2025) |
| "No one has studied supervision quality for code retrieval" | CoRNStack, CodeR, SweRank all do |
| "Training on repository-level data improves repository-level retrieval" is open | CORE-Bench SFT: Qwen3-0.6B 17.0→26.5, Qwen3-8B 20.3→32.8 |
| The quantity–quality tradeoff is unmeasured | SweRank §5.3.1 measured it: filter rank K, optimal at moderate K≈20 |
| "First systematic study" of anything | Unverifiable; do not use |

### What survives

A controlled head-to-head of filtering versus weighting versus curriculum at a matched optimization budget, in a repository-level setting, with the agent held constant downstream. SweRank did filtering alone. CORE-Bench did one recipe. CodeR did curriculum inside a recipe. Nobody ran the comparison.

This is now an **empirical study** contribution rather than a discovery, and the proposal should say so in those words.

### The sentence to use

Our literature audit did not identify a study that systematically evaluates the controlled pipeline from retriever supervision quality, through retrieval performance, to repository-level coding-agent success.

Never: "first systematic study", "no one has studied", "novel approach to code retrieval".

### Where fresh room opened

CORE-Bench names three things it does not measure: the token cost of an agent's exploratory search loops, repository freshness with a stale index, and cross-language retrieval. The first is the professor's standing latency requirement, written into a benchmark paper as an open gap. Separately, no published graph schema includes test or configuration edges, while CORE-Bench Level-3 scores exactly that context.

## Literature map

Every paper that bears on the project, what it established, and why our work is not it. Citations here are corrected — the earlier proposal draft had CoRNStack attributed to the wrong authors.

### Supervision and training data for code retrieval

| Work | Established | Why RQ2 is not it |
|---|---|---|
| [Sun et al., ICSE 2022](https://arxiv.org/abs/2202.06649) — high-quality training sets for neural code search | Over a third of queries noisy; rule-based + model-based filtering; +19.2% MRR, +21.3% Answer@1 | Shows filtering works. No comparison against weighting or curriculum at matched budget |
| [Li et al., EMNLP 2023](https://arxiv.org/abs/2310.08069) — Rethinking Negative Pairs in Code Search | False negatives are pervasive; Soft-InfoNCE soft weighting | One intervention, snippet-level, no agent |
| [Suresh et al., 2024 — CoRNStack](https://arxiv.org/abs/2412.01007) (ICLR 2025) | Consistency filtering + hard-negative mining; evaluates SWE-bench function localization | Closest prior work. Ablations within one recipe, not a matched-budget comparison; agent not held constant |
| [Li et al., NeurIPS 2025 — CodeR](https://arxiv.org/abs/2508.11442) | Synthetic heterogeneous data + curriculum (annealing) across 16 tasks | Curriculum inside a recipe, not a controlled arm |
| [Gangi Reddy et al., 2025 — SweRank / SweLoc](https://arxiv.org/abs/2505.07849) (ICLR 2026) | Retrieve-and-rerank for issue localization; SweLoc training set; **filter-rank K tradeoff, optimal at moderate K≈20**; data-size curve | Filtering only. This is our training-data source and our quality signal |

### Repository-level retrieval and benchmarks

| Work | Established | Relevance |
|---|---|---|
| [Zhang et al., 2026 — CORE-Bench](https://arxiv.org/abs/2606.11864) | Three-level benchmark; sharp drop from snippet to agentic retrieval; weak L1→L2 correlation | **Primary evaluation.** See its own section below |
| [Jimenez et al., ICLR 2024 — SWE-bench](https://arxiv.org/abs/2310.06770) | Real GitHub issues with executable tests | RQ3 outcome measure; its train split is a mining source |
| [Wang et al., 2024 — CodeRAG-Bench](https://arxiv.org/abs/2406.14497) | Whether retrieval augments code generation | Related framing |
| CoIR | 10 datasets, 8 retrieval tasks, ~2M documents | Generalization check only; cut first if behind |
| CodeSearchNet | ~2M comment–code pairs, 6 languages | Transfer-gap arm, and the substrate Sun et al. characterized |

### Structural and graph approaches

| Work | Established | Relevance |
|---|---|---|
| [Chen et al., ACL 2025 — LocAgent](https://arxiv.org/abs/2503.09089) | Heterogeneous code graph; 92.7% file-level Acc@5; graph ablation; better localization → +12% Pass@10 | **Schema to adopt.** Its Table 5 is an RQ1-shaped ablation already run |
| [Yang et al., 2025 — KGCompass](https://arxiv.org/abs/2503.21710) | Graph unifying code entities with issues and PRs; 69.7% of localized bugs need multi-hop; 45.67% repair on SWE-bench-Lite | Adds the issue node our professor's chain starts from |
| [Jiang et al., 2025 — CoSIL](https://arxiv.org/abs/2503.22424) | Training-free, index-free call-graph search; +8.6–98.2% function Top-1; resolved rate +9.3–31.5% | Graph as agent tool, no training |
| [Agent Retrieval Bench, 2026](https://arxiv.org/abs/2607.24882) | File-level repository context retrieval; semantic and structure-aware retrieval are complementary | Supports RQ1's premise |

### Precedent for the RQ3 shape

LocAgent, CoSIL and KGCompass all show that better localization raises resolved rate. All three vary the *localization method*. None varies the *retriever's training supervision* with the agent held constant. That distinction is the whole of RQ3 and must be stated explicitly whenever RQ3 is defended.

## Ground truth and datasets

Ground truth is not missing. It is a dataset-selection and disjointness problem, and the only piece that must genuinely be built is the training pool.

### The constraint that breaks the obvious plan

**CORE-Bench releases evaluation data only.** The HuggingFace release is Level-2, Level-3 and rewritten-query benchmark data, laid out as `LEVEL-2/<dataset>/<repository>/` with `corpus.jsonl`, `queries.jsonl`, `qrels.jsonl`. There is no train split. The 53,301-PR SFT set used in the paper was not released.

So "train on CORE-Bench supervision" has no referent. CORE-Bench is evaluation, full stop.

### The mining recipe

All three published training sets used the same mechanical procedure, and it requires no human annotation:

- Mine merged PRs that close an issue.
- Issue text becomes the query.
- Functions touched by the patch become positives.
- Other functions in the same repository become negatives; mine hard ones by similarity.
This is what SweLoc, CoRNStack and CORE-Bench's SFT set all did. Replicating it on repositories post-dating model cutoffs is the honest answer to "establish your ground truth".

### Dataset assignment by stage

| Stage | Dataset | Role | Note |
|---|---|---|---|
| A — train | **SweLoc** (SweRank) | Primary pool | Released; purpose-built for issue localization |
| A — train | **Own PR-mined set** | Contamination-safe replication | The piece we actually build |
| A — train | CodeSearchNet | Transfer-gap arm | Not a substitute for repo-level data |
| C — retrieval eval | **CORE-Bench L2** | Primary metric | Issue-to-edit localization |
| C — retrieval eval | **CORE-Bench L3** | Structural / graph question | Tests, docs, configuration |
| C — retrieval eval | CORE-Bench L2/L3 REWRITE | Free query-rewriting ablation | Paper reports rewriting can hurt |
| C — retrieval eval | Loc-Bench | Contamination check, category balance | 660 examples, post-Oct-2024 |
| C — retrieval eval | CoIR | Generalization | Cut first if behind |
| D — agent eval | **SWE-bench Verified** | Resolved rate | Overlaps L2 — see below |

Dropped: Nokia / Stack Overflow code-search data. It adds a third distribution with its own relevance biases, serves none of the three RQs, and is scope creep.

### The overlap: a trap and an opportunity

CORE-Bench Level-2 is registered over SWE-bench Pro, Verified, Live, SWE-Bench++, SWE-bench+, Multi-SWE-bench and SWE-bench Multilingual; Level-3 over Pro, Verified, Multi-SWE-bench and Multilingual. **SWE-bench Verified sits inside both.**

*The trap.* If the training pool contains any repository appearing in L2, L3 or Verified, there is leakage. Instance-level disjointness is insufficient — a model that saw `django` functions in training has an advantage on every `django` instance. Enforce **repository-level disjointness**: build the held-out repo list first, filter the training pool against it, report the counts.

*The opportunity.* Because the same instances carry both retrieval qrels and executable tests, retrieval quality and resolved rate can be computed **on the same instance and paired**. RQ3 then becomes "for instances where retrieval improved, did resolution improve" — a paired per-instance analysis with far more power than comparing aggregate rates at n=30–50. This is the strongest single design choice available and it exists only because of the overlap.

### Label quality caveat to state out loud

LocAgent is explicit that patch-derived locations are approximate: a bug can be fixed somewhere other than where it was fixed historically, so gold locations are approximate targets. They also exclude edited documentation, import statements and comments from the localization target. The RQ2 false-negative discussion is literally about this.

## Structural signals and knowledge graphs

The professor's suggestion is correct and the schema already exists in published form. The gap we can fill is at the two ends of his chain: the issue at one end, tests and configuration at the other.

### The chain he described

`issue → implementation → caller → dependency → test → configuration`

No published schema covers all of it. LocAgent covers implementation through dependency. KGCompass adds the issue. Tests and configuration are covered by nobody — and are exactly what CORE-Bench Level-3 scores.

### LocAgent schema (adopt this)

Directed heterogeneous graph, built with Python `ast`, indexing in seconds per repository.

- Node types: `directory`, `file`, `class`, `function`
- Edge types: `contain`, `import`, `invoke`, `inherit`
- Function is the smallest node; its source is the retrieval document
- Entity id is the fully qualified name, e.g. `src/utils.py:MathUtils.calculate_sum`

### LocAgent's ablation — already an RQ1

| Setting | File Acc@5 | Module Acc@10 | Function Acc@10 |
|---|---|---|---|
| Full | 88.32 | 82.85 | 71.53 |
| w/o graph traversal | 86.13 | 78.47 | 66.06 |
| `contain` edges only | 86.50 | 79.56 | 66.42 |
| 1 hop only | 86.86 | 80.29 | 66.79 |
| w/o BM25 index | 75.18 | 68.98 | 60.22 |

Three readings that change our design. Directory structure is nearly worthless — `contain`-only barely beats removing the graph, so `invoke`/`import`/`inherit` carry the signal. Multi-hop matters more at function level than file level. And removing BM25 costs more than removing the graph entirely, which is a warning against over-investing in structure.

### KGCompass extension

Unifies code entities with repository artifacts — issues and pull requests become nodes. Scores functions by combining semantic similarity with shortest path length from the issue node. Reports that 69.7% of successfully localized bugs required multi-hop traversal. Language-agnostic and incrementally updatable.

### Our addition

Add `test` and `config` node types with `tests`/`configures` edges, and evaluate on CORE-Bench L3 rather than L2. This is where the remaining structural novelty concentrates.

### Design fork to decide

LocAgent uses the graph as an **agent tool** (the agent calls `TraverseGraph`). Our RIL design uses it as a **retrieval signal** (hop-decay score fused with BM25 and dense). These are different systems with different latency profiles. Pick deliberately; do not drift between them.

Baseline scoring if signal: `struct(u) = γ^dist(ℓ,u)` with γ≈0.5. Personalized PageRank seeded at the query location is the more principled version, worth trying second.

### Known limitation to quantify

Static call-graph extraction in Python is incomplete — dynamic dispatch, `getattr`, decorators, monkey-patching and duck typing all produce unresolvable edges. Expect 70–85% edge recovery. Measure and report this number; if RQ1 finds structural signals weak, incomplete extraction is a candidate explanation and the coverage figure is what makes that credible.

## CORE-Bench reference

[CORE-Bench](https://arxiv.org/abs/2606.11864) (Zhang et al., Beihang/Peking, arXiv 2606.11864, submitted 10 June 2026, revised 13 July 2026) establishes that repository-level retrieval is a distinct and much harder problem than snippet retrieval. It is our primary evaluation and our framing.

Data: [zhangfw123/CORE-Bench](https://huggingface.co/datasets/zhangfw123/CORE-Bench) · Code: [CORE-Bench-Eval](https://github.com/zhangfw123/CORE-Bench-Eval) · built on MTEB.

### The three levels

| Level | Goal | Scale |
|---|---|---|
| L1 — Code Understanding | Text-to-code, code-to-text, code-to-code, hybrid, competitive programming | 172,961 queries; 2,412,296 corpus items |
| L2 — Issue-to-Edit Localization | Retrieve files or chunks that must be modified | 632 repositories; 5,061 queries; 9,377,120 chunks |
| L3 — Broader Context Retrieval | Retrieve auxiliary code, tests, documentation, configuration | 97 repositories; 2,580 queries; 2,609,581 chunks |

L2 and L3 are built from SWE-bench-series instances. Registered groups: `CORE_BENCH_LEVEL1`, `LEVEL2`, `LEVEL3`, `LEVEL2_REWRITE`, `LEVEL3_REWRITE`.

### The performance cliff (nDCG@10)

| Model | L1 | L2 | L3 |
|---|---|---|---|
| Qwen3-8B | 71.7 | 20.3 | 34.4 |
| e5-mistral-7b | 54.7 | 18.3 | 33.9 |

Roughly a 70% collapse from L1 to L2. Code-specific embedding models — CodeRankEmbed, Jina Code, SweRankEmbed-Large — do not meaningfully close the gap.

### Four findings that shape our design

- **Cross-level correlation is weak.** L1 only moderately predicts L2. Snippet benchmarks tell you almost nothing about agent performance — this independently justifies our "metrics are a leaky proxy" argument.
- **Dense repositories punish recall.** Recall@100 drops sharply in large tightly-coupled codebases even when nDCG@10 holds; relevant chunks are pushed past the top-100. This is the recall-ceiling problem, measured.
- **Query rewriting can hurt.** Cleaning issue text removes repository-specific anchors — error strings, API names, URLs — that are critical signals. Either drop query expansion or ablate it against the REWRITE splits.
- **SFT on repository-level data works.** Qwen3-0.6B 17.0→26.5 (+56%), Qwen3-8B 20.3→32.8 (+62%), trained on 53,301 PRs across 628 repositories with multi-positive InfoNCE and repository-local hard negatives. A 0.6B model reaches ~80% of the 8B model's post-SFT performance.
That fourth finding is why RQ2 is a comparison of interventions and not a demonstration that supervision matters.

### What it does not measure

- Token cost of an agent's multi-step exploratory search loops — single-pass retrieval only
- Repository freshness; it uses fixed snapshots, so stale-index behaviour is untested
- Cross-language retrieval; L2 and L3 are segmented by language

### Granularity mismatch to resolve

L2 retrieves files or chunks, averaging roughly 15,000 chunks per repository. Our CodeUnit design is function-level. Recommendation: adopt their chunking for reported metrics so numbers are comparable, keep function-level units internally for the graph.

## Latency and throughput

The professor requires this on every project. It is also an open gap CORE-Bench names explicitly, which means it can be a contribution rather than a compliance exercise.

### His stated requirements

- Latency and throughput analysis: what takes the time, sourcing or ranking
- Detailed benchmarking and profiling: per-query, per-component time attribution
- Ablation on latency — if this element changes, how do latency and throughput change
- Record latency and throughput before every commit
- Benchmark per hardware spec
- Plan experiments around where time actually goes, and invest there

### Expected time distribution — hypotheses, not facts

| Stage | Rough expectation |
|---|---|
| Query encode (one forward pass) | ~5 ms |
| BM25 over 10⁴ units | ~1–10 ms |
| Flat exact ANN over 10⁴ × 768 | ~1–5 ms |
| Graph expansion | ~1 ms |
| RRF fusion | <1 ms |
| Cross-encoder rerank, 100 candidates | ~500–1000 ms |

If this holds, ranking dominates sourcing by about two orders of magnitude, and the entire RQ1 signal debate is latency-irrelevant. That is a genuine finding and it is exactly his "this is where my time is going" instruction. It also names the optimization axis: rerank 20 instead of 100, distil the cross-encoder, or drop it and measure the nDCG cost.

### Reframe RQ1 as a Pareto question

"Which signals improve nDCG" is done. "Which signals improve nDCG per millisecond" is not. Same four configurations, every row carrying p50/p95/p99 latency and a quality-per-unit-cost column. A signal adding 0.4 nDCG for 1 ms is free; for 200 ms it is not.

### Keep these separate

Latency is per-query, batch size 1, interactive — what the agent experiences. Throughput is indexing (units/sec) and training (samples/sec). Batch size 1 is the worst case for GPU utilization and documenting that gap is itself a result. Separate tables.

### Profiling correctness

- `torch.cuda.synchronize()` before and after every timed GPU section — without it CUDA is async and timings are fiction. Most common mistake.
- Discard the first N calls; warmup, JIT and cache population make call 1 unrepresentative.
- Report p50/p95/p99, never the mean. Tail latency is what hurts an interactive system.
- Separate cold-cache from warm-cache paths explicitly.
- `cProfile` / `py-spy` for CPU attribution, `torch.profiler` for GPU — not just wall-clock timers.

### Per-commit harness — build in week 1

A benchmark script running a fixed query set, writing p50/p95/p99 per stage plus hardware spec to an append-only CSV, failing loudly on regression past a threshold. Cheap to build, gives the final report a longitudinal record rather than one snapshot, and is strong portfolio material.

### The connection to RQ3

An agent calls retrieval repeatedly while exploring. At 800 ms per call and 30 calls, that is 24 seconds per task of pure retrieval. Retrieval latency is therefore part of the agent's cost budget, not just an engineering concern. **Resolved rate per unit of agent wall-clock** is a metric nobody reports, follows directly from his emphasis, and strengthens RQ3.

### Scheduling constraint

RQ2 requires the retrieval stack frozen across all arms. All latency optimization must land **before** the RQ2 runs start, with the frozen config getting its own benchmark snapshot. Note also that the four RQ2 encoders are architecturally identical, so query latency does not vary across arms — RQ2's cost story is training throughput, not inference latency.

## Experimental design

The methodological claim is precision about what is controlled. "Fixed budget" is ambiguous and the ambiguity changes the experiment.

### What "budget" means

| If you fix… | Then… | Consequence |
|---|---|---|
| Wall-clock / GPU-hours | Arms with per-example overhead complete fewer updates | You are measuring implementation efficiency, not supervision |
| Unique examples seen | Filtering, having fewer examples, gets fewer updates | Confounds supervision with training length |
| **Optimizer updates** | **Every arm gets the same gradient steps at the same batch size** | **Filtering necessarily reuses data more — reported, not eliminated** |

We fix optimizer updates. GPU-hours, unique examples seen and effective epochs are recorded alongside every result.

### The four supervision arms

| Arm | Positives | Negatives | Ordering | Data exposure |
|---|---|---|---|---|
| RAW | all | random in-batch | random | full pool, 1 epoch |
| FILTER | threshold on quality signal | mined hard | random | reduced pool, more epochs |
| WEIGHT | all, loss-scaled | mined hard | random | full pool, 1 epoch |
| CURRICULUM | all | mined hard | easy → hard | full pool, 1 epoch |

### The quality signal — do not invent one

The single sharpest critique received: *we cannot simply label examples "noisy" without evidence.* There is a published answer. SweRank filters by **K, the minimum rank of the positive relative to negatives under a base retriever**; raising K relaxes filtering, yielding more instances and more noise; optimal at moderate K≈20.

Using K gives a continuous, reproducible quality axis with a published reference point, and makes FILTER and WEIGHT the *same signal* applied as a hard threshold versus a soft weight — a far cleaner comparison than separate heuristics.

**Warning.** The filter rules drafted earlier (docstring under four words, docstring over 300 tokens, auto-generated detection) were designed for docstring–code pairs. Issue-localization data has a different noise structure; a 400-word bug report with a stack trace breaks all of them. Repository-level data needs repository-level quality signals. Settle this in week 1.

**Second warning.** If a learned model computes the filter, use a *separately pretrained* encoder, never the model being trained — otherwise it is a self-confirming loop that removes exactly what the model has not yet learned.

### Held identical across arms

```
base checkpoint, seed, architecture, pooling
batch size, learning rate + schedule, warmup, weight decay
optimizer updates (target 20,000)
temperature tau (0.05), max sequence length
evaluation set, metric code, index type (flat exact)
context assembly step — byte-identical
```

Varies: the supervision strategy, and nothing else.

### Statistics

Three seeds minimum per arm; retrieval fine-tuning is noisy and a 0.5-point nDCG gap from one seed is not a result. Report mean ± standard deviation; if two arms overlap within one SD, say they are indistinguishable at this sample size.

For RQ3 at n≈30, binomial standard error near a 30% resolve rate is roughly 8.4 percentage points. Use a **paired McNemar test** on per-instance outcomes — more power than comparing rates, and available because all arms run the same instances. Report confidence intervals, not bare percentages.

Rehearsed line: *"With thirty instances I can detect a large effect, not a subtle one. If arms differ by three points I will report them as indistinguishable, not claim one is better."*

### Secondary and ablation — only if the core completes

- **Quantity–quality tradeoff.** Best core arm at 100/80/60/40% of pool. Note SweRank already published a version of this; frame as replication at repository level.
- **Positive versus negative quality.** Degrade one side at a time. To the best of the audit, no code-retrieval paper isolates this.

## Threats to validity

Volunteering these is the single most effective move in a proposal defence. Raise each before a reviewer does.

| Threat | Why it bites | Mitigation |
|---|---|---|
| Data-budget confound in FILTER | Fewer examples at equal updates means more reuse; a FILTER win may be "less data seen more often" | Report unique-examples-seen; add a subsampled-RAW control at the same pool size and updates |
| Repository leakage | Training pool and L2/L3/Verified may share repositories | Repository-level disjointness, not instance-level; build the held-out repo list first and report counts |
| Filter uses a learned model | Risks removing exactly what the model has not yet learned | Independent pretrained encoder for filtering; report drop rate |
| Quality signal not transferable | Docstring-era filters break on issue text | Use SweRank's K-rank signal; settle in week 1 |
| Small RQ3 sample | n≈30 gives ±8.4pp standard error | Paired McNemar; report CIs; state detectable effect size up front |
| Benchmark contamination | Base LLM has likely seen SWE-bench repositories | Inflates absolute rates identically across arms, so the comparison holds; say so, and do not report absolute rates as agent capability |
| Incomplete call graphs | Python dynamism defeats static resolution | Measure and report edge-recovery coverage (expect 70–85%) |
| Single language | Python only | Scope the claim to Python; do not generalize |
| Seed variance | One run can show a spurious gap | Three seeds minimum; mean ± SD |
| Granularity mismatch | CORE-Bench is chunk-level, our units are functions | Adopt their chunking for reported metrics |

### The null result is the good outcome

It is entirely possible that nDCG differs across arms while resolved rate does not. Three readings, all findings:

- The agent may be robust to ordering as long as the right file is somewhere in context — so nDCG gains that reorder an already-adequate set are invisible downstream.
- The binding constraint may be reasoning, not context. The retrieval-versus-reasoning failure log shows this directly.
- Thirty instances may be too few.
"Retrieval metrics are a leaky proxy for agent utility, and here is the failure-mode breakdown showing why" is a stronger claim than a modest positive result, and it is what the field currently lacks. What must not happen is quietly reframing a null as a positive.

## Open decisions

Every one of these must close by end of week 2. Each has a recommendation; none is settled until the team agrees and it is written down.

| # | Decision | Options | Recommendation |
|---|---|---|---|
| 1 | Training pool | SweLoc / own PR-mined / both | **Both** — SweLoc to avoid being blocked, own set for contamination safety |
| 2 | Quality signal | SweRank K-rank / heuristics / LLM judge | **K-rank**, published and continuous |
| 3 | Graph role | retrieval signal (hop-decay score) vs agent tool (TraverseGraph) | **Signal** — matches RIL architecture and keeps latency predictable |
| 4 | Retrieval granularity | function / CORE-Bench chunks / both | **Both** — chunks for reported metrics, functions internally |
| 5 | Primary benchmark | L2 / L3 / Loc-Bench | **L2 primary, L3 for the graph question**, Loc-Bench as contamination check |
| 6 | Base encoder | CodeBERT / UniXcoder / Qwen3-Embedding-0.6B | **Qwen3-0.6B** — CORE-Bench reports strong post-SFT results at CPU-feasible size |
| 7 | Agent scaffold | SWE-agent / OpenHands / Agentless / custom | **Agentless** — simplest to hold constant; complexity is a liability here |
| 8 | Base LLM for agent | API / local quantized | Decide on budget; if local, quantize identically across all arms |
| 9 | Cross-encoder rerank | include / exclude | Include but measure; it likely dominates latency |
| 10 | Usable by others? | yes / no | Decide now — it changes CLI, config and packaging decisions in week 1, not week 10 |

### Week-1 deliverables, in order

- Freeze the CodeUnit schema and write it down — every component reads it; changing it in week 9 means re-indexing and re-running everything
- Build the held-out repository list from CORE-Bench L2/L3 and SWE-bench Verified
- Filter any candidate training pool against that list; record how many instances survive
- Stand up the per-commit latency harness (fixed query set → p50/p95/p99 per stage → append-only CSV)
- Parse one real repository end to end; print ten CodeUnits and the call-graph edge-recovery percentage
- Decide items 1–10 above and record the decision and reasoning

### Things to say "I don't know" about

Do not bluff on: exact figures from papers not read in full; whether the effect will be significant; which intervention will win; implementation details not yet decided. "That is provisional — I will fix it in week 1 once I have looked at the data" is a complete and respectable answer.

## Architecture and implementation

### The CodeUnit — freeze this in week 1

The interface between the parser, all three retrieval signals, the training-data builder and the evaluation harness. Every component reads it.

```
@dataclass
class CodeUnit:
    # identity
    id: str                 # "auth.py::TokenManager.verify_jwt"
    repo_id: str
    language: str

    # location
    file: str
    start_line: int
    end_line: int

    # structure -> feeds the dense encoder
    unit_type: str          # function | method | class
    name: str
    qualified_name: str
    signature: str
    docstring: str | None

    # content
    source: str

    # relationships -> feeds the structural signal
    calls: list[str]
    called_by: list[str]
    tests: list[str]
    configs: list[str]

    # metadata
    is_test: bool
    loc: int
    last_modified: str
```

### Offline indexing, once per repository

- Parse with `ast` (or tree-sitter if multi-language later). Skip `__pycache__`, `.git`, vendored and generated files.
- Build call, import, inherit graphs. **Record edge-recovery coverage.**
- Build the lexical index: split identifiers (camelCase, snake_case), index name / signature / docstring / body as separately weighted fields. BM25 with k₁=1.2, b=0.75 — tune b, since code unit lengths vary enormously.
- Encode units and store in a flat exact index. **This is the only box that changes between experimental arms.**

### Online retrieval

```
def retrieve(location, task, max_results=20, max_tokens=4096):
    q = interpret(location, task)

    cand_lex    = bm25.search(q, k=1000)
    cand_dense  = ann.search(encoder(q), k=1000)
    cand_struct = graph.neighbours(location, max_hops=2)

    fused = rrf([cand_lex, cand_dense, cand_struct], k=60)
    top   = cross_encoder.rerank(q, fused[:100])[:max_results]

    return assemble(top, budget=max_tokens)
```

Use RRF, not a weighted score sum: BM25 returns unbounded scores whose scale shifts with corpus statistics while cosine sits in a narrow band, so a weighted sum needs per-corpus retuning. RRF uses rank only and needs none — worth more than the last fraction of a point when the stack must stay identical across four arms.

Use a **flat exact** index, not ANN. At 10³–10⁵ units per repository it costs milliseconds, and it removes ANN recall as a confound — an apparent difference between arms must not be an artifact of approximate search.

The `assemble` step is easy to overlook: deduplicate overlapping units, order so the most relevant survives truncation, attach signatures of called functions, fit a hard token budget. **Keep it byte-identical across arms.**

### Defaults to start from

| Parameter | Value |
|---|---|
| Pooling | mean over tokens, masked |
| Temperature tau | 0.05 (range 0.03–0.07) |
| Batch size | as large as memory allows — it is the in-batch negative count |
| Learning rate | 2e-5, linear decay, 10% warmup |
| Optimizer updates | 20,000, fixed across arms |
| Max sequence length | 512 |
| Fusion | RRF, k=60 |
| Seeds | 3 minimum per arm |

### Repository layout

```
ril/
  parsing/      repository_parser.py, code_unit.py, call_graph.py
  retrieval/    bm25_index.py, dense_encoder.py, hybrid_retriever.py, ranking.py
  training/     contrastive_loss.py, training.py, data_loader.py, supervision.py
  evaluation/   metrics.py, core_bench.py, agent_integration.py
  bench/        latency_harness.py, profile_stages.py
  analysis/     error_analysis.py, visualization.py
  config/       parameters.py, paths.py
```

## Timeline and fallback

The dependency structure matters more than the dates. RQ2 cannot start until the training pipeline works; RQ3 cannot start until RQ2 has produced at least two distinguishable checkpoints.

| Weeks | Work | Owner |
|---|---|---|
| 1–2 | CodeUnit schema frozen, held-out repo list, latency harness, decisions 1–10 closed | All |
| 1–4 | Parsing, call graph, BM25 index | Person A |
| 3–8 | Dense encoder, baseline training, data pipeline | Person B |
| 3–6 | Evaluation harness, CORE-Bench loaders, metrics | Person C |
| 5–8 | RQ1 ablation with latency columns | Person A |
| 6–12 | RQ2: four arms × three seeds | Person B |
| 7–10 | Graph extension: test and config edges, L3 evaluation | Person A |
| 10–14 | RQ3: agent integration, paired per-instance runs | Person C |
| 13–16 | Analysis, error breakdown, report, presentation | All |

### Go / no-go at week 12

One question: do we have at least two trained retrievers with a measurable retrieval difference? If yes, RQ3 proceeds. If no, RQ3 is cut and the project ships as RQ1 + RQ2 + the latency analysis, which is still a complete and defensible study.

Declaring this fallback in the proposal is what stops a slipped schedule from becoming a failed project.

### Milestones worth showing the professor

| Week | Artifact |
|---|---|
| 3 | Parser running on a real repository; ten CodeUnits and the edge-recovery percentage |
| 6 | Baseline encoder trained; a natural-language query returning the right function |
| 9 | RQ1 ablation table with the latency column |
| 12 | Four RQ2 arms, three seeds each, with the budget-accounting table |
| 14 | RQ3 resolved rates with CIs and the retrieval-vs-reasoning failure breakdown |

### The five-minute pitch

- **Setting.** Coding agents solve real repository tasks. They cannot read the whole repository — attention is quadratic — so something must select what they see.
- **System.** RIL is that selector: function-level indexing, three signals, fusion, assembly under a token budget.
- **Observation.** The retriever is trained, and the training-data decisions are usually made by convention. Prior work shows they affect retrieval metrics. Whether they affect whether the agent fixes the bug is less established.
- **Experiment.** Four retrievers differing only in supervision at matched optimizer updates; measure retrieval (RQ2), then plug each into the same agent and measure resolved rate (RQ3). RQ1 establishes the architecture the others hold fixed.
- **Claim.** Narrow and defensible: the audit found no study running this chain end to end with the agent held constant. And the null result is publishable, because the failure breakdown says why.

## References

All links verified October 2026. Citations corrected against the earlier proposal draft.

### Core papers

- Zhang, F., Zhang, Y., Li, M., Long, D., Hu, L., Xie, P., Zhang, Z. & Zhuang, F. (2026). *CORE-Bench: A Comprehensive Benchmark for Code Retrieval in the Era of Agentic Coding.* [arXiv:2606.11864](https://arxiv.org/abs/2606.11864) · [dataset](https://huggingface.co/datasets/zhangfw123/CORE-Bench) · [eval code](https://github.com/zhangfw123/CORE-Bench-Eval)
- Gangi Reddy, R. et al. (2025). *SweRank: Software Issue Localization with Code Ranking.* [arXiv:2505.07849](https://arxiv.org/abs/2505.07849) · [code](https://github.com/gangiswag/SweRank) · [SweRankEmbed-Large](https://huggingface.co/Salesforce/SweRankEmbed-Large)
- Chen, Z., Tang, X., Deng, G., Wu, F., Wu, J., Jiang, Z., Prasanna, V., Cohan, A. & Wang, X. (2025). *LocAgent: Graph-Guided LLM Agents for Code Localization.* ACL 2025. [arXiv:2503.09089](https://arxiv.org/abs/2503.09089) · [code](https://github.com/gersteinlab/LocAgent)
- Suresh, T., Gangi Reddy, R., Xu, Y., Nussbaum, Z., Mulyar, A., Duderstadt, B. & Ji, H. (2024). *CoRNStack: High-Quality Contrastive Data for Better Code Ranking.* ICLR 2025. [arXiv:2412.01007](https://arxiv.org/abs/2412.01007)
- Jimenez, C. E., Yang, J., Wettig, A., Yao, S., Pei, K., Press, O. & Narasimhan, K. (2024). *SWE-bench: Can Language Models Resolve Real-World GitHub Issues?* ICLR 2024. [arXiv:2310.06770](https://arxiv.org/abs/2310.06770) · [code](https://github.com/SWE-bench/SWE-bench)

### Supervision and training data

- Sun, Z. et al. (2022). *On the Importance of Building High-quality Training Datasets for Neural Code Search.* ICSE 2022. [arXiv:2202.06649](https://arxiv.org/abs/2202.06649)
- Li, H. et al. (2023). *Rethinking Negative Pairs in Code Search.* EMNLP 2023. [arXiv:2310.08069](https://arxiv.org/abs/2310.08069)
- Li, C. et al. (2025). *CodeR / Towards a Generalist Code Embedding Model Based on Massive Data Synthesis.* NeurIPS 2025. [arXiv:2508.11442](https://arxiv.org/abs/2508.11442)

### Structural and graph approaches

- Yang, B., Tian, H., Ren, J., Jin, S., Liu, Y., Liu, F. & Le, B. (2025). *Enhancing Repository-Level Software Repair via Repository-Aware Knowledge Graphs (KGCompass).* [arXiv:2503.21710](https://arxiv.org/abs/2503.21710)
- *CoSIL: Software Issue Localization via LLM-Driven Code Repository Graph Searching* (2025). [arXiv:2503.22424](https://arxiv.org/abs/2503.22424)
- *Agent Retrieval Bench: Evaluating Repository Context Retrieval for Coding Agents* (2026). [arXiv:2607.24882](https://arxiv.org/abs/2607.24882)

### Agents and related benchmarks

- Xia, C. S., Deng, Y., Dunn, S. & Zhang, L. (2024). *Agentless: Demystifying LLM-based Software Engineering Agents.* [arXiv:2407.01489](https://arxiv.org/abs/2407.01489)
- Yang, J. et al. (2024). *SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering.* [arXiv:2405.15793](https://arxiv.org/abs/2405.15793)
- Wang, X. et al. (2025). *OpenHands: An Open Platform for AI Software Developers as Generalist Agents.* ICLR 2025.
- Wang, Z. Z. et al. (2024). *CodeRAG-Bench: Can Retrieval Augment Code Generation?* [arXiv:2406.14497](https://arxiv.org/abs/2406.14497)

### Datasets

- [CodeSearchNet](https://github.com/github/CodeSearchNet) — ~2M comment–code pairs, 6 languages
- [CoIR](https://github.com/CoIR-team/coir) — 10 datasets, 8 retrieval tasks, ~2M documents
- Loc-Bench — 660 examples; bug 282, feature 203, security 31, performance 144; released with LocAgent

### Correction log

- CoRNStack is **Suresh et al.**, not "Zhang, X. et al." as in the earlier draft
- CORE-Bench releases **evaluation data only**; its 53k-PR SFT set is unreleased
- RQ2 wording is **matched optimization budgets**, not "fixed training budgets"
