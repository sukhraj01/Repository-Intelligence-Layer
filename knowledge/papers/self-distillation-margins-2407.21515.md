read: full — 11 pages incl. appendices, PDF v2, pdftotext -layout (poppler), page counts equal (pdfinfo 11, extracted 11, none blank); no appendix (pages 10-11 are references); Figures 3-6 are plots read through their captions and the text; re-read in full from the stored PDF (SHA-256 295857bef30227615c48c1c3b4ca8cf1834c10429fa41bff65b6464b04336100), first read 2026-10-29, 2026-11-14

# Self-distillation with adaptive relevance margins — Gienapp, Deckers, Potthast and Scells (arXiv 2407.21515v2, ICTIR 2025)

Re-read 2026-11-14 from the stored PDF: body and appendices read page by page; the reference list (pp. 9 to 11) was checked for the entries the text cites rather than read entry by entry.

Source file: arXiv PDF v2 (20 Jun 2025), 11 pages (body pp.1-9, references pp.9-11, no appendix). Text passage retrieval on MS MARCO. Included for two things: a supervision signal that is the encoder's own pretrained similarity (an explicit self-teacher), and a learning curve in triplets seen.

## What it established

- A margin loss whose per-triplet target is the encoder's own (rescaled) similarity between the positive and the negative document: hard triplets (similar positive and negative) get a larger target and so a larger loss, which is "implicit hard negative mining" with no teacher and no hyperparameter (Sec. 3, pp.3-4; Eq. 2). A variant spreads the target over all in-batch negatives ("distributed", Eq. 3).
- In the full-ranking setting, the distributed variant on a 66M encoder reaches MS MARCO TREC-DL 2019 nDCG@10 0.64 and 2020 0.62 against 0.69 and 0.65 for a reproduction of teacher-distilled batch-sampled training (about 14.6M triplets) and 0.71 and 0.69 for the original (about 22.4M triplets); the authors call the differences to the reproduction statistically equivalent by paired equivalence tests with a margin of 0.05, with a conservative reading of "equivalent" at n = 43 and 54 queries (Table 4, p.8; Sec. 5.5, p.8).
- Learning curve: with adaptive targets, nDCG@10 peaks after about half of the data (full MS MARCO triplet file of 39,780,811) and declines afterwards, "suggesting a divergence from the target task"; the distributed variant peaks earlier still (Sec. 5.2-5.3, p.5; Figures 4-5). Data seen at the early-stopped optimum: 1.98M to 7.30M triplets for the self-distillation rows against about 14.6M and 22.4M for teacher distillation (Tables 3-4, pp.7-8); the abstract's "13.5% of the data" appears to be (our arithmetic, 1.98M over 14.6M) the ratio of the smaller self-distillation runs to the larger teacher run.
- With a tuned static margin, results match the teacher-distilled reproduction, but the sweep costs 3x to 15x the training time of the self-distillation variants (Sec. 5.4, p.8). In-batch negatives do not help the static margin and hurt its nDCG@10 (Sec. 5.1, p.5; Table 3, p.7).

## What it did not establish

- Hyperparameter selection and early stopping use TREC-DL 2019 scores, which is also one of the two reporting sets; the authors say so and use TREC-DL 2020 as the neutral set (Sec. 5.4, p.7). Equivalence claims rest on 43 and 54 queries and an equivalence margin of 0.05 nDCG@10, large next to the 0.01 to 0.04 differences that decide the project's arm comparisons.
- No code, no repository-scale pool, no multi-positive queries; the positive-negative similarity that defines the target is document-to-document similarity of a BERT-style encoder, which for functions of one repository may be dominated by shared lexical context.
- Not a filter or a hard weight: the self-signal enters through the loss target; no comparison with removing low-confidence pairs. Single runs per cell; no seeds.
- The learning curve is one epoch over one triplet file with the per-run peak chosen on the test queries, so the "peak at about half" is optimistic.

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| Training triplets in the MS MARCO file | 39 780 811 | Sec. 4, p.4 |
| Self-distillation vs teacher distillation: share of data | 13.5% | Abstract, p.1 |
| Teacher-distilled original: triplets seen (conservative) | 22.4M | Table 4, p.8 |
| Teacher-distilled reproduction: triplets seen | 14.6M | Table 4, p.8 |
| Distributed targets, 66M encoder: DL19 / DL20 nDCG@10 | 0.64 / 0.62 | Table 4, p.8 |
| Teacher distillation (original, batch sampling, in-batch negatives): DL19 / DL20 nDCG@10 | 0.71 / 0.69 | Table 4, p.8 |
| Triplets seen, distributed / adaptive with in-batch negatives (66M encoder) | 7.30M / 1.98M | Table 3, p.7 |
| Tuned static target: training time relative to distributed (range) | 3x to 6x | Sec. 5.4, p.8 |
| Early stopping: consecutive checks without gain | 16 | Sec. 5.4, p.7 |
| Grid-search subset size | 2.56 M | Sec. 5.1, p.5 |
| Equivalence margin | 0.05 | Sec. 5.4, p.7 |
| Batch sizes studied | 64 / 128 | Sec. 4, p.4 |

## Method details we need

- Loss (Eqs. 1-5, pp.3-4): mean squared error between the cosine margin sim(q, d+) - sim(q, d-) and a target; static = a constant, adaptive = (1 + sim(d+, d-)) / 2, distributed = the same target taken against every in-batch negative.
- Hardware and set-up: one 40 GB GPU, mixed precision, quantised optimiser states; learning rate 5e-6 divided by the batch size; evaluation by re-ranking BM25 top 1000 for hyperparameter work and by a full index for the reported tables (Sec. 4, p.4).

## Relation to RQ1 / RQ2 / RQ3

- RQ1, RQ3: none.
- RQ2: (a) a weight that is the model's own similarity-based difficulty, computed on the fly, with no separate teacher; it is the opposite of the project's independent-teacher rule and an example of the self-teacher design that Q52 worries about, with the unfavourable evidence that the self-signal overfits ("tendency to overfit in adaptive and distributed margins", p.8) unless stopped by an external score. (b) A learning curve in updates: peaks well inside one epoch and then declines when the supervision is the model itself, which is a warning for any schedule that runs a self-judged signal for the whole budget. (c) A reminder that tuning the loss's constant (the margin) moved results by more than 0.1 nDCG@10 (Sec. 5.1, p.5), so a fixed K or sigmoid scale chosen once may have the same sensitivity.

## Discrepancies

- With the abstract: "13.5% of the data" compares the smallest self-distillation run with the largest teacher run; the like-for-like ratios in Table 4 are 2x to 11x (Sec. 5.5, p.8).
- Internal: the caption of Figure 3 says "(left)" twice for the two panels; the text is unambiguous.

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| Self-distillation matches teacher distillation in-domain | confirmed against the reproduction only | Table 4, p.8 | the original teacher-distilled run is 0.07 higher on DL19 nDCG@10 |
| Teacher-free training needs far fewer triplets | confirmed in triplets seen | Tables 3-4, pp.7-8 | different software and hardware, time not comparable |
| In-batch negatives help | contradicted for the static margin | Sec. 5.1, p.5 | random in-batch negatives easy |
