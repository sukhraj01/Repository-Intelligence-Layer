# References

> **Derived copy** of the team's Master Project Document (rev 16, dated 2026-10-11).
> The master doc is the source of truth. If this file and the master disagree, the master wins; record the drift as an Open question in `PROJECT_STATE.md` instead of silently editing here.

*Master-doc section(s): References.*

All links verified October 2026. Citations corrected against the earlier proposal draft.

## Core papers

- Zhang, F., Zhang, Y., Li, M., Long, D., Hu, L., Xie, P., Zhang, Z. & Zhuang, F. (2026). *CORE-Bench: A Comprehensive Benchmark for Code Retrieval in the Era of Agentic Coding.* [arXiv:2606.11864](https://arxiv.org/abs/2606.11864) · [dataset](https://huggingface.co/datasets/zhangfw123/CORE-Bench) · [eval code](https://github.com/zhangfw123/CORE-Bench-Eval)
- Gangi Reddy, R. et al. (2025). *SweRank: Software Issue Localization with Code Ranking.* [arXiv:2505.07849](https://arxiv.org/abs/2505.07849) · [code](https://github.com/gangiswag/SweRank) · [SweRankEmbed-Large](https://huggingface.co/Salesforce/SweRankEmbed-Large)
- Chen, Z., Tang, X., Deng, G., Wu, F., Wu, J., Jiang, Z., Prasanna, V., Cohan, A. & Wang, X. (2025). *LocAgent: Graph-Guided LLM Agents for Code Localization.* ACL 2025. [arXiv:2503.09089](https://arxiv.org/abs/2503.09089) · [code](https://github.com/gersteinlab/LocAgent)
- Suresh, T., Gangi Reddy, R., Xu, Y., Nussbaum, Z., Mulyar, A., Duderstadt, B. & Ji, H. (2024). *CoRNStack: High-Quality Contrastive Data for Better Code Ranking.* ICLR 2025. [arXiv:2412.01007](https://arxiv.org/abs/2412.01007)
- Jimenez, C. E., Yang, J., Wettig, A., Yao, S., Pei, K., Press, O. & Narasimhan, K. (2024). *SWE-bench: Can Language Models Resolve Real-World GitHub Issues?* ICLR 2024. [arXiv:2310.06770](https://arxiv.org/abs/2310.06770) · [code](https://github.com/SWE-bench/SWE-bench)

## Supervision and training data

- Sun, Z. et al. (2022). *On the Importance of Building High-quality Training Datasets for Neural Code Search.* ICSE 2022. [arXiv:2202.06649](https://arxiv.org/abs/2202.06649)
- Li, H. et al. (2023). *Rethinking Negative Pairs in Code Search.* EMNLP 2023. [arXiv:2310.08069](https://arxiv.org/abs/2310.08069)
- Li, C. et al. (2025). *CodeR / Towards a Generalist Code Embedding Model Based on Massive Data Synthesis.* NeurIPS 2025. [arXiv:2508.11442](https://arxiv.org/abs/2508.11442)

## Structural and graph approaches

- Yang, B., Tian, H., Ren, J., Jin, S., Liu, Y., Liu, F. & Le, B. (2025). *Enhancing Repository-Level Software Repair via Repository-Aware Knowledge Graphs (KGCompass).* [arXiv:2503.21710](https://arxiv.org/abs/2503.21710)
- *CoSIL: Software Issue Localization via LLM-Driven Code Repository Graph Searching* (2025). [arXiv:2503.22424](https://arxiv.org/abs/2503.22424)
- *Agent Retrieval Bench: Evaluating Repository Context Retrieval for Coding Agents* (2026). [arXiv:2607.24882](https://arxiv.org/abs/2607.24882)

## Agents and related benchmarks

- Xia, C. S., Deng, Y., Dunn, S. & Zhang, L. (2024). *Agentless: Demystifying LLM-based Software Engineering Agents.* [arXiv:2407.01489](https://arxiv.org/abs/2407.01489)
- Yang, J. et al. (2024). *SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering.* [arXiv:2405.15793](https://arxiv.org/abs/2405.15793)
- Wang, X. et al. (2025). *OpenHands: An Open Platform for AI Software Developers as Generalist Agents.* ICLR 2025.
- Wang, Z. Z. et al. (2024). *CodeRAG-Bench: Can Retrieval Augment Code Generation?* [arXiv:2406.14497](https://arxiv.org/abs/2406.14497)

## Datasets

- [CodeSearchNet](https://github.com/github/CodeSearchNet) — ~2M comment–code pairs, 6 languages
- [CoIR](https://github.com/CoIR-team/coir) — 10 datasets, 8 retrieval tasks, ~2M documents
- Loc-Bench — 660 examples; bug 282, feature 203, security 31, performance 144; released with LocAgent

## Correction log

- CoRNStack is **Suresh et al.**, not "Zhang, X. et al." as in the earlier draft
- CORE-Bench releases **evaluation data only**; its 53k-PR SFT set is unreleased
- RQ2 wording is **matched optimization budgets**, not "fixed training budgets"
