read: full — 46 pages incl. appendices, PDF v1, pdftotext -layout (poppler) plus page rasters of Table 4 and Figure 7 (p.8) and of the image-only pages 21, 24, 31 and 33, 2026-10-17

# GREPO — Wang, Chen, Wang et al. (arXiv 2602.13921v1, 14 Feb 2026)

Source file: arXiv PDF v1, 46 pages (body 8 pages, references pp.8-10, appendices A-N pp.11-46). The extracted
text has 46 pages; ten of them (21-27, 30, 31, 33) have almost no extractable text because their content is
images: code-snippet screenshots of the similarity case studies (Figure 12, pp.21-28) and screenshots of the
rewriting instruction templates and example outputs (Figures 15-16, pp.30-34). Pages 21, 24, 31 and 33 were rasterized and read (code snippets; the query-rewriting instruction template; an example of
rewritten output). The other six (pp.22-23, 25-27, 30) were not rasterized; their captions (Figures 12 and 15, pp.28, 32)
say they are of the same kind. None of the pages looked at carries a number used here. `scripts/check_paper_note.py` reports no page as blank (each
has a header line). All other pages were read, including the temporal-anchor method (Appendix K, pp.34-36), the
overlap analysis (Appendix N, pp.38-41) and the repository list (Table 8, pp.37-38).

## What it established

- A benchmark of 86 Python repositories and 47,294 issue-to-fix tasks, with a heterogeneous, temporally indexed
  repository graph per commit (directory, file, class, function nodes; contain, call, inherit and
  previous/next-version edges) and node features from a frozen embedding model, so that graph neural networks can be
  trained and compared with retrieval and LLM baselines (Sec. 4, pp.3-5; Table 1, p.3).
- On nine held-out test repositories, every tested GNN has a higher mean query recall than the retrieval and LLM
  baselines at Hit@5, Hit@10 and Hit@20; GATv2 and GAT are the best (Table 3, p.7).
- Ablations on the best-known model (GAT): removing the temporal anchors costs far more than removing any
  feature, edge type or semantic anchor (Table 4, p.8).
- Scaling: with the nine test repositories excluded from training, the average Hit@K rises with the number of
  training repositories and at 77 repositories matches the model trained with the test repositories' earlier issues
  (Figure 7 and Sec. 5.3, p.8).

## What it did not establish

- No seeds and no confidence intervals; every cell of Tables 3 and 4 is a single value.
- "Hit@K" here is mean recall (Eq. 3, p.6), not the hit rate of the usual definition. It is computed against the full
  ground-truth set, and a ground-truth node outside the extracted subgraph counts as zero (Sec. 5.1, pp.6-7). The
  subgraph comes from the anchors, so the metric also measures anchor coverage.
- Not a clean test of message passing: the temporal anchors add candidates to the subgraph (Appendix K.2, p.35), so
  the large drop in the "without temporal anchors" row removes a candidate source as well as a signal. The authors note
  that injecting candidates "can look like a candidate-source swap" (Appendix K, p.35).
- No timing of GNN inference or of graph construction in seconds; construction is argued by a changed-files ratio
  and node counts (Figure 4, p.4; Appendix C, p.16). Hardware is one RTX 4090 (Appendix L, p.36).
- No accuracy of the call and inheritance edges, which come from a static type-inference library whose
  unresolved targets are dropped and whose ambiguous targets all receive an edge (Appendix A.1, p.11; A.3, p.15).
- No check of overlap with SWE-bench: seven repositories of the twelve in SWE-bench appear in the paper's list.
- The baselines are weak and not tuned to this setting: the agent baseline (run with an open 72B model)
  has an average Hit@20 of 12.23 (Table 3, p.7), far below what the agent's own paper reports on other data.

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages. Hit@K is mean
recall in percent.

| Claim | Value | Where |
|---|---|---|
| Benchmark size | 86 repositories; 47,294 tasks | Sec. 1, p.2 |
| Evaluation repositories | nine of the 86 | Sec. 5.1, p.6 |
| Split | 80% earliest issues for training, 20% for testing, per repository | Sec. 5.1, p.6 |
| GAT, full model, Hit@1 / @5 / @10 / @20 | 14.80 / 31.51 / 37.40 / 41.25 | Table 4, p.8 |
| Without temporal anchors, Hit@1 / @5 / @10 / @20 | 8.09 / 19.13 / 24.18 / 28.78 | Table 4, p.8 |
| Without semantic anchors | 14.31 / 31.47 / 36.40 / 38.85 | Table 4, p.8 |
| Without contain edges | 14.12 / 30.56 / 34.87 / 37.47 | Table 4, p.8 |
| Without call edges | 14.61 / 32.01 / 37.15 / 40.80 | Table 4, p.8 |
| Without inherit edges | 14.07 / 30.32 / 35.94 / 40.30 | Table 4, p.8 |
| Without edge-type embeddings | 13.97 / 31.21 / 36.29 / 40.04 | Table 4, p.8 |
| Without query-node similarity / without anchor labels | 13.43 / 30.16 / 36.57 / 40.67 and 13.61 / 30.49 / 36.15 / 40.35 | Table 4, p.8 |
| Best baseline at Hit@1 (Agentless, a closed-source model) / Hit@20 | 13.65 / 23.43 | Table 3, p.7 |
| Retrieval baseline CF-RAG, Hit@1 / Hit@20 | 0.70 / 19.93 | Table 3, p.7 |
| Agent baseline, Hit@1 / Hit@20 | 5.04 / 12.23 | Table 3, p.7 |
| GATv2, Hit@1 / @5 / @10 / @20 | 14.84 / 32.47 / 37.68 / 41.54 | Table 3, p.7 |
| Candidate coverage of the temporal retriever (issues whose ground truth is in its list) | 62.8% | Table 13, p.41 |
| Anchor hit/recall, all anchors vs extractor-only, patched nodes | 0.380 vs 0.161 | App. H, p.29 |
| Training repositories at which the zero-shot model matches the in-repository model | 77 | Sec. 5.3, p.8 |
| GAT reranker: layers, heads, hidden size | 4, 4, 128 | Table 7, p.36 |
| Training: epochs, learning rate, batch size | 10; 1e-4; 1 | App. L, p.36 |
| Embedding dimension | 4096 | Sec. 4.3, p.5 |

## Method details we need

- **Graph (Sec. 4.1, p.4; Appendix A, pp.11-16).** A tree-sitter parser creates directory, file, class and function
  nodes; contain edges come from the file system and the syntax tree; call and inheritance edges come from running
  a static type-inference library at each call site and base-class token and joining the result to the extracted
  definitions by (relative path, line); built-in and external targets are dropped; each edge has a reverse edge.
  The temporal graph keeps one node per version with a start and an end commit and previous/next links
  (Appendix A.4, p.16); commits are linearised along the longest path of the commit DAG (Appendix D, p.17).
- **Labels (Sec. 4.2, p.5; Appendix E, pp.17-19).** Merged pull requests linked to issues by closing keywords; the
  input is the issue title and its first message only; ground truth is the set of functions and classes the pull
  request changed, mapped to the graph at the base commit; examples with no Python file mapping are dropped.
- **Features (Sec. 4.3, p.5).** Node text embedded with an open 8B embedding model; query-node similarity from up to
  five LLM-rewritten queries; anchors from fuzzy matching of extracted entities plus dense search of the rewritten
  queries, and (best setting) a temporal prior from a transformer over commit-history neighbours trained on the
  training split (Appendix K, pp.34-36).
- **Model (Appendix K.3-K.4, p.35-36).** A query-aware graph attention reranker on the k=1 subgraph around
  the anchors, with residual edge gates from the temporal prior.
- **Baselines (Sec. 5.2, p.7).** An agent with an open 72B model, a direct-prompting localizer with a closed-source
  model, and a retrieval pipeline that also generates the anchors.

## Graph facts recorded for this project (R2 fields)

| Field | GREPO |
|---|---|
| Graph role | learned (a GNN reranker trained on issue-to-patched-node supervision over the graph); anchors from retrieval; not a hand-set signal and not an agent tool |
| Edge types used | contain, call, child/parent (inheritance), previous/next version (Sec. 4.1, p.4; App. A.1, p.11), each with a reverse edge |
| Edge types ablated | yes, contain, call, inherit removed one at a time, plus edge-type embeddings (Table 4, p.8); single run, no intervals |
| Resolution coverage measured | no; unresolved calls are silently absent, ambiguous calls get edges to all candidates |
| Latency | none for inference; incremental-build argument only (Figure 4, p.4) |
| Held-out handling | nine test repositories; chronological 80/20 split per repository; main table trains on the same repositories' earlier issues; a zero-shot variant excludes the nine repositories (Sec. 5.1, p.6; Sec. 5.3, p.8); issue text restricted to title and first message |

## Relation to RQ1 / RQ2 / RQ3

- RQ1: a learned alternative to the project's fixed signals; the call-edge ablation shows a small effect (40.80 vs
  41.25 at Hit@20) and the contain-edge ablation a larger one (37.47), which is the only learned-graph edge-type
  evidence among the papers read so far. The effect sizes are from single runs.
- RQ2: the supervision here is the full set of patched nodes per issue with no quality filter. It is a different
  setting (graph reranking over anchors), so it neither supports nor contradicts a claim about contrastive
  supervision of an encoder.
- RQ3: no resolution outcome is measured.
- Leakage: GREPO's 86 repositories include seven of the twelve SWE-bench repositories (astropy, django, matplotlib,
  flask, xarray, pylint, sphinx; Table 8, pp.37-38, from the repository links). Using it as a training pool
  needs the project's repository-level filter.

## Discrepancies

- **G3 holds, with a qualification about what it measures.** Hit@1 14.80 to 8.09 and Hit@20 41.25 to 28.78
  without temporal anchors (Table 4, p.8). The anchors are a candidate source, and Hit@K counts a node missing from the
  subgraph as a miss (Sec. 5.1, p.7), so the drop partly reflects recall of the candidate set.
- Internal: the text says "all ablated variants result in performance degradation" (Sec. 5.4, p.8), but the row
  without call edges has Hit@5 32.01, above the full model's 31.51 (Table 4, p.8).
- Internal: the GNN advantage over the best baseline is 1.15 points at Hit@1 (14.80 vs 13.65) and 17.82 at Hit@20
  (41.25 vs 23.43) (Table 3, p.7); "consistently outperform" is a statement about Hit@5 and deeper; at Hit@1 the
  differences are small and unreplicated.
- The temporal-anchor drop (6.71 at Hit@1) is five times the largest edge or feature drop at Hit@1 (1.37, without
  query-node similarity; Table 4, p.8) (derived from Table 4).

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| G3 removing temporal anchors drops Hit@1 14.80 to 8.09 | confirmed | Table 4, p.8 | Graph model GAT, average over the nine test repositories. |
| G3 removing temporal anchors drops Hit@20 41.25 to 28.78 | confirmed | Table 4, p.8 | Also Hit@5 31.51 to 19.13 and Hit@10 37.40 to 24.18. |
