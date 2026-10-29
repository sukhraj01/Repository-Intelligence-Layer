read: full — 18 pages incl. appendices, PDF v2, pdftotext -layout (poppler), page counts equal (pdfinfo 18, extracted 18, none blank); proof and tables of the appendix read, 2026-10-29

# GloFND — Balmaseda, Wang, Lin and Yang (arXiv 2502.20612v2, ICML 2025), "Discovering Global False Negatives On the Fly for Self-supervised Contrastive Learning"

Source file: arXiv PDF v2 (25 Jun 2025), 18 pages (body pp.1-9, references pp.10-13, appendices A-D pp.13-17 with the proof of Lemma 3.1, the bimodal extension, intuition for alpha, set-up details, significance tests, a SimCLR run and a CLIP fine-tuning run). Image and image-text pretraining; no text or code retrieval. Read for the one feature that bears on the project: a false-negative detector that is the encoder being trained.

## What it established

- A per-anchor threshold, learned by stochastic gradient steps on a quantile objective, marks the top-alpha share of an anchor's negatives (by the current encoder's similarity) as false negatives and drops them from the loss, at an extra cost of about 2% of epoch time (Sec. 3, pp.3-5; Sec. 4.3, p.8).
- On ImageNet100 with labels as ground truth, the detector's precision/recall/F1 at the last epoch is 48.40 / 58.81 / 53.10 against 27.57 / 53.67 / 36.42 for a mini-batch top-k rule; semi-supervised linear accuracy averages 63.36 against 61.66 for no detection and 62.60 for the batch rule (Table 1, p.6). Transfer average over eight datasets 64.31 against 62.67 and 63.40 (Table 2, p.6). Paired one-sided t-tests are below 0.05 in all four label fractions (Table 5, p.17).
- The detector is the model being trained, so it needs a warm-up: the start epoch was varied with the total fixed at 200, and the result peaked at 70 and declined after that; applied too early the similarities do not yet reflect semantics, applied too late there is too little training left (Sec. 4.3, p.8, Figure 5d).

## What it did not establish

- Nothing about text, code, or retrieval with queries; the negatives are other images and the positives are augmented views of the same image.
- No comparison against removing false negatives with an independent model; the detector's threshold quality is measured only against class labels (the label rule marks every same-class pair a false negative, Sec. 4.1, p.6).
- Filtering is the only action tried ("how to make the best use of false negatives" is left open, p.9). The share alpha is tuned with the downstream score (Appendix C, p.14).
- Gains are 1 to 2 points on image benchmarks, three seeds (Sec. 4, p.5); the CLIP fine-tuning table shows no seeds.

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| False negatives: share of negative pairs (SogCLR, ImageNet100) | 1% | Sec. 1, p.1 |
| Detector precision / recall / F1, GloFND | 48.40 / 58.81 / 53.10 | Table 1, p.6 |
| Same, mini-batch top-k rule | 27.57 / 53.67 / 36.42 | Table 1, p.6 |
| Semi-supervised average top-1: no detection / batch rule / GloFND | 61.66 / 62.60 / 63.36 | Table 1, p.6 |
| Transfer average: no detection / GloFND | 62.67 / 64.31 | Table 2, p.6 |
| Added epoch time | 2% (427 s to 435 s) | Sec. 4.1, p.7; Sec. 4.3, p.8 |
| Start epoch with best result, of 200 epochs | 70 | Sec. 4.3, p.8 |
| Learned-threshold error: GloFND / batch rule (mean absolute error) | 0.1 / 0.21 | Sec. 4.3, p.8 |
| Seeds | 3 | Sec. 4, p.5 |
| Image-text retrieval average, fine-tuned CLIP: base / GloFND | 44.43 / 54.08 | Table 8, p.17 |

## Method details we need

- Objective (Eq. 2, p.4): lambda_i = argmin over nu in [-1, 1] of nu*alpha + mean over negatives of (r - nu)+; the solution is the k-th largest similarity with k = ceil(alpha * number of negatives) (Lemma 3.1, p.4; proof p.14).
- Alternating updates (Algorithm 1, p.5): a threshold step per sampled anchor, then the encoder step on the loss with the flagged negatives removed. Thresholds start at 1 (nothing flagged) and use Adam with learning rate 0.05 (p.6).
- The first epochs run without detection; start epoch is a tuned hyperparameter (70 of 200 in the main run; 15 or 20 for the 37-epoch CLIP runs, pp.6-7, 16).

## Relation to RQ1 / RQ2 / RQ3

- RQ1, RQ3: none.
- RQ2: the only measured statement here about a detector that is the model in training: it works after a warm-up and is harmful or useless before it, with the best start at about a third of the schedule in this setting. That is the self-confirming loop of Q52 with a number attached, in images. It argues for a teacher that is separate from the trained model (the project's rule) or, if the model is its own judge, for a start point and a schedule that are themselves reported. Also shows "drop everything above a quantile of similarity" as a per-anchor rule, which is a score-quantile cousin of a rank cut K. No weighting; no curriculum.

## Discrepancies

- With the master document: not cited. With RLHN and ARHN (text): those use external judges (language models), this uses the learner itself; the two kinds of detector are not compared anywhere in the notes read.
- Internal: the text reports a "1.04%-2.44%" improvement per label fraction (Sec. 4.1, p.7); these are points of accuracy and match the differences in Table 1 (77.59 against 76.55, 37.38 against 34.94). Consistent.

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| A self-detected false-negative filter helps contrastive pretraining | confirmed on images, 3 seeds | Table 1, p.6; Table 5, p.17 | gain 1.7 points average over no filtering |
| The self-detector needs a warm-up | confirmed | Figure 5d, p.8 | optimum at 70 of 200 epochs |
| Detection transfers to text or code | not found | - | no text experiment |
