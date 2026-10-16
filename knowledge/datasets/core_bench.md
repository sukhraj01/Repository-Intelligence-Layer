# CORE-Bench (Level-2, Level-3, Rewrite variants)

- **URL:** https://huggingface.co/datasets/zhangfw123/CORE-Bench (retrieved 2026-10-17)
- **Licence:** cc-by-nc-sa-4.0 (non-commercial, share-alike). Commit only counts, repository names and derived tables, never dataset text.
- **Paper / code:** arXiv:2606.11864; evaluation code github.com/zhangfw123/CORE-Bench-Eval (commit 5d00cdc, 2026-07-13).
- **Level-1 is not in this package.** The dataset viewer is broken; use the tree API or `hf_hub_download` with patterns, never `load_dataset`.
- **Fetched where:** listing, manifest and card on Ada (login node); samples by Slurm job 24592 on partition `u22`. Raw files live in `~/ril_s2/` on Ada and `data/raw/core_bench/` locally (untracked).

## Size (measured, `results/logs/s2_ground_truth_a_2026-10-17.json`, `results/tables/core_bench_listing_summary.csv`)

| Quantity | Value | Label |
|---|---|---|
| Whole repository | 32,238,633,709 B (32.2 GB) | measured (tree listing); card says 32.2 GB |
| Data files only | 32,237,587,759 B in 4,945 files (1,458 repo folders over 4 levels) | measured |
| L2 + L3 originals | 16,998,825,388 B | measured |
| L2 / L3 / Rewrite-L2 / Rewrite-L3 | 12.48 / 4.52 / 11.59 / 3.65 GB | measured |

The Rewrite folders duplicate the original `corpus.jsonl` and `qrels.jsonl` byte for byte (verified by sha256 on the three sampled repositories; per-dataset corpus byte totals identical between original and Rewrite in the listing). Exception: the Rewrite `SWE-bench_Multilingual` folders (L2 and L3) hold only `queries.jsonl`.

## Counts: card vs paper vs measurement

The dataset ships `manifest.json` with per-repository counts. Summed, it reproduces the card exactly (L2: 632 folders, 5,061 queries, 9,377,120 corpus rows, 52,712 qrels; L3: 97 / 2,580 / 2,609,581 / 106,479; every sub-dataset row of the card table matches). The tree listing gives the same folder counts. So card, manifest and listing agree. The paper's mean chunk lengths (about 1,005 L2, 1,155 L3; unit unstated) are `paper_reported`; our sample mean was 953 characters over 11,031 chunks from three repositories (a sample, not a population estimate).

**"Repos" is not "distinct repositories".** 632 and 97 are counts of folders. Folder names are not uniformly `owner__name`: 143 of 632 L2 folders and 11 of 97 L3 folders contain no `__`. Examples read from the first query id of each folder: Verified `pylint` holds `pylint-dev__pylint-4551`, `pytest` holds `pytest-dev__pytest-*`, `scikit` holds `scikit-learn__scikit-learn-*`, `sphinx` holds `sphinx-doc__sphinx-*`; in SWE-Bench-plus-plus `django` holds `django-helpdesk__django-helpdesk-1289`, `Comfy` holds `Comfy-Org__ComfyUI_frontend-4191`; in Multi-SWE-bench `clap` holds `clap-rs__clap-1624`. The truncation looks like a cut at the first hyphen. Whether two repositories can share one truncated folder has not been checked; the canonical repository must be taken from the query ids, not the folder name.

## Layout and fields (measured on pallets__flask, psf__requests, mwaskom__seaborn at L2, L3, Rewrite-L2)

- Folder = one evaluation split (`test_<folder>` in the eval loader). Files: `corpus.jsonl`, `queries.jsonl`, `qrels.jsonl`, `qrels/test.tsv` (not present in Rewrite folders).
- **corpus row:** exactly `_id`, `text`. `_id` is a random UUID (36 chars, all rows). It encodes no path and no line span, and the chunk text does not start with a file path (a path-like first line appears in 23 of 2,356 requests chunks). Chunks are at most 4,096 characters; many begin mid-function (for example a body starting at `super().__init__(`), so chunks are text windows, not function units.
- **query row:** `_id` (an instance id such as `pallets__flask-5014`), `text` (issue text), `filtered_corpus_id` (list of corpus ids).
- **Rewrite query row:** the same plus `original_text` (equal to the L2 text in 11 of 11 sampled rows), `rewrite_reason`, `content_type`, `description_style`, `intent_type`; `filtered_corpus_id` identical to the original.
- **qrels:** row `{query_id, corpus_id, score}`; `score` is 1 in every sampled row (binary; 19 L2 and 141 L3 sampled rows). `qrels.jsonl` and `qrels/test.tsv` list the same pairs. The manifest reports `positive_qrels == qrels` in every folder, so no zero-score rows exist anywhere.
- **Per-query candidate sets.** The corpus of a folder is the union of the `filtered_corpus_id` lists of its queries (corpus minus union = 0 in all nine sampled folders). Each list is that instance's candidate chunks (19,049 to 25,391 ids per query for django), and every qrel positive lies inside its own query's list. This explains the oversized Verified `queries.jsonl`: 99.85% of the bytes of the django file (173,748,698 B, 188 queries) are the id lists, against 1,282 characters of mean issue text.
- **L2 vs L3 corpora** differ in UUIDs for the same chunk text; the text overlap is complete in the direction L3 into L2 (requests: 1,735 L3 texts all present among 2,356 L2 texts).
- **Positives per query (sample).** L2: 1 to 3 (flask 1; requests 1.62 mean; seaborn 2.5). L3: 8 to 37 (requests mean 17.4; flask 21; seaborn 33). Positive chunks are mostly code starting at a `def`/`class` (heuristic: 11 of 13 for requests L2); L3 adds imports, docs, config-like chunks. The classifier is a crude text heuristic; proper label-quality work is separate.

## Evaluation protocol (read from CORE-Bench-Eval, not run)

- `run_mteb.py` / `run_bm25.py` retrieve over the whole folder corpus, then post-filter each query's ranking to its own `filtered_corpus_id` set before scoring ("filter mode").
- Metrics come from the MTEB retrieval evaluator (`ndcg_at_k`, `recall_at_k`, ...) with the default k list; main score `ndcg_at_10`. A separate collector (`collect_results/collect_core_bench_results.py`) recomputes metrics itself with binary gain (`dcg = sum(hit / log2(rank+1))`, ideal DCG over `min(#gold, k)`), and averages over queries.
- Whether the card's NDCG@10 / Recall@100 are macro over folders or over queries was not established.

## Label provenance (`paper_reported`)

L2 qrels are chunks aligned to the PR patch by modified files and line ranges at the commit before the PR. L3 qrels come from agent browsing trajectories judged by a three-vote LLM ensemble, so L3 labels are not patch-derived. SFT data (628 repositories, 53,301 queries) is described as disjoint from the SWE-bench family; a public release is not stated.

## Open items

Distinct canonical repository set (needs query ids per folder); the L2/L3 ↔ Verified instance mapping; label quality on a sample.
