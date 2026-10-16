# papers/ — reading status

Master doc rule: **do not bluff on exact figures from papers not read in full.** This table tracks
which papers have actually been read, so quoted numbers can be trusted. "Read in full?" is for the
engineer/team to fill in; it is `?` because nothing here can know.

When a paper is read, add `knowledge/papers/<slug>.md` with: what it established; what it did *not*;
numbers we may quote (with table/page); how it relates to RQ1/RQ2/RQ3.

| Paper | arXiv / venue | Role in this project | Read in full? | Note file |
|---|---|---|---|---|
| CORE-Bench — Zhang et al. 2026 | 2606.11864 | Primary evaluation and framing | ? | — |
| SweRank — Gangi Reddy et al. 2025 | 2505.07849 (ICLR 2026) | Training-data source (SweLoc); K-rank quality signal | ? | — |
| LocAgent — Chen et al. 2025 | 2503.09089 (ACL 2025) | Graph schema to adopt; Table 5 ablation | ? | — |
| CoRNStack — Suresh et al. 2024 | 2412.01007 (ICLR 2025) | Closest prior work on supervision | ? | — |
| SWE-bench — Jimenez et al. 2024 | 2310.06770 (ICLR 2024) | RQ3 outcome measure; mining source | ? | — |
| Sun et al. 2022 | 2202.06649 (ICSE 2022) | Filtering noisy queries (+19.2% MRR) | ? | — |
| Rethinking Negative Pairs — Li et al. 2023 | 2310.08069 (EMNLP 2023) | Soft-InfoNCE weighting | ? | — |
| CodeR — Li et al. 2025 | 2508.11442 (NeurIPS 2025) | Curriculum (annealing) inside a recipe | ? | — |
| KGCompass — Yang et al. 2025 | 2503.21710 | Issue node; 69.7% multi-hop | ? | — |
| CoSIL — Jiang et al. 2025 | 2503.22424 | Graph as agent tool, training-free | ? | — |
| Agent Retrieval Bench 2026 | 2607.24882 | File-level context retrieval; complementarity of signals | ? | — |
| Agentless — Xia et al. 2024 | 2407.01489 | Candidate agent scaffold (ADR-007) | ? | — |
| SWE-agent — Yang et al. 2024 | 2405.15793 | Alternative scaffold | ? | — |
| OpenHands — Wang et al. 2025 | ICLR 2025 | Alternative scaffold | ? | — |
| CodeRAG-Bench — Wang et al. 2024 | 2406.14497 | Related framing | ? | — |

Full citations: `docs/11_references.md`.
