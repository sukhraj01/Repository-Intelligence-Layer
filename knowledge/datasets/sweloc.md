# SweLoc (SweRank training data)

**Status (2026-10-17): no dataset named SweLoc is published; one undocumented candidate exists.**

## Checks, all run from Ada

| Check | Result |
|---|---|
| HF dataset search `SweLoc`, `sweloc`, `swe-loc` (name match) | no SweLoc dataset (`swe-loc` returns unrelated localisation sets) |
| HF dataset search `swerank`, `SweRank` | one hit, `swe-ranking-agent/eval_agent`, not a training set |
| HF datasets by author `Salesforce`, search `swe` | none |
| HF models `swerank` | SweRankEmbed-Small/Large, SweRankLLM-Small/Large (Salesforce) plus third-party derivatives |
| GitHub `gangiswag/SweRank` (now `SalesforceAIResearch/SweRank`, last push 2026-06-02) | README describes collecting SweLoc ("Python repositories", "heavily based on SWE-Bench") and links only the Lite and Loc-Bench eval data (Google Drive); says the retriever training script is not included. Open issues #5 (script for processed eval sets) and #6 (Large version); closed #3 "When can the model be released?" and #4 "Missing build_dataset.py". No releases. |
| SweRank+ (arXiv:2512.20482) | abstract: trained on "a carefully curated large-scale issue localization dataset spanning multiple popular programming languages" (the multilingual size and release statement from earlier notes were not re-read here) |

## Candidate: `gangiswag/train_data`

- Dataset repo by the SweRank first author, created 2025-09-23, 11 downloads at the time of check, **no dataset card**, three zip files: `train.zip` (23,561,667,819 B), `retrieval_dataset_creation.zip` (1,859,314,046 B), `swe_bench_verified.zip` (634,692,547 B). Listed through the zip central directories with range requests; nothing was downloaded beyond three small instances.
- `train.zip` (measured): 56,279 instances in 10 language folders (python 24,285; rust 5,879; java 5,518; php 4,591; ruby 4,244; typescript 3,882; go 2,985; cpp 2,359; javascript 1,513; c 1,023), 149.4 GB uncompressed. 56,279 equals the PR count `paper_reported` for the multilingual extension; directory names give 4,049 distinct `owner__name` strings against 4,060 repositories reported there.
- Layout: `train/<language>/<owner>__<name>-<PR>/{corpus.jsonl, queries.jsonl, qrels/test.tsv}` (BEIR style, one instance per directory; python corpora sum to 24.7 GB uncompressed).
- Sample (3 python instances): corpus row `{_id, title, text, metadata}` with `_id` = `<path>/<Class>/<function>` (function level), text = `_id` + newline + code; query `{_id, text, metadata}` with `metadata` carrying `repo` (`owner/name`) and `base_commit`; qrels binary score 1 on changed functions.
- **Unresolved:** whether the python subfolder is the SweLoc of the SweRank paper or a different (multilingual) set; the card is absent and the SweRank paper was not read in full. Because of the `repo` metadata a repository-level filter is feasible. Not downloaded in full (python subset would be about 24.7 GB of corpora).

## Candidate against the held-out list (measured, S4, job 24604; provisional, Q7 unresolved)

The candidate's python instance directory names were read from the already-fetched zip central directory (no further download): 24,285 instance directories over 2,448 distinct `owner/name` repositories (names taken from the `owner__name-<PR>` directory names, not from the `repo` metadata field, which was only sampled). Against the held-out list (605 repositories): 89 held-out repositories occur, 3,431 instances (14.13%) dropped, 20,854 instances (85.87%) and 2,359 repositories (96.36%) survive. The largest dropped repositories by instances (up to 140 each) are listed in the pool report. None of the 169 Loc-Bench V0.2 repositories outside the list occurs in this candidate. Of 10 surviving repositories sharing a name with a held-out one, all 10 were looked up on GitHub and 3 resolve to a held-out repository under its current name (54 instances: `airtai/faststream`, `jazzband/django-dbbackup`, `lepture/authlib`); none is a fork. This is a survival measurement on an unconfirmed candidate; it says nothing about whether the candidate is the intended pool. Report: `data/held_out/pool_filter_report_gangiswag_train_data_python.md`.

## Collection recipe (read from the repository, not run)

`src/collect/collect_data.sh`: top PyPI packages scraped (selenium, hugovk top-pypi-packages page) → GitHub URL → `owner/name` list → merged PRs that reference an issue (keywords close/fix/resolve), with patch and, if present, test patch (`build_dataset.py`: `is_valid_pull`, `is_valid_instance`, `has_test_patch`) → `SWE_PRS_FT_DATASET.jsonl` (500 lines per repo max, `test_patch` removed). GitHub token required (`GITHUB_TOKEN`; `GITHUB_TOKENS` for parallel); the client sleeps five minutes on rate-limit exhaustion. `--cutoff_date` exists. `get_train_by_repo.py` clones each repository at `base_commit`, extracts all Python functions, positives = functions changed by the patch (existing, not newly added), negatives = every other function. `repo_negative_mining.py` ranks each instance's functions with `cornstack/CodeRankEmbed` (dot product, max length 1024); `filter_dataset.py` keeps instances whose positive rank is 0 to 10 and keeps only negatives ranked 3 to 25. So the quality signal in the published recipe is a separately pretrained encoder's rank of the positive. Script drift: the README names `negative_mining.sh`, the file is `src/run_negative_mining.sh`; `get_valid_urls.py` ignores its own arguments.

## Pool check of the candidate (E-POOL-CHECK, 2026-10-18; counts in `results/tables/x_pool_check_*.csv`)

Queries and qrels of all 24,285 python instance directories read by one range request each; corpus of a seeded sample of 300. Each directory holds one query (`_id`, `text`, `metadata` with only `repo` and `base_commit`: no creation date, no rank, no score field) and a qrels file whose rows all carry score 1. `qrel_rows_total` is 307,996 (mean 12.68 positives per directory, median 4, 95th percentile 42, maximum 3,924, none with zero), not the 49,973 instances of the SweRank+ table for the Python row. The corpus of a directory is the repository's function list at the base commit (sample: median 410 functions, mean 1,047, range 24 to 15,584; every positive id found in its corpus, 2,765 of 2,765; function ids unique within a corpus). Overlap of (repository, PR number): 60 pairs with CORE-Bench L2 (56 SWE-bench-Live, 4 SWE-Bench-plus-plus; 18 repositories, all on the held-out list), none with Verified (0 of 500, also none by base commit), none with L3, none with the other L2 sub-datasets; the Pro ids carry no PR number and cannot be compared.

## Teacher ranks and filter state (E-POOL-RANKS, 2026-10-25)

Ranks of 1,522 positives of 160 sampled directories under SweRankEmbed-Small, CodeRankEmbed and BM25 (`docs/EXPERIMENTS.md`, E-POOL-RANKS):
the qrels are not consistency-filtered per positive (about 39% of positives outside the SweRankEmbed-Small top 40), while every sampled
directory has a positive in that model's top 10, against 19% of the authors' never-filtered Verified export; whether that reflects a
PR-level filter or the model's fit to these PRs is open. Corpus rows store `<id>\n<code>`; 43 of the 500 Verified-export directories have no
qrels file. No positive lies in a test file.

