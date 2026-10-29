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
| CoREB; LLM type and call-graph study | 2605.04615; 2410.00603 | Scan candidates | dropped with a reason (2026-10-23) | listed in `LANDSCAPE.md` |

Fourth reading pass (2026-10-23; refreshed scan with queries and dates in `LANDSCAPE.md`):

| Paper | arXiv / venue | Role in this project | Read depth | Note file |
|---|---|---|---|---|
| Qwen3 Embedding — Zhang et al. 2025 | 2506.05176 | ADR-006 candidate encoder (0.6B) | full, 14 pp, v3, 2026-10-23 | `qwen3-embedding-2506.05176.md` |
| NV-Retriever — Moreira et al. 2024 | 2407.15831 | Negative selection with false-negative removal (negative policy) | full, 11 pp, v2, 2026-10-23 | `nv-retriever-2407.15831.md` |
| MAP4CS — Chen et al. 2026 | 2610.11727 | Filtering training pairs of a code retriever (FILTER-like, not budget-matched) | full, 24 pp, v1, 2026-10-23 | `map4cs-2610.11727.md` |
| What Tracks Hard-Negative Transfer? — Sinha et al. 2026 | 2603.20990 | Negative sources; frozen-encoder statistics against false-negative-shaped controls | full, 15 pp, v5, 2026-10-23 | `hard-negative-transfer-2603.20990.md` |
| LogicLoc — Xu et al. 2026 | 2604.16021 | Program-fact graph as an agent tool; keyword shortcut | full, 22 pp, v2, 2026-10-23 | `logicloc-2604.16021.md` |
| RepoNavigator — Zhang et al. 2026 | 2512.20957 (ICML 2026 per the PDF) | Symbol resolution as an agent's only tool | full, 27 pp, v6, 2026-10-23 | `reponavigator-2512.20957.md` |
| NoCFG — Abadi et al. 2021 | 2105.03099 | Python call-graph precision and recall against test-driven dynamic graphs | full, 11 pp, v1, 2026-10-23 | `nocfg-2105.03099.md` |

Fifth reading pass (2026-10-29; supervision quality: noisy or weighted supervision, false negatives, teacher independence, learning curves; queries and dates in `LANDSCAPE.md`):

| Paper | arXiv / venue | Role in this project | Read depth | Note file |
|---|---|---|---|---|
| ARHN — Choi et al. 2026 | 2604.11092 | Rank-relative-to-the-positive edit of mined negatives | full, 10 pp, v1, 2026-10-29 | `arhn-2604.11092.md` |
| GloFND — Balmaseda et al. 2025 | 2502.20612 (ICML 2025) | Self-judged false-negative detector needs a warm-up (images) | full, 18 pp, v2, 2026-10-29 | `glofnd-2502.20612.md` |
| D-SCL — Long et al. 2023 | 2311.16481 | Mislabelled positives are easy positives (images) | full, 16 pp, v1, 2026-10-29 | `debiased-scl-2311.16481.md` |
| MM-IssueLoc — Zhan et al. 2026 | 2607.15205 | Issue retriever, file-then-function schedule, same-repository negatives | full, 22 pp, v1, 2026-10-29 | `mm-issueloc-2607.15205.md` |
| Uncertainty-aware code search — Liu et al. | AAAI 2025 (no arXiv version) | Not a confidence weighting; hard-negative selection | full, 9 pp, proceedings copy, 2026-10-29 | `uncertainty-aware-code-search-aaai2025.md` |
| Noisy Pair Corrector — Zhang et al. 2023 | 2311.03798 (Findings of EMNLP 2023) | Loss-based detection of mismatched pairs, warm-up, code and text | full, 13 pp, v1, 2026-10-29 | `npc-2311.03798.md` |
| ADAM — Tao et al. | 2212.10192 | Teacher-confidence shrinking subset | full, 13 pp, v2, 2026-10-29 | `adam-2212.10192.md` |
| CL-DRD — Zeng et al. 2022 | 2204.13679 (SIGIR 2022) | Supervision-granularity curriculum with a reversed-order control | full, 5 pp, v1, 2026-10-29 | `cl-drd-2204.13679.md` |
| Curriculum learning strategies for IR — Penha and Hauff | 1912.08555 (ECIR 2020) | Difficulty by model confidence, pacing functions, five seeds | full, 15 pp, v1, 2026-10-29 | `curriculum-ir-1912.08555.md` |
| Self-distillation with adaptive margins — Gienapp et al. | 2407.21515 (ICTIR 2025) | Encoder's own similarity as target; learning curve in triplets | full, 11 pp, v2, 2026-10-29 | `self-distillation-margins-2407.21515.md` |
| Promptagator — Dai et al. | 2209.11755 (ICLR 2023) | Round-trip filter judged by a retriever trained on the same data | full, 21 pp, v1, 2026-10-29 | `promptagator-2209.11755.md` |
| When fine-tuning fails — Pande et al. 2025 | 2506.18535 | Fine-tuning an already strong small encoder (weak evidence) | full, 7 pp, v1, 2026-10-29 | `finetuning-fails-msmarco-2506.18535.md` |

Full citations: `docs/11_references.md` (identifiers, titles, first authors and years audited against arXiv and Crossref on 2026-10-23; corrections and the list of mismatches in `docs/DEVIATIONS.md`, DEV-011).
