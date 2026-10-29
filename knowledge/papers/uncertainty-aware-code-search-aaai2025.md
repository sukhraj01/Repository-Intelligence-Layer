read: full — 9 pages incl. appendices, PDF v1, AAAI-25 proceedings copy (pp.18807-18815; identical bytes from the publisher and the authors' site; no arXiv version found) read with pdftotext -layout (poppler), page counts equal (pdfinfo 9, extracted 9, none blank), no appendix, 2026-10-29

# Liu, Zhan and Zhang (AAAI 2025), "Uncertainty-Aware Contrastive Learning With Hard Negative Sampling for Code Search Tasks"

Source file: AAAI-25 proceedings PDF, 9 pages (body pp.1-7, references pp.7-9). A lead in `LANDSCAPE.md` described it as "uncertainty-aware contrastive learning". Read in full, it is not a method that weights or filters training pairs by confidence: "uncertainty" here means that a query or a code is mapped to a Gaussian in embedding space and several samples are drawn from it (a data-augmentation device). It is kept in the reading list for its hard-negative selection and because it shows what a code-search training comparison at this scale looks like.

## What it established

- Method (Sec. "Proposed Approach", pp.2-4): a code-search encoder initialised from a pretrained contrastive code encoder, trained with an in-batch contrastive loss plus (a) a hard-negative term built from the k queries most similar to the anchor query (the candidate pair is chosen at rank k/10 of the BM25-sorted candidates "in order to avoid sampling a false negative", p.3), (b) a Gaussian re-parameterised view for queries and for codes with a KL regulariser, (c) a unimodal contrastive term (Eqs. 1-4, p.4).
- On CodeSearchNet (six languages; Python has 251,820 training pairs, Table 1, p.4) the MRR averaged over languages is 0.800 with hard negatives and 0.796 with in-batch negatives only, against 0.788 for the strongest baseline of the same family (Table 2, p.5).
- Ablation (Table 3, p.6): removing the hard negatives (Bi+Uni+sort) 0.796; replacing them by random sampling 0.796; removing the sorting module 0.793; removing the intra-modal term 0.794 (all against 0.800 for the full method).

## What it did not establish

- No weighting by confidence, no filter of training pairs, no curriculum: the mechanism studied is embedding-space sampling and negative construction.
- The hard-negative gain is 0.004 MRR (0.800 against 0.796) from one run with a fixed seed 123456 (Sec. "Implementation Details", p.4); the random-negative replacement shows no difference to the version without hard negatives (0.796 and 0.796, Table 3). The paper's wording ("can really help") is stronger than the table.
- The results of ten baselines are copied from earlier papers with other training set-ups (Sec. "Comparisons", p.5); no repository-level or issue-style task; the false-negative protection is the BM25 rank choice, not measured against labels.

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| Average MRR over six languages: full method with hard negatives / in-batch only | 0.800 / 0.796 | Table 2, p.5 |
| Best baseline in the same table | 0.788 | Table 2, p.5 |
| Ablation: random sampling instead of hard negatives / without sorting module / without intra-modal term | 0.796 / 0.793 / 0.794 | Table 3, p.6 |
| Python training pairs | 251,820 | Table 1, p.4 |
| Seed / epochs / batch size / learning rate | 123456 / 10 / 128 / 8e-6 | Sec. Implementation Details, p.4 |
| Temperature | 0.03 | Sec. Implementation Details, p.4 |
| GPUs | four 24 GB cards | Sec. Implementation Details, p.4 |

## Method details we need

- Candidate negatives for a query anchor: the other queries in the batch are ranked by encoder similarity, the top-k kept, and one chosen at the 1/10 position of the BM25-sorted list (p.3); the code of the other query of the pair becomes a hard negative for the anchor. Used in addition to in-batch negatives.
- Hyperparameter sensitivity (Figure 3, p.6): learning rate stable between 5e-6 and 2e-5 with the best at 8e-6; temperature stable between 0.01 and 0.05.

## Relation to RQ1 / RQ2 / RQ3

- RQ1, RQ3: none.
- RQ2: a source on the negative policy (Q46) only, with a small effect in one run; useful mainly to correct the lead: nothing in it supports or tests a confidence-weighted supervision arm.

## Discrepancies

- With `LANDSCAPE.md` (before this note): the lead grouped it with "uncertainty-aware supervision modelling". The paper's uncertainty is a representation device (Gaussian embeddings), not a label-confidence estimate.
- Internal: the text says that the substitution of semantic negatives by random ones "can further impair model performance" (p.6); Table 3 shows 0.796 for both.

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| Uncertainty learning and hard negatives improve code search | weakly supported | Tables 2-3, pp.5-6 | 0.004 MRR from hard negatives, one run |
| Hard negatives beat random sampling | not supported by Table 3 | Table 3, p.6 | both 0.796 |
