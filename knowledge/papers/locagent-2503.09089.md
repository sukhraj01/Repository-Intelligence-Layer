read: full — 18 pages incl. appendices, PDF v2, pdftotext -layout (poppler) plus page rasters of Tables 4-6 (pp.8-9), 2026-10-17

# LocAgent — Chen, Tang, Deng et al. (arXiv 2503.09089v2, ACL 2025 version, 29 Apr 2025)

Source file: arXiv PDF v2, 18 pages (body 11 pages with the reference list starting on p.11, references pp.11-13,
appendices A-D pp.14-18). The extracted text has 18 pages and no blank page (`scripts/check_paper_note.py`).
Every page was read, including the output-format study (Appendix A, pp.14-16), the NDCG table (Table 11, p.17)
and the instruction template (Figure 8, p.18). Table 6 (ablation) was looked at as a raster (p.9).
The superseded v1 (17 pages) was only searched for the Loc-Bench counts; it is not a source.

## What it established

- A typed repository graph (directory, file, class, function nodes; contain, import, invoke, inherit edges) built
  with the Python AST, plus a BM25 index over entity ids and entity contents, exposed to an LLM agent through three
  tools: SearchEntity, TraverseGraph (type-aware BFS with chosen hops and relation types) and RetrieveEntity
  (Sec. 3.1-3.2, pp.4-6; Table 2, p.5).
- On SWE-Bench-Lite (274 instances) the agent beats embedding, procedure-based and agent-based baselines at file,
  module and function level (Table 4, p.8); a 7B and a 32B open model fine-tuned on 768 trajectories reach
  results comparable to a closed-source model (Table 4, p.8; Figure 4, p.9).
- Removing components of the toolset lowers accuracy; the largest drops come from removing SearchEntity or the BM25
  index, the smaller ones from removing graph traversal (Table 6, p.9).
- Better localization raises downstream repair success under a fixed repair stage (Table 8, p.11).
- Loc-Bench: a localization benchmark of recent issues with bug, feature, security and performance categories
  (Table 3, p.7; Sec. 4.2, p.7).

## What it did not establish

- No per-edge-type ablation. The only edge-type comparison is "contain only" against all four types (Table 6, p.9);
  import, invoke and inherit are never removed one at a time.
- No measurement of how accurately invoke or import edges are resolved (no precision or recall of the graph itself).
- No seeds, no confidence intervals; every ablation cell is one run on 274 instances (one instance is about 0.37
  points, inference from the 274 of Sec. 5.1, p.7). The ablation uses the fine-tuned 7B model only (Sec. 5.6, p.10).
- No wall-clock latency. Cost in dollars and the number of agent rounds are reported (Table 5, p.9). "A few seconds
  per codebase" for indexing is a statement (pp.2, 5), not a table.
- No statement that the repositories of the SWE-bench training split used for fine-tuning are disjoint from the
  repositories of SWE-Bench-Lite or Loc-Bench (the training data are described on p.6 and in Appendix C.1.3, p.16).
- The number of repositories in Loc-Bench is not stated in this version.
- The effect of graph traversal is small next to the effect of search: removing TraverseGraph costs 5.47 function
  points (71.53 to 66.06), removing SearchEntity costs 18.25 (Table 6, p.9).

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| Loc-Bench size and categories (bug / feature / security / performance), v2 | 560; 242 / 150 / 29 / 139 | Table 3, p.7 |
| SWE-Bench-Lite instances kept for localization | 274 of 300 | Sec. 5.1, p.7 |
| Bug-report issues in Loc-Bench are created after this month | October 2024 | Sec. 4.2, p.7 |
| Ablation, full model (file Acc@5 / module Acc@10 / function Acc@10) | 88.32 / 82.85 / 71.53 | Table 6, p.9 |
| Ablation, without TraverseGraph | 86.13 / 78.47 / 66.06 | Table 6, p.9 |
| Ablation, relation types limited to contain | 86.50 / 79.56 / 66.42 | Table 6, p.9 |
| Ablation, traverse hops fixed to 1 | 86.86 / 80.29 / 66.79 | Table 6, p.9 |
| Ablation, without RetrieveEntity | 87.59 / 81.39 / 69.34 | Table 6, p.9 |
| Ablation, without SearchEntity | 68.98 / 61.31 / 53.28 | Table 6, p.9 |
| Ablation, without the BM25 index | 75.18 / 68.98 / 60.22 | Table 6, p.9 |
| Fine-tuned 32B model, SWE-Bench-Lite (file Acc@5 / module Acc@10 / function Acc@10) | 92.70 / 87.23 / 77.01 | Table 4, p.8 |
| Fine-tuned 7B model, same columns | 88.32 / 82.85 / 71.53 | Table 4, p.8 |
| Best embedding baseline CodeRankEmbed, function Acc@10 | 58.76 | Table 4, p.8 |
| Agent rounds and dollar cost per instance, fine-tuned 7B / 32B | 6 and 0.05; 9 and 0.09 | Table 5, p.9 |
| Training trajectories: from a closed-source model / later from the fine-tuned 32B | 433; 335 | Sec. 3.3, p.6 |
| Training samples in Appendix C.1.3 | 768 | App. C.1.3, p.16 |
| Downstream repair, Acc@5 / Pass@10 with a closed-source localizer in the agent vs the baseline pipeline | 73.36; 37.59 vs 58.39; 33.58 | Table 8, p.11 |
| Same table, Pass@1: baseline pipeline / fine-tuned 32B localizer / closed-source localizer | 26.31; 26.79; 27.92 | Table 8, p.11 |
| Same table, fine-tuned 32B localizer: Acc@5 / Pass@10 | 69.34; 36.13 | Table 8, p.11 |
| Loc-Bench file Acc@5 / function Acc@10, fine-tuned 7B vs CodeRankEmbed | 78.57; 51.43 vs 74.29; 43.39 | Table 7, p.11 |

## Method details we need

- **Graph (Sec. 3.1, pp.4-5).** Nodes: directories and Python files, then classes and functions parsed from the AST
  recursively; function is the smallest node and its code is the document. Edges: contain (tree over all node
  types), invoke (function or class to function or class; an invoke to a class is an instantiation), import (file to
  function or class), inherit (class to class). Entity ids are fully qualified names (`path:Class.method`).
- **Indexes (p.5).** Entity-id index, name-to-nodes dictionary, BM25 over ids, and an inverted index from code
  chunks to entities.
- **Agent (Sec. 3.2, p.6).** Chain-of-thought instruction (Figure 8, p.18), two interactions per issue at
  temperature 1.0, re-ranked by mean reciprocal rank (App. A.2, p.14). TraverseGraph prints the subgraph as an
  indented tree with relation names (Figure 7, p.15); tree format beat row, incident, DOT and JSON formats on 37
  hard instances (Table 9, p.16).
- **Fine-tuning (Sec. 3.3, p.6; App. C.1.3, p.16).** LoRA SFT of the 7B and 32B base models, five epochs, maximum
  128k tokens. Only trajectories that localized correctly are kept.
- **Difficulty (App. C.1.2, p.16).** The "hop" of an instance is the shortest graph distance between functions
  named in the issue (extracted by a closed-source model, version in App. C.1.2) and the patched functions.
- **Metrics (Sec. 5.1, p.7).** Acc@k is "all ground-truth locations inside the top-k"; NDCG is in Table 11, p.17.

## Graph facts recorded for this project (R2 fields)

| Field | LocAgent |
|---|---|
| Graph role | agent tool (type-aware BFS tool plus BM25 entity search); not a score signal and not learned (the learned part is the LLM) |
| Edge types used | contain, import, invoke, inherit (Sec. 3.1, p.4); node types directory, file, class, function |
| Edge types ablated | only "contain" against all four (Table 6, p.9); no per-type removal; hops 1 vs unbounded also run |
| Resolution coverage measured | no; graph accuracy is never compared with an oracle |
| Latency | none in seconds; cost and rounds (Table 5, p.9); indexing "a few seconds" asserted (p.2) |
| Held-out handling | evaluation on SWE-Bench-Lite and Loc-Bench (Bug Report issues created after October 2024); fine-tuning on SWE-bench training trajectories; no repository-level disjointness statement |

## Relation to RQ1 / RQ2 / RQ3

- RQ1: this is the schema the project's parser follows (Table 1, p.4). Its ablation gives an order of magnitude
  for graph traversal on top of a strong search tool (5.5 function points) but not for any single edge type.
  The ablation is for an agent that already has BM25 search; it does not transfer directly to a fused retriever.
- RQ2: no supervision study; nothing to take.
- RQ3: Table 8 (p.11) shows a localization gain carrying to repair under one fixed pipeline; it is one run per
  cell and the repair stage is fixed, so it is a suggestive precedent for RQ3, not a result.
- Leakage: Loc-Bench repositories overlap the benchmarks held out by the project (the data audit measured
  128 of 165 Loc-Bench V1 repositories outside the held-out list); see `PROJECT_STATE.md` Q9.

## Discrepancies

- With the master document / first pass: the lead gave Loc-Bench as 660 = 282 bug / 203 feature / 31 security / 144
  performance. This version (v2) states 560 = 242 / 150 / 29 / 139 (Table 3, p.7). The 660 figures occur in the
  superseded v1 (found by search in that PDF, which was not read in full). The data audit's 560 rows in V1 agree
  with v2. The first-pass lead also called the ablation "Table 5"; in v2 it is Table 6 (Table 5 is the efficiency
  table).
- With the lead "created after Oct 2024": true only for the Bug Report category (Sec. 4.2, p.7); security and
  performance issues were found by keyword search on the GitHub API (Table 10, p.16) without a date statement.
- Internal: the text gives 433 trajectories from the closed-source model plus 335 from the 32B model (Sec. 3.3,
  p.6; 768 in all), Appendix C.1.3 (p.16) gives 447 from the closed-source model and "the remaining samples"
  from the 32B model (768 in all, so 321).

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| L1 ablation numbers: full vs without TraverseGraph vs contain-only vs one hop vs without BM25 | confirmed | Table 6, p.9 | Values in the table above. It is Table 6 in v2, not Table 5. Single run, fine-tuned 7B model, 274 instances. |
| L1 contain-only is almost the same as no traversal | confirmed | Table 6, p.9; Sec. 5.6, p.10 | Function Acc@10 66.42 vs 66.06; the paper says contain adds "only marginal improvements" (p.10). |
| L1 Loc-Bench 660 = 282 / 203 / 31 / 144 | contradicted for v2 | Table 3, p.7 | v2 gives 560 = 242 / 150 / 29 / 139; the 660 split is in the superseded v1 (search only). |
| L1 Loc-Bench created after October 2024 | partly confirmed | Sec. 4.2, p.7 | Bug Report category only. |

## Scaffold reading (added 2026-11-08 for ADR-007; sections quoted below were re-read against the PDF v2 fetched that day, page count 18 unchanged; the full reading is the one dated in the first line)

- **What the repair stage is (Sec. 5.8, p.11).** The paper does not build a repair scaffold: for the downstream test it
  takes the Agentless editing method, with a closed-source model as the editor "for consistency", and changes only the
  localization given to it. Baseline is the Agentless pipeline's own localization (Table 8, p.11).
- **Retrieval swap with a fixed repair stage.** This is a retrieval-stage swap under a fixed edit method, the shape RQ3
  needs, but through a localization agent, not a retriever. Acc@5 rises from 58.39 to 69.34 (fine-tuned 32B) and 73.36
  (closed-source model), while Pass@1 rises from 26.31 to 26.79 and 27.92 (Table 8, p.11): a 15-point localization gain
  moves Pass@1 by 1.61 points (derived), and Pass@10 by 4.01 (derived from 33.58 and 37.59). One run per row, no
  interval, no run count stated; the paper does not define how Pass@1 and Pass@10 were obtained from the edit stage.
- **Model and decoding for the edit stage:** not stated beyond a named closed-source model (Sec. 5.8, p.11) and "the Agentless editing method"; no
  temperature, no seed, no budget. Cost is reported for localization only (Table 5, p.9), not for repair.
- **Implication for this project (inference).** The one published fixed-repair swap with a Pass@1 column shows a
  resolved-rate gain of about 1.6 points for a very large localization gain; the project's power table (minimum
  detectable difference 4.4 to 9.7 points at N = 327, `docs/RQ3_PILOT.md`) cannot see an effect of that size. That does not
  change D113, which names estimates with intervals for every contrast except the one primary; it is the reason the
  primary contrast is RAW against the untrained encoder (the larger expected difference).
- **Against the project's documents:** `docs/EVAL_API.md` lists "LocAgent v2: separate localization tools from a fixed
  downstream repair scaffold; count localization and repair together; repeat matched dev pairs". The paper counts
  localization cost only (Table 5, p.9) and does not repeat matched pairs; the first part of that row is how the paper
  proceeds, the other two are the project's requirements, not the paper's practice.
