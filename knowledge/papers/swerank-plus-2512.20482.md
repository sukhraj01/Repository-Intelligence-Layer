read: full — 11 pages incl. appendices, PDF v1, pdftotext -layout (poppler) plus page rasters of Table 1 and Figure 3, 2026-10-17

# SweRank+ — Gangi Reddy, Liu et al. (arXiv 2512.20482v1, 23 Dec 2025)

Source file: arXiv PDF v1, 11 pages (body 9, references pp. 9-10, two instruction templates p.11; there is
no separate appendix). The extracted text has 11 pages, none blank. Footnote 1 on p.1 says code and models
"will be released" (future tense).

## What it established

- A multilingual extension of SweRank: SweLocMulti, a training set over ten languages, and SweRankEmbedMulti /
  SweRankLLMMulti trained on it, plus SweRankAgent, a multi-turn search loop that calls the retriever and
  reranker as a tool (Sec. 3-4, pp.3-5).
- Table 1 (p.3) gives repositories, pull requests and training instances per language. The Python row is
  2,448 repositories, 24,285 PRs and 49,973 instances; all languages 4,060 / 56,279 / 155,663.
- An "instance" is a (issue query, one modified function) pair: "modified functions in the corresponding PR
  [are] treated as positive examples" (Sec. 3.1, p.3), so instances per PR is about 2.06 for Python
  (49,973 / 24,285, our arithmetic).
- Collection filters: repositories with at least 40% code in the target language, more than 1,000 stars and at
  least one commit in the preceding six months; PRs linked to an issue that modify test files (Sec. 3.1, p.3).
- Consistency filter: keep an instance only if the positive ranks within the top-40 functions of the repository
  under SweRankEmbed-Small (Sec. 3.1, p.3-4).
- Multilingual training also improves Python benchmarks over the Python-only model (Table 2, p.6).
- Multi-turn search improves function Acc@10 on all five benchmarks (Table 4, p.7); naive query
  reformulation does not.

## What it did not establish

- Whether repositories from the evaluation benchmarks (SWE-bench Lite, Loc-Bench, SWE-bench Verified,
  SWE-PolyBench, SWE-bench Multilingual, Multi-SWE-bench) were excluded from SweLocMulti: no statement of
  exclusion, de-duplication or decontamination appears anywhere in the paper (searched the whole text).
  SweRank (the earlier paper) did state such an exclusion for its own pool.
- Whether Table 1's instance counts are before or after the top-40 filter: the caption says "training
  instances", the filter is described in Sec. 3.1, and nothing states the order.
- Whether the Python row is the SweLoc pool of the earlier paper: the earlier paper reports 3387
  repositories at an 80% Python threshold; this row has 2,448 at 40%, and the paper says it extends "the data
  collection and filtering pipeline" without relating the counts.
- Training hyperparameters (learning rate, epochs, batch size): none given.
- Release of data or models (future tense only).

## Numbers we may quote

Values are `paper_reported`. Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| Python row: repositories / PRs / instances | 2448 / 24285 / 49973 | Table 1, p.3 |
| All languages: repositories / PRs / instances | 4060 / 56279 / 155663 | Table 1, p.3 |
| Languages in the dataset | 10 | Sec. 1, p.2 |
| Repository filter: minimum share of the language; stars | 40%; 1,000 | Sec. 3.1, p.3 |
| Consistency filter rank | 40 | Sec. 3.1, p.4 |
| Retriever initialisation sizes (Qwen3-Embedding) | 0.6B; 8B | Sec. 5.2.1, p.6 |
| Retriever candidates passed to the reranker; reformulated queries | 100; five | Sec. 5.3.1, p.7 |
| Verified function Acc@5 / Acc@10: SweRankEmbed-Small | 59.74 / 68.49 | Table 2, p.6 |
| Verified function Acc@5 / Acc@10: SweRankEmbedMulti-Small | 64.99 / 71.77 | Table 2, p.6 |
| Verified function Acc@10: SweRankEmbedPython-Small / SweRankEmbedPython-Large | 71.12; 75.05 | Table 2, p.6 |
| Verified function Acc@10: SweRankEmbed-Large / SweRankEmbedMulti-Large | 74.18; 76.37 | Table 2, p.6 |
| Verified function Acc@10 with reranker: SweRankLLMMulti-Small / SweRankLLMMulti-Large | 79.43; 81.18 | Table 3, p.6 |
| Verified Acc@10, single query vs multi-turn agent | 79.43; 81.74 | Table 4, p.7 |
| SWE-Bench-Lite Acc@10 single query vs multi-turn agent | 85.77; 88.32 | Table 4, p.7 |
| Multilingual benchmarks Acc@10 single query vs agent: SWE-PolyBench / SWE-Bench-Multilingual | 59.54; 62.63 / 66.67; 73.08 | Table 4, p.7 |

## Method details we need

- **Pipeline (pp.3-4).** Per language: popular repositories, PRs linked to issues that modify tests, query =
  issue text, positives = modified functions, consistency filtering and hard-negative mining "from SweRank"
  (Suresh et al. 2024, the CoRNStack paper), InfoNCE "identical to SweRankEmbed's training objective".
- **Function extraction at evaluation (Sec. 5.1, p.5).** Tree-sitter extracts all functions of the codebase as the
  candidate corpus; functions modified in the PR are positives.
- **Models (p.6).** Small and large retrievers initialised from Qwen3-Embedding 0.6B and 8B; rerankers from
  CodeRankLLM (7B) and Qwen-2.5-32B-Instruct.
- **SweRankAgent (Sec. 4, p.4-5).** Search, reasoning, reformulation, aggregate; the tool returns the top-10
  after reranking the top-100; the agent's model is a closed-source model named on p.7.

## Relation to RQ1 / RQ2 / RQ3

- RQ2: the public pool the project located (`gangiswag/train_data`, Python part) matches this paper's Table 1
  Python row in repositories and PR directories (the data audit measurement); the pool is SweLocMulti's Python part,
  not the original SweLoc (see Claims checked, S2).
- RQ2: the top-40 filter (here) vs top-20 (earlier paper) shows the filter threshold varies between the same
  authors' releases with no ablation in this paper.
- Leakage: a pool with no stated exclusion of benchmark repositories needs the project's own repository-level
  filter; the data audit measured 89 held-out repositories in the Python pool. This note does not repeat that number
  as a paper claim.
- RQ3: an agent loop over a fixed retriever improves localization by 2.3 points on Verified (Table 4); it
  localizes, it does not resolve issues.

## Discrepancies

- With the earlier reading of the pool: the earlier table called 24,285 and 56,279 "instances"; in this paper they are PRs
  (Table 1 headers), and an instance is a function-level pair (49,973 for Python).
- With the earlier paper: pool filters differ (80% Python vs 40% language; 3387 vs 2,448 repositories; top-20
  vs top-40) and the instance definition is the same.

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| S2 Table 1 Python row: 2,448 repositories, 24,285 PRs, 49,973 instances | confirmed | Table 1, p.3 | Matches the data audit measurement of `gangiswag/train_data` python (24,285 directories, 2,448 repositories). Total row 56,279 PRs matches the 56,279 directories the data audit counted over all languages. |
| S2 so the candidate pool is SweLocMulti's Python part, not the original SweLoc | supported | Table 1, p.3; Sec. 3.1, p.3 | Counts match exactly; the paper states SweLocMulti "extends" SweLoc, and the original reports 3387 repositories. Whether the released Python part is the whole old SweLoc plus extra repositories is not stated. |
| S2 filter: positive in the top 40 under SweRankEmbed-Small | confirmed | Sec. 3.1, pp.3-4 | |
| S2 repositories at least 40% language, more than 1,000 stars, commit in the last six months | confirmed | Sec. 3.1, p.3 | |
| S2 does the paper say SWE-bench or Loc-Bench repositories were excluded | not found | whole paper | The evaluation sets include Verified, Lite and Loc-Bench (Sec. 5.1, p.5). |
| S2 what an instance is | found | Sec. 3.1, p.3 | One modified function with its issue text. 49,973 / 24,285 = 2.06 per PR. |
| S2 are the 24,285 before or after the top-40 filter | not found | Table 1 caption, Sec. 3.1 | The caption says "training instances". The filter is defined per instance, so the 24,285 PRs are post-filter only if PRs left with no surviving instance were dropped; the paper does not say. |

## Figures looked at

Table 1 (p.3, rasterized): all numbers match the extracted text; sums check (56,279 PRs, 155,663 instances).
Figure 3 (p.7): bar chart of language-wise function Acc@10, no numbers in text; not quoted.
