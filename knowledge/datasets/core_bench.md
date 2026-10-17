# CORE-Bench (Level-2, Level-3, Rewrite variants)

Labels: **measured** = produced by a run with a log in `results/logs/` and a row in `RESULTS.md`
(S2 = `s2_ground_truth_a_2026-10-17.json`, S4 = `s4_ground_truth_b_2026-10-17.json`);
**paper_reported** = quoted from the paper or the dataset card and not checked unless a measured value is given beside it.

- **URL:** https://huggingface.co/datasets/zhangfw123/CORE-Bench (retrieved 2026-10-17)
- **Licence:** cc-by-nc-sa-4.0 (non-commercial, share-alike). Commit only counts, repository names and derived tables, never dataset text.
- **Paper / code:** arXiv:2606.11864 (v3, paper_reported); evaluation code github.com/zhangfw123/CORE-Bench-Eval (commit 5d00cdc, 2026-07-13).
- **Level-1 is not in this package.** The dataset viewer is broken; use the tree API or `hf_hub_download` with patterns, never `load_dataset`.
- **Fetched where:** listing, manifest and card on Ada (login node). Samples (S2) by Slurm job 24592; instance ids, corpus statistics and query statistics (S4) streamed on Ada by jobs 24595, 24596, 24605/24606, nothing stored except numbers and ids. Raw files live in `~/ril_s2/` on Ada and `data/raw/core_bench/` locally (untracked).

## Size (measured, S2)

| Quantity | Value |
|---|---|
| Whole repository | 32,238,633,709 B (32.2 GB); card says 32.2 GB |
| Data files only | 32,237,587,759 B in 4,945 files (1,458 repo folders over 4 levels) |
| L2 + L3 originals | 16,998,825,388 B |
| L2 / L3 / Rewrite-L2 / Rewrite-L3 | 12.48 / 4.52 / 11.59 / 3.65 GB |

## Card vs paper vs measured (S4, table `results/tables/core_bench_card_vs_measured.csv`)

Every card statistic was re-measured from the file bytes (rows of `queries.jsonl`, `corpus.jsonl`, `qrels.jsonl`, all 729 L2/L3 folders). The card (a table in the dataset README, identical to the paper's figures where the paper states them) and the measurement agree on every row except the meaning of "repos".

| Statistic | Card | Paper | Measured |
|---|---|---|---|
| L2 "repos" | 632 | not stated separately | 632 **folders**, **605 distinct repositories** |
| L3 "repos" | 97 | not stated separately | 97 folders, **92 distinct repositories** |
| L2 queries / corpus chunks / qrels | 5,061 / 9,377,120 / 52,712 | same | 5,061 / 9,377,120 / 52,712 |
| L3 queries / corpus chunks / qrels | 2,580 / 2,609,581 / 106,479 | same | 2,580 / 2,609,581 / 106,479 |
| Rels per query L2 / L3 | 10.42 / 41.27 | same | 10.42 / 41.27 |
| Mean chunk length L2 / L3 | 1,004.9 / 1,154.8 | about 1,005 / 1,155 (unit not stated) | 1,004.9 / 1,154.8 **characters** |
| Mean query length L2 / L3 | 1,558.5 / 1,074.4 | not stated | 1,558.5 / 1,074.4 characters |
| Per sub-dataset queries, chunks, qrels (11 rows) | see card | not stated | all 11 rows identical |
| Per sub-dataset "repos" (e.g. SWE-bench Live 209, Multi-SWE-bench 35, SWE-Bench++ 319) | folder counts | not stated | folders match; distinct repositories 213, 39, 338 |
| SFT set: repositories / queries | not in the package | 628 / 53,301 | not measurable (data not released) |
| BM25 nDCG@10 / Recall@100 on L2 | 13.0 / 38.8 | same | **13.00 / 38.82** (pilot E1, 5,061 queries): mean over the 7 sub-datasets of the mean over folders; mean over queries is 13.28 / 36.27 |

Other measured facts (S4):

- Every query has at least one positive (0 queries without qrels); every qrels `score` is 1 (binary) in all 729 folders.
- Corpus ids: 11,986,701 rows (= 9,377,120 + 2,609,581), all 36-character UUIDs, all distinct within a folder, no malformed rows.
- **Chunk size is not capped at 4,096 characters.** The S2 sample (three small repositories) showed at most 4,096; across the whole corpus the longest chunk is 1,009,865 characters (a SWE-Bench++ folder of the lablup organisation; the next ones are 977,475, 898,571, 835,423, 817,424). Chunks are text windows of very different sizes, and the mean (about 1,000) hides a heavy tail.
- **Per-query candidate lists** (`filtered_corpus_id`): mean 9,783 ids per query in L2 and 11,391 in L3, minimum 32, maximum 348,310 (L2) / 139,977 (L3). Candidate lists are 99.85% of the bytes of the django Verified `queries.jsonl` (S2).
- **Rewrite qrels are not always identical to the originals.** Rewrite query id sets equal the originals in all 729 folders (283 folders list them in a different order). The 81 Rewrite `SWE-bench_Multilingual` folders (41 L2, 40 L3) contain no qrels file; 13 other Rewrite folders hold fewer qrels rows than their original (158 rows fewer in all; largest differences `ponyc` L3 42, `mypy` L2 25, `tox` L2 22). The card says Rewrite variants share qrels with the originals.

## Repository naming (measured, S4; list in `data/held_out/held_out_repos.json`, per-folder table in `results/tables/core_bench_folder_repos.csv`)

- **Folder names are truncated and are not repository names.** 143 of 632 L2 folders and 11 of 97 L3 folders contain no `__`; 242 L2 and 17 L3 folders do not equal the repository they hold. The canonical repository of a folder was read from the instance ids in its `queries.jsonl` (`owner__name-<PR>`, and `instance_owner__name-<hash>[-v<hash>]` in the Pro split): all 1,458 folders resolved, none was guessed.
- Examples: folder `KhronosGroup__Vulkan` holds `KhronosGroup/Vulkan-ValidationLayers`; `django` holds `django-guardian/django-guardian` and `django-json-api/django-rest-framework-json-api`; `open` holds seven repositories of three owners.
- **One folder can hold several repositories:** 17 L2 and 2 L3 folders (L2: 2 Multi-SWE-bench, 12 SWE-Bench++, 3 SWE-bench Live).
- **One repository can sit in several folders:** three SWE-bench Live repositories exist as two case-variant folders each (`Flexget__Flexget` / `flexget__flexget`, `Kozea__WeasyPrint` / `kozea__weasyprint`, `PyPSA__PyPSA` / `pypsa__pypsa`). These collide on case-insensitive file systems (a laptop copy of per-folder files loses them), so derived files are kept as one JSON keyed by path.
- Distinct canonical repositories (case-folded `owner/name`): L2 605, L3 92; L3 is wholly inside L2; the 12 SWE-bench Verified repositories are inside both. Rewrite datasets have exactly the repository sets of their originals.
- Per dataset (distinct repositories): L2 Multi-SWE-bench 39, SWE-Bench++ 338, SWE-bench Live 213, SWE-bench+ 6, Multilingual 41, Pro 10, Verified 12; L3 Multi-SWE-bench 39, Multilingual 40, Pro 10, Verified 12.

## Layout and fields (measured, S2, on pallets__flask, psf__requests, mwaskom__seaborn at L2, L3, Rewrite-L2)

- Folder = one evaluation split (`test_<folder>` in the eval loader). Files: `corpus.jsonl`, `queries.jsonl`, `qrels.jsonl`, `qrels/test.tsv` (not present in Rewrite folders).
- **corpus row:** exactly `_id`, `text`. `_id` is a random UUID. It encodes no path and no line span, and the chunk text does not start with a file path. Many chunks begin mid-function, so chunks are text windows, not function units.
- **query row:** `_id` (an instance id such as `pallets__flask-5014`), `text` (issue text), `filtered_corpus_id` (list of corpus ids).
- **Rewrite query row:** the same plus `original_text`, `rewrite_reason`, `content_type`, `description_style`, `intent_type`; `filtered_corpus_id` identical to the original.
- **qrels:** row `{query_id, corpus_id, score}`; `qrels.jsonl` and `qrels/test.tsv` list the same pairs.
- **Per-query candidate sets.** The corpus of a folder is the union of its queries' `filtered_corpus_id` lists (corpus minus union = 0 in the nine sampled folders). Every qrel positive lies inside its own query's list.
- **L2 vs L3 corpora** differ in UUIDs for the same chunk text; text overlap is complete in the direction L3 into L2 on the sample.

## Instance overlap and paired n (measured, S4, `results/tables/paired_n.json`)

| Quantity | n |
|---|---|
| L2 `SWE-bench_Verified` queries that are SWE-bench Verified `instance_id`s | 432 of 500 |
| L3 `SWE-bench_Verified` queries that are Verified `instance_id`s | 302 of 500 |
| In both L2 and L3 Verified | 302 (all L3 Verified instances are also in L2 Verified) |
| Query ids absent from the Verified metadata | 0 |
| All datasets: distinct instance ids L2 / L3 / both | 5,035 / 2,567 / 2,567 (rows 5,061 / 2,580: 26 ids occur in more than one L2 dataset; L3 has 13 surplus rows) |

Per repository (Verified / L2 / L3 / both): astropy 22/22/11/11, django 231/188/136/136, matplotlib 34/32/24/24, seaborn 2/2/1/1, flask 1/1/1/1, requests 8/8/5/5, xarray 22/18/13/13, pylint 10/9/3/3, pytest 19/15/10/10, scikit-learn 32/26/21/21, sphinx 44/42/26/26, sympy 75/69/51/51.

## Label quality: observations (S4, `results/tables/label_quality_sample.json`; not a quality verdict)

- Method: L2 `SWE-bench_Verified` instances of six repositories (pallets/flask, psf/requests, mwaskom/seaborn, pydata/xarray, matplotlib/matplotlib, astropy/astropy; 83 L2 instances in total). Seeded sample (seed 0) of 30 instances (astropy 7, matplotlib 15, seaborn 1, requests 4, xarray 3; flask was not drawn), 53 positive chunks. Chunk text was classified on the cluster with a crude line-ratio heuristic (imports >= 60% of lines, comments >= 60%, test markers, config key/section lines, rst markers, else code); only counts left the cluster.
- Result: 50 of 53 positives classed as code, 3 as import blocks (matplotlib 1, seaborn 1, requests 1); 0 docs, 0 comments, 0 test, 0 config. 35 of 53 positive chunks start at a `def`/`class` line, 18 start elsewhere (mid-unit windows). Mean positive chunk length 1,932 characters (the corpus mean is about 1,000).
- Single vs multiple positives: sample 17 instances with one positive, 13 with several; population of the six repositories 44 single, 39 multiple (of 83).
- What the heuristic cannot see: whether a positive code chunk is the edited code or a window that merely overlaps the patch's line range (a docstring, a comment inside a function, an untouched neighbour), and whether other chunks that would fix the issue are labelled negative. Positives are assigned by overlap of file and line range with the PR patch (paper_reported), so the false-negative question is untested here.
- L3 (paper_reported): "L3 qrels come from agent browsing trajectories judged by a three-vote LLM ensemble", so L3 labels are model judgements of usefulness, not patch-derived, and they include context chunks (imports, docs, config) by design. Measured: 41.27 positives per query against 10.42 in L2.

## Evaluation protocol (read from CORE-Bench-Eval, not run)

- `run_mteb.py` / `run_bm25.py` retrieve over the whole folder corpus, then post-filter each query's ranking to its own `filtered_corpus_id` set before scoring ("filter mode").
- Metrics come from the MTEB retrieval evaluator (`ndcg_at_k`, `recall_at_k`, ...) with the default k list; main score `ndcg_at_10`. A separate collector (`collect_results/collect_core_bench_results.py`) recomputes metrics with binary gain and averages over queries.
- The card's NDCG@10 / Recall@100 are averages over folders (L2: over the seven sub-datasets, each the mean of its folders), not over queries; measured by pilot E1, which reproduces 13.0 / 38.8 and the Verified rows 11.9 / 46.7 and 22.2 / 33.9 this way (`docs/EXPERIMENTS.md` E-BM25-REPRO). 1,676 of the 52,712 L2 qrels rows repeat a (query, chunk) pair, leaving 51,036 distinct positives.

## Label provenance (paper_reported)

L2 qrels are chunks aligned to the PR patch by modified files and line ranges at the commit before the PR. L3 qrels come from agent browsing trajectories judged by a three-vote LLM ensemble. SFT data (628 repositories, 53,301 queries) is described as disjoint from the SWE-bench family; a public release is not stated.

## Chunk-to-unit mapping on the Verified samples (pilot M, measured 2026-10-17; exploratory)

- Method: for each Verified instance of pallets/flask, psf/requests and mwaskom/seaborn in the L2 and L3 sample folders (11 instances; L3 holds 7 of them), the base commit was checked out and each positive chunk's text located in the files (exact, trimmed, line endings, collapsed whitespace), then its line span mapped to the frozen units. Run on Ada; `results/tables/m_*.csv`, `results/logs/m_chunk_unit_reach_2026-10-17.json`. Counts only are stored (licence).
- Match: 160 of 160 positives (19 L2, 141 L3) found by exact text at one location each.
- Spans against the frozen units: one function or method 118, several 21, class only 5, residual lines only 16 (10.0%).
- L3 positives by kind (141): method 101, function 12, class 5, module residual 13, test unit 10, documentation or configuration 0. L3 labels (judged, paper_reported) are therefore code units in this sample; 12 of the 141 are text-identical to an L2 positive and 15 map to an L2 unit.
- Of the 19 L2 positives, 3 map to residual lines only (imports and module-level code).
