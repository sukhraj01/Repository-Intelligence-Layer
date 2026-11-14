read: full — 21 pages incl. appendices, PDF v1, pdftotext -layout (poppler), page counts equal (pdfinfo 21, extracted 21, none blank); appendix tables and the pipeline figure read; re-read in full from the stored PDF (SHA-256 c2dec45d0b2d4c9393a5e8f51a52628897e511960a253d9dcfc00348fae93457), first read 2026-10-29, 2026-11-14

# Promptagator — Dai, Zhao, Ma, Luan and colleagues (arXiv 2209.11755v1, ICLR 2023), "Few-shot Dense Retrieval From 8 Examples"

Re-read 2026-11-14 from the stored PDF: body and appendices read page by page; the reference list (pp. 10 to 16) was checked for the entries the text cites rather than read entry by entry.

Source file: arXiv PDF v1 (23 Sep 2022), 21 pages (body pp.1-10, references pp.11-16, appendices A-D pp.17-21: prompt templates, pipeline figure, generated-query statistics, author contributions). Text retrieval from a large instruction-tuned language model's synthetic queries (the model is a 137B-parameter instruction-tuned checkpoint). Included for one design: a round-trip filter whose judge is a retriever trained on the same noisy data.

## What it established

- Synthetic (query, passage) pairs from few-shot prompts are filtered by round-trip consistency using the retriever trained on the same synthetic data: a pair is kept only if its passage is the top-ranked result (K = 1) for its query under that initial retriever; K was tuned on a separate validation set (Sec. 3.2, p.4; Sec. 4.1, p.6). The retriever is then fine-tuned further on the kept pairs (Sec. 3.3, p.5).
- On 11 BEIR datasets the filter improves nDCG@10 on 8 of 11 datasets and by 2.5 points on average (Figure 2a, Sec. 4.3, p.7). It hurts on the smallest sets (NFCorpus and SciFact); the authors conjecture overfitting from further tuning on the filtered data, and note that high-quality pairs were removed because the initial retriever ranked other documents higher; they suggest query-specific K (Sec. 4.3, p.7).
- Few-shot average nDCG@10 for the 110M dual encoder 47.8 against 45.5 for the zero-shot prompt and 46.6 and 46.2 for two retrievers trained on 500K supervised MS MARCO pairs (Table 2, p.7).
- A cross-attention reranker trained on the same generated data adds about 5 points (52.8 average; Table 2, p.7).

## What it did not establish

- No condition separates the filter's judge from the learner: the initial retriever is trained on the unfiltered synthetic data and judges it, with no independent retriever as control. The only evidence about this self-judging choice is the 8-of-11 win count and the two small-set losses.
- The filter's effect is shown as per-dataset deltas in a plot (Figure 2a); no seeds, no intervals; the average 2.5 is the mean of 11 dataset deltas.
- No comparison with weighting instead of removing, and no ordering of the kept pairs. Text only; relevance is "answers the question" style, not multi-positive repository queries.
- Some results are from a language model trained with some benchmark datasets in its instruction mixture (two BEIR datasets), checked in an ablation (Table 3, p.8; average 48.5 against 47.0 without them).

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| Datasets where the filter helps / average gain in nDCG@10 | 8 of 11 / 2.5 points | Sec. 4.3, p.7 |
| Filter rule: K of the top-K kept | 1 | Sec. 4.1, p.6 |
| Few-shot 110M dual encoder, average nDCG@10 (11 BEIR sets) | 47.8 | Table 2, p.7 |
| Zero-shot prompt, same model | 45.5 | Table 2, p.7 |
| Retriever trained on 500K supervised pairs (SPLADE v2 / ColBERT v2) | 46.6 / 46.2 | Table 2, p.7 |
| Few-shot reranker added (average) | 52.8 | Table 2, p.7 |
| Synthetic queries per document / documents sampled per corpus | 8 / 1 million | Sec. 3.1, p.4 |
| Dual-encoder batch size: small corpora / others; steps: large / others | 128 / 6k; 5k / 1k | Sec. 4.1, p.6 |
| Reranker negatives sampled from top 200 | 31 | Sec. 3.3, p.5 |
| Average of the ablation without two benchmark datasets in the language model's mix | 47.0 | Table 3, p.8 |
| Queries generated in all (two prompts) | 58.46M | Sec. 7, p.10 |

## Method details we need

- Pipeline (Figure 5; Sec. 3): generate with the prompt, train an initial dual encoder for a set number of epochs on all synthetic pairs, keep pairs whose passage is the initial retriever's top-K for its query, continue fine-tuning on the kept pairs, then train the reranker.
- Dual encoder: a 110M encoder initialised from a text-to-text model's encoder, pretrained with random crops of one document as positives, fine-tuned with in-batch random negatives (Sec. 3.3, p.5). The paper notes that for small corpora multiple relevant documents in one batch interact negatively with the in-batch loss, so batch size is reduced (Sec. 4.1, p.6).

## Relation to RQ1 / RQ2 / RQ3

- RQ1, RQ3: none.
- RQ2: the clearest published case of a rank-based filter of the form "keep the pair only if the positive is in the top K of a retriever", which is the project's K-rank cut with K = 1, with the judge trained on the same data that it filters (the self-teacher of Q52). It reports a gain on average, with losses where the data are small, and names the failure the project's smoke pilots also saw (filtering removes valid pairs that a judge ranks low; strict K shrinks the usable set). It is not an independent-teacher design, and it gives no evidence that a K chosen on one validation set transfers; K was tuned on a different task.

## Discrepancies

- With the master document: not cited; the project rule that the K-rank encoder is never the model being trained is stricter than this paper's practice.
- Internal: the abstract's "1.2 nDCG on average" over a supervised baseline matches the table (47.8 against 46.6).

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| Round-trip filtering with a self-trained retriever improves retrieval | confirmed on average, mixed per dataset | Sec. 4.3, p.7 | 8 of 11 |
| It hurts small corpora | confirmed by observation, cause conjectured | Sec. 4.3, p.7 | NFCorpus, SciFact |
| K = 1 is best | found on MS MARCO validation | Sec. 4.1, p.6 | not re-tuned per task |
