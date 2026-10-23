# Experimental design + Threats to validity

> **Derived copy** of the team's Master Project Document (rev 16, dated 2026-10-11).
> The master doc is the source of truth. If this file and the master disagree, the master wins; record the drift as an Open question in `PROJECT_STATE.md` instead of silently editing here.

*Master-doc section(s): Experimental design, Threats to validity.*

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
| Incomplete call graphs | Python dynamism defeats static resolution | Measure and report edge-recovery coverage as defined in ADR-012 (no expected range; corrected, see DEV-007) |
| Single language | Python only | Scope the claim to Python; do not generalize |
| Seed variance | One run can show a spurious gap | Three seeds minimum; mean ± SD |
| Granularity mismatch | CORE-Bench is chunk-level, our units are functions | Adopt their chunking for reported metrics |

### The null result is the good outcome

It is entirely possible that nDCG differs across arms while resolved rate does not. Three readings, all findings:

- The agent may be robust to ordering as long as the right file is somewhere in context — so nDCG gains that reorder an already-adequate set are invisible downstream.
- The binding constraint may be reasoning, not context. The retrieval-versus-reasoning failure log shows this directly.
- Thirty instances may be too few.
"Retrieval metrics are a leaky proxy for agent utility, and here is the failure-mode breakdown showing why" is a stronger claim than a modest positive result, and it is what the field currently lacks. What must not happen is quietly reframing a null as a positive.
