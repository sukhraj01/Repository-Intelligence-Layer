read: full — 27 pages incl. appendices, PDF v6, pdftotext -layout (poppler), Figures 3-8 (pp.7, 8, 15) rendered and looked at, 2026-10-23

# RepoNavigator — Zhang, Duan, Zhang et al. (arXiv 2512.20957v6, ICML 2026 per the PDF's first page), "One Tool Is Enough: Reinforcement Learning of LLM Agents for Repository-Level Code Navigation"

Source file: arXiv PDF v6 (dated 26 May 2026; the earlier scan fetched v5, v6 is the highest version that resolves), 27 pages: body pp.1-9, references pp.9-11, appendices pp.12-27 (baseline tool sets, experimental details, extra results, analysis, threats, a full case-study trajectory). The extracted text has 27 pages and no blank page. Figures 3, 4, 5 (p.7), 6 (p.8), 7, 8 (p.15) were rendered and looked at; Figure 6 is a Venn sketch without numbers; only values printed in tables or text are quoted below. Read because the earlier scan listed it abstract-only and it uses static symbol resolution (a language server) as the only navigation tool of an LLM agent, which bears on the graph role and on edge resolution.

## What it established

- An LLM agent whose single tool is "jump to the definition of a symbol used in file F", implemented with a Python language server (Pyright), trained with GRPO directly from instruct models of 7B, 14B and 32B, beats the listed agent baselines of the same model size on per-sample F1 and IoU at function and file level on SWE-bench Verified and on the Python part of SWE-bench Pro (Tables 1-2, pp.5-6).
- Adding the multi-tool sets used by earlier agents (get class, get function, get repository structure) to the jump tool lowered function-level IoU after outcome-only RL from 24.28 (jump alone) to 13.71 (all four tools), one run each, 7B model (Table 4, p.8; Table 6, p.13).
- Plugging the agents' function-level output into the same repair stage (Agentless's) on SWE-bench Verified with a 14B model: resolved 10.12% (Agentless localization) to 15.03% (trained RepoNavigator) (Table 3, p.7). One run each.
- RL from the instruct model beat SFT and SFT followed by RL on function-level metrics, 7B (Table 8, p.14).

## What it did not establish

- **Not the standard task.** Every method, baselines included, receives "the precise file path and the corresponding entry function" for each issue, "normally a testing function" (Appendix B, p.13; Appendix F, p.17). In the case study the entry point is the test that exercises the faulty function (p.20). The paper does not say how entry points were chosen; if they come from the evaluation tests, they carry information from the gold test patch. Results are not comparable with localization on issue text alone, and the claim that every relevant location lies on a dependency path from the entry point (Sec. 5.3, p.8) is argued, not measured (Figure 6 has no numbers).
- **No measurement of resolution quality.** The language server's resolution rate, failures on dynamic constructs, or how often the gold function is reachable by jumps from the entry point are not reported; the paper says it "did not observe any instances of monkey patching or dynamic imports" (p.14) without a count.
- One run per cell; no seeds or intervals; the RL hyperparameters (clip, learning rate, batch 128, 12 tool calls, 10,240 tokens) are fixed, λ = 0.5 varied over 0.4 to 0.6 only (Table 7, p.14).
- No embedding retriever among the baselines; nothing about training retrievers.
- Baseline OrcaLoca on Verified is copied from another paper because its code could not be reproduced (p.12).

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| Training set: samples filtered from SWE-smith / batch size / epochs | 4k / 128 / 1 | p.5 |
| RL rollouts per training sample when filtering (sample dropped if all score zero) | 16 | Sec. 4.1, p.4 |
| Maximum tool calls per episode / maximum response length | 12 / 10240 | Appendix B, p.13 |
| Reward weight between DICE and tool-call success | 0.5 | Eq. 5, p.4 |
| Verified, function-level IoU, trained RepoNavigator 7B / 14B / 32B | 26.43 / 26.84 / 32.30 | Table 1, p.5 |
| Verified, function-level IoU, training-free RepoNavigator 7B / 14B / 32B | 15.46 / 23.00 / 25.16 | Table 1, p.5 |
| Verified, function-level recall, distilled RepoSearcher 7B / 32B (high recall, low precision) | 63.26 / 69.50 | Table 1, p.5 |
| Pro (Python), function-level IoU, trained RepoNavigator 7B / 14B / 32B | 12.02 / 14.58 / 17.16 | Table 2, p.6 |
| Tool-set ablation, function-level IoU: jump only / jump plus three tools | 24.28 / 13.71 | Table 4, p.8 |
| Resolved on Verified with the Agentless repair stage: Agentless / LocAgent / RepoSearcher / RepoNavigator / RepoNavigator with RL | 10.12 / 13.01 / 12.47 / 14.74 / 15.03 | Table 3, p.7 |
| Function IoU of the same five localizers | 12.28 / 12.32 / 10.60 / 23.00 / 26.84 | Table 3, p.7 |
| Mean tokens per issue (thousands), RepoNavigator / LocAgent, 14B on Pro | 2.68 / 48.86 | Table 9, p.14 |
| Correlation between tool reward and DICE reward during training | 0.8886 | Appendix C.3, p.15 |

## Method details we need

- **Jump** (Sec. 3.3, pp.3-4): name symbols resolved along local, enclosing, module, builtins scopes; attributes resolved by inferred receiver type and method resolution order; cross-file by an import dependency graph that follows re-exports and `__all__`. This is the same resolution problem as the project's `invoke` edges, done by a type checker rather than an AST resolver.
- **Metrics** (Appendix B, p.13): per-sample F1 (DICE) and IoU of predicted against gold sets; an empty prediction scores zero.
- **Leakage control** (Appendix D.5, p.17): training samples whose repositories overlap SWE-bench Verified or Pro are removed (repository-level, as the project does).

## Relation to RQ1 / RQ2 / RQ3

- RQ1 / graph (Q30, Q35, Q36): evidence that a language server's symbol resolution is usable as an agent's only navigation primitive; a lead for the project's resolver comparison (X1 uses Jedi as a second reader; Pyright is a third option). It does not measure resolution precision or recall, so it does not inform the `ambiguous` or `external` policy directly. The graph enters here as an agent tool, not as a ranking signal.
- RQ2: none (the training is RL of an agent, not contrastive training of a retriever). The training-set filter (drop samples where 16 rollouts all score zero) is a difficulty filter on agent data, not a quality signal for retriever pairs.
- RQ3: one more data point that better function-level localization raised resolved rate with a fixed repair stage (+4.91 points from Agentless's localization to the trained agent, one run, 500-instance Verified, entry point given). Run-to-run variation is not reported, so the size of the difference cannot be judged.

## Discrepancies

- With the earlier scan entry ("single jump-to-definition tool plus reinforcement learning"): confirmed; the scan did not note the entry-point input, which changes the task.
- Internal: the abstract says the 32B model exceeds closed-source models such as one named there "on most metrics" (p.1). In Table 1 (p.5) the trained 32B model (34.09 function per-sample F1, 67.75 file) is above two of the three closed-source rows at function level, below one of them at file level (73.01), and below the strongest closed-source row on every metric (43.62 function per-sample F1); all closed-source rows run inside the RepoNavigator or RepoSearcher scaffold (closed-source models, versions in the paper's table 1). Table 3's caption says "14B" and its RepoNavigator rows match the 14B rows of Table 1 (23.00, 26.84). Figure 3's caption mentions "RFT" while the legend says "SFT".

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| Earlier scan (abstract only): one jump tool plus RL | confirmed | Sec. 3, pp.3-4 | entry point supplied to every method (p.13) |
| Abstract: 32B exceeds closed-source models on most metrics | qualified | Table 1, p.5 | holds against the named model's row at function level, not against the strongest closed-source row |
| Fewer tools are better | confirmed for one setting | Table 4, p.8 | one run each, 7B, outcome-only reward |
| Exhaustive jumps from the entry point reach every gold location | not measured | Sec. 5.3, p.8 | Figure 6 is a sketch without numbers |
