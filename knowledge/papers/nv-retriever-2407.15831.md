read: full — 11 pages incl. appendices, PDF v2, pdftotext -layout (poppler), Figures 1-4 (pp.5, 6, 7, 8) rendered and looked at, 2026-10-23

# NV-Retriever — Moreira, Osmulski, Xu, Ak, Schifferer and Oldridge (arXiv 2407.15831v2, 2024/2025), "NV-Retriever: Improving text embedding models with effective hard-negative mining"

Source file: arXiv PDF v2 (dated 7 Feb 2025; highest version that resolves), 11 pages: body pp.1-8, references pp.8-9, appendices A-B pp.9-11 (teacher agreement, the production model's data, hyperparameters and leaderboard table). The extracted text has 11 pages and no blank page. Figures 1-4 carry numbers and were rendered and looked at; only values that also appear in the text or tables are quoted. Text retrieval, not code. Read because it was a lead in the earlier scan (named in the RLHN note for its margin rule) and it is the most direct published ablation of **hard-negative selection with false-negative removal**, which is the RQ2 negative policy that must be held identical across arms.

## What it established

- With a fixed base model (a 334M encoder), fixed teacher and four mined negatives per query, the way negatives are selected moves the average nDCG@10 over three QA sets from 0.5407 (take the teacher's top-k non-positives) to 0.5856 (drop any candidate scoring above 95% of the positive's teacher score, then take the top-k) (Table 3, p.6).
- "Positive-aware" thresholds (relative to the positive's own teacher score) beat absolute thresholds and rank shifting: at scale (7B base, 728,160 training examples, 15 BEIR sets) the averages are 51.44 (naive top-k), 54.66 (skip the top 10), 55.81 (absolute score threshold 0.7), 59.77 (margin 0.05 below the positive), 60.55 (95% of the positive) (Table 5, p.8).
- The teacher matters: negatives mined with BM25 gave a lower average (0.5002) than random negatives (0.5248) for the 334M base; stronger dense teachers gave up to 0.5810 (Table 1, p.4). Different teachers agree little on their top-4 negatives (Jaccard mostly below 0.30) (p.5; Table 6, p.9).
- An LLM judge on a sample of mined negatives rated 38.8% (one dataset) and 47% (another) of naive top-k negatives as relevant to the query, i.e. false negatives; the positive-aware rule mined 57% and 50% fewer such negatives (Sec. 4.5.1, p.7).

## What it did not establish

- **Nothing about code or repositories.** Training and evaluation are general-text QA and BEIR. Whether a 95% rule transfers to issue-to-function pairs, where a repository holds many functions related to an issue, is untested.
- **One run per configuration**, no seeds or intervals. Neighbouring configurations in the threshold sweeps differ by about 0.01 nDCG (Figure 1, p.5), the same order as the gaps between the best methods in Table 3 (0.5835 against 0.5856), so the choice between the two positive-aware variants is not distinguishable on this evidence.
- The thresholds were selected on the evaluation sets (Figure 1 sweeps report the same three BEIR sets used in Table 3), so the best configuration's score is optimistic.
- The false-negative rates come from one LLM judge (an open model, checked against a second open model, footnote 17, p.7) on a train-set sample of unstated size; no human check.
- Single positive per query; how the rule applies with several positives (the project's case) is not discussed.

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| Ablation train set size | 287k | Sec. 3.3.1, p.4 |
| Mined negatives per query in the ablation | 4 | p.4 |
| Teacher comparison, average nDCG@10: BM25 / random / best teacher | 0.5002 / 0.5248 / 0.5810 | Table 1, p.4 |
| Teachers' top-4 negatives agreement (Jaccard) | lower than 30% | p.5; Appendix A, p.9 |
| Base-model ablation, average nDCG@10: naive top-k / skip top 10 / absolute 0.7 / margin 0.05 / 95% of positive | 0.5407 / 0.5695 / 0.5759 / 0.5835 / 0.5856 | Table 3, p.6 |
| 7B base, one negative: naive top-k / 95% of positive | 0.6214 / 0.6479 | Table 4, p.7 |
| At scale, 15 BEIR sets average: naive top-k / skip top 10 / absolute 0.7 / margin 0.05 / 95% of positive | 51.44 / 54.66 / 55.81 / 59.77 / 60.55 | Table 5, p.8 |
| Training examples at scale | 728,160 | Sec. 4.4, p.7 |
| Naive top-k negatives judged relevant (false negatives), two train sets | 38.8% / 47% | Sec. 4.5.1, p.7 |
| Reduction of judged false negatives by the positive-aware rule, same two sets | 57% / 50% | Sec. 4.5.1, p.7 |
| Best number of candidates to sample four negatives from | top-10 | Sec. 4.3.2, p.6 |
| Production model training: stages / epochs per stage / GPU-hours scale | 2 / 12 / about 90 hours on 8 GPUs | Appendix B.5, p.10 |

## Method details we need

- **Positive-aware filter** (Algorithms 1-3, p.3): for each mined candidate n with teacher score s(n), keep it only if s(n) < s(p) − margin (margin variant) or s(n) < s(p) × perc (percentage variant); then take the top-k survivors (or sample among the top-10 by a softmax over scores, footnote 13, p.6).
- **Teacher and base are distinct** (Sec. 3.3, p.4): negatives are mined once, up front, with a separate pretrained teacher; the base model being trained is never the miner. This matches the project's rule that the quality signal (K-rank) comes from a separately pretrained encoder.
- **Instruction on queries only** (Appendix B.3, p.10): "{task_definition}: {query}", instruction tokens masked from pooling.

## Relation to RQ1 / RQ2 / RQ3

- RQ1: none.
- RQ2 (negative policy, held identical across arms): the strongest published evidence that the negative-selection rule can move a retriever as much as a supervision change can (about 4.5 nDCG points on the small ablation, 9 points at scale). Consequences for the project: (a) the negative policy (random repository-local as in CORE-Bench, teacher top-M as in SweRank, or teacher top-M with a positive-aware cut) must be fixed and documented before the arms run, because a different policy per arm would confound the comparison; (b) a positive-aware cut is itself a form of false-negative filtering, so if FILTER's K-rank teacher is also the negative miner, FILTER and the negative policy share one signal and the report must say so; (c) E-PILOT-NEG (T2) is the place to measure whether a positive-aware cut matters on repository-level pairs. With several positives per query the rule needs a stated choice (lowest or highest positive score).
- RQ3: none.

## Discrepancies

- With the project documents: the RLHN note refers to "a 95% margin" rule from this paper (as RLHN itself does); the paper calls it a percentage of the positive score (TopK-PercPos), distinct from its absolute margin variant (0.05). Both readings name the same 95% rule; the word "margin" is ambiguous and should be avoided.
- Internal: the abstract gives 60.9 for the production model on MTEB Retrieval; the mining comparison at scale gives 60.55 for the same mining rule before a second training stage (p.7), which the paper explains.

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| Earlier lead: "margin rule" for false-negative removal | confirmed, with the naming caveat above | Algorithms 2-3, p.3; Table 3, p.6 | percentage variant (95%) best, margin variant (0.05) second |
| Hard negatives from BM25 help (common assumption from earlier dense-retrieval work) | contradicted for this setting | Table 1, p.4 | BM25-mined negatives below random negatives, one run |
| Negative mining removes false negatives | confirmed by an LLM judge only | Sec. 4.5.1, p.7 | sample size not stated |
