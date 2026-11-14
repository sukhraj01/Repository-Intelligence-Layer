read: full — 7 pages incl. appendices, PDF v1, pdftotext -layout (poppler), page counts equal (pdfinfo 7, extracted 7, none blank); no appendix; re-read in full from the stored PDF (SHA-256 c2d647ec2aba00007db34cb8b8bc7f7e0ea031ffe1bdf96a065339fadee33d45), first read 2026-10-29, 2026-11-14

# When Fine-Tuning Fails — Pande, Kumar and Damle (arXiv 2506.18535v1, June 2025), "Lessons from MS MARCO Passage Ranking"

Re-read 2026-11-14 from the stored PDF: body and appendices read page by page; the reference list (p. 7) was checked for the entries the text cites rather than read entry by entry.

Source file: arXiv PDF v1 (23 Jun 2025), 7 pages (body pp.1-6, references p.7). A student-team study of fine-tuning one small general-purpose sentence encoder on MS MARCO. Included for topic (iv): it is the only item found that reports what happens when a small encoder that is already strong on the task is fine-tuned with a standard recipe, and it should be weighed as a low-evidence source (see below).

## What it established

- Starting from a 22.7M-parameter sentence encoder that had been trained on over a billion pairs including 9,144,553 MS MARCO pairs, every fine-tuning variant is below the unmodified encoder on MS MARCO dev: MRR@10 0.3026 for the base against 0.2619 (full fine-tuning, 1M random-negative triplets), 0.2536 (full, 503K hard-negative triplets), 0.2557 (LoRA, random) and 0.2050 (LoRA, hard) (Table I, p.3; changes -13.5% to -32.3%).
- Hard negatives, taken at random from ranks 51 to 200 of the base model's own top 200 (Sec. III.D, p.2), did worse than random ones in both full and LoRA fine-tuning (Table I, p.3).
- The authors read their UMAP plots of 1,000 query-positive pairs as progressive "flattening" of the embedding space with performance (Figure 2, p.4); this is a qualitative reading of a projection.

## What it did not establish

- The conclusion that fine-tuning fails "on saturated benchmarks" is drawn from one base model, one dataset, one run per cell, one learning rate (2e-5, batch 128, linear warm-up of 1,000 steps, 3 to 5 epochs, a triplet loss with margin 0.2; Sec. IV.B, p.3). No learning-rate sweep, no early stopping, no seeds, no intervals. A small-batch triplet loss with a fixed margin on a model trained with in-batch softmax at batch 1,024 is a mismatch of objective, which the authors list as a limitation (Sec. VI.F, p.5).
- The hard negatives are drawn from the base model's own ranks 51-200 with no false-negative control; MS MARCO's sparse labels make many of them relevant, which is the usual explanation for such results and is not tested here.
- The mechanism (embedding-space collapse) is shown only by visualisation and training loss; no measurement links collapse to the drop.
- No learning curve: every cell is one end-of-training number. Nothing about how many updates are needed before a specialised encoder moves.

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| Base encoder MRR@10 on MS MARCO dev | 0.3026 | Table I, p.3 |
| Full fine-tuning, random negatives / hard negatives, MRR@10 | 0.2619 / 0.2536 | Table I, p.3 |
| LoRA, random negatives / hard negatives, MRR@10 | 0.2557 / 0.2050 | Table I, p.3 |
| Largest drop relative to base | 32.3% | Table I, p.3 |
| MS MARCO pairs already in the base encoder's training | 9,144,553 | Sec. I, p.1 |
| Hard-negative triplets / random triplets used | 503,000 / 1 million | Sec. III.D, p.2 |
| Hard negatives sampled from ranks | 51 to 200 | Sec. III.D, p.2 |
| Learning rate / batch size | 2e-5 / 128 | Sec. IV.B, p.3 |
| LoRA rank | 16 | Sec. III.E, p.3 |
| Estimated time for the full triple file | 260 hours | Sec. IV.A, p.3 |

## Method details we need

- Training: AdamW, learning rate 2e-5 with 1,000 warm-up steps, batch 128, gradient clip 1.0, weight decay 0.01; 5 epochs for full fine-tuning on hard negatives and 3 for the rest; triplet loss with margin 0.2 (Sec. III.C and IV.B, pp.2-3). LoRA on query and value projections.
- Evaluation: MRR@10 and MRR@100 on the MS MARCO dev qrels (55,578 judgments as stated); inference time over 10,000 queries (Sec. IV.C, p.3).

## Relation to RQ1 / RQ2 / RQ3

- RQ1, RQ3: none.
- RQ2: a caution about (iv), with the evidence class "one run, one dataset, text": the project's base encoder was trained on code-retrieval data and the smoke pilots moved it by +8.3 dev L2 nDCG@10 in 63 updates (a measured result, not from this paper), so the project's situation is the opposite of the paper's (a base that the data improved, not a saturated one). What carries over is the method of the warning: fixed recipe, no learning-rate or step sweep, and an end-of-training number cannot tell "no gain" from "overshoot". The negative-source result agrees in direction with the sources that found mined negatives from the same model unhelpful, and has the same unexplained false-negative confound.

## Discrepancies

- With the abstract: the abstract says "comprehensive experiments" and the conclusion says "definitive evidence"; the study has five single-run cells and one hyperparameter set.
- Internal: the abstract lists 13.5% to 32.3% as degradation; Table I agrees (13.5, 16.2, 15.5, 32.3).

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| All five fine-tuning cells are below the base | confirmed for these cells | Table I, p.3 | single recipe |
| Hard negatives are worse than random on a saturated model | confirmed for this recipe | Table I, p.3 | negatives from the base model's ranks 51-200, no false-negative control |
| Embedding-space collapse explains it | not tested beyond a visualisation | Figure 2, p.4 | |
