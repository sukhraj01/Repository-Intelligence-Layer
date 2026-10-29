read: full — 16 pages incl. appendices, PDF v1, pdftotext -layout (poppler), page counts equal (pdfinfo 16, extracted 16, none blank); supplement (pp.12-16) read, figures that are similarity histograms looked at through their captions and the JSD table, 2026-10-29

# D-SCL — Long, Killick, Zhuang, McCreadie, Aragon-Camarasa and Henderson (arXiv 2311.16481v1, November 2023), "Elucidating and Overcoming the Challenges of Label Noise in Supervised Contrastive Learning"

Source file: arXiv PDF v1 (25 Nov 2023), 16 pages (body pp.1-8, references pp.9-11, supplement pp.12-16: similarity histograms, divergence table, derivations, ablations, sensitivity to the assumed noise rate). Image classification with supervised contrastive losses. Included for its analysis of which training pairs a noise estimate should down-weight.

## What it established

- In human-labelled image sets (ImageNet, CIFAR-100) the label-error rate of about 5.85% implies that about 11% of positive pairs are wrong against about 0.1% of negative pairs (CIFAR-100: 11.4% against 0.11%; ImageNet 11.32% against 0.09%; Sec. 4.1, p.4). From this the authors argue that mislabelled pairs matter mainly as false positives, not false negatives.
- Mislabelled samples are "easy positives": their embeddings are as close to the anchor as the true positives' (Jensen-Shannon divergence between true-positive and false-positive similarity distributions 0.29 on ImageNet, against 0.74 between true positives and true negatives; Table 5, p.13). The abstract states that labelling errors appear as easy positives "in around 99% of cases" (Abstract, p.1) and the text says the performance decline is attributed to false positives in approximately 99% of cases (p.2).
- Method: a supervised contrastive loss that re-weights the positives by a von Mises-Fisher factor so that positives far from the anchor weigh more (the "easy" ones less), with an importance-sampling correction for the assumed noise rate (Sec. 5, pp.5-6). Accuracy: ImageNet-1k from scratch, BEiT-3 base 84.21 against 82.57 for the unmodified supervised contrastive loss and 77.91 for cross-entropy (Table 1, p.7); fine-tuning gains 0.7 to 3.4 points over the same baseline (Table 3, p.8).
- Ablation (CIFAR-100): debiasing positives alone 63.18, negatives alone 61.30, both 64.47, supervised contrastive 60.25 (Table 6, p.15). Assumed noise rate 1% to 20%: results move by at most 0.31 points between the standard 3% and the best value, but degrade beyond 10% (Table 8, p.16).
- At high synthetic noise (CIFAR-N at 40%) the method falls behind selection-based noise-robust methods (Table 4, p.8: 45.17 and 68.92 against 57.52 and 87.16 for the two selection methods, depending on the dataset), and the authors say the method assumes human-type, similarity-correlated errors, not synthetic noise (Sec. 6.3, p.8).

## What it did not establish

- Nothing about text, code, or retrieval; classes, not queries; the noise rate and the label of each example are known from consensus studies, which the project does not have.
- The 99% figure is an analysis of how the performance decline arises (Sec. 4), not a count of mislabelled examples that lie close to their anchor; the supplement quantifies it with similarity histograms and the divergence table only (p.13).
- Three seeds (Sec. 6, p.6) but only means are shown; no intervals.
- The method re-weights by the model's own embedding similarity (the model being trained), so it is a self-signal; no independent-detector variant is tried.

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| Error rate of ImageNet and CIFAR-100 validation sets | 5.83% / 5.85% | Sec. 4, p.4 |
| Positive pairs / negative pairs likely wrong (CIFAR-100) | 11.4% / 0.11% | Sec. 4.1, p.4 |
| JSD true positives vs false positives / vs true negatives (ImageNet) | 0.29 / 0.74 | Table 5, p.13 |
| ImageNet-1k top-1, BEiT-3 from scratch: cross-entropy / unmodified supervised contrastive / D-SCL | 77.91 / 82.57 / 84.21 | Table 1, p.7 |
| CIFAR-100 ablation: debias positives only / negatives only / both | 63.18 / 61.30 / 64.47 | Table 6, p.15 |
| CIFAR-100 ablation: supervised contrastive without debiasing | 60.25 | Table 6, p.15 |
| CIFAR-100N 40% noise: D-SCL / best selection-based method | 45.17 / 57.52 | Table 4, p.8 |
| Assumed noise rate: best on CIFAR-100 / at the typical 3% | 64.47 / 64.16 | Table 8, p.16 |
| Typical annotation error rate used as baseline | 3.3% | Sec. 7, p.8 |
| Seeds | three | Sec. 6, p.6 |

## Method details we need

- Loss (Eqs. 6-11, 28, pp.5-6 and supplement): positives sampled from q+ proportional to exp(beta f(x)^T f(x+)) times the class-conditional prior, then debiased by subtracting the negative-class share (tau-minus over tau-plus); the same for negatives. tau-plus is the assumed same-class probability; beta sets how strongly far positives are preferred.
- Set-up: BEiT-3 base (ViT) and ResNet-50, linear head on frozen embeddings for evaluation (Sec. 6.1, p.6).

## Relation to RQ1 / RQ2 / RQ3

- RQ1, RQ3: none.
- RQ2: the one source read that says which direction a confidence weight should lean when errors are similarity-correlated: a weight that favours the pairs the model already finds easy (as a small K does) also favours the mislabelled ones, because mislabelled positives look like easy positives. This is image evidence, with the noise coming from annotators mistaking similar classes; a repository pool's noise (a patch touches a file the issue text never mentions) need not be similarity-correlated, and X3 showed the pool's positives are mostly ranked high by the teacher (Q50). So it is a reason to measure which K-ranks the pool's wrong positives have, not a result for the project.

## Discrepancies

- With the abstract: "around 99% of cases" in the abstract and in the introduction is a statement about attribution of the decline, not a frequency of mislabelled easy positives; the body analysis does not give a count behind 99%. Treated as unverified beyond the quoted statement.
- Internal: Table 4 gives D-SCL a clean-data advantage and a noisy-data deficit; the text says it is "competitive up to 18%" (Sec. 6.3, p.8): at 18% on CIFAR-10N it is 88.75 against 90.49 and 89.72.

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| False positives dominate false negatives under human noise | confirmed arithmetically | Sec. 4.1, p.4 | from the assumed error rate |
| Mislabelled samples are easy positives | supported by similarity overlap | Table 5, p.13 | JSD 0.29 against 0.74 |
| Down-weighting easy positives helps at low noise | confirmed on three vision sets | Table 1, p.7 | gain 1.6 points over the unmodified loss on ImageNet-1k |
