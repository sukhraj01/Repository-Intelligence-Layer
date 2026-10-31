# Research questions + What the literature audit changed

> **Derived copy** of the team's Master Project Document (rev 16, dated 2026-10-11).
> The master doc is the source of truth. If this file and the master disagree, the master wins; record the drift as an Open question in `PROJECT_STATE.md` instead of silently editing here.

*Master-doc section(s): Research questions, What the literature audit changed.*

## Research questions

Three questions in a chain: what signals work, how supervision changes the retriever, and whether that change reaches the agent.

**RQ1 — Which retrieval signals contribute to repository-level code retrieval?**

Incremental ablation measuring what lexical and structural signals add to a dense baseline: dense only, dense + BM25, dense + structural, all three. Not lexical-only or structural-only, because neither is a system anyone would build. Role: foundation, not headline. Report nDCG@10, MRR, Recall@10, and latency per configuration.

**RQ2 — How does training supervision quality and composition affect repository-level retrieval under matched optimization budgets?**

Core controlled experiment. Four arms — raw, filtering, weighting, curriculum — trained for the same number of optimizer updates at matched batch size and schedule. Compute cost, unique examples seen, and effective epochs are reported, not controlled: every table row states the number of optimizer updates, the distinct examples seen, the effective epochs and the pool it drew from, and a cell that cannot reach the common distinct-example count without repeating examples is flagged, never silently included. A random subsample of the raw pool, of the size of each filtered pool, is trained alongside every filtering comparison, and "quality beyond quantity" means beating that subsample, not only the full-pool raw arm. Secondary: the quantity–quality tradeoff. Ablation: positive-side versus negative-side quality.

**RQ3 — Does improving retriever supervision translate into improved coding-agent performance?**

The main scientific payoff and the only place a causal claim is available. Four retrievers from RQ2, one fixed agent scaffold, one fixed base model, fixed temperature and seed, same instances. Outcome: resolved rate. Critical diagnostic: for every failure, whether the gold-patch file was in the retrieved context — this splits retrieval failures from reasoning failures and is what makes a null result publishable.

### Wording that must not drift

The RQ2 heading says *matched optimization budgets*, not *fixed training budgets*. The two are different experiments and the distinction is the methodological claim. See Experimental design.

## What the literature audit changed

The audit ran across six-plus search rounds and repeatedly narrowed the claim. This section exists so nobody on the team re-inflates it later.

### Claims that were killed

| Original claim | Killed by |
|---|---|
| "We discovered that training data noise hurts code retrieval" | Sun et al., ICSE 2022 — measured it, filtered, +19.2% MRR (relative, one model (DeepCS), Java only, averaged over three small evaluation sets; corrected, see DEV-007) |
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
