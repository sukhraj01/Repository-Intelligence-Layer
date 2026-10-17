read: full — 20 pages incl. appendices, PDF v2, pdftotext -layout (poppler) plus page rasters of Figures 2, 3, 5 and 9, 2026-10-17

# SweRank — Gangi Reddy, Suresh, Doo et al. (arXiv 2505.07849v2, ICLR 2026 version, 22 Apr 2026)

Source file: arXiv PDF v2, 20 pages (body 10, references pp. 11-15, appendices A-I pp. 16-20).
Extracted text has 20 pages, none blank. Appendices A-I were read in full (they were not seen in the
first pass behind the master document's summary). Figure 5a was read off the plot (log x-axis); those
values are approximate and are listed apart from the checked numbers.

## What it established

- A retrieve-and-rerank pipeline for issue localization: a bi-encoder (SweRankEmbed, 137M and 7B) and a
  listwise reranker (SweRankLLM, 7B and 32B), trained on a Python issue-to-function dataset (SweLoc) built
  from pull requests of popular PyPI packages (Sec. 3, pp.3-5; Sec. 4, p.5).
- Retrievers trained on it beat prior embedding models and agent pipelines on function-level Acc@10 on
  SWE-Bench-Lite and Loc-Bench (Tables 1-2, pp.6, 8).
- Training data construction: positives are modified functions, one training instance per modified
  function; consistency filtering keeps an instance only if the positive ranks within the top K=20
  functions of its repository under a separately pretrained embedder; hard negatives come from the top M=15
  (Sec. 3.2-3.3, pp.4-5).
- Filtering matters: no filtering (K=None) drops function Acc@10 below the pretrained model; K=20 is best
  among K in {5, 10, 20, 50, None} (Figure 5a, p.8; text p.7).
- More data helps even at K=20 (Figure 5b, p.8); harder, iteratively mined negatives help (Figure 9, p.18).
- The same data improves several other retrievers and rerankers when used to fine-tune them (Tables 3-4,
  pp.8-9; Table 7, p.16).
- Downstream: with a fixed repair pipeline, better file localization gives a small repair gain (Table 6, p.9).

## What it did not establish

- No statement of the number of training instances after filtering in the text; no release statement for
  the dataset itself (the footnote on p.1 names code and models only).
- The filter is a rank cut with a binary keep/drop; there is no weighting, no curriculum, and no comparison
  of filter teachers.
- The K ablation is one training run per point on the small model, no seeds or intervals.
- Training positives are functions modified by the PR; whether such functions are the most useful positives
  is not tested.
- Evaluation sets (SWE-Bench-Lite, Loc-Bench) are the training distribution's neighbours; the paper
  excludes SWE-bench and Loc-Bench repositories from SweLoc (p.4) but does not report an overlap audit
  beyond that rule.
- Latency of the retrieval stage is stated as negligible after pre-computed embeddings; no per-query
  retrieval latency is reported (Appendix G, p.19, covers the reranker end to end).

## Numbers we may quote

Values are `paper_reported`. Function-level Acc@k is the share of instances whose all gold functions
are in the top k. Page numbers are PDF pages. Closed-source systems in the paper's tables are not quoted.

| Claim | Value | Where |
|---|---|---|
| SweLoc source: top PyPI packages considered; repositories after filters | 11,000; 3387 | Sec. 3.1, p.4 |
| Minimum share of Python code in a repository | 80% | Sec. 3.1, p.4 |
| Initial (PR, codebase) pairs | 67,341 | Sec. 3.1, p.4 |
| Consistency filter K; hard negatives from the top M | 20; 15 | Sec. 3.3, pp.4-5 |
| Mean query length in SweLoc (tokens) | 382.56 | Fig. 3, p.4 |
| Query tokens in SWE-Bench issues vs CodeSearchNet queries (footnote) | 460; 12 | footnote 2, p.2 |
| Small retriever training: epochs / learning rate / batch / hard negatives | 2; 2e-5; 64; 15 | Appendix A.1, p.16 |
| Large retriever training: epochs / learning rate / batch / hard negatives | 1; 8e-6; 64; 7 | Appendix A.1, p.16 |
| Reranker training: epochs / global batch / learning rate / warmup steps | 1; 128; 5e-6; 50 | Appendix A.2, p.16 |
| GPUs for the small retriever | 8 GH200 | Appendix A.1, p.16 |
| SWE-Bench-Lite instances kept (functions modified) of 300; Loc-Bench examples | 274; 560 | Sec. 5.1, p.7 |
| SWE-Bench-Lite function Acc@10: BM25 / CodeRankEmbed / SweRankEmbed-Small / SweRankEmbed-Large | 36.86; 58.76; 74.45; 82.12 | Table 1, p.6 |
| SWE-Bench-Lite function Acc@5: CodeRankEmbed / SweRankEmbed-Small / SweRankEmbed-Large | 51.82; 63.14; 71.90 | Table 1, p.6 |
| SWE-Bench-Lite file Acc@1: CodeRankEmbed / SweRankEmbed-Small / SweRankEmbed-Large | 52.55; 66.42; 72.63 | Table 1, p.6 |
| Loc-Bench function Acc@10: CodeRankEmbed / SweRankEmbed-Small / SweRankEmbed-Large | 47.86; 58.57; 63.21 | Table 2, p.8 |
| Fine-tuning CodeRankEmbed on SweLoc, function Acc@10 before to after | 59.5; 72.3 | Table 3, p.8 |
| Fine-tuning Arctic-Embed: before to after | 53.7; 71.9 | Table 3, p.8 |
| Fine-tuning Arctic-Embed-v2.0: before to after | 62.0; 70.1 | Table 3, p.8 |
| Retrieval ceiling Acc@100 on SWE-Bench-Lite: Small / Large | 91.97; 93.43 | Table 8, p.17 |
| Repair pass@1 with a fixed repair pipeline: native localizer / SweRank / oracle file | 21.0; 24.5; 25.9 | Table 6, p.9 |
| Table 6 file Acc@1 of SweRank | 83.2 | Table 6, p.9 |
| Reranker latency per instance on one 80 GB GPU (seconds) | 12.5 | Table 12, p.19 |
| SweRankEmbed-Large on SWE-Bench Multilingual, Acc@10 | 50.85 | Table 11, p.18 |
| Qwen3-Embedding-0.6B fine-tuned on SweLoc, function Acc@10 before to after | 62.77; 75.18 | Table 9, p.17 |

### Read from figures (approximate, not checked by script)

| Item | Value | Where |
|---|---|---|
| Training instances at K=5 / 10 / 20 / 50 / None (x-axis, log scale) | about 8e4 / 1.05e5 / 1.4e5 / 2.0e5 / 5e5 | Fig. 5a, p.8 |
| Function Acc@10 of the small retriever at K=5 / 10 / 20 / 50 / None | about 67.5 / 70.5 / 72.3 / 71.2 / 53.5 | Fig. 5a, p.8 |
| Pretrained baseline, function Acc@10 | about 58.8 (equals Table 1's 58.76) | Fig. 5a, p.8 |
| File Acc@3 at K=20 / None / pretrained | about 87.3 / 76.3 / 77.8 | Fig. 5a, p.8 |
| Small retriever, function Acc@10: random / 1st-iteration / 2nd-iteration negatives | about 65.5 / 72.3 / 74.5 | Fig. 9, p.18 |
| Large retriever, same | about 73.3 / 80.7 / 82.1 | Fig. 9, p.18 |

## Method details we need

- **Data (pp.3-5).** Repositories: top 11,000 PyPI packages with a GitHub repository, at least 80% Python,
  repositories already in SWE-Bench or Loc-Bench excluded, near-identical repositories removed by source-code
  overlap, giving 3387. PRs that resolve a linked issue and modify test files (the SWE-bench criteria); the
  codebase at the PR base commit. Query = issue text; each modified function is a positive and a separate
  training instance (a PR modifying N functions gives N instances, p.4). Negatives are the other functions of
  the repository.
- **Consistency filter (p.4).** The embedding model is CodeRankEmbed. The small retriever is initialised from
  CodeRankEmbed and the large one from GTE-Qwen2-7B-Instruct (Sec. 5.1, p.6), so for the small variant the
  filter teacher and the initial student are the same checkpoint. An instance is kept if the positive is within
  the top K=20 functions of the repository by similarity to the issue. K ablation in Figure 5a.
- **Hard negatives (p.5).** From the same similarity matrix, the top M=15 functions of the repository for the
  query that are not the positive. Iterative mining (Appendix E, p.18): 1st iteration negatives from the
  small pretrained model, 2nd iteration from the 1st-iteration small model.
- **Loss (Sec. 4.1, p.5).** InfoNCE over the positive and `N(M+1)-1` negatives (in-batch positives and all hard
  negatives); no temperature appears in Eq. 1. Query prefix strings are given in Appendix A.1.
- **Reranker (Sec. 4.2, p.5).** Listwise, trained only to emit the identifier of the single positive first.
- **Compute (Appendix A).** 8 GH200 GPUs for the retrievers, 16 for the reranker; DeepSpeed ZeRO-3.
- **Evaluation (p.7).** Acc@k = all gold functions within the top k; file and module scores are the maximum of
  contained functions; SWE-Bench-Lite restricted to 274 instances where existing functions were modified.

## Relation to RQ1 / RQ2 / RQ3

- RQ2: this is the K-rank source. The filter's quality signal is the rank of the positive among repository
  functions under a base retriever, which is the signal the project uses for FILTER and WEIGHT. Figure 5a is
  the only evidence in the literature we have read for the sign and size of the filter effect, from one run per
  point. It tests keep/drop only; WEIGHT and CURRICULUM are not tested.
- RQ2: the project's rule is that the quality encoder is a separately pretrained model, never the model being
  trained. In this paper the small retriever starts from the same checkpoint that does the filtering; the
  filter runs before training, so the teacher is the pretrained checkpoint, but teacher and student are not
  independent models. The large retriever starts from a different model than the filter teacher.
- RQ3: Table 6 is the only repair-level number and uses one repair pipeline, one benchmark and no intervals.

## Discrepancies

- Instance counts per K are not in the text; only the log-axis reading in the table above exists.
- Internal: the K=20 point in Figure 5a (function Acc@10 about 72.3) differs from the final small retriever
  (74.45, Table 1). The same 72.3 appears in Table 3 for one epoch of fine-tuning CodeRankEmbed, and Figure 9
  puts the 2nd-iteration-negatives result at about 74.5. This suggests Figure 5a used one epoch and
  1st-iteration negatives, while Appendix A.1 gives two epochs for the final small model (inference, not
  stated in the paper).
- Loc-Bench example count: the paper says 560 (p.7). The data audit measured 560 rows in Loc-Bench V1 over 165
  repositories; V0.2 has 660 (the data audit). The master document's 660 is the older version.
- The data audit measured that the public pool `gangiswag/train_data` (python) has 24,285 instance directories and
  2,448 repositories. Those are the SweRank+ Table 1 Python row (see the SweRank+ note), not this paper's
  3387 repositories; the SweLoc pool described here has no public count of final instances in the text.

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| S1 top 11,000 PyPI packages to 3,387 repositories (at least 80% Python, SWE-bench and Loc-Bench repositories excluded, dedup by code overlap) | confirmed | Sec. 3.1, p.4 | |
| S1 67,341 (PR, codebase) pairs | confirmed | Sec. 3.1, p.4 | |
| S1 keep an instance only if the positive ranks in the top K=20 under CodeRankEmbed; hard negatives from top M=15 | confirmed | Sec. 3.3, pp.4-5 | Rank is among the other functions of the same repository. |
| S1 final instance count | not found in text | pp.3-8 | Read off Figure 5a only: about 1.4e5 at K=20, about 5e5 without filtering (approximate). |
| S1 App E negative-mining ablation | found | Appendix E, Figure 9, p.18 | Random, 1st-iteration, 2nd-iteration negatives; numbers only in the plot. |
| S1 K-ablation values behind Fig 5a, "no filtering lowers performance below the pretrained model" | confirmed | Figure 5a, p.8; text pp.7-8 | Function Acc@10 about 53.5 without filtering vs about 58.8 pretrained (plot reading). |
| S1 hyperparameters | confirmed | Appendix A, p.16 | Values in the table above. |
| S1 any release statement | partly | footnote 1, p.1 | "Code and models are available" at the authors' repository; the dataset is not named. |

## Figures looked at

Figure 2 (p.3): pipeline schematic, no numbers. Figure 3 (p.4): query-length histogram with mean 382.56;
pies for files, modules and functions modified per issue (one function in about half of the instances;
percentages read off the pies are not quoted). Figure 5 (p.8): described above. Figure 9 (p.18): above.
