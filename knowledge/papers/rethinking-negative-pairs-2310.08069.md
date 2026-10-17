read: full — 15 pages incl. appendices, PDF v1, pdftotext -layout (poppler) plus page raster of p.7 (Table 1), 2026-10-17

# Rethinking Negative Pairs in Code Search — Li et al. (arXiv 2310.08069v1, EMNLP 2023)

Source file: arXiv PDF v1, 15 pages (body 9 pages, limitations p.9, references pp.9-12, appendices A-D pp.12-15 including the proofs of Theorems 1-2 and Proposition 1, hyper-parameters, timing and a case study). arXiv holds only v1. The extracted text has 15 pages and no blank page. Every page was read, including the three proofs at the level of what they assume; Table 1 was also looked at as a raster.

## What it established

- Soft-InfoNCE: the InfoNCE loss with a weight w_ij on each in-batch negative, w_ij = (beta - alpha * sim_ij) / (beta - alpha/(N-1) * sum_j sim_ij), where sim_ij is an estimated similarity of the query to negative code j, normalised by a softmax with temperature t so that the weights sum to N-1 (Eqs. 3-4, p.3). With all weights equal to 1 it reduces to InfoNCE (p.3). Negatives that look more relevant to the query get smaller weights; the weight acts only on the denominator.
- Three ways to estimate sim_ij: BM25 over the in-batch queries and code; unsupervised SimCSE similarity between the query and the negative's own query; and a "trained model", the same architecture trained earlier with InfoNCE on the same language and then frozen (Sec. 3.2, p.4; Sec. 5, p.6).
- On CodeSearchNet (six languages, MRR), three pre-trained code models fine-tuned with Soft-InfoNCE gain about 1-2% MRR over InfoNCE (Table 1, p.7; text p.6). The gain is larger on CodeBERT than on the two stronger models.
- Compared with other loss designs built on the same similarity scores (binary cross-entropy, a weighted InfoNCE with the similarity as a numerator weight, a KL regulariser) Soft-InfoNCE is higher on all three models, and weighted InfoNCE is lower than plain InfoNCE on CodeBERT (Table 2 p.8; Table 5 p.13). Removing the top-k most similar negatives or those above a threshold ratio is lower than Soft-InfoNCE on one model and dataset (Table 3, p.8).
- Theory (Sec. 4, pp.4-5; Appendix B): the weighted loss upper-bounds a KL term between the estimated similarity distribution and the model's, and can be read as importance sampling of the negative set; false-negative removal is the special case with weight 0 for the removed ones (p.5). The proofs depend on stated approximations (dot products are positive; the in-batch estimate of the negative set is good).

## What it did not establish

- It does not measure how many in-batch negatives are false negatives. The statement that code duplication makes false negatives common is attributed to earlier work (Lopes et al. 2017; Allamanis 2019; Introduction, p.1); the paper's own evidence is the weight plot (Figure 2 p.7) and an eight-sample case study in Appendix D.2 (p.15), where the three estimators disagree about which negative is least negative.
- No weighting of positives or of queries; only negatives are weighted. No data filtering, no curriculum.
- No retrieval on a repository, no issue text, no agent; queries are docstring first sentences of CodeSearchNet functions and the evaluation codebases are small (1,400 to 13,914 candidates, Table 6, p.14).
- The estimator "trained model" is not independent of the model being trained: it is the same architecture trained earlier on the same data with plain InfoNCE (p.6). The project rule that a learned quality signal must come from a separately pretrained encoder is therefore not what this paper does; the paper does not discuss self-confirmation.
- No test of whether the three estimators agree with human judgement; the authors state the estimation methods "are not fully investigated" (Limitations, p.9).
- Three seeds are reported, but no interval; the authors say all gains meet p < 0.01 except GraphCodeBERT and UniXcoder on Go (p.6).
- Matched compute is not claimed: training with the estimator costs more time per batch (Table 8, p.14).

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages. MRR on the CodeSearchNet test split.

| Claim | Value | Where |
|---|---|---|
| Overall gain of Soft-InfoNCE over InfoNCE | about 1%-2% MRR | Sec. 6, p.6 |
| CodeBERT, Ruby MRR: InfoNCE / Soft-InfoNCE with trained model | 0.648 / 0.682 | Table 1, p.7 |
| UniXcoder, Ruby MRR: InfoNCE / best Soft-InfoNCE | 0.740 / 0.753 | Table 1, p.7 |
| Overall MRR (average of six languages), CodeBERT: BCE / weighted InfoNCE / KL regulariser / Soft-InfoNCE | 0.641 / 0.639 / 0.648 / 0.687 | Table 2, p.8 |
| Same, GraphCodeBERT: Soft-InfoNCE | 0.722 | Table 2, p.8 |
| Same, UniXcoder: Soft-InfoNCE | 0.751 | Table 2, p.8 |
| GraphCodeBERT, CodeSearchNet Python MRR: InfoNCE / best false-negative cancellation / Soft-InfoNCE | 0.690 / 0.689 / 0.700 | Table 1 p.7; Table 3 and text, p.8 |
| Hyper-parameters alpha and beta used (alpha + beta = 2) | 1.3 and 0.7 | Sec. 6 and Table 7, pp.8, 14 |
| Time per batch (CodeBERT): InfoNCE / Soft-InfoNCE with BM25 / SimCSE / trained model | 0.75 s / 0.77 s / 0.81 s / 0.98 s | Table 8, p.14 |
| Softmax temperature t: BM25 / SimCSE / trained model | 1.0 / 0.1 / 5.0 | Table 7, p.14 |
| Seeds | 1234, 12345, 123456 | Sec. 5, p.6 |
| Training epochs | 30 | Sec. 5, p.6 |
| Evaluation codebase sizes: Python / Java | 13,914 / 5,183 candidates | Table 6, p.14 |

## Method details we need

- **Loss** (Eqs. 1-4, p.3): batch of N query-code pairs; the other N-1 codes are negatives; dot-product similarity; weights clamped to at least 0.1 (Appendix C.2, p.14).
- **Estimators** (p.4): BM25 uses only the in-batch data; SimCSE is initialised from a sentence-embedding checkpoint and trained on all queries of the six languages; the trained model is trained per language until convergence and frozen.
- **Models and data** (Sec. 5, p.6): CodeBERT, GraphCodeBERT and UniXcoder, fine-tuned on CodeSearchNet with the filtering of Guo et al. 2021; one RTX A6000 GPU.
- **Reported cost** (Table 8, p.14): 0.75 s per batch for InfoNCE against 0.98 s for Soft-InfoNCE with the trained-model estimator, averaged over 30 epochs on CodeBERT.
- **Not given**: batch size and learning rate beyond "follow the original paper"; hardware wall-clock for a full run.

## Relation to RQ1 / RQ2 / RQ3

- RQ1: none.
- RQ2: the only one of the three cited precedents that changes the loss rather than the data. It is a WEIGHT-style intervention on negatives, with weights from an external estimator and optimisation steps unchanged. It does not weight positives or queries, so it is not the same thing as the WEIGHT arm's use of a K-rank score on instances; the paper supports "soft weighting of negatives gives a small gain on an older architecture" and nothing more. Its "trained model" estimator is the self-referential case the master document warns against (`docs/08_experimental_design.md`, second warning).
- RQ3: none.

## Discrepancies

- With the master document (`docs/03_literature_map.md`): "False negatives are pervasive" is not measured in this paper; it is cited from earlier work and illustrated on eight examples. "Soft-InfoNCE soft weighting" and "One intervention, snippet-level, no agent" are confirmed.
- Internal: the text says the weights of weighted InfoNCE are "only at around 0.03" (p.7) while the weights of Soft-InfoNCE are clamped to at least 0.1 and plotted between about 0.1 and 1.6 (Figure 2, p.7); both statements are about different losses, so this is not an inconsistency, but the two scales should not be compared.

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| Master document: "Soft-InfoNCE soft weighting" is an intervention for false negatives | confirmed | Eqs. 3-4, p.3 | Weights on in-batch negatives, estimated by BM25, SimCSE or a frozen same-architecture model. |
| Master document: "False negatives are pervasive" | not found as a measurement | Introduction p.1; Sec. 6 p.8 | Attributed to Lopes et al. and Allamanis; no count of false negatives in any batch. |
| Master document: "One intervention, snippet-level, no agent" | confirmed | Sec. 5, p.6 | CodeSearchNet function retrieval only. |
