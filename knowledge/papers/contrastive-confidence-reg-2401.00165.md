read: full — 14 pages incl. appendices, PDF v2, pdftotext -layout (poppler); re-read in full from the stored PDF (SHA-256 46d0fc3197d4fc4a8934f267ccb185f515d7340b3bab00f5ab99741b1ffffd61), first read 2026-11-12, 2026-11-14

# Mitigating the Impact of False Negatives in Dense Retrieval with Contrastive Confidence Regularization — Wang, Zhang and Nguyen (arXiv 2401.00165v2, 13 Jan 2024; AAAI 2024)

Re-read 2026-11-14 from the stored PDF: body and appendices read page by page; the reference list (pp. 8 to 10) was checked for the entries the text cites rather than read entry by entry.

Source file: arXiv PDF v2, 14 pages (body 7 pages, references pp. 8-9, appendix A and proofs pp. 10-14). The extracted text has 14 pages and no blank page. Every page was read, including Tables 1-6, the proofs and the code listing. Literature-scan source for the refresh of 2026-11-12 (topic: loss-level handling of false negatives; it was the closest unread paper on a loss-level weight named in the earlier landscape).

## What it established

- A regularizer for the contrastive (NCE) loss: the loss of the positive is pushed away from the mean loss over all passages of the query, which the authors argue makes the model more confident and robust to false negatives; under stated assumptions (a pair is more likely clean than noisy; bounded similarity; no false positives) a coefficient between 0 and 1 exists for which the regularized loss has the same minimiser as the clean loss, and 0.5 is a safe choice (Sec. 4, pp.3-5; Theorems 1-2, p.4-5; proofs, pp.12-13).
- A "passage sieve": train a model with the regularized loss and cosine similarity, then keep a hard negative only if its loss is at least the mean loss of the positive and the negatives of its query; a negative scored above chance is guaranteed to be dropped (Algorithm 1, Lemma 1, p.5; proof p.13-14).
- On three question-answering and web-search datasets, a stronger retriever trained on the sieved negatives beat the same retriever trained without it by 0.0 to 1.3 points on the reported metrics (Table 1, p.6), and the regularizer alone raised a dense passage retriever's recall at batch size 128 and matched its published Recall@100 at batch size 64 (Table 4, p.7).
- A simulation on one dataset with some positives converted to false negatives shows the regularizer separates the loss distributions of false negatives, hard negatives and in-batch negatives (Sec. 4.1, p.4; Fig. 1).

## What it did not establish

- Anything for code retrieval or repository-level data: all experiments are text (Natural Questions, TriviaQA, MS MARCO passage; p.5).
- Robustness to false positives: Theorem 2 assumes there is none in the data (p.5; proof, p.13). The regularizer handles unlabelled positives among sampled negatives, not wrong positives.
- Variance across seeds or intervals: no seed, interval or significance test is reported; each cell is a single reported value (Tables 1-4, pp.6-7; this is an absence in the text, inference).
- Matched compute: the sieve raises preprocessing from 10 minutes to 2 h 10 min on one dataset (Table 5, p.11); the retriever's training time is unchanged, but the comparison to the baseline is not budget-matched in total.
- Comparison with weighting of positives or with a curriculum.

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| False-negative rate found by manual review of MS MARCO top passages (cited work) | 70% | Sec. 1, p.1 |
| Datasets | 3 | Sec. 6.1, p.5 |
| NQ Recall@5 of the backbone / with the sieve | 77.9 / 79.2 | Table 1, p.6 |
| NQ Recall@100 of the backbone / with the sieve | 90.1 / 90.7 | Table 1, p.6 |
| MS MARCO MRR@10 of the backbone / with the sieve | 39.5 / 39.8 | Table 1, p.6 |
| Sieve hyper-parameters: coefficient, epochs, learning rate | 0.5, 1, 1e-7 | Sec. 6.2, p.6 |
| Initial number of hard negatives for the sieve, relative to the downstream count | two times | Sec. 6.2, p.6 |
| DPR with the regularizer, NQ Recall@20, batch 128 / DPR alone | 79.5 / 78.4 | Table 4, p.7 |
| Coefficient range for dot-product similarity | 0.001 to 0.0001 | Sec. 6.4, p.7 |
| Sieve-out rate in practice | below 0.5 | Appendix A.5, p.11 |
| Data preprocessing time, backbone alone / with the sieve | 10min / 2h 10min | Table 5, p.11 |

## Method details we need

- **Loss** (Eq. 7-8, pp.3-4; code listing, p.10): L = NCE(positive) minus beta times the mean of the NCE loss over all passages of the query; implemented with one extra mean over the log-softmax matrix.
- **Sieve** (Algorithm 1, p.5): train with the regularized loss for one epoch from a pretrained dense retriever; for each query compute the loss of every candidate negative; keep a negative whose loss is at least the threshold, the mean loss over the positive and the sampled negatives; the sieve rate stays near but below one half (p.11).
- **Where the signal comes from**: the model's own scores under the regularized loss, not an independent teacher (the sieve model is trained on the same noisy set; Algorithm 1, p.5). This is the self-judged form the project's quality-signal rule avoids.

## Relation to RQ1 / RQ2 / RQ3

- RQ1, RQ3: none.
- RQ2: a loss-level alternative to FILTER and WEIGHT that treats the noise as unlabelled positives among negatives; the project's noise model is the opposite (wrong or weak positives from mined pull-request pairs), for which this paper's guarantee does not apply (Theorem 2 assumes no false positives). It is listed in the related work as one more single-intervention study outside code retrieval; it is not a candidate arm of the final design (no design change is made here).

## Discrepancies

- The earlier landscape described it as a confidence regularizer and a passage sieve and as the closest remaining loss-level weight: confirmed.
- The abstract says the sieve "improves any downstream dense retrieval models"; the experiments use one downstream model family (AR2) and one other model for the regularizer alone (DPR); the limitations section says so (Appendix A.1, p.10).
- Table 4 compares DPR with the regularizer at batch 64 and 128 against the published DPR numbers (batch 128, Recall@5 not reported; p.7), so the baseline is not re-run by the authors in that table.

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| Lead (landscape): loss-level weight, confidence regularizer plus passage sieve | confirmed | Sec. 4-5, pp.3-5 | Text retrieval only. |
| Method guards against noisy positives | contradicted | Theorem 2, p.5 | Assumes no false positives. |
| Gains reported with intervals or seeds | not found | Tables 1-4, pp.6-7 | Single values. |
