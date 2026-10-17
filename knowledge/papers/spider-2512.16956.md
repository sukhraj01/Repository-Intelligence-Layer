read: full — 38 pages incl. appendices, PDF v3, pdftotext -layout (poppler) plus page rasters of Table 2 and Table 3 (p.8), 2026-10-17

# SpIDER — Chaudhari, Jacob, Cao, Rashid, Goswami, Bock (arXiv 2512.16956v3, 31 Aug 2026)

Source file: arXiv PDF v3, 38 pages (body 9 pages, limitations p.10, references pp.10-11, appendix A pp.11-38).
The extracted text has 38 pages and no blank page (`scripts/check_paper_note.py`). Every page was read, including
the theory (A.2, pp.12-18), the locality study (A.3, pp.18-19), the FAQ (A.14, pp.27-28) and all tables of
pp.29-38. The KDE and per-K figures (Figures 4-7, pp.22-24) carry no numbers beyond those in the tables. The
superseded v1 (16 pages) and v2 (21 pages) were fetched and only searched for the "12.9" figure; they are not
sources. The paper is cited as an ICML 2026 paper in `knowledge/papers/README.md`; the PDF itself carries no venue.

## What it established

- A function-level retrieval method on top of any dense retriever: take the dense top-K list (K = 20), choose the
  top C = 5 as seed centres, explore the code graph around each centre up to depth d (default 4) along chosen edge
  types, keep neighbours that also fall inside the dense top N = 500, let an LLM filter the surviving neighbours
  (one call per centre), and put the admitted neighbours into the list in place of the lowest-ranked non-centre
  items so that K stays fixed (Sec. 4.2, pp.5-6; Algorithm 1, p.20).
- Across four languages and three benchmarks the main configuration (containment edges only) raises Recall@20 and
  Acc@20 over the same encoder's dense list by at least 13% relative (+0.05 to +0.12 absolute), and by at least
  27% relative once call edges are explored (abstract, p.1; Table 2, p.8; Table 3, p.8).
- Edge-type comparison (single run on SWE-PolyBench): invoke edges beat containment in every language, containment
  plus invoke is best, import and inherit edges add nothing (Table 3, p.8), with paired tests agreeing
  (Sec. 5.2, p.8; A.9, p.21; Table 20, p.36).
- Under a "hands-tied" agent that sees only the retrieved top-K functions, SpIDER lists resolve more Verified
  instances than the dense list at K in {5, 10, 15, 20} (Table 4, p.9).
- A fixed exchange identity: the change in recall equals admitted hits minus displaced hits divided by the number of
  edited functions, so recall rises iff admitted precision exceeds the relevance of the displaced rank-K items
  (Proposition 4.1, p.6; proof p.12).

## What it did not establish

- Not a measure of graph accuracy: the edges are raw AST and name matches and no precision or recall of call or
  import resolution is given; "call-graph resolution is more brittle in dynamic languages" is asserted (A.14, p.27).
- The depth, centre-count and filter-threshold sweeps (Tables 9, 10, 14, 19) are single runs with two decimals;
  the authors state that differences of 0.01 in them are below the noise of the filter, which runs at non-zero
  temperature (Remark A.15, p.17).
- No wall-clock table and no percentiles. Latency appears as a sentence: roughly 5-10 seconds per query against
  under 1 second for dense retrieval (A.14, pp.27-28). Cost is in tokens (Tables 3, 8, 14).
- The edge-type result is for SWE-PolyBench only; the Verified and Multi-SWE-bench cells use containment only
  (Limitations, p.10).
- Hyperparameters C, d, N were chosen by grid search on the Python split of SWE-PolyBench, which is also an
  evaluation split (Sec. 5.1, p.6); A.11 (pp.25-26) argues the choice is near each language's optimum.
- No claim about repository overlap between the dense encoder's training repositories (about 3,300, p.7) and the
  evaluation repositories is made.
- The closed-form depth theory (Theorem A.11, p.15) is a hypothesis the authors say the data cannot confirm or
  refute (Remark A.15, p.17).
- The downstream result is one run per K; the authors do not read the K = 5 gain of 2 instances as an effect (A.8, p.21).

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages. Recall and
accuracy are fractions at K = 20 unless stated.

| Claim | Value | Where |
|---|---|---|
| Headline minimum relative gain over the same encoder's dense list, containment edges / with call edges | 13% / 27% | Abstract, p.1 |
| Corresponding absolute Recall@20 gains | +0.05 to +0.12; +0.11 to +0.19 | Abstract, p.1 |
| Configuration | K = 20, C = 5, d = 4, N = 500 | Sec. 5.1, p.6 |
| Python (SWE-PolyBench), SweRankEmbed-Small: dense vs SpIDER Recall@20 / Acc@20 | 0.42 / 0.35 vs 0.49 / 0.40 | Table 2, p.8 |
| SWE-bench Verified, same encoder: dense vs SpIDER | 0.54 / 0.49 vs 0.61 / 0.56 | Table 2, p.8 |
| Python edge ablation: contains d=4 / invokes d=2 / imports d=2 / inherits d=2 (Recall@20) | 0.49; 0.56; 0.44; 0.42 | Table 3, p.8 |
| Python tokens per instance: contains / invokes / both | 12.9K; 109.9K; 110.1K | Table 3, p.8 |
| Python containment plus invokes: Recall@20 / Acc@20 | 0.60 / 0.52 | Table 3, p.8 |
| Java: dense / contains / invokes / both (Recall@20) | 0.31; 0.36; 0.42; 0.42 | Table 3, p.8 |
| JavaScript: dense / contains / invokes / both (Recall@20) | 0.52; 0.60; 0.65; 0.66 | Table 3, p.8 |
| TypeScript: dense / contains / invokes / both (Recall@20) | 0.29; 0.35; 0.47; 0.48 | Table 3, p.8 |
| Java tokens: contains / invokes | 7.8K; 87.4K | Table 3, p.8 |
| Hands-tied resolve rate at K=10: dense / contains / invokes | 0.611; 0.681; 0.658 | Table 4, p.9 |
| Resolve rate at K=20, dense; tokens per instance at K=10 (contains) vs K=20 (dense) | 0.650; 81.5K vs 185.3K | Table 4, p.9 |
| Open-weight filter (30B coder) vs closed-source filter vs dense, Python Recall@20 / Acc@20 | 0.48 / 0.38; 0.49 / 0.40; 0.42 / 0.35 | Table 23, p.38 |
| Lexical keyword baseline vs SpIDER containment, JavaScript Recall@20 / Acc@20 | 0.69 / 0.61 vs 0.60 / 0.52 | Table 22, p.38 |
| Iterative agent, Python Recall@20 and tokens per instance | 0.84; 273.2K | Table 22, p.38 |
| Share of the unfiltered-neighbourhood recall that the LLM filter keeps | 79 to 89 | Table 21, p.37 |
| Marginal 95% interval, Python Recall@20: SpIDER vs dense | 0.49 ± 0.06 vs 0.42 ± 0.06 | Table 13, p.32 |
| Instances with at least one ground-truth function beyond dense rank 500 (Verified / Python / Java / JavaScript) | 38.2 / 51.1 / 62.0 / 21.8 percent | Table 6, p.30 |
| Retained instances: Verified / PolyBench Python / Java / JavaScript | 469 / 182 / 158 / 573 | Table 6, p.30 |
| Verified multi-function instances with all ground truth within 4 / 2 containment hops | 169 (88.9%) / 119 (62.6%) of 190 | A.3, p.18 |
| Ground-truth function pairs on Verified: siblings at 2 hops / cross-file at 6 or more | 1,171 (30%) / 1,851 (48%) of 3,869 | A.3, pp.18-19 |
| Mean invoke-connected ratio of ground-truth pairs: Verified / Python / Java / JavaScript | 0.57; 0.31; 0.63; 0.59 | Table 6, p.30 |
| Per-query LLM input at default settings; output | about 18 to 32K tokens; about 150 to 300 | A.14, p.27 |
| Stated latency per query: this method vs dense only | roughly 5 to 10 seconds vs under 1 second | A.14, pp.27-28 |
| Stated LocAgent run time on Verified / PolyBench Python subset | over 48 hours / about 24 hours | Table 11 caption, p.31 |
| Dense encoder's stated training repositories | roughly 3,300 | Sec. 5.2, p.7 |

## Method details we need

- **Graph (Sec. 4.1, p.4; A.6, p.20).** The schema of the LocAgent paper (directory, file, class, function nodes;
  contains, invokes, imports, inherits edges), built per repository from the primary language only (Python with
  `ast`; Java, JavaScript, TypeScript with a tree-sitter parser). A file node exists only if it holds a function
  or class; configuration-only files are ignored. Because no inherit edge touches a function node in this schema
  and import edges touch function nodes only in Python, those two edge types cannot surface new functions
  (Table 3 caption, p.8).
- **Expansion (Sec. 4.2, p.5).** BFS from each centre to depth d along the chosen edge types; two functions in one
  class are 2 hops apart, functions in different files 4 or more. The invoke setting caps exploration at the 100
  highest-ranked neighbours per query (Table 3 caption, p.8).
- **Filter (Sec. 4.2, p.5; A.5, p.20).** A zero-shot LLM judges each neighbour, instructed to be restrictive; centres
  are always kept. A closed-source model (version in Sec. 5.1, p.6) at temperature 0.1; three open-weight coder
  models also tested (A.13, pp.26-27).
- **Metrics (Sec. 5.1, p.6).** Recall@K = |V* ∩ S| / |V*|; Acc@K = 1 iff all edited functions are in the top K.
- **Encoders (Sec. 5.1, p.6).** SweRankEmbed-Small zero-shot (the load-bearing dense comparison), two code encoders,
  BM25 with a sparse variant of the method.
- **Benchmark (SpIDER-Bench; A.14, p.28).** Built from SWE-bench Verified, SWE-PolyBench and Multi-SWE-bench at the
  issue base commit; instances without function-level edits are excluded.

## Graph facts recorded for this project (R2 fields)

| Field | SpIDER |
|---|---|
| Graph role | signal added to a dense list (expansion plus a zero-shot LLM filter under a fixed budget); not an agent tool; the graph is not learned; the encoder is separately pretrained |
| Edge types used | contains (default, d=4); invokes, imports, inherits tested (Table 3, p.8); schema also has directory and file nodes |
| Edge types ablated | yes, one edge type at a time and containment plus invokes, on SWE-PolyBench only, single run plus paired tests (Table 3, p.8; Table 20, p.36) |
| Resolution coverage measured | no accuracy of edges; locality statistics of the ground truth are measured (Table 6, p.30) |
| Latency | a stated 5-10 s per query vs under 1 s dense (pp.27-28), no percentiles; token counts per edge setting (Table 3, p.8) |
| Held-out handling | no training of its own; hyperparameters tuned on the Python split of one evaluation benchmark; overlap of the encoder's training repositories with the evaluation repositories not discussed |

## Relation to RQ1 / RQ2 / RQ3

- RQ1: the closest published design to the project's structural signal (dense seeds, graph expansion, fixed budget).
  Its edge-type table is the only edge-by-edge result among the graph papers read so far, and it says containment
  is cheap and works, call edges work better and cost about eight times more tokens (110.1K vs 12.9K on Python).
  The cost is LLM tokens from the filter; it would not transfer unchanged to a filter-free expansion.
- RQ2: nothing on supervision; note that the encoder used (SweRankEmbed-Small) is a SweRank artifact.
- RQ3: Table 4 (p.9) is a retrieval-to-resolution result with the agent restricted to the retrieved list; one run per
  cell, a Verified subset, and a closed-source repair backbone.
- A caution for the project's fusion design: expansion that adds nodes must evict others to stay at budget; the
  identity of Proposition 4.1 shows when that exchange loses (admitted precision below the frontier's relevance).

## Discrepancies

- **G2 "+12.9% Recall@20 over the best embedding model".** Not in v3. The abstract of v3 says "at least 13% relative"
  (p.1); "at least 12.9% and 14%" (Recall@20 and Acc@20) is v1 text found by search. Either way it is a relative
  minimum over language-by-dataset cells against the same encoder's dense list (Table 2, p.8), not an improvement over
  the best embedding model and not an average. The FAQ states it is relative (A.14, p.27).
- **"Exploration mainly follows containment edges".** True of the reported configuration (Table 2, p.8; Limitations,
  p.10) and false as a statement about what works best: invoke edges beat containment in every language
  (Table 3, p.8). Containment is the default because it costs about an order of magnitude fewer tokens (A.14, p.27).
- **Contrast with LocAgent's contain-only ablation.** LocAgent's contain-only variant is about level with no traversal
  (LocAgent note, Table 6, p.9: function Acc@10 66.42 vs 66.06), whereas SpIDER's containment expansion gives +0.05 to
  +0.12 Recall@20 over dense retrieval. The settings differ (an agent with BM25 search and a fine-tuned 7B model against
  dense seeds with an LLM filter), so the two numbers do not contradict each other; they do show the value of
  containment depends on what already supplies the seeds.
- Internal: the LocAgent row of Table 12 (p.31, labelled SWE-PolyBench) has Recall@3 0.18, Acc@3 0.17, MRR@3 0.12, which are the
  SWE-bench Verified values of Table 11, not the PolyBench Python values (0.23, 0.17, 0.21).
- Internal: the abstract's "rising to at least 27% relative" is the minimum over four languages for containment plus
  invoke edges measured on SWE-PolyBench only (Sec. 5.2, p.7; Table 3, p.8).

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| G2 dense top-C = 5 centres | confirmed | Sec. 5.1, p.6; Algorithm 1, p.20 | |
| G2 BFS depth d up to 4 | confirmed | Sec. 5.1, p.6; Sec. 4.2, p.5 | d = 4 default; d = 8 tested (Table 9, p.31). |
| G2 neighbours kept if in top-N = 500 | confirmed | Sec. 4.2, p.5; Sec. 5.1, p.6 | |
| G2 one LLM call per centre | confirmed | Sec. 5.3, p.9; A.14, p.27 | Concurrent calls; about 5-10 seconds stated. |
| G2 +12.9% Recall@20 over the best embedding model | not found in v3 (v1 says 12.9%); different quantity | Abstract, p.1; Table 2, p.8 | v3: at least 13% relative over the same encoder's dense list. |
| G2 exploration mainly follows containment edges | partly confirmed | Table 2, p.8; Table 3, p.8; Limitations, p.10 | Default only; invoke edges are better in every language. |
