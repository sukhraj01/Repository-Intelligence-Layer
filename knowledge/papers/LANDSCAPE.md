# Literature landscape — scan of 2025-2026 work around the project's questions

Scan dates: 2026-10-17 (first scan) and 2026-10-23 (refresh, section "Refreshed scan" below). Scope of the first scan: five topics (graph-structured retrieval for issue localization; training-data quality for code retrievers; follow-ups to CORE-Bench and SweRank; evolutionary coupling and co-change for localization; static against dynamic call-graph accuracy for Python), plus the call-graph accuracy definitions asked for in the reading plan.

Rule applied (`knowledge/papers/README.md`): every candidate below is either **read in full** (a note exists, checked by `scripts/check_paper_note.py`) or listed **abstract only** (the PDF was fetched and its abstract page read; no number is quoted) or **lead only** (named by a search result or by a paper read in full; not fetched). Search-engine summaries are leads, never sources. Absence from this scan is not evidence of absence in the literature: the search tool returns a handful of results per query and its summaries were not trusted without the PDF.

## Search log

All queries were run on 2026-10-17 with a general web search tool (mode in brackets). The results named below were then fetched as versioned PDFs from arxiv.org (highest version that resolves) or, for one paper, from the authors' project site.

| # | Query | Mode | Used for |
|---|---|---|---|
| 1 | Towards A Generalist Code Embedding Model Based On Massive Data Synthesis CodeR arXiv | standard | found the CodeR identifier (2505.12697), which differs from the one in the project references |
| 2 | graph-structured retrieval issue localization repository code graph 2026 arXiv | extended | graph retrieval: LARGER, SpIDER (already read), GraphLocator, SemNav, Echo |
| 3 | training data quality code retrieval filtering reweighting curriculum hard negative mining issue localization embedding 2026 | extended | training-data quality: CoRNStack (read), general text embedding work |
| 4 | CORE-Bench code retrieval agentic coding follow-up SweRank follow-up localization reranker 2026 | extended | follow-ups: Agent Retrieval Bench, CoREB |
| 5 | co-change evolutionary coupling history signal issue localization LLM agent repository 2025 2026 | extended | co-change: Exploration Structure |
| 6 | static versus dynamic call graph accuracy Python empirical study precision recall PyCG Jarvis comparison | extended | Total Recall, NoCFG, DyPyBench pointers |
| 7 | SWE-bench issue localization embedding model training data synthetic hard negatives noisy labels 2026 arXiv code retriever fine-tuning | extended | SweRank family, Neurosymbolic localization |
| 8 | Python call graph construction benchmark dynamic ground truth unsoundness empirical 2024 2025 2026 type inference | standard | DyPyBench, LLM type and call-graph study |
| 9 | false negatives label noise code search contrastive learning positive pairs filtering 2025 2026 | standard | false-negative work (text and image) |
| 10 | issue localization retriever trained with graph-based hard negatives or structural negatives repository code embedding | standard | none found beyond SweRank, CoRNStack, SpIDER |
| 11 | DyPyBench dynamic call graphs Python executable benchmark compare static call graphs PyCG recall | standard | DyPyBench |
| 12 | code embedding model training data selection noisy synthetic queries verification consistency filter ablation CoIR SWE-bench localization 2026 | extended | CodeR, text-embedding data-selection work |
| 13 | Beyond Retrieval: A Multitask Benchmark and Model for Code Search COREB arXiv 2605.04615 | standard | CoREB (name clash with CORE-Bench) |
| 14 | "CORE-Bench" code retrieval agentic coding evaluated cited benchmark embedding Level-2 Level-3 repository retrieval new paper | extended | papers citing CORE-Bench |
| 15 | SWE-Explore repository exploration line budget successful trajectories ground truth arXiv | standard | SWE-Explore, Cost-Effective Exploration |
| 16 | logical coupling co-change files mined from commit history improve retrieval-based bug localization 2025 learning-to-rank | standard | older co-change work (2013-2024) |
| 17 | hard negative mining code retrieval 2025 false negative filtering contrastive code embedding model arXiv | standard | none new beyond SweRank, CoRNStack |
| 18 | LLM-based relabeling or reweighting of noisy training queries code search dataset quality 2025 | standard | RLHN (text retrieval) |
| 19 | retriever training for issue localization SWE-bench reinforcement learning code search agent CodeScout RepoNavigator language server | standard | CodeGrep, RepoNavigator |

Dead ends: queries 3, 7, 10, 12 and 17 returned no 2025-2026 paper that trains a code retriever with a filtering, weighting or curriculum intervention and compares against an unmodified arm at matched cost; query 5 returned no measurement of co-change for localization with language-model agents; query 8 returned nothing newer than 2024 on Python call-graph benchmarks apart from a type-and-call-graph study with language models. These are results of this scan only.

## Candidates

### Read in full in the third reading pass (notes in this directory)

| Paper | Note | Topic |
|---|---|---|
| PyCG, Salis et al., ICSE 2021 (2103.00587) | `pycg-2103.00587.md` | call-graph precision and recall for Python |
| Jarvis, Huang et al., ICSE 2023 (2305.05949) | `jarvis-2305.05949.md` | same |
| Sun et al., ICSE 2022 (2202.06649) | `sun-2202.06649.md` | query filtering for code search |
| Rethinking Negative Pairs, Li et al., EMNLP 2023 (2310.08069) | `rethinking-negative-pairs-2310.08069.md` | weighting of negatives |
| CodeR, Li et al. (2505.12697; the references' 2508.11442 is a different paper) | `coder-2505.12697.md` | synthetic data and staged curriculum |
| Agent Retrieval Bench (2607.24882) | `agent-retrieval-bench-2607.24882.md` | follow-up benchmark; complementarity |
| DyPyBench, Bouzenia et al., FSE 2024 (2403.00539) | `dypybench-2403.00539.md` | static against dynamic call graphs, Python |
| Total Recall?, Helm et al., ISSTA 2024 (no arXiv version) | `total-recall-helm-2024.md` | dynamic baselines for call-graph precision and recall (Java) |
| GraphLocator, Liu et al. (2512.22469) | `graphlocator-2512.22469.md` | graph-structured localization |
| SemNav, Wei et al. (2609.31176) | `semnav-2609.31176.md` | graph with on-demand edge resolution |
| SWE-Explore, Zhang et al. (2606.07297) | `swe-explore-2606.07297.md` | follow-up benchmark; metric against repair |
| Exploration Structure, Fattha et al. (2606.11976) | `exploration-structure-2606.11976.md` | co-change (as a proposal) |
| CodeGrep, Chen et al. (2608.05886) | `codegrep-2608.05886.md` | trained retriever, resolved rate with the agent fixed |
| RLHN, Thakur et al. (2505.16967) | `rlhn-2505.16967.md` | false negatives and pruning, text retrieval |
| Cost-Effective Exploration, Al Awad and Ivanov (2608.29675) | `cost-effective-exploration-2608.29675.md` | follow-up evaluation; repository-clustered statistics |

Read in full in the earlier reading passes and used below: CORE-Bench, SweRank, SweRank+, CoRNStack, SWE-bench, LocAgent, KGCompass, CoSIL, LARGER, SpIDER, GREPO, ARISE (see `README.md` for pages and versions).

### Formerly "abstract only": disposition after the reading pass of 2026-10-23

Every entry the first scan left at abstract depth that bears on RQ2 or on the graph was read in full or dropped with a reason.

| Paper | Identifier | Disposition |
|---|---|---|
| LogicLoc and KA-LogicQuery, "Neurosymbolic Repo-level Code Localization" | 2604.16021 | read in full: `logicloc-2604.16021.md` |
| RepoNavigator, "One Tool Is Enough" | 2512.20957 (v6) | read in full: `reponavigator-2512.20957.md` |
| NoCFG | 2105.03099 | read in full: `nocfg-2105.03099.md` |
| CoDiEmb (the paper the project references' CodeR identifier pointed to) | 2508.11442 | dropped: a general embedder trained jointly for retrieval and sentence similarity; no filtering, weighting, curriculum, negative-policy or graph content (`codiemb-2508.11442.md`, NOT READ) |
| CoREB, "Beyond Retrieval: A Multitask Benchmark and Model for Code Search" | 2605.04615 | dropped: a code-search and reranking benchmark built from rewritten competitive-programming problems plus a fine-tuned reranker; no repository structure and no filter, weight, curriculum or negative-policy comparison for a retriever (abstract, Sec. 1 and a search of the full extracted text for these terms) |
| "An Empirical Study of Large Language Models for Type and Call Graph Analysis in Python and JavaScript" | 2410.00603 | dropped: evaluates language models and tools on one-feature micro-benchmarks, not on repositories; an LLM-based edge resolver is not among the options the project measures (own AST resolver, Jedi, dynamic oracle), and the PyCG micro-suite figures it builds on are already in `pycg-2103.00587.md`. Revisit if an LLM resolver is proposed |

### Lead only (named by a search result or by a paper read in full; not fetched)

Echo (2603.07326); Arctic-Embed 2.0 (2412.04506); KaLM-Embedding-V2 (2506.20923); NV-Retriever (2407.15831; now read in full, `nv-retriever-2407.15831.md`); "Effective Hard Negative Mining for Contrastive Learning-Based Code Search" (ACM, doi 10.1145/3695994; publisher PDF blocked from this machine on 2026-10-23 and no arXiv version found, not yet read); CodeXEmbed (2411.12644); Granite Embedding R2 (2508.21085); SWE-Adept (2603.01327); Nemotron-Cascade (2512.13607); GloFND (2502.20612); a debiased supervised contrastive objective (2311.16481); MULocBench / PLocBench (2509.25242; one benchmark under two names in the papers that cite it); ContextBench (2602.05892); SWE-ContextBench (2602.08316); Loc2Repair, SWE-Router (cited in `cost-effective-exploration-2608.29675.md`); tool-integrated reinforcement learning for repository search (2508.03012); two different papers both called "CodeScout" (2603.17829 and 2603.05744, cited by the SemNav and SWE-Explore papers); classic co-change work named in `exploration-structure-2606.11976.md` and in search results (Gall et al. 1998; Zimmermann et al. 2005; Wang and Lo 2014 and a 2013 co-change bug-localization study), none read.

## Refreshed scan, 2026-10-23

Scope (three topics): weighted or curriculum contrastive training of code retrievers; false negatives in repository-level training pairs; graph- or structure-aware reranking of dense results. Target window: work since 2026-10-17, with anything earlier that the first scan missed recorded as well.

Method. (a) The arXiv listing search (`arxiv.org/search`, abstract field, newest announcement first, 50 results per query), all queries run on 2026-10-23, recording the newest submission date returned and every result submitted on or after 2026-10-01. (b) A general web search tool, also on 2026-10-23 (its summaries are leads only). (c) The arXiv API (`export.arxiv.org`) was tried first and returned rate-limit errors after two queries; those two queries are logged and the rest were moved to the listing search.

| # | Query | Tool | Newest submission returned | Relevant results (leads unless read) |
|---|---|---|---|---|
| R1 | abs:"code retrieval" | arXiv API | 2026-10-02 | none since 2026-10-17 |
| R2 | abs:"issue localization" | arXiv API | 2026-09-25 | none since 2026-10-17 |
| R3 | "issue localization" | listing | 2026-10-07 | none relevant |
| R4 | "code localization" | listing | 2026-10-19 | none relevant |
| R5 | "code search" contrastive | listing | 2026-09-05 | none since 2026-10-01 |
| R6 | "code retrieval" negatives | listing | 2026-08-25 | none since 2026-10-01 |
| R7 | "false negatives" retrieval | listing | 2026-10-21 | 2603.20990 (revised 2026-10-14; read in full) |
| R8 | "hard negatives" embedding | listing | 2026-10-22 | none on code; 2610.24478 (legal reranker) and 2610.15035 (multimodal) off scope |
| R9 | curriculum contrastive retrieval | listing | 2026-09-26 | none since 2026-10-01 |
| R10 | weighted contrastive retrieval | listing | 2026-10-22 | none on code |
| R11 | "repository-level" retrieval graph | listing | 2026-09-25 | none since 2026-10-01 |
| R12 | rerank graph code | listing | 2026-10-22 | none on code |
| R13 | "code embedding" | listing | 2026-10-21 | 2610.30016 (Code Comprehensor, 2026-10-21) |
| R14 | "embedding model" training data quality | listing | 2026-10-09 | none on code |
| R15 | SWE-bench localization retriever | listing | 2026-10-13 | 2610.05099, 2610.05830, 2609.06780 |
| R16 | SweRank | listing | 2026-10-14 | 2610.21073 (2026-10-14) |
| R17 | "CORE-Bench" | listing | 2026-08-24 | none since the first scan |
| R18 | "code retriever" | listing | 2026-10-12 | none relevant since 2026-10-01 |
| R19 | issue function-level retrieval embedding | listing | 2026-08-24 | none |
| R20 | structure-aware code retrieval | listing | 2026-10-22 | 2610.11727 (MAP4CS, 2026-10-08; read in full) |
| R21 | call graph retrieval augmented | listing | 2026-10-15 | none on code |
| R22 | "noisy labels" code search | listing | 2024-06-09 | none |
| R23 | issue localization graph | listing | 2026-10-21 | none relevant |
| W1 | curriculum or weighted contrastive training code retriever issue localization 2026 arXiv | web (extended) | — | MM-IssueLoc (2607.15205); otherwise known papers |
| W2 | false negatives repository-level code retrieval training pairs same repository negatives contrastive 2026 | web (extended) | — | CoRet (ACL 2025 short); ARHN (2604.11092) |
| W3 | graph-aware reranking of dense code retrieval results call graph structure-aware reranker repository 2026 arXiv | web (extended) | — | GRACE (2509.05980, code completion) |
| W4 | SweRank follow-up 2026 retriever training data filtering K-rank threshold ablation issue localization embedding | web (extended) | — | none new |
| W5 | dense retrieval graph expansion rerank function-level localization call graph neighbors fused with embedding scores October 2026 | web (standard) | — | none new beyond SpIDER |
| W6 | "Effective Hard Negative Mining for Contrastive Learning-Based Code Search" arXiv | web (standard) | — | journal version only; an AAAI 2025 code-search paper on uncertainty-aware hard negatives |

Result of the refresh. No paper submitted between 2026-10-17 and 2026-10-23 was found that trains a code retriever with weighting or a curriculum, measures false negatives in repository-level pairs, or reranks dense results with a repository graph. Two items submitted after 2026-10-17 are on neighbouring topics (Code Comprehensor; and, outside code, a per-policy relevance filter, 2610.29326, dropped as off topic). Two relevant items the first scan missed were found and read in full: MAP4CS (filtering training pairs of a code retriever) and a study of hard-negative sources (2603.20990). The listing search returns at most 50 results per query sorted by date, so absence here is absence in that window for these queries only.

### Read in full in the fourth reading pass (2026-10-23)

| Paper | Note | Topic |
|---|---|---|
| Qwen3 Embedding technical report (2506.05176) | `qwen3-embedding-2506.05176.md` | ADR-006 candidate encoder |
| NV-Retriever (2407.15831) | `nv-retriever-2407.15831.md` | negative selection with false-negative removal |
| MAP4CS (2610.11727) | `map4cs-2610.11727.md` | filtering training pairs of a code retriever |
| What Tracks Hard-Negative Transfer? (2603.20990) | `hard-negative-transfer-2603.20990.md` | negative sources; frozen-encoder statistics and false negatives |
| LogicLoc (2604.16021) | `logicloc-2604.16021.md` | program-fact graph as an agent tool; keyword shortcut |
| RepoNavigator (2512.20957) | `reponavigator-2512.20957.md` | symbol resolution as an agent's only tool |
| NoCFG (2105.03099) | `nocfg-2105.03099.md` | Python call-graph precision and recall against test-driven dynamic graphs |

### Not yet read (bearing on RQ2 or the graph; leads only, no number quoted)

RQ2: GloFND (2502.20612, global false-negative detection); a debiased supervised contrastive objective (2311.16481); "Effective Hard Negative Mining for Contrastive Learning-Based Code Search" (doi 10.1145/3695994, PDF not obtainable from this machine); ARHN, relabelling hard negatives with open models (2604.11092); uncertainty-aware contrastive learning with hard negative sampling for code search (AAAI 2025); MM-IssueLoc (2607.15205, same-repository hard negatives and multi-positive rows); CoRet (ACL 2025 short, in-repository negatives). Graph: GRACE (2509.05980, graph-aware reranking for code completion); Code Comprehensor (2610.30016). RQ3: Skip the Compressor (2610.21073, whole-file selection against retrievers at a fixed token budget); Loc2Repair (2606.30963); small localization agents with semantic search (2610.05099); leaderboard contamination auditing (2610.05830); agentic exploits in SWE benchmarks (2609.06780).

## What the scan found, by topic (neutral; evidence from notes)

1. **Graph-structured retrieval for issue localization.** Seven of the papers in hand use the graph or a resolver as a tool an LLM agent calls (LocAgent, CoSIL, ARISE, GraphLocator, SemNav, RepoNavigator through a language server, and LogicLoc through Datalog queries over AST facts), three use it as a signal or to expand a retrieval list (KGCompass, SpIDER, LARGER), and one learns over it (GREPO). Edge-type ablations exist only in SpIDER and GREPO (R2 notes); GraphLocator ablates tools, not edges; SemNav ablates online edge resolution (-7.00 points of File Hit@10, one run, 4B model). Resolution coverage as a rate is reported by none of them. RepoNavigator supplies every method with an entry function (normally a test) per issue, which changes the task; LogicLoc reports that over 50% of SWE-bench Lite issues name the gold location (method not given) and is below a trained retrieve-and-rerank system on that benchmark. The 2026-10-23 refresh found no graph-aware reranking of dense results for issue localization beyond SpIDER.
2. **Training-data quality for code retrievers.** Query filtering (Sun), negative weighting (Li), consistency filtering with hard negatives (CoRNStack, SweRank), a staged data-domain schedule with a difficulty filter (CodeR), trajectory-mined and judge-filtered positives (CodeGrep). Outside code, relabelling and pruning (RLHN), positive-aware negative selection (NV-Retriever) and negative-source comparisons (2603.20990). In code, MAP4CS (2026) filters training pairs and compares against random and full sets, but with update counts differing twentyfold and one seed. No paper found that places filter, weight and curriculum interventions next to an unmodified arm at matched optimisation budget for a code retriever (also none in the 2026-10-23 refresh).
3. **CORE-Bench and SweRank follow-ups.** Agent Retrieval Bench cites CORE-Bench and reports no use of its labels; SWE-Explore builds line-level labels on the same Verified, Pro and Multilingual instances; SweRank+ (R1) extends the training data. No paper found that reproduces CORE-Bench's supervised recipe or tests a different supervision on it.
4. **Co-change and evolutionary coupling.** One 2026 paper proposes mining co-change for routing and measures nothing; the finding it does report (documentation files are missed 73% of the time) is the sort of dependency co-change would address. Older bug-localization work using co-change history is named but unread.
5. **Static against dynamic call graphs for Python.** One study compares PyCG with executed edges at scale (49% of dynamic edges present, built-in callees included); NoCFG reports about 89% precision and recall against test-driven dynamic graphs on five small projects; PyCG and Jarvis report their own numbers on hand-built or test-plus-hand ground truths; one Java study shows test-based dynamic baselines can mis-state precision and recall in either direction.

## Call-graph precision and recall: definitions side by side (for ADR-012; no choice made)

| Source | Ground truth | Edge scope | Precision | Recall | Reported |
|---|---|---|---|---|---|
| PyCG (`pycg-2103.00587.md`) | hand-built by one author, five packages under 3.5k lines; micro-suite of 112 one-path programs | external callees and module-level callers included | valid generated calls over generated calls | valid generated calls over all calls | 99.2% / 69.9% (macro); 111 of 112 complete, 103 of 112 sound (micro) |
| Jarvis (`jarvis-2305.05949.md`) | test traces plus three authors' manual additions, six applications, 20,085 relations | application functions and library callees reachable from entry functions | edge-set ratio; in entry-function mode counts chains | edge-set ratio | 0.99 / 0.82 (application-only exhaustive); 0.35 / 0.60 (application-centered whole program) |
| DyPyBench (`dypybench-2403.00539.md`) | executed edges from each project's test suite | all callees including built-in methods | not reported | share of dynamic edges in the static graph | 49% of edges, 95% of callers, 48.5% of callees (39 projects) |
| Total Recall (`total-recall-helm-2024.md`) | executed edges from fixed entry points, with a corpus extended by hand and fuzzing | whole graph or core package only | lower bound against the dynamic sample | bounded by sample coverage | Java only; test-based baselines can be arbitrarily wrong |
| NoCFG (`nocfg-2105.03099.md`) | dynamic graph from each project's tests (`pycallgraph`), both graphs restricted to test reachability; five projects of 573 to 12,336 lines | not stated precisely | matched over static edges (lower bound) | matched over dynamic edges | 89.66% / 89.01% (weighted); per project 83.33% to 95.89% / 81.40% to 100% |

## Claims checked: statements in the project documents about these papers

| Statement (where) | Verdict | Evidence |
|---|---|---|
| Sun et al.: "+19.2% MRR, +21.3% Answer@1" (`docs/03`, `docs/02`) | confirmed, with qualifiers | DeepCS only, Java only, relative, mean over three small evaluation sets, five-run medians; filtered set has half the data and half the training time (`sun-2202.06649.md`, Table 2 p.7) |
| Sun et al.: "Over a third of queries noisy" (`docs/03`) | confirmed, marginally overstated | 33.1% carry a noise feature (Figure 1 p.2); manual rating scores 79.0% of the set as non-query-like (Table 4 p.9) |
| Sun et al.: "No comparison against weighting or curriculum at matched budget" | confirmed | no such arm exists; the filtered runs are also not matched in optimiser steps |
| Li et al. 2023: "False negatives are pervasive; Soft-InfoNCE soft weighting" | partly confirmed | the method is as described; pervasiveness is cited from earlier work, not measured (`rethinking-negative-pairs-2310.08069.md`) |
| CodeR: arXiv 2508.11442 (`docs/11`, `docs/03`) | contradicted | 2508.11442 is CoDiEmb; CodeR is 2505.12697 |
| CodeR: "Synthetic heterogeneous data + curriculum (annealing) across 16 tasks"; "curriculum inside a recipe" | confirmed | three-stage data-domain order; 16 datasets; single-run ablation on a reduced configuration (`coder-2505.12697.md`) |
| Agent Retrieval Bench: "semantic and structure-aware retrieval are complementary" (`docs/03`) | confirmed at system level | different winners by task; two-system fusion beats both; the structural system is a path-and-symbol repository map (`agent-retrieval-bench-2607.24882.md`) |
| Agent Retrieval Bench: "Supports RQ1's premise" | partly | no signal ablation on one retriever; no latency; 345 positive samples in 25 repositories |
| "Expect 70-85% edge recovery" for Python static call graphs (`docs/05`) | not supported by the sources read | PyCG 69.9% on its own hand-built truth; Jarvis 0.76 and 0.82 recall on its truth; DyPyBench 49% of executed edges (`pycg-2103.00587.md`, `jarvis-2305.05949.md`, `dypybench-2403.00539.md`) |
| README: PyCG and Jarvis as "basis for the edge-recovery definition" | confirmed as two distinct definitions | see the definitions table above |

## Neutral summary table: what is taken, what is open, what is contradicted, per RQ (updated 2026-10-23)

"Taken" means stated by a source read in full (the note and page are the evidence); it is not a project decision. "Contradicted" means a project statement or an earlier lead that a source read in full does not support as worded. Rows added on 2026-10-23 are marked (new).

| RQ | Taken (source) | Open (no source found, or untested) | Contradicted or qualified (source) |
|---|---|---|---|
| RQ1: which signals matter, with latency | Lexical retrieval alone is much weaker than neural or agentic methods on issue localization (BM25 envelope in `exploration-structure-2606.11976.md`; `core-bench-2606.11864.md` Table 17). A repository map and embeddings win on different tasks and a fusion beats both (`agent-retrieval-bench-2607.24882.md`). Online edge resolution helped an LLM-agent localizer (`semnav-2609.31176.md`). Static Python call graphs recover a share of executed or hand-counted edges that depends on the definition (49% to 89%; definitions table above, NoCFG added). (new) Issue texts often name the gold location (over 50% of SWE-bench Lite, `logicloc-2604.16021.md` p.13, method not given). (new) The candidate encoder Qwen3-Embedding-0.6B: 0.6B parameters, 32K sequence length, 1024 dimensions, instruction on the query side only, Apache 2.0, MTEB (Code) average 75.41 (`qwen3-embedding-2506.05176.md`). | An edge-type ablation on a dense retriever with latency per row. Whether graph edges raise an embedding model's ranking (no graph-aware reranking of dense results for issue localization found beyond SpIDER, refresh of 2026-10-23). Co-change as a signal. Edge-resolution coverage on library-style repositories and for in-repo callees only. Per-signal latency (no paper reports it). (new) Gains split by whether the issue names the gold unit (the keyword-shortcut share on the project's own sets). (new) Repository-level zero-shot quality and cost of Qwen3-Embedding-0.6B (the report has neither; X2 measures them). | "70-85% edge recovery" (`docs/05`) is not supported as a general figure. "Supports RQ1's premise" holds only at system level. A fusion result between two different systems does not isolate signals. (new) Qwen3-Embedding's code results are function and snippet tasks with CodeSearchNet in both its training data and its evaluation; they are not repository-level evidence. (new) LogicLoc's large gains are on structural predicates, not issues; on issues it is below SweRank. |
| RQ2: supervision under matched optimisation budgets | Query filtering helped older models (`sun-2202.06649.md`). Soft weighting of negatives gave about 1-2% MRR (`rethinking-negative-pairs-2310.08069.md`). Relabelling and pruning helped text retrievers (`rlhn-2505.16967.md`). Consistency filtering with mined negatives and a staged data-domain schedule are used inside recipes (`cornstack-2412.01007.md`, `swerank-2505.07849.md`, `coder-2505.12697.md`). Trajectory-mined, judge-filtered positives raised file precision (`codegrep-2608.05886.md`). (new) The negative-selection rule alone moved a text retriever by about 4.5 nDCG points (small set-up) and 9 points (at scale) at fixed data and model, with a cut relative to the positive's teacher score best (`nv-retriever-2407.15831.md` Tables 3, 5). (new) BM25-mined negatives transferred worst among mined sources in two independent text studies (`nv-retriever-2407.15831.md` Table 1; `hard-negative-transfer-2603.20990.md` Table 1). (new) A filtered 5% subset of code-retriever pairs beat a random 5% subset in every reported cell, one seed (`map4cs-2610.11727.md` Table 1). (new) The candidate base encoder was itself trained with a cosine-threshold data filter and an in-batch false-negative mask (`qwen3-embedding-2506.05176.md` pp.5-6). | A controlled comparison of filter, weight and curriculum for a code retriever at matched optimisation steps (none found, refresh of 2026-10-23 included). Effect of the choice of quality-signal encoder (K-rank teacher). Weighting positives rather than negatives. Whether seeds change any ranking. (new) The false-negative rate among repository-local negatives for issue-to-function pairs (no measurement found for code). (new) Whether a positive-aware negative cut matters on repository-level pairs, and how it is defined with several positives (E-PILOT-NEG). (new) Whether the K-rank teacher and the negative miner should be the same model (if so FILTER and the negative policy share one signal). | "Curriculum" in CodeR is data-domain order plus a difficulty filter, not a quality curriculum. RLHN's pruning was selected on the evaluation benchmark. Sun et al. is not matched in optimiser steps. (new) MAP4CS's "5% matches full data" is not a matched-budget result (twentyfold fewer updates; full-data runs fall below zero-shot in four of six rows). (new) "Harder negatives transfer better" was not supported in 2603.20990 (hardness proxies picked a lower-transfer source), and a frozen-encoder preference statistic, the per-negative relative of K-rank, was fooled by false-negative-shaped controls. NV-Retriever's thresholds were chosen on its evaluation sets. |
| RQ3: resolved rate with the agent fixed | A retriever with much higher file precision gave +1.2 points on 500 Verified instances in one run; a weak lexical retriever lowered it (`codegrep-2608.05886.md`). Explorer-level retrieval metrics correlate with resolved rate across 14 systems (`swe-explore-2606.07297.md`). Localization quality raises resolved rate in repair pilots with one sample per cell (`graphlocator-2512.22469.md`, `semnav-2609.31176.md`). (new) With one repair stage held fixed, better function-level localization went with higher resolved rate (10.12% to 15.03% on Verified, 14B model, one run each, entry function supplied) (`reponavigator-2512.20957.md` Table 3). | A retriever trained with different supervision, agent fixed, with paired intervals and repeated agent runs. The size of run-to-run variation. Whether the precision-threshold pattern transfers to other agents. Whether empty-context baselines are inflated by memorisation on canonical repositories. (new, lead) Whether whole-file selection beats chunk retrieval at a fixed token budget (2610.21073, not read). | "Better localization raises resolved rate" is not uniform: a higher-recall localizer gave a lower resolved rate than a higher-precision one (`graphlocator-2512.22469.md`, Table 5), and a dense retriever was neutral (`codegrep-2608.05886.md`). Agent Retrieval Bench disclaims any retrieval-to-patch-success claim. CoSIL's large function-level gain came with no resolved-rate gain over a published baseline in one end-to-end comparison (94 against 96 of 300; 86 for the reproduced baseline; `cosil-2503.22424.md`). (new) RepoNavigator's gains come with an entry function per issue supplied to every method, which is not the standard task. |
