# Timeline and fallback

> **Derived copy** of the team's Master Project Document (rev 16, dated 2026-10-11).
> The master doc is the source of truth. If this file and the master disagree, the master wins; record the drift as an Open question in `PROJECT_STATE.md` instead of silently editing here.

*Master-doc section(s): Timeline and fallback.*

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

## Go / no-go at week 12

One question: do we have at least two trained retrievers with a measurable retrieval difference? If yes, RQ3 proceeds. If no, RQ3 is cut and the project ships as RQ1 + RQ2 + the latency analysis, which is still a complete and defensible study.

Declaring this fallback in the proposal is what stops a slipped schedule from becoming a failed project.

## Milestones worth showing the professor

| Week | Artifact |
|---|---|
| 3 | Parser running on a real repository; ten CodeUnits and the edge-recovery percentage |
| 6 | Baseline encoder trained; a natural-language query returning the right function |
| 9 | RQ1 ablation table with the latency column |
| 12 | Four RQ2 arms, three seeds each, with the budget-accounting table |
| 14 | RQ3 resolved rates with CIs and the retrieval-vs-reasoning failure breakdown |

## The five-minute pitch

- **Setting.** Coding agents solve real repository tasks. They cannot read the whole repository — attention is quadratic — so something must select what they see.
- **System.** RIL is that selector: function-level indexing, three signals, fusion, assembly under a token budget.
- **Observation.** The retriever is trained, and the training-data decisions are usually made by convention. Prior work shows they affect retrieval metrics. Whether they affect whether the agent fixes the bug is less established.
- **Experiment.** Four retrievers differing only in supervision at matched optimizer updates; measure retrieval (RQ2), then plug each into the same agent and measure resolved rate (RQ3). RQ1 establishes the architecture the others hold fixed.
- **Claim.** Narrow and defensible: the audit found no study running this chain end to end with the agent held constant. And the null result is publishable, because the failure breakdown says why.
