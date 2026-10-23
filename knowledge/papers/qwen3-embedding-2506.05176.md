read: full — 14 pages incl. appendices, PDF v3, pdftotext -layout (poppler), the two figures (pp.3-4) rendered and looked at, 2026-10-23

# Qwen3 Embedding — Zhang, Li, Long, Zhang et al. (arXiv 2506.05176v3, technical report, 2025), "Qwen3 Embedding: Advancing Text Embedding and Reranking Through Foundation Models"

Source file: arXiv PDF v3 (dated 11 Jun 2025; v3 is the highest version that resolves), 14 pages: body pp.1-9 (architecture, training, evaluation, a one-table ablation), references pp.9-11, appendix pp.12-14 (synthesis templates, training-data table, per-task tables for English, Chinese and code). The extracted text has 14 pages and no blank page. The two figures (architecture, training pipeline) carry no numbers; they were rendered and looked at. Read for ADR-006 (base encoder): the master document names Qwen3-Embedding-0.6B as the candidate, and CORE-Bench and SweRank report fine-tunes of it.

## What it established

- Three embedding models (0.6B, 4B, 8B) and three rerankers of the same sizes, all initialised from the dense Qwen3 foundation models; every model has a 32K sequence length; the 0.6B embedding model has 28 layers and a 1024-dimensional output, and all embedding models support custom output dimensions ("MRL") and task instructions (Table 1, p.4).
- The models are released under the Apache 2.0 licence (abstract, p.1).
- Embedding = last-layer hidden state at an appended end-of-text token, causal attention. The instruction is prepended to the **query only**; documents are encoded without an instruction. Query input format: `{Instruction} {Query}<|endoftext|>` (p.3).
- Training: stage 1, weakly supervised contrastive training on about 150M synthetic pairs written with a 32B instruct model; stage 2, supervised fine-tuning on about 7M labelled pairs plus about 12M synthetic pairs kept by a cosine-similarity filter (> 0.7); stage 3, spherical-interpolation merging of several stage-2 checkpoints. The rerankers skip stage 1 (Sec. 3.2-3.3, pp.5-6; Table 6, p.13).
- On the 12-task MTEB (Code, v1) suite the 0.6B embedding model averages 75.41 nDCG@10, the 4B 80.06, the 8B 80.68 (Table 3, p.7; Table 9, p.14). The 0.6B model is above every other open model listed on that suite (Table 9: best other 63.74).
- Single-run ablation on the 0.6B model (Table 5, p.8): without the synthetic stage-1 data the code average falls from 75.41 to 74.58; without merging to 74.89; stage 1 alone gives 66.79.

## What it did not establish

- **Nothing at repository level.** No issue-to-function retrieval, no SWE-bench-style localization, no CORE-Bench (which postdates it), no long code files. The code suite is MTEB (Code, v1): function, snippet, question-answer and SQL retrieval tasks (Table 9, p.14).
- **Possible train-test overlap on code.** CodeSearchNet is listed among the supervised fine-tuning data (Table 6, p.13) and CodeSearchNet tasks are part of the code evaluation (Table 9, p.14). The paper does not discuss overlap; the code averages may be inflated relative to unseen code.
- **No training hyperparameters.** The temperature τ, the number of hard negatives K, batch size, learning rate, step counts, the maximum training sequence length and the hard-negative source are not given. The 32K figure is the model's sequence length (Table 1), not the training length; no result is reported for inputs longer than the benchmarks' own.
- **No instruction text for code tasks.** The format is given; the instruction strings used for MTEB (Code) are not listed in the paper.
- **No latency, throughput or memory** for any model.
- One run per configuration, no seeds, no intervals; the ablation (Table 5) is on the 0.6B model only.
- Baseline scores for other models are taken from the online leaderboard (4 June 2025) or other papers, not re-run (Tables 2-3, pp.6-7).

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| Model sizes (embedding and reranker) | 0.6B, 4B, 8B | Table 1, p.4 |
| Sequence length of every model | 32K | Table 1, p.4 |
| Qwen3-Embedding-0.6B: layers / embedding dimension | 28 / 1024 | Table 1, p.4 |
| Qwen3-Embedding-4B / 8B embedding dimension | 2560 / 4096 | Table 1, p.4 |
| Licence | Apache 2.0 | Abstract, p.1 |
| False-negative mask margin: an in-batch item is masked if its score exceeds the positive's by more than | 0.1 | Sec. 3.1, p.5 |
| Stage-1 synthetic pairs | about 150 million | Sec. 3.3, p.6 |
| Cosine filter for synthetic pairs kept in stage 2 | greater than 0.7 | Sec. 3.3, p.6 |
| Stage-2 synthetic pairs kept | about 12 million | Sec. 3.3, p.6 |
| Stage-2 labelled pairs | about 7M | Table 6, p.13 |
| Evaluation: tasks in all / code retrieval tasks | 216 / 12 | Sec. 4.1, p.7 |
| MTEB (Code) average, embedding 0.6B / 4B / 8B | 75.41 / 80.06 / 80.68 | Table 3, p.7 |
| MTEB (Code) average, best other open model in Table 9 | 63.74 | Table 9, p.14 |
| 0.6B on COIR-CodeSearchNet / CodeSearchNet / CosQA | 84.69 / 91.01 / 36.48 | Table 9, p.14 |
| 0.6B on Apps / StackOverflow-QA | 75.34 / 89.99 | Table 9, p.14 |
| Ablation on 0.6B, code average: stage 1 only / without synthetic data / without merging / full | 66.79 / 74.58 / 74.89 / 75.41 | Table 5, p.8 |
| Reranker 0.6B / 4B / 8B on MTEB-Code, top-100 of the 0.6B embedder | 73.42 / 81.20 / 81.22 | Table 4, p.8 |
| Rerankers re-rank this many candidates from the 0.6B embedder | 100 | Sec. 4.2, p.8 |
| MTEB Multilingual mean (task), 0.6B / 8B | 64.33 / 70.58 | Table 2, p.6 |

## Method details we need

- **Pooling and input** (p.3): last-token pooling at the appended end-of-text token. Queries: `{Instruction} {Query}<|endoftext|>`; documents unchanged. For the project this means a task instruction string has to be chosen for issue-to-code retrieval; the paper gives none for code. Same instruction must be used across arms (it belongs in the "held identical" block if this encoder is chosen).
- **Loss** (Eq. 1, pp.4-5): InfoNCE with cosine similarity and temperature τ; the normaliser holds the positive, K hard negatives, in-batch queries (query-query), in-batch documents against the positive document (document-document) and in-batch documents against the query. Every in-batch term carries a mask m_ij = 0 when its score exceeds the positive's score by more than 0.1, or when the in-batch document equals the positive. This is a **false-negative mask built into the loss**, computed by the model being trained.
- **Data filter** (p.6): synthetic pairs for stage 2 are kept if their cosine similarity exceeds 0.7, sampled at random; the scoring model is not named.
- **Synthesis** (Appendix A.1, pp.12-13): document-to-query, a configuration step (question type, difficulty, persona from five retrieved candidates) then query generation with stated length and language.
- **Reranker** (p.3-4): point-wise yes/no classification under a chat template, score = softmax over the "yes" and "no" next-token logits.
- **Merging** (p.5): spherical linear interpolation over checkpoints of stage 2.

## Relation to RQ1 / RQ2 / RQ3

- RQ1: a candidate dense signal. Its code results are on function and snippet tasks, not repository-level issue retrieval; the project's own dense numbers (X2) are the relevant evidence, not these. The 32K sequence length makes long units encodable, but the paper reports nothing about quality or cost at long lengths.
- RQ2 (ADR-006 and the negative policy):
  - The base model was itself trained with a **cosine-threshold filter** on its synthetic data and a **false-negative mask** in its loss. If this encoder is the RQ2 base, the FILTER arm is applied on top of a model already shaped by a filtered stage; this does not break the comparison (all arms share the base), but the description of the base should say so.
  - If the project reuses the paper's mask (in-batch items scoring above positive + 0.1 removed), it is a negative-policy choice that must be held identical across arms; the mask uses the model being trained, which is allowed for the loss but not for the quality signal (the project rule for the K-rank signal).
  - Licence (Apache 2.0) permits use and redistribution of fine-tuned weights.
- RQ3: none directly.

## Discrepancies

- With the project documents: `docs/12_open_decisions.md` and ADR-006 write the candidate as "Qwen3-0.6B" in places, which is CORE-Bench's label for its fine-tune; the released base model is Qwen3-Embedding-0.6B. Both name the same 0.6B embedding base; the wording should say which (base or fine-tuned) a number refers to.
- With CORE-Bench and SweRank: those papers fine-tune this family on pull-request data and report repository-level numbers (`core-bench-2606.11864.md` Table 3; `swerank-2505.07849.md` Table 9). This report gives no repository-level number for the base, so the base's zero-shot strength on the project's task comes only from those papers and from X2.
- Internal: the 8B model's Chinese MTEB mean (task) is 73.83 in Table 3 (p.7) and 73.84 in Table 8 (p.14); a rounding difference. The introduction speaks of "Qwen3-8B-Embedding" (p.2) while the tables use "Qwen3-Embedding-8B"; same model.

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| Master document: Qwen3-Embedding-0.6B is a CPU-feasible encoder with strong code retrieval | partly | Table 1 p.4; Table 9 p.14 | 0.6B parameters and strong MTEB (Code) results confirmed; CPU feasibility is not discussed in the paper (no latency or memory) and is for X2 to measure |
| Licence permits the project's use | confirmed | Abstract p.1 | Apache 2.0 |
| Long context (32K) | confirmed as model sequence length | Table 1 p.4 | no evaluation at long input lengths |
| Instruction-aware embedding | confirmed, query side only | p.3 | documents carry no instruction |
| Code retrieval results transfer to repository-level issue localization | not established | — | no such evaluation in the paper; CodeSearchNet appears in both the training data (Table 6) and the code evaluation (Table 9) |
