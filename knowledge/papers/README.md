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
| LocAgent — Chen et al. 2025 | 2503.09089 (ACL 2025) | Graph schema to adopt; Table 5 ablation | ? | — |
| CoRNStack — Suresh et al. 2024 | 2412.01007 (ICLR 2025) | Closest prior work on supervision | full, 18 pp, v3, 2026-10-17 | `cornstack-2412.01007.md` |
| SWE-bench — Jimenez et al. 2024 | 2310.06770 (ICLR 2024) | RQ3 outcome measure; mining source | full, 52 pp, v3, 2026-10-17 (no Verified section in this paper) | `swe-bench-2310.06770.md` |
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
| SweRank+ — Gangi Reddy et al. 2025 | 2512.20482 | Multilingual extension of the training data; training-data table | full, 11 pp, v1, 2026-10-17 | `swerank-plus-2512.20482.md` |
| LARGER — 2026 | 2605.16352 | Typed repository graph incl. test/docs/config links; expansion on top of lexical search | ? | — |
| SpIDER — 2026 | 2512.16956 (ICML 2026) | Graph expansion on top of dense retrieval (closest to the signal design) | ? | — |
| GREPO — 2026 | 2602.13921 | GNNs over repository graphs; temporal anchors | ? | — |
| ARISE — 2026 | 2605.03117 | Repository graph with data-flow edges; call-resolution policy | ? | — |
| PyCG — Salis et al. 2021 | ICSE 2021 | Call-graph precision/recall on Python; basis for the edge-recovery definition | ? | — |
| Jarvis — 2023 | ICSE 2023 | Later Python call-graph generator; comparison point | ? | — |

Full citations: `docs/11_references.md`.
