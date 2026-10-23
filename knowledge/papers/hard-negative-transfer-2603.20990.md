read: full — 15 pages incl. appendices, PDF v5, pdftotext -layout (poppler); the paper has tables only and no figures, 2026-10-23

# What Tracks Hard-Negative Transfer? — Sinha, Seetharaman and Bansal (arXiv 2603.20990v5, 2026), "What Tracks Hard-Negative Transfer? A Study of Lexical and Semantic Signals"

Source file: arXiv PDF v5 (dated 14 Oct 2026; highest version that resolves), 15 pages: body pp.1-8, references pp.8-10, appendices A-D pp.10-15 (full-file scores, definitions and proofs, robustness checks, the generation prompt). The extracted text has 15 pages and no blank page. Found by the refreshed scan of 2026-10-23 (latest revision after the earlier scan). Text retrieval (MS MARCO training, BEIR evaluation), not code. Read because it compares **negative sources** (BM25-mined, dense-mined, synthetic negatives written by a language model, and hybrids) at fixed training settings and tests whether training-free statistics, including a frozen-encoder "does the encoder prefer the positive" score close in spirit to K-rank, can tell good supervision from false-negative-shaped supervision.

## What it established

- With about 400,000 MS MARCO query-positive pairs, ten negatives per query and one epoch, the transfer ordering on eleven BEIR sets was synthetic > dense-mined > BM25-mined negatives for all three backbones tried (two 110M encoders and a 66M one); mean nDCG@10 gaps LLM minus BM25 of 0.048, 0.027 and 0.085 (Sec. 5.1, p.4; Table 1, p.5).
- A training-free lexical statistic (one minus the IDF-weighted share of query tokens found in the negative) reproduced every complete source ordering; frozen-encoder statistics (the two-document probability of the positive over the negative; positive-negative locality; inversion rate) reproduced none of them, and adding them to the lexical statistic did not improve agreement (Table 4, p.6; Sec. 5.2, p.4).
- "Hardness" proxies (loss proxy, share of records with any negative ranked above the positive) picked the dense or BM25+dense source as hardest, not the best-transferring one (Sec. 5.1, p.4; Table 3, p.6).
- Constructed controls fool the statistics: random passages and a **false-negative-shaped control (other queries' positives near the target positive)** score as well as or better than every genuine source on the combined statistic; on one backbone the false-negative-shaped control ranks first of fourteen (Table 5 and Sec. 6.1, p.7). Only one of 36 backbone-weighting cells ranked all eight controls below all six genuine sources (Sec. 6.2, p.7).
- Among BM25-mined negatives, 89.6% have high query-token coverage (at least half the IDF mass) against 38.0% for synthetic ones; the frozen encoder already prefers the negative over the labeled positive for 16.8% of BM25, 33.5% of dense and 2.1% of LLM negatives (p.6; Table 10, p.15).

## What it did not establish

- One fine-tuning run per source and backbone; no seeds or intervals (Sec. 3.2, p.3; Limitations, p.8). The orderings are two orderings repeated over three backbones on shared data, not six independent results (the paper says so, p.4).
- No human relevance judgments; the false-negative controls are constructed, not verified false negatives (p.2, p.8).
- Source composition and training volume both differ between the individual (K = 10) and hybrid (K = 20) settings, so hybrids are compared only among themselves (p.2).
- Nothing about code, repositories or several positives per query (the first positive is used, p.3).

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| Training pairs / negatives per query (individual sources) / epochs | about 400,000 / 10 / one epoch | p.1; Sec. 3.1-3.2, pp.2-3 |
| Effective batch size / temperature | 4096 / 0.05 | Sec. 3.2, p.3 |
| BEIR datasets / backbones | eleven / three | Abstract, p.1 |
| Mean nDCG@10 gap, synthetic over BM25-mined negatives, three backbones | 0.048, 0.027, 0.085 | Sec. 5.1, p.4 |
| Mean nDCG@10 gap, synthetic over dense-mined negatives | 0.019, 0.014, 0.037 | Sec. 5.1, p.4 |
| Mean nDCG@10, E5-base backbone: BM25 / dense / LLM negatives | 0.452 / 0.465 / 0.479 | Table 1, p.5 |
| Block orderings recovered: lexical statistic / positive-preference statistic | 6/6 / 0/6 | Table 4, p.6 |
| Negatives with high query-token coverage: BM25 / dense / LLM | 89.6% / 69.3% / 38.0% | p.6 |
| Negatives the frozen encoder ranks above the positive: BM25 / dense / LLM | 16.8% / 33.5% / 2.1% | p.6; Table 10, p.15 |
| Backbone-weighting cells that rank all controls below all genuine sources | one of thirty-six | Sec. 6.2, p.7 |
| Lexical-matched resampling: negatives kept per source / repetitions | 115,869 (46.35%) / 100 | p.5 |

## Method details we need

- **Statistics** (Sec. 4.1, p.3): lexical residuality ψ = 1 − IDF-weighted query-token coverage by the negative; ρ = σ((u·v⁺ − u·v⁻)/τ) under a frozen encoder (the two-document probability of the positive, i.e. a per-negative version of "does a frozen model rank the positive above this negative"); η = σ((v⁺·v⁻ − u·v⁻)/τ).
- **Controls** (Sec. 6.1, p.7): random passages; shuffled negatives; half the negatives replaced by the record's own positive; negatives replaced by another query's positive chosen for closeness to the target positive (false-negative-shaped); BM25 sources diluted 25-100% with random passages.

## Relation to RQ1 / RQ2 / RQ3

- RQ1: none.
- RQ2 (negative policy and the quality signal):
  - A second independent result, after `nv-retriever-2407.15831.md`, in which BM25-mined negatives transfer worst among the mined sources. For code, the project's repository-local random negatives (CORE-Bench) and teacher-mined negatives (SweRank) are the two policies on the table; this paper does not test random negatives but shows the mining source alone moves transfer by up to 0.085 nDCG at fixed volume.
  - Caution for FILTER and WEIGHT: a frozen-encoder preference score (ρ, the per-negative relative of K-rank) failed to order negative sources by transfer and was fooled by false-negative-shaped controls. This does not test K-rank as a filter on positives, but it is evidence that frozen-encoder agreement and supervision validity are different things; a K-rank-filtered pool should be audited for false negatives by an independent check, not by the same teacher.
- RQ3: none.

## Discrepancies

- None with the project documents (not cited there). Internal: the abstract's "reproduces the aggregate transfer ordering in all six backbone and setting blocks" is consistent with Table 4 (6/6); the paper itself stresses that the six blocks are not independent (p.4).

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| Harder negatives transfer better | contradicted in this setting | Table 3, p.6; p.4 | hardness proxies pick a lower-transfer source |
| Frozen-encoder statistics can screen false negatives | not supported for the tested statistics | Sec. 6, p.7 | the paper limits this to its tested weightings |
| BM25-mined negatives are a weak source | confirmed here (one run per cell) | Table 1, p.5 | consistent with `nv-retriever-2407.15831.md` Table 1 |
