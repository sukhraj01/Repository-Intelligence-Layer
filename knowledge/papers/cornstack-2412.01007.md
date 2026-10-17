read: full — 18 pages incl. appendices, PDF v3, pdftotext -layout (poppler), 2026-10-17

# CoRNStack — Suresh, Gangi Reddy et al. (arXiv 2412.01007v3, ICLR 2025 version, 4 Mar 2025)

Source file: arXiv PDF v3 (the latest of three versions; the unversioned URL returned the identical file).
18 pages: body 10, references pp. 11-14, appendix A pp. 15-18. The extracted text has 18 pages, none blank.

## What it established

- A large (text, code) contrastive corpus built from The Stack v2 (docstring as the query, function as the
  positive), six languages, about 21M examples after filtering (Table 1, p.3; Sec. 4.1, p.6).
- Dual consistency filtering: keep a pair only if the positive is within the top-k most similar snippets for its
  text (k=2) and the similarity exceeds a threshold (0.7), using a separate proxy embedding model
  (Sec. 2.2, p.4 and footnote 5).
- Hard-negative mining with softmax sampling over a large pool, false negatives removed by a relative
  similarity threshold, and a curriculum that lowers the sampling temperature during training so negatives get
  harder (Sec. 2.3 and 3.1, pp.4-5).
- Ablation on 10% of the data: each ingredient helps on CodeSearchNet and AdvTest; no filtering is worst
  (Table 4, p.7).
- A retriever trained on it (CodeRankEmbed, 137M) and a listwise reranker (CodeRankLLM, 7B) lead their baselines
  on code search and on function localization on SWE-Bench-Lite (Tables 3, 5, 6, pp.7-9).
- An automated judge rates positive-pair correctness at 77.1% for this corpus against 52.9% for Stack v2 and
  55.8% for CodeSearchNet (Table 2, p.4).

## What it did not establish

- All evidence is on docstring-to-function retrieval and a 274-instance function-localization set; nothing at
  the issue-to-edit level on repository snapshots with agent outcomes.
- The curriculum is over negative difficulty, not over example order or quality; curriculum over examples is
  not tested. The top-k/threshold filter is a binary keep; weighting is not tested.
- The ablation is one run per row on 10% of the data; no seeds, no intervals.
- The judge for pair correctness is an instruction-tuned code model scoring 10k pairs for three seeds
  (p.4); its agreement with humans is not reported.
- Decontamination is exact-match only; the authors say additional semantic filtering is needed (Limitations, p.10).
- Whether the corpus overlaps the repositories behind SWE-bench or CORE-Bench is not examined.

## Numbers we may quote

Values are `paper_reported`. Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| Python examples original / selected | 46.1M; 10M | Table 1, p.3 |
| All selected examples (training set size) | 21M | Sec. 4.1, p.6 |
| Consistency filter: top-k and similarity threshold | k=2; 0.7 | Sec. 2.2, p.4 |
| Pair correctness (LLM judge): CosQA / CodeSearchNet / Stack v2 / CoRNStack | 63.9; 55.8; 52.9; 77.1 | Table 2, p.4 |
| Judge sample: pairs per dataset; seeds | 10k; 3 | Sec. 2.2, p.4 |
| InfoNCE temperature tau | 0.07 | Eq. 1, p.5 |
| False-negative threshold gamma; sampling temperature decays from to | 0.95; 0.05 to 0.001 | footnote 6, p.5 |
| Retriever training: epochs; batch size; hard negatives per example | three; 128; 15 | Sec. 4.1, p.6 |
| CodeRankEmbed: CodeSearchNet average MRR / AdvTest MRR / CoIR nDCG@10 | 77.9; 59.5; 60.1 | Table 3, p.7 |
| Ablation, CodeSearchNet / AdvTest: full recipe | 72.7; 50.8 | Table 4, p.7 |
| Ablation: consistency filtering only | 63.3; 39.2 | Table 4, p.7 |
| Ablation: no filtering | 56.7; 37.6 | Table 4, p.7 |
| Ablation: filtering plus top-K hard negatives | 71.4; 48.6 | Table 4, p.7 |
| Ablation: filtering plus softmax-sampled negatives | 72.3; 49.4 | Table 4, p.7 |
| Reranker training: tuples picked; training instances | 50k; 250k | Sec. 4.2.1, p.8 |
| SWE-Bench-Lite instances kept of 300 | 274; 300 | Sec. 4.3.1, p.9 |
| SWE-Bench-Lite function top-10: CodeRankEmbed / with reranker | 59.1; 73.7 | Table 6, p.9 |
| Fine-tuning Arctic-Embed-M for one epoch: CodeSearchNet average before to after | 53.4; 77.7 | Table 9, p.16 |
| Same, 2M-example CoRNStack subset vs CodeSearchNet: CodeSearchNet average | 71.4; 65.8 | Table 10, p.16 |

## Method details we need

- **Data selection (Sec. 2.1, p.3).** De-duplicated Stack v2; docstring is the text, function the code;
  non-English or too-short text removed; code that does not parse with Tree-sitter removed; text longer than
  256 tokens is not removed (to keep long issue-like queries). Python is subsampled so it is 50% of the
  data (footnote 3).
- **Filter (Sec. 2.2, p.4).** Similarity matrix `S = T_v · C_v^T` over the corpus using a proxy embedding model
  that is not the model being trained (Jina-Code-v2, footnote 5). Keep (t_i, c_i) if S_ii is within the top-k
  of row i and S_ii > delta.
- **Negatives (Sec. 2.3 and 3.1, pp.4-5).** Offline: drop candidates whose similarity exceeds gamma · S_ii.
  Online: sample M negatives with probability proportional to exp(S_ij / tau'), tau' decayed linearly
  (0.05 to 0.001).
- **Loss (Eq. 1, p.5).** InfoNCE with temperature 0.07 over the positive, the hard negatives of every example
  in the batch and the other in-batch positives: `N(M+1)-1` negatives per positive.
- **Training (Sec. 4.1, p.6).** Initialised from a text encoder with an 8,192-token window; three epochs, four
  GH200 GPUs, batch 128, 15 hard negatives; `contrastors` package.

## Relation to RQ1 / RQ2 / RQ3

- RQ2: the closest published supervision comparison (no filter / filter / filter plus negatives plus curriculum),
  but at 10% data, one seed, on docstring retrieval, with a binary filter. It supports "filtering matters"
  for that setting. WEIGHT and example-order CURRICULUM arms have no precedent here; the paper's curriculum
  is over negatives.
- RQ2 independence: the filter's proxy model (Jina-Code-v2) is not the trained model, the property the project
  requires of its quality signal.
- RQ3: Table 6 reports function localization, not resolution.
- Related note: the SweRank paper reuses this recipe with K=20 on an issue-localization pool (see that note).

## Discrepancies

- Internal: Sec. 4.2.2 (p.8) calls the zero-shot model "the code LLM (Qwen-2.5-Text)" where Table 5 names it
  Qwen-2.5-Code. A naming slip, no effect on numbers.
- With the SweRank paper: SweRank describes the filter as "top-K consistency filtering (Suresh et al., 2024)"
  using K as a repository-wide rank (K=20); this paper's filter has top-k with k=2 and a threshold 0.7 on a
  docstring corpus. The two are different instantiations of one idea.

## Claims checked

No numbered lead from the brief targets this paper. The checks done for the note:

| Claim | Verdict | Where | Note |
|---|---|---|---|
| Two-step filter: top-k then similarity threshold | confirmed | Sec. 2.2, p.4 | k=2, delta=0.7. |
| Proxy filter model differs from the trained model | confirmed | footnote 5, p.4 | Jina-Code-v2 vs Arctic-Embed-M initialisation. |
| Curriculum applies to negatives | confirmed | Sec. 3.1, p.5 | Temperature annealing. |
| Dataset and code are available | stated, not verified | footnote 1, p.1 | |
