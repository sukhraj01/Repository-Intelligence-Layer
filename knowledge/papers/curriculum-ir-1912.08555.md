read: full — 15 pages incl. appendices, PDF v1, pdftotext -layout (poppler), page counts equal (pdfinfo 15, extracted 15, none blank); no appendix (pp.13-15 are references); Figures 3-5 are plots, read through captions and text; re-read in full from the stored PDF (SHA-256 43c92e0be77a3048459893199339828a2718c11b810c308362b46b61a809520d), first read 2026-10-29, 2026-11-14

# Curriculum Learning Strategies for IR — Penha and Hauff (arXiv 1912.08555v1, ECIR 2020), "An Empirical Study on Conversation Response Ranking"

Re-read 2026-11-14 from the stored PDF: body and appendices read page by page; the reference list (pp. 13 to 15) was checked for the entries the text cites rather than read entry by entry.

Source file: arXiv PDF v1 (18 Dec 2019), 15 pages (body pp.1-12, references pp.13-15). A cross-encoder (BERT) re-ranker for conversation response ranking on two datasets; it is not a first-stage retriever and not code. Included because it is the one study found that compares several difficulty definitions and several pacing schedules against a no-curriculum baseline with five seeds and paired tests.

## What it established

- Framework (Sec. 3, pp.5-8): a scoring function sorts the training set by difficulty before training; a pacing function says which fraction of the sorted set may be sampled at each step, starting at a fraction delta and reaching all of it at step T (Figure 1, Tables 2-3). The model samples uniformly inside the available prefix.
- Difficulty by heuristics of the inputs (number of turns, word counts, variance of retrieval scores over candidates) does not beat random order; difficulty by a previously fine-tuned model's confidence on the labelled pair (difference between its score for the positive and the negative, or its loss) does (Sec. 5, p.10; Table 5, p.11). Test MAP, mean of five runs: MSDialog random 0.7098, confidence-based 0.7241 (loss-based 0.7240); MANtIS random 0.7131, confidence-based 0.7222. Standard deviations over the five runs are 0.0056 to 0.0111 (Table 5, p.11), so the MSDialog gain (0.0143) is about 2.5 times the baseline's seed standard deviation and the MANtIS gain (0.0091) about 1 time (our arithmetic). The paper's headline is "up to 2%" relative (Abstract, p.1).
- Pacing: functions that give the model more time on hard instances (square-root and similar) are best; a geometric schedule that gives easy instances more time is also above the baseline but not the best; changing n of the root function towards 10 moves the schedule towards uniform sampling and the result towards the baseline (Sec. 5, p.10 and note 12).
- The gains are spread over domains, conversation lengths and difficulty buckets (Figures 4-5, pp.10-12).

## What it did not establish

- Not a retrieval-stage result: a cross-encoder fine-tuned from BERT with ten candidates per query, binary labels and a balanced positive/negative sample.
- The difficulty model is BERT fine-tuned on the same training set that is then ordered, the same model class as the student; there is no independent-teacher control, and no comparison with a weight or a filter that uses the same score (the paper names dynamic sampling and hard-example mining as future work, p.4).
- No reversed-order control: "easy to hard" is compared with random order, not with "hard to easy" under the same scores, so the contribution of the order itself, as against the use of a fraction schedule that also repeats early instances, is not separated (the pacing makes early instances more frequent).
- Five seeds, selection of the best checkpoint per run on the dev set, paired tests against the baseline run-by-run; no repository- or domain-clustered statistics.

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| MSDialog test MAP, 5-run mean: random order / confidence-ordered (pair score) | 0.7098 / 0.7241 | Table 5, p.11 |
| MSDialog test MAP, loss-ordered | 0.7240 | Table 5, p.11 |
| MANtIS test MAP, 5-run mean: random order / confidence-ordered | 0.7131 / 0.7222 | Table 5, p.11 |
| Seed standard deviation, MSDialog random order | 0.0056 | Table 5, p.11 |
| Heuristic scoring function, best (number of turns), MSDialog | 0.7157 | Table 5, p.11 |
| Initial fraction of data available (delta) / share of steps to reach all data | 33% / 90% | Sec. 4, p.9 |
| Seeds per configuration | five | Sec. 4, p.9 |
| MSDialog / MANtIS context-response pairs | 246K / 1.3 million | Sec. 4, p.8 |
| Headline relative gain | up to 2% | Abstract, p.1 |

## Method details we need

- Scoring (Table 2, p.6): confidence score = minus the difference between the fine-tuned model's prediction for the positive and for a negative; loss score = the model's mean loss over the candidates of the instance.
- Pacing (Table 3, p.7): step, linear, root-n and geometric progression, each from delta = 0.33 to 1 over T = 0.9 of the training steps; the root-2 schedule was used for the main table (Sec. 5, p.10).
- Training: BERT base, Adam at 5e-5, balanced positives and negatives, five runs per configuration, best dev checkpoint per run (Sec. 4, p.9).

## Relation to RQ1 / RQ2 / RQ3

- RQ1, RQ3: none.
- RQ2: the best-evidenced difficulty order is "ranked by an external model's confidence on the labelled pair", which is the K-rank idea; the input-feature difficulty measures (length, count) were not useful. The pace matters (hard instances early enough). It carries three cautions for the project's CURRICULUM arm: (1) the scoring model was trained on the data it orders; (2) a pacing function is a second free parameter besides the order, and the project's arm has only a sort; (3) no reversed control exists here, which CL-DRD (`cl-drd-2204.13679.md`) has. Evidence class: read in full; one text task; mean-of-five differences of about 2.5 baseline SDs (MSDialog) and 1 SD (MANtIS).

## Discrepancies

- With the master document: not cited.
- Internal: the abstract's "up to 2%" is relative MAP gain; the absolute differences in Table 5 are 0.0143 (MSDialog) and 0.0091 (MANtIS).

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| Curriculum improves a neural ranker | confirmed for model-confidence difficulty only | Table 5, p.11 | heuristics do not beat random |
| Giving hard instances more time is better | confirmed for the root schedules | Sec. 5, p.10 | geometric schedule also above baseline |
| Gains come from ordering alone | not isolated | Sec. 3, p.6 | pacing also changes repetition |
