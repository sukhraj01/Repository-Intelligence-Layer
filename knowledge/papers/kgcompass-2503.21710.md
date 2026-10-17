read: full — 21 pages incl. appendices, PDF v3, pdftotext -layout (poppler) plus page rasters of Table 4 and Figures 8-10 (pp.13-14), 2026-10-17

# KGCompass — Yang, Ren, Jin et al. (arXiv 2503.21710v3, 3 Oct 2025)

Source file: arXiv PDF v3, 21 pages (body 19 pages, references pp.19-21; the paper has no appendix).
The extracted text has 21 pages and no blank page (`scripts/check_paper_note.py`). Every page was read.
The earlier versions v1 (12 pages) and v2 (17 Sep 2025) were fetched and only searched for the multi-hop
figures; they are not sources. The figure values below are read from the v3 text and from rasters of
Figures 8-10 (they agree with the text).

## What it established

- A repair pipeline for SWE-bench Lite that builds a knowledge graph per issue, links the issue to repository files
  and symbols (and to earlier issues and pull requests) by template-based text matching, adds static AST edges
  (containment, calls, imports, attribute references), scores functions by an
  embedding-plus-edit-similarity score decayed by graph distance, passes the top 15 plus up to 5 suggested by an
  LLM to a patch generator together with the entity path that connects each function to the issue, then ranks
  patches with generated tests (Sec. 3, pp.4-8).
- Against a "pure-LLM" pipeline that differs only in how the 20 candidates are chosen, resolved rate rises for four
  backbones (Table 2, p.12) and the hybrid candidate list covers more ground-truth functions than either source
  alone (Table 5, p.15).
- Entity-path context in the repair step adds resolved instances beyond the graph-selected candidates alone
  (Table 6, p.16).
- Resolved-rate gains are larger when the issue text names no file or function (Table 4, p.13).

## What it did not establish

- No ablation of edge types, hop count or graph distance. The ablations are KG against no KG, entity path against
  none, ranking policy and patch pool size (Sec. 5.3, pp.15-17). "Multi-hop" is a description of where ground-truth
  functions lie, not a manipulated variable.
- No measurement of how accurately static edges or text-match links are resolved.
- No latency in seconds; cost in dollars and tokens only (Table 3, p.12).
- The relevance weights alpha = 0.3 and beta = 0.6 come from "initial parameter exploration" (Sec. 4.3, p.9); the
  exploration is not reported.
- One run per cell, no seeds or confidence intervals; the benchmark is Python only (Sec. 6, p.17 notes language
  adapters but reports nothing outside SWE-bench Lite).
- Whether the 146 ground-truth functions of Figure 8 are all ground-truth functions of the 300 instances, only
  those of instances that were localized, or only those inside the KG candidate list is not stated in Sec. 5.2
  (p.14); the abstract says "among the bugs that KGCompass successfully localizes" (p.1).

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| Ground-truth functions analysed for hop distance | 146 | Sec. 5.2, p.14 |
| Direct (one-hop) from the issue node | 15 (10.3%) | Sec. 5.2, p.14 |
| Two / three / four hops from the issue node | 108 (74.0%); 21 (14.4%); 2 (1.4%) | Sec. 5.2, p.14 |
| Share needing at least one intermediate entity | 89.7% | Sec. 5.2, p.14 |
| Intermediate entities on ground-truth paths | 156: 113 files (72.4%), 25 functions (16.0%), 11 pull requests (7.1%), 7 issues (4.5%) | Sec. 5.2, p.14 |
| Issues whose text names a ground-truth file or function / does not | 32.7% / 67.3% | Table 4, p.13 |
| Older closed-source backbone, resolved with explicit location: KGCompass vs pure-LLM | 65.3% vs 55.1% | Table 4, p.13 |
| Older closed-source backbone, resolved without explicit location | 36.6% vs 25.7% | Table 4, p.13 |
| Newer closed-source backbone, resolved with / without explicit location | 76.5% vs 57.2%; 49.5% vs 29.2% | Table 4, p.13 |
| KG-only top-20 coverage of ground truth, file / function | 68.7 / 40.4 | Table 5, p.15 |
| Hybrid KG + LLM coverage (newer backbone row), file / function | 91.0 / 66.7 | Table 5, p.15 |
| LLM-only coverage (same backbone), file / function | 77.3 / 52.6 | Table 5, p.15 |
| Hybrid and LLM-only coverage (older backbone row), file / function | 84.3 / 57.7 and 81.0 / 53.1 | Table 5, p.15 |
| Rank of the ground-truth function in the 20 KG candidates: rank 1 / top 5 / top 10 | 42 (28.8%); 93 (63.7%); 121 (82.9%) | Sec. 5.2, pp.14-15 |
| Share of obtained ground-truth locations covered by the top 15 KG functions | 97.3% | Sec. 5.2, p.15 |
| Resolved rate, KGCompass vs pure-LLM, closed-source backbones (newer and older rows) | 58.3% vs 38.7%; 46.0% vs 35.3% | Table 2, p.12 |
| Resolved rate, open backbones (KGCompass vs pure-LLM) | 36.7% vs 17.0%; 33.3% vs 13.0% | Table 2, p.12 |
| Entity-path ablation, older backbone, temperature 0: full / without KG / without entity path | 108 (36.0%); 85 (28.3%); 102 (34.0%) | Table 6, p.16 |
| Same ablation, newer backbone | 142 (47.3%); 91 (30.3%); 131 (43.7%) | Table 6, p.16 |
| Average cost per repair | $0.1999 | Sec. 5.1, p.11 |
| Relevance weights | alpha 0.3, beta 0.6 | Sec. 4.3, p.9 |
| Share of mined artifacts removed by the creation-time filter | 24.0% | Sec. 3.1, p.5 |
| Django snapshot size in the benchmark | 2,750 files; 27,867 functions | Sec. 4.1, p.8 |

## Method details we need

- **Graph (Sec. 3.1, p.5).** Code nodes: files, classes, functions from static AST analysis, with containment
  edges (file to class or function, class to function) and explicit reference edges (direct calls, imports,
  attribute references). Artifact nodes: issues and pull requests, linked to code nodes by a template-based
  regular-expression extractor over issue text, comments and pull-request elements (files, symbols, line numbers).
  Only artifacts older than the instance's `created_at` are kept (24.0% of mined artifacts were dropped).
  The graph is stored in a graph database (Sec. 4.3, p.9).
- **Score (Eq. 1, p.5).** `S(f) = beta^l(f) * (alpha * cos_norm(e_i, e_f) + (1 - alpha) * lev(t_i, t_f))`, where
  `l(f)` is the weighted shortest-path length from the issue node (Dijkstra), embeddings come from a code
  embedding model of the Jina family (Sec. 4.3, p.9), `lev` is normalised Levenshtein similarity.
  Edge weights of the weighted path are not given.
- **Candidates (Sec. 3.1, p.6).** Top 15 by `S(f)` plus up to 5 from an LLM given the issue text.
- **Pipeline (Sec. 3.2-3.3, pp.6-8).** Search/replace patches, hybrid greedy and sampled generation, an indentation
  repair step, then ranking by regression tests, generated reproduction tests, majority vote, patch size.
- **Backbones (Sec. 4.3, p.9).** Closed-source models (versions in the paper's Table 2) and two open-weight
  models; one setting uses a separate cheaper model for generated tests.

## Graph facts recorded for this project (R2 fields)

| Field | KGCompass |
|---|---|
| Graph role | signal (a distance-decayed relevance score selects 15 candidates) and prompt context (entity paths); not an agent tool, not learned |
| Edge types used | containment, call, import, attribute reference (code); issue/pull-request mention links by text matching (artifacts) |
| Edge types ablated | no; graph on/off and entity path on/off only (Tables 5-6, pp.15-16) |
| Resolution coverage measured | no accuracy of edge resolution; only coverage of ground truth by the candidate list (Table 5, p.15) |
| Latency | none in seconds; dollar and token cost per stage (Table 3, p.12) |
| Held-out handling | no training; creation-time filter on artifacts; evaluation on SWE-bench Lite only |

## Relation to RQ1 / RQ2 / RQ3

- RQ1: it is evidence that a graph-distance-decayed score helps candidate coverage over an LLM-only selector, with
  one unmeasured design (edge weights) and no signal-by-signal ablation, so it cannot rank signals.
- RQ2: nothing on retriever supervision.
- RQ3: Tables 2 and 6 show that changing the candidate list changes resolved rate with the rest of the pipeline
  fixed (one run per cell). The candidate list changes at the same time as the entity-path context, so the gain
  is not attributable to retrieval alone.

## Discrepancies

- **K1 (details below).** The master document's "69.7% of localized bugs needed multi-hop" is the value in the
  superseded v1 (12 pages); v3 says 89.7%.
  - v1, found by search (v1 not read in full): "30.3% (63 functions) can be reached via direct single-hop
    connections, while 69.7% require multi-hop traversals ... 58.2% (121 functions) necessitate two hops, and 11.5%
    (24 functions) require three or more" (208 functions in all).
  - v3, Sec. 5.2, p.14 and Figure 8, p.13: 15 of 146 (10.3%) direct, 108 (74.0%), 21 (14.4%), 2 (1.4%); 89.7%
    need at least one intermediate entity. The counts 15 + 108 + 21 + 2 sum to 146.
  - The ground-truth population changed between versions (208 functions in v1, 146 in v3) and so did the KG-only
    coverage (v1 text: top-20 KG candidates cover 84.3% of files and 58.8% of functions; v3 Table 5: 68.7 and 40.4).
    The reason is not stated in v3.
- **The base of 89.7%** is the 146 ground-truth functions, not "bugs that KGCompass successfully localizes" (abstract,
  p.1) and not instances (Sec. 5.2, p.14). The abstract also says these bugs "lack explicit location hints", which
  is a different quantity: 67.3% of instances have no file or function name in the issue text (Table 4, p.13).
- **What "multi-hop" measures (inference).** Two hops from the issue node is the route issue to a mentioned file to a
  function inside it (Figure 9, p.14: 72.4% of intermediate entities are files; 108 of 146 functions at two hops).
  The count therefore mostly reflects "a file is mentioned and the function sits in it" in a graph with file hubs, not
  that deeper reasoning was needed.
- Internal: v3 states function-level accuracy "Func Acc." with a Jaccard overlap (Sec. 4.2, pp.8-9), so it is lower
  than a hit rate and not comparable with Acc@k in the other graph papers.

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| K1 master doc "69.7% of localized bugs needed multi-hop" | contradicted for v3; true of the superseded v1 | Abstract, p.1; Sec. 5.2, p.14; Figure 8, p.13 | v3: 89.7% of 146 ground-truth functions are two or more hops from the issue node (10.3% direct). 69.7% is v1 text (search only). |
| K1 first pass "89.7% of ground-truth functions need at least two hops (10.3% one hop)" | confirmed | Sec. 5.2, p.14 | Base is functions, not instances or "successfully localized bugs". |
| K1 first pass "67.3% of instances without explicit location hints" | confirmed, different quantity | Table 4, p.13; p.2 | Share of SWE-bench Lite instances whose issue text names no ground-truth file or function (32.7% do). Not a hop statistic. |
| K2 hop distribution 74.0% two / 14.4% three / 1.4% four | confirmed | Sec. 5.2, p.14; Figure 8, p.13 | Counts 108, 21, 2 of 146. |
| K2 S(f) = beta^l (alpha cos + (1 - alpha) lev), alpha = 0.3, beta = 0.6 | confirmed | Eq. 1, p.5; Sec. 4.3, p.9 | Hyperparameters chosen by unreported exploration. |
| K2 KG-only coverage 68.7% files / 40.4% functions | confirmed | Table 5, p.15 | Top-20 KG candidates without LLM suggestions. |
| K2 hybrid 91.0 / 66.7 vs LLM-only 77.3 / 52.6 | confirmed | Table 5, p.15 | Newer-backbone rows; the older-backbone rows are 84.3 / 57.7 vs 81.0 / 53.1. |
| K2 no hop-count ablation | confirmed (absence) | Sec. 5.3, pp.15-17 | Ablations are location source, entity path, ranking, pool size. |
