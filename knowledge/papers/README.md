# papers/ — reading status

Rule: **a paper counts as a source only after it has been read in full** — the PDF from title to
last appendix page, every results table, every figure that carries a number. Abstracts, HTML
summaries, search snippets and other papers' descriptions are leads. Do not quote exact figures from
a paper that is not marked read in full; label them `unverified lead`.

Each paper gets `knowledge/papers/<slug>.md` whose first lines read
`read: full — N pages incl. appendices, PDF vK, method, date` (or `read: NOT READ (reason)`), then:
what it established; what it did *not* establish; numbers we may quote (with table/page/figure; each
is re-found in the extracted text by `scripts/check_paper_note.py`); method details we need
(hyperparameters, data construction); how it relates to RQ1/RQ2/RQ3; discrepancies (with the master
document, with other papers, internal); and a table of the claims that were checked
(confirmed / contradicted / not found, with page).

| Paper | arXiv / venue | Role in this project | Read depth | Note file |
|---|---|---|---|---|
| CORE-Bench — Zhang et al. 2026 | 2606.11864 | Primary evaluation and framing | full, 27 pp, v3, 2026-10-17 | `core-bench-2606.11864.md` |
| SweRank — Gangi Reddy et al. 2025 | 2505.07849 (ICLR 2026) | Training-data source (SweLoc); K-rank quality signal | full, 20 pp, v2, 2026-10-17 | `swerank-2505.07849.md` |
| LocAgent — Chen et al. 2025 | 2503.09089 (ACL 2025) | Graph schema to adopt; Table 6 ablation (Table 5 in the first pass is the cost table) | full, 18 pp, v2, 2026-10-17 | `locagent-2503.09089.md` |
| CoRNStack — Suresh et al. 2024 | 2412.01007 (ICLR 2025) | Closest prior work on supervision | full, 18 pp, v3, 2026-10-17 | `cornstack-2412.01007.md` |
| SWE-bench — Jimenez et al. 2024 | 2310.06770 (ICLR 2024) | RQ3 outcome measure; mining source | full, 52 pp, v3, 2026-10-17 (no Verified section in this paper) | `swe-bench-2310.06770.md` |
| Sun et al. 2022 | 2202.06649 (ICSE 2022) | Filtering noisy queries (+19.2% MRR, DeepCS only; see note) | full, 12 pp, v1, 2026-10-17 | `sun-2202.06649.md` |
| Rethinking Negative Pairs — Li et al. 2023 | 2310.08069 (EMNLP 2023) | Soft-InfoNCE weighting of negatives | full, 15 pp, v1, 2026-10-17 | `rethinking-negative-pairs-2310.08069.md` |
| CodeR — Li et al. 2025 | 2505.12697 (NeurIPS 2025); the references' 2508.11442 is a different paper (CoDiEmb) | Staged data-domain schedule (annealing) inside a recipe | full, 21 pp, v1, 2026-10-17 | `coder-2505.12697.md`; `codiemb-2508.11442.md` (NOT READ, off topic) |
| KGCompass — Yang et al. 2025 | 2503.21710 | Issue node; multi-hop share (89.7% in v3; 69.7% was v1) | full, 21 pp, v3, 2026-10-17 | `kgcompass-2503.21710.md` |
| CoSIL — Jiang et al. 2025 | 2503.22424 (ASE 2025) | Graph as agent tool, training-free | full, 17 pp, v3, 2026-10-17 | `cosil-2503.22424.md` |
| Agent Retrieval Bench — Qin et al. 2026 | 2607.24882 | File-level context retrieval; complementarity of signals | full, 29 pp, v1, 2026-10-17 | `agent-retrieval-bench-2607.24882.md` |
| Agentless — Xia et al. 2024 | 2407.01489 | Candidate agent scaffold (ADR-007) | ? | — |
| SWE-agent — Yang et al. 2024 | 2405.15793 | Alternative scaffold | ? | — |
| OpenHands — Wang et al. 2025 | 2407.16741 (ICLR 2025) | Alternative scaffold | ? | — |
| CodeRAG-Bench — Wang et al. 2024 | 2406.14497 | Related framing | ? | — |
| SweRank+ — Gangi Reddy et al. 2025 | 2512.20482 | Multilingual extension of the training data; training-data table | full, 11 pp, v1, 2026-10-17 | `swerank-plus-2512.20482.md` |
| LARGER — 2026 | 2605.16352 | Typed repository graph incl. test/docs/config links; expansion on top of lexical search | full, 21 pp, v1, 2026-10-17 | `larger-2605.16352.md` |
| SpIDER — Chaudhari et al. 2026 | 2512.16956 (EMNLP 2026 per the arXiv comment of v3; ICML 2026 here earlier was wrong, see DEV-011) | Graph expansion on top of dense retrieval (closest to the signal design) | full, 38 pp, v3, 2026-10-17 | `spider-2512.16956.md` |
| GREPO — 2026 | 2602.13921 | GNNs over repository graphs; temporal anchors | full, 46 pp, v1, 2026-10-17 (ten image-only pages looked at in part) | `grepo-2602.13921.md` |
| ARISE — 2026 | 2605.03117 | Repository graph with data-flow edges; call-resolution policy | full, 13 pp, v2, 2026-10-17 | `arise-2605.03117.md` |
| PyCG — Salis et al. 2021 | 2103.00587 (ICSE 2021) | Call-graph precision/recall on Python; basis for the edge-recovery definition | full, 12 pp, v1, 2026-10-17 | `pycg-2103.00587.md` |
| Jarvis — Huang et al. 2023 | 2305.05949 (ICSE 2023) | Later Python call-graph generator; comparison point | full, 12 pp, v5, 2026-10-17 | `jarvis-2305.05949.md` |

Literature scan (third reading pass; queries and the full candidate list are in `LANDSCAPE.md`):

| Paper | arXiv / venue | Role in this project | Read depth | Note file |
|---|---|---|---|---|
| DyPyBench — Bouzenia et al. 2024 | 2403.00539 (FSE 2024) | Static against dynamic call graphs for Python (49% of executed edges) | full, 21 pp, v1, 2026-10-17 | `dypybench-2403.00539.md` |
| Total Recall? — Helm et al. 2024 | ISSTA 2024 (author copy, no arXiv) | Dynamic baselines for call-graph precision and recall (Java) | full, 12 pp, v1, 2026-10-17 | `total-recall-helm-2024.md` |
| GraphLocator — Liu et al. 2025 | 2512.22469 | Graph as an LLM agent's tool; causal sub-issue graph | full, 21 pp, v1, 2026-10-17 | `graphlocator-2512.22469.md` |
| SemNav — Wei et al. 2026 | 2609.31176 | Graph with on-demand edge resolution through a language server | full, 9 pp, v1, 2026-10-17 | `semnav-2609.31176.md` |
| SWE-Explore — Zhang et al. 2026 | 2606.07297 | Line-level exploration benchmark; metric against repair | full, 20 pp, v1, 2026-10-17 | `swe-explore-2606.07297.md` |
| Exploration Structure — Fattha et al. 2026 | 2606.11976 | Co-change proposed, not measured; documentation files missed | full, 22 pp, v1, 2026-10-17 | `exploration-structure-2606.11976.md` |
| CodeGrep — Chen et al. 2026 | 2608.05886 | Trained retriever, resolved rate with the agent fixed (+1.2 points, one run) | full, 16 pp, v1, 2026-10-17 | `codegrep-2608.05886.md` |
| RLHN — Thakur et al. 2025 | 2505.16967 (EMNLP 2025 Findings) | False negatives and pruning for text retrievers | full, 20 pp, v2, 2026-10-17 | `rlhn-2505.16967.md` |
| Cost-Effective Exploration — Al Awad and Ivanov 2026 | 2608.29675 | Repository-clustered statistics on a Verified-derived arm | full, 11 pp, v1, 2026-10-17 | `cost-effective-exploration-2608.29675.md` |
| CoREB; LogicLoc; LLM type and call-graph study; RepoNavigator; NoCFG | 2605.04615; 2604.16021; 2410.00603; 2512.20957; 2105.03099 | Scan candidates | abstract only | listed in `LANDSCAPE.md` |

Full citations: `docs/11_references.md` (identifiers, titles, first authors and years audited against arXiv and Crossref on 2026-10-23; corrections and the list of mismatches in `docs/DEVIATIONS.md`, DEV-011).
