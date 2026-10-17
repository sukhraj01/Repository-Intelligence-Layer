read: full — 27 pages incl. appendices, PDF v3, pdftotext -layout (poppler) plus page rasters of Figures 1-4, 2026-10-17

# CORE-Bench — Zhang et al. 2026 (arXiv 2606.11864v3, dated 24 Aug 2026)

Source file: arXiv PDF v3, 27 pages (body 9 pages, references pp. 9-11, appendices A-I pp. 11-27).
The extracted text has 27 pages and no blank page (`scripts/check_paper_note.py`). The reference list
was read for the works it names; the remaining pages were read in full, including every table in
Appendices A-H and the three instruction templates in Tables 23-25.

## What it established

- A three-level code-retrieval benchmark: Level-1 (traditional code understanding), Level-2
  (issue-to-edit localization, labels from the pull-request patch), Level-3 (broader context, labels
  from agent browse traces filtered by a three-vote judge ensemble). Built from SWE-bench-family
  datasets; 11 programming languages (Figure 1a, p.3).
- Evaluation is whole-snapshot retrieval over the repository state at the pull-request commit: the
  corpus is built per repository by merging and de-duplicating chunks over several snapshots, then
  filtered per query to "the documents visible at the corresponding PR or issue state" (Sec. 4.1, p.5).
  Construction step two checks out the commit immediately before the pull request (Sec. 3.2.2, p.4).
- Strong results on code-search benchmarks do not carry over: the best general embedding model drops
  from 71.7/96.9 (Level-1) to 20.3/48.0 (Level-2) and 34.4/41.5 (Level-3), NDCG@10/Recall@100
  (Table 3, p.6).
- A simple supervised fine-tune of the Qwen3-Embedding family on pull-request-derived supervision
  from repositories outside the SWE-bench family roughly doubles Level-2/3 scores (Table 3, p.6;
  data in Appendix B, p.12).
- Rewritten queries often do not help and can hurt (Table 3, Sec. 4.2, p.6).

## What it did not establish

- No evidence that the retrieval gain carries to issue resolution by an agent: the only resolved-rate
  numbers are the annotation-validation reruns (Table 11, p.16), which compare label sets, not retrievers.
- No ablation of the supervision recipe: there is one training recipe, no filtering, weighting or
  curriculum comparison, no data-scale curve, and no seeds or confidence intervals anywhere.
- No hyperparameters for the fine-tune beyond epochs, negatives and loss form (see Method details).
- No statement that the supervised training data is released; the dataset footnote (p.1) refers to the
  benchmark data (the Hugging Face repository lists only Level-2/3 and rewrite folders).
- Level-3 label noise is not measured against humans; Table 11 is the only validation.
- Limitations stated by the authors (p.9): data mostly from SWE-bench-series sources, uneven language
  diversity, no freshness metrics.

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). NDCG@10/Recall@100 in percent.
Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| Level-2 size: repositories / queries / chunks / qrels | 632 / 5,061 / 9,377,120 / 52,712 | Table 1, p.3 |
| Level-2 relevant chunks per query; mean query / chunk length (characters) | 10.42; 1,558.5; 1,004.9 | Table 1, p.3 |
| Level-3 size: repositories / queries / chunks / qrels | 97 / 2,580 / 2,609,581 / 106,479 | Table 1, p.3 |
| Level-3 relevant chunks per query; mean query / chunk length | 41.27; 1,074.4; 1,154.8 | Table 1, p.3 |
| Level-1 size: queries / corpus items | 172,961 / 2,412,296 | Table 1, p.3 |
| Query intent, Level-2: bug / feature | 3,047 / 1,659 | Table 2, p.3 |
| Verified at Level-2: repositories / queries / chunks / qrels / qrels per query | 12 / 432 / 398,397 / 1,173 / 2.72 | Table 8, p.12 |
| Verified at Level-3: queries / chunks / qrels / qrels per query | 302 / 372,258 / 8,928 / 29.56 | Table 8, p.12 |
| BM25 Level-2 average | 13.0 / 38.8 | Table 17, p.19 |
| BM25 Level-3 average | 20.5 / 30.1 | Table 17, p.19 |
| BM25 on Verified, Level-2 and Level-3 | 11.9 / 46.7 and 22.2 / 33.9 | Table 17, p.19 |
| Qwen3-Embedding-8B: Level-1 / Level-2 / Level-3 | 71.7 / 96.9; 20.3 / 48.0; 34.4 / 41.5 | Table 3, p.6 |
| SweRankEmbed-Large: Level-2 / Level-3 | 22.4 / 52.1; 34.4 / 42.4 | Table 3, p.6 |
| CodeRankEmbed: Level-2 / Level-3 | 12.1 / 32.9; 22.5 / 28.6 | Table 3, p.6 |
| Qwen3-0.6B-SFT: Level-2 / Level-3 | 26.5 / 59.4; 44.5 / 54.4 | Table 3, p.6 |
| Qwen3-8B-SFT: Level-2 / Level-3 | 32.8 / 66.4; 50.2 / 61.4 | Table 3, p.6 |
| Qwen3-8B-SFT on Verified: Level-2 / Level-3 | 33.9 / 76.1; 51.1 / 63.3 | Table 17, p.19 |
| Rewrite averages of Qwen3-8B-SFT: Level-2 / Level-3 | 29.2 / 64.0; 44.4 / 57.4 | Table 3, p.6 |
| Training data: repositories / queries / qrels / corpus chunks | 628 / 53,301 / 1,218,875 / 29,171,451 | Table 9, p.12 |
| Training data: qrels per query; mean query / chunk length | 22.87; 375.1; 2,188.4 | Table 9, p.12 |
| Repository-local negatives sampled per query | 64 | Appendix B, p.12 |
| Query filter: raw / kept / removed (leak, meaningless) | 5,550 / 5,061 / 489 (380, 109) | Table 12, p.17 |
| Verified query filter: raw / kept / removed | 500 / 432 / 68 | Table 12, p.17 |
| Level-3 annotation validation on Verified: full agent / Level-3 allowlist / Level-2 allowlist | 73.0 / 69.0 / 62.0 | Table 11, p.16 |
| Same, Multilingual / Pro / Multi-SWE-bench (full / L3 / L2) | 65.0 / 59.0 / 43.0; 46.1 / 43.2 / 36.9; 42.0 / 39.5 / 23.3 | Table 11, p.16 |
| Figure 3 dashed lines (average of the five shown models): Level-3 / Level-2 NDCG@10 | 33.6; 18.4 | Fig. 3, p.6 |
| Spearman correlation of Level-1 average with Level-2 / Level-3 average | 0.64; 0.69 | Fig. 4, p.6 |

## Method details we need

- **Chunking (Sec. 3.2.2, p.4).** Source and documentation files are chunked "with AST and
  LangChain-based splitters", irrelevant file types filtered, "preserving file paths and line spans".
  Mean chunk length at evaluation is 1,004.9 characters (Table 1); the training set has 2,188.4
  (Table 9), so chunk definitions differ between evaluation and training.
- **Level-2 labels.** The patch is aligned to the pre-PR chunks "by matching modified files and edited
  line ranges" (p.4). A positive is therefore any chunk overlapping an edited line range, not only code.
- **Level-3 labels (Sec. 3.2.3, p.5; Algorithm 1, p.14; Table 25, p.27).** A mini-agent reruns each
  task with Qwen3.5-397B-A17B; files opened by `cat`, `grep`, `head`, `sed` are extracted and aligned to
  the Level-2 chunks; each (query, chunk) pair is judged by three votes (two from the open model, one
  from a closed-source model whose version is named in Sec. 3.2.3, p.5). The judge returns a label
  high / partial / irrelevant with score 2 / 1 / 0 and a confidence. Algorithm 1 keeps `c in R_i | score(c) > 0`.
  How the three votes combine into `score(c)` is not stated.
- **Retrieval-corpus construction (Sec. 4.1, p.5).** The evaluator builds a repository-level corpus
  "by merging and deduplicating chunks from different temporal snapshots, while preserving repository
  and commit metadata for each chunk" and filters it per query to the state visible at that PR or issue.
- **Metrics (Appendix D, p.13).** NDCG@10 with gain 2^rel - 1; Recall@100 = |R_q ∩ top-100| / |R_q|.
- **Query rewriting and filtering (Sec. 3.3, Tables 23-24, pp.25-26).** Both stages use Qwen3.5-397B-A17B.
- **SFT data (Sec. 3.4, Appendix B, pp.5, 12).** Pull requests outside the SWE-bench family; the
  repositories are stated to be disjoint from the SWE-bench family. PR description is the query, patch-aligned
  chunks are positives, 64 repository-local negatives are sampled from the same repository. Training
  examples use a 1:8 positive-to-negative ratio, multi-positive InfoNCE
  `L(q) = -log( sum_{d in P} exp(s(q,d)/tau) / sum_{d in P ∪ N} exp(s(q,d)/tau) )`, checkpoints after three epochs.
  No filtering, weighting or ordering step is described.
- **Missing:** learning rate, batch size, temperature value, optimizer, hardware, seeds.
- **Evaluation code** is a modified MTEB (p.5); `data/raw/core_bench_eval/` is the released toolkit.

## Relation to RQ1 / RQ2 / RQ3

- RQ1: Table 17 gives BM25 as the sparse reference (13.0/38.8 at Level-2, which our loader should
  reproduce); there is no signal ablation and no latency column in the paper.
- RQ2: the paper's SFT row is the "RAW" arm in spirit (no filtering step is described), at one budget and
  one seed; it neither supports nor contradicts a claim that filtering or weighting helps.
- RQ3: Table 11 shows Level-3 labels help an agent more than Level-2 labels under an allowlist
  (69.0 vs 62.0 on Verified), which is about label content, not retriever quality.
- Leakage: the training repositories are said to be disjoint from the SWE-bench family (Sec. 3.4),
  which is a repository-level statement for that family only; the Level-2/3 sub-datasets other than
  Verified are separate sources (Table 8).

## Discrepancies

- With the project master document: the Level-2/3 candidate list is not "the whole folder corpus" and is
  not a sample; it is the snapshot at the instance base commit (claim C1 below; data check in
  `results/tables/r1_c1_snapshot_check.json`).
- With the data audit (`PROJECT_STATE.md` Q11): chunk ids and the `{_id, text}` row layout match the released
  files; the paper's statement that metadata is preserved refers to the internal pipeline (the
  Level-3 judge template, Table 25, p.27, shows `file_path`, `start_line`, `end_line`, `language`,
  `chunk_index` fields) and is not in the released corpus.
- Internal: Table 4 (p.7) lists Qwen3-4B-SFT with 92.0 NDCG@10 in the Swift column at Level-2 (Table 19, p.21,
  also 92.0). Swift is 0.2% of Level-2 (Figure 1a, p.3), about ten queries (inference), so the per-language
  Swift cells are not interpretable; Table 3's averages are unaffected.
- Internal: the Abstract says "over 180K queries"; Table 1 gives 172,961 + 5,061 + 2,580 = 180,602 (consistent).

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| C1 per-query filter keeps "documents visible at the PR or issue state"; so the filtered list is the repository snapshot at the base commit | confirmed (text) and supported by data | Sec. 4.1, p.5; Sec. 3.2.2, p.4 | The sentence is in Sec. 4.1, not Appendix D. Measured on 11 instances: all 12,153 list chunks occur in the base-commit snapshot (detail below). |
| C2 chunks keep "file paths and line spans"; released rows are `{_id, text}`; is another file carrying the metadata | text confirmed; no such file | Sec. 3.2.2, p.4; Sec. 4.1, p.5; Table 25, p.27 | The 7,159-entry listing of the dataset repository (the data audit) has only `queries.jsonl`, `corpus.jsonl`, `qrels.jsonl`, `test.tsv`, `manifest.json`, `README.md`, `.gitattributes` and one PDF; no metadata file. |
| C3 Level-3 keep rule `score(c) > 0` in a three-vote ensemble (two open-model votes, one closed-source vote): what is the score, is one positive vote enough | partly confirmed; aggregation not found | Algorithm 1 line 8, p.14; Sec. 3.2.3, p.5; Table 25, p.27 | Per-vote score is 2 / 1 / 0 (high / partial / irrelevant). The paper does not say how three votes become `score(c)`, so whether one positive vote suffices is not stated. The data audit measured score 1 on every row of the released L2 and L3 qrels (52,712 and 106,479 rows), so the released labels are binary and the vote aggregation is not visible in them. |
| C4 SFT set: 628 repositories, 53,301 queries, 64 repository-local negatives, 1:8, multi-positive InfoNCE, three epochs, no filtering step, mean chunk 2,188 characters | confirmed | Table 9, Appendix B, pp.12-13 | The 64 negatives are a pool; batches use a 1:8 ratio. |
| C4 hyperparameters (learning rate, batch size, temperature) in Appendix B | not found | Appendix B, p.12 | Only epochs, negative counts, ratio and loss form are given. |
| C4 release of the SFT data | not found | p.1 footnote, Appendix B | The footnote says the dataset (benchmark) is on Hugging Face; the training set is not mentioned as released. |
| C5 Table 11 L3-allowlist 69.0% vs L2-allowlist 62.0% on Verified | confirmed (numbers) | Table 11, p.16; Sec. 3.2.3, p.5; App. F.2, pp.14-15 | Agent is the mini-agent rerun in a closed allowlist setting (p.5). The model used in the allowlist reruns and the number of instances per cell are not stated. The authors say allowlisted rates can be lower than the full-agent rate and the L3-vs-L2 comparison is the point (p.15). |

### C1 detail: data test (measured, `results/tables/r1_c1_snapshot_check.json`, run `r1-c1-snapshot-check`)

Question: is a query's `filtered_corpus_id` list the repository snapshot at the instance base commit?
Method: for the 11 Verified instances of three repositories in the released Level-2 samples, check out the
base commit (from the SWE-bench Verified metadata), locate every corpus chunk in the snapshot files by
exact text (then stripped text, then line-ending-normalised text), and count (a) list chunks found in the
snapshot, (b) corpus chunks outside the list that also occur in the snapshot, (c) how much of the
snapshot text the list chunks tile. The chunker itself is not released, so the snapshot's chunk count
cannot be recomputed; the test is by location of text.

| Check | Result |
|---|---|
| List chunks located in the snapshot at the base commit | 12,153 of 12,153 (11,793 exact, 6 stripped, 354 after line-ending normalisation, 0 not found) over 11 instances |
| `pallets__flask-5014` (the only Verified flask instance) | list 1,000 = whole folder corpus 1,000; all 1,000 chunks tile 99.2% of the text of the 211 snapshot files of the same extensions |
| `psf__requests` (8 instances, lists 638 to 1,025; folder corpus 2,356) | all list chunks located; the lists tile 96.0% to 97.8% of the snapshot text of those extensions; list sizes differ by instance (638, 787, 795, 831, 902, 1,025, then 645 and 646 for the two highest instance numbers), i.e. each instance has its own snapshot |
| `mwaskom__seaborn` (2 instances, lists 2,425 and 2,459; corpus 2,515) | all located; the lists tile 76% of the text of the snapshot files with those extensions (185 of 275 files have a chunk); the remaining files are not explained by this test |
| Corpus chunks outside the list (11,931 sampled, seed 17) that occur in the snapshot text | 423 (3.5%); 390 of them lie inside regions already covered by list chunks (chunks from other snapshots with shifted boundaries); 33 (0.3% of the sample) lie in regions the list does not cover |
| Data-audit statistics over all 729 Level-2/3 folders | in 312 of the 324 folders with a single query the list equals the folder corpus; in all 405 folders with several queries the longest list is shorter than the folder corpus (median mean-list / corpus = 0.65) |

Reading: the list is the snapshot at the base commit (as the text of Sec. 4.1 says), and the folder corpus is
the union over the snapshots of the folder's instances. Evaluation is therefore whole-snapshot retrieval over
the repository state a coding agent would see, not retrieval from a sampled candidate set. What the data
does not show: that every file of the snapshot is chunked (seaborn: 76%), nor the exact chunk boundaries.
Twelve single-query folders (list / corpus between 0.11 and 0.99 in the data audit statistics) have a list
shorter than the folder corpus; the cause is not examined (17 Level-2 folders merge several repositories).

## Figures looked at

Figure 1a/1b (p.3): language shares match Table text; Figure 1b plots corpus size against qrels per query
per repository, 632 Level-2 and 97 Level-3 points. Figure 2 (p.4): construction pipeline, no numbers.
Figure 3 (p.6): five bars per level, dashed averages 33.6 and 18.4. Figure 4 (p.6): correlations 0.47-0.75.
