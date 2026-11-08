# References

> **Derived copy** of the team's Master Project Document (rev 16, dated 2026-10-11).
> The master doc is the source of truth. If this file and the master disagree, the master wins; record the drift as an Open question in `PROJECT_STATE.md` instead of silently editing here.

*Master-doc section(s): References.*

All links verified October 2026. Citations corrected against the earlier proposal draft. Identifiers, titles, first authors and years audited against arXiv and Crossref on 2026-10-23; corrections are marked inline and listed in `docs/DEVIATIONS.md` (DEV-011).

## Core papers

- Zhang, F., Zhang, Y., Li, M., Long, D., Hu, L., Xie, P., Zhang, Z. & Zhuang, F. (2026). *CORE-Bench: A Comprehensive Benchmark for Code Retrieval in the Era of Agentic Coding.* EMNLP 2026 (venue added, see DEV-011). [arXiv:2606.11864](https://arxiv.org/abs/2606.11864) · [dataset](https://huggingface.co/datasets/zhangfw123/CORE-Bench) · [eval code](https://github.com/zhangfw123/CORE-Bench-Eval)
- Gangi Reddy, R. et al. (2025). *SweRank: Software Issue Localization with Code Ranking.* [arXiv:2505.07849](https://arxiv.org/abs/2505.07849) · [code](https://github.com/gangiswag/SweRank) · [SweRankEmbed-Large](https://huggingface.co/Salesforce/SweRankEmbed-Large)
- Chen, Z., Tang, X., Deng, G., Wu, F., Wu, J., Jiang, Z., Prasanna, V., Cohan, A. & Wang, X. (2025). *LocAgent: Graph-Guided LLM Agents for Code Localization.* ACL 2025. [arXiv:2503.09089](https://arxiv.org/abs/2503.09089) · [code](https://github.com/gersteinlab/LocAgent)
- Suresh, T., Gangi Reddy, R., Xu, Y., Nussbaum, Z., Mulyar, A., Duderstadt, B. & Ji, H. (2024). *CoRNStack: High-Quality Contrastive Data for Better Code Retrieval and Reranking.* ICLR 2025 (title of v3; corrected, see DEV-011). [arXiv:2412.01007](https://arxiv.org/abs/2412.01007)
- Jimenez, C. E., Yang, J., Wettig, A., Yao, S., Pei, K., Press, O. & Narasimhan, K. (2024). *SWE-bench: Can Language Models Resolve Real-World GitHub Issues?* ICLR 2024. [arXiv:2310.06770](https://arxiv.org/abs/2310.06770) · [code](https://github.com/SWE-bench/SWE-bench)

## Supervision and training data

- Sun, Z. et al. (2022). *On the Importance of Building High-quality Training Datasets for Neural Code Search.* ICSE 2022. [arXiv:2202.06649](https://arxiv.org/abs/2202.06649)
- Li, H. et al. (2023). *Rethinking Negative Pairs in Code Search.* EMNLP 2023. [arXiv:2310.08069](https://arxiv.org/abs/2310.08069)
- Li, C. et al. (2025). *CodeR / Towards a Generalist Code Embedding Model Based on Massive Data Synthesis.* NeurIPS 2025. [arXiv:2505.12697](https://arxiv.org/abs/2505.12697) (identifier corrected, see DEV-007; 2508.11442 is CoDiEmb)

## Structural and graph approaches

- Yang, B., Ren, J., Jin, S., Liu, Y., Liu, F., Le, B. & Tian, H. (2025) (author order of v3; corrected, see DEV-011). *Enhancing Repository-Level Software Repair via Repository-Aware Knowledge Graphs (KGCompass).* [arXiv:2503.21710](https://arxiv.org/abs/2503.21710)
- Jiang, Z. et al. (2025). *Issue Localization via LLM-Driven Iterative Code Graph Searching* (CoSIL; v3 title, v1 was "CoSIL: Software Issue Localization via LLM-Driven Code Repository Graph Searching"). ASE 2025. [arXiv:2503.22424](https://arxiv.org/abs/2503.22424) (corrected, see DEV-011)
- Qin, B. et al. (2026). *Agent Retrieval Bench: Evaluating Repository Context Retrieval for Coding Agents.* (first author added, see DEV-011) [arXiv:2607.24882](https://arxiv.org/abs/2607.24882)

## Agents and related benchmarks

- Xia, C. S., Deng, Y., Dunn, S. & Zhang, L. (2024). *Agentless: Demystifying LLM-based Software Engineering Agents.* [arXiv:2407.01489](https://arxiv.org/abs/2407.01489) (read in full as v2, 2026-11-08)
- Yang, J. et al. (2024). *SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering.* [arXiv:2405.15793](https://arxiv.org/abs/2405.15793) (NeurIPS 2024; read in full as v3, 2026-11-08)
- Wang, X. et al. (2025). *OpenHands: An Open Platform for AI Software Developers as Generalist Agents.* ICLR 2025. [arXiv:2407.16741](https://arxiv.org/abs/2407.16741) (identifier added, see DEV-011; read in full as v3, 2026-11-08)
- Wang, Z. Z. et al. (2024). *CodeRAG-Bench: Can Retrieval Augment Code Generation?* [arXiv:2406.14497](https://arxiv.org/abs/2406.14497)

## Datasets

- [CodeSearchNet](https://github.com/github/CodeSearchNet) — ~2M comment–code pairs, 6 languages
- [CoIR](https://github.com/CoIR-team/coir) — 10 datasets, 8 retrieval tasks, ~2M documents
- Loc-Bench — 560 examples in LocAgent v2 (bug 242, feature 150, security 29, performance 139); 660 with bug 282, feature 203, security 31, performance 144 is LocAgent v1; the released dataset has 560 rows in V1 and 660 in V0.2 (corrected, see DEV-001 and DEV-005); released with LocAgent

## Correction log

- CoRNStack is **Suresh et al.**, not "Zhang, X. et al." as in the earlier draft
- CORE-Bench releases **evaluation data only**; its 53k-PR SFT set is unreleased
- RQ2 wording is **matched optimization budgets**, not "fixed training budgets"
