# Literature map

> **Derived copy** of the team's Master Project Document (rev 16, dated 2026-10-11).
> The master doc is the source of truth. If this file and the master disagree, the master wins; record the drift as an Open question in `PROJECT_STATE.md` instead of silently editing here.

*Master-doc section(s): Literature map.*

Every paper that bears on the project, what it established, and why our work is not it. Citations here are corrected — the earlier proposal draft had CoRNStack attributed to the wrong authors.

## Supervision and training data for code retrieval

| Work | Established | Why RQ2 is not it |
|---|---|---|
| [Sun et al., ICSE 2022](https://arxiv.org/abs/2202.06649) — high-quality training sets for neural code search | 33.1% of queries carry a noise feature (corrected, see DEV-007); rule-based + model-based filtering; +19.2% MRR, +21.3% Answer@1, relative, for DeepCS on Java only (corrected, see DEV-007) | Shows filtering works. No comparison against weighting or curriculum at matched budget |
| [Li et al., EMNLP 2023](https://arxiv.org/abs/2310.08069) — Rethinking Negative Pairs in Code Search | Soft-InfoNCE soft weighting of in-batch negatives; that false negatives are common is cited from earlier work, not measured there (corrected, see DEV-007) | One intervention, snippet-level, no agent |
| [Suresh et al., 2024 — CoRNStack](https://arxiv.org/abs/2412.01007) (ICLR 2025) | Consistency filtering + hard-negative mining; evaluates SWE-bench function localization | Closest prior work. Ablations within one recipe, not a matched-budget comparison; agent not held constant |
| [Li et al., NeurIPS 2025 — CodeR](https://arxiv.org/abs/2505.12697) (identifier corrected, see DEV-007) | Synthetic heterogeneous data + curriculum (annealing) across 16 tasks | Curriculum inside a recipe, not a controlled arm |
| [Gangi Reddy et al., 2025 — SweRank / SweLoc](https://arxiv.org/abs/2505.07849) (ICLR 2026) | Retrieve-and-rerank for issue localization; SweLoc training set; **filter-rank K tradeoff, optimal at moderate K≈20**; data-size curve | Filtering only. This is our training-data source and our quality signal |

## Repository-level retrieval and benchmarks

| Work | Established | Relevance |
|---|---|---|
| [Zhang et al., 2026 — CORE-Bench](https://arxiv.org/abs/2606.11864) | Three-level benchmark; sharp drop from snippet to agentic retrieval; weak L1→L2 correlation | **Primary evaluation.** See its own section below |
| [Jimenez et al., ICLR 2024 — SWE-bench](https://arxiv.org/abs/2310.06770) | Real GitHub issues with executable tests | RQ3 outcome measure; its train split is a mining source |
| [Wang et al., 2024 — CodeRAG-Bench](https://arxiv.org/abs/2406.14497) | Whether retrieval augments code generation | Related framing |
| CoIR | 10 datasets, 8 retrieval tasks, ~2M documents | Generalization check only; cut first if behind |
| CodeSearchNet | ~2M comment–code pairs, 6 languages | Transfer-gap arm, and the substrate Sun et al. characterized |

## Structural and graph approaches

| Work | Established | Relevance |
|---|---|---|
| [Chen et al., ACL 2025 — LocAgent](https://arxiv.org/abs/2503.09089) | Heterogeneous code graph; 92.7% file-level Acc@5; graph ablation; better localization → +12% Pass@10 | **Schema to adopt.** Its Table 6 (Table 5 is the cost table; corrected, see DEV-005) is an RQ1-shaped ablation already run |
| [Yang et al., 2025 — KGCompass](https://arxiv.org/abs/2503.21710) | Graph unifying code entities with issues and PRs; 89.7% of 146 ground-truth functions lie two or more hops from the issue node (corrected, see DEV-005; 69.7% was the superseded first version); 45.67% repair on SWE-bench-Lite | Adds the issue node our professor's chain starts from |
| [Jiang et al., ASE 2025 — CoSIL](https://arxiv.org/abs/2503.22424) (venue added, see DEV-011) | Training-free, index-free call-graph search; +8.6–98.2% function Top-1; resolved rate +9.3–31.5% | Graph as agent tool, no training |
| [Qin et al., 2026 — Agent Retrieval Bench](https://arxiv.org/abs/2607.24882) (first author added, see DEV-011) | File-level repository context retrieval; semantic and structure-aware retrieval are complementary | Supports RQ1's premise |

## Precedent for the RQ3 shape

LocAgent, CoSIL and KGCompass all show that better localization raises resolved rate. All three vary the *localization method*. None varies the *retriever's training supervision* with the agent held constant. That distinction is the whole of RQ3 and must be stated explicitly whenever RQ3 is defended.
