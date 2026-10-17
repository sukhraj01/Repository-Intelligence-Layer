read: full — 21 pages incl. appendices, PDF v1, pdftotext -layout (poppler) plus page rasters of pp.6, 7 and 9 (Tables 2-4 and 7), 2026-10-17

# CodeR — Li et al. (arXiv 2505.12697v1), "Towards A Generalist Code Embedding Model Based On Massive Data Synthesis"

Source file: arXiv PDF v1, 21 pages (body 9 pages, limitations p.10, references pp.10-12, appendices A-G pp.13-21: instruction tuning, set-up, the 47 task definitions, generation and annotation templates, the filtering template, evaluation instructions). arXiv holds only v1, whose first page says "Preprint. Under review"; the venue given in the project references (NeurIPS 2025) comes from the conference's own listing found by search, not from this PDF. The extracted text has 21 pages once a stray form-feed character in the page-2 text is removed (the raw `pdftotext -layout` output split page 2 into two pieces; extraction was redone page by page so the count equals `pdfinfo`). No page is blank.

**Identifier correction.** The project references (`docs/11_references.md`, `docs/03_literature_map.md` and the master document) give this paper as arXiv 2508.11442. That identifier is a different paper: "CoDiEmb: A Collaborative yet Distinct Framework for Unified Representation Learning in Information Retrieval and Semantic Textual Similarity" (Zhang et al., Tsinghua University and Tencent Youtu Lab; v2 dated 29 Sep 2025, 22 pages), which is about joint training of retrieval and sentence-similarity encoders and has nothing to do with CodeR's data synthesis or its curriculum. See `LANDSCAPE.md`. The CodeR paper is 2505.12697. Every statement below is about 2505.12697v1.

## What it established

- CodeR-Pile: a synthetic training set for code retrieval of 2,885,059 samples over 47 tasks in four task types (text-to-code, code-to-text, code-to-code, hybrid), 20 programming languages and two natural languages (Table 9 p.15; Sec. 3, pp.3-4). Tasks and instructions are drafted by four large models and checked by hand; query-positive pairs are produced by an open 32B code model from files of a public GitHub code corpus; each pair is then judged by the same open model and kept only if labelled a true positive; 15 hard negatives per kept pair are mined from the real corpus with a top-k-percent-of-positive margin (95%) (Sec. 3 pp.4-5; Appendix E p.16).
- Training with a three-stage "Annealing" curriculum on Qwen2.5-Coder-1.5B with LoRA: stage 1 text-only data, stage 2 a mixture of text and code data, stage 3 code data only, restricted to harder samples (Sec. 4, p.5; Figure 3 p.5).
- Results on CoIR (10 datasets) and CodeRAG (6 datasets): average NDCG@10 of 81.77 on CoIR (Table 2 p.6) and 72.8 on CodeRAG (Table 4 p.7), above the baselines the authors ran or quoted, including two closed-source embedding models.
- Ablations of the training procedure (Table 7, p.9) and of the data (Tables 5-6, p.8): task coverage, generator size, mined against generated negatives, annotation accuracy.

## What it did not establish

- Every curriculum and filtering ablation is single-run, with no seed or interval, and most are on a reduced configuration: Table 7 is computed for the model trained on "text-only data and synthetic data" (average 70.12), not the headline model (81.77, Table 2 p.6). The differences are 1.2 to 1.9 points of average NDCG@10 (Table 7, p.9).
- The curriculum is ordered by data source and domain (text, then text and code, then code), not by per-example difficulty or quality inside one data pool, so it is not the CURRICULUM arm of RQ2. The stage-3 data selection is a difficulty filter (below), mixed with the ordering in the same ablation row.
- No code retrieval at repository level and no issue text: CoIR and CodeRAG are function-, snippet- and question-level tasks; the one SWE-bench-derived column is the CodeRAG SWE-bench-Lite split, where CodeR scores 67.4 (Table 4, p.7).
- No agent and no resolved-rate measurement.
- Learning rate, batch size and number of epochs are only partly given (learning rates per stage and temperature are in Appendix C, p.13; batch size is not).
- The annotation-accuracy check (Table 6, p.8) is 10 pairs per task and label, reviewed by human experts "with the assistance of powerful LLMs"; for pairs labelled 0 the open generator's accuracy is only 38% (Sec. 5.3, p.8).

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages. NDCG@10 in percent.

| Claim | Value | Where |
|---|---|---|
| CodeR-Pile size: samples / tasks / programming languages | 2,885,059 / 47 / 20 | Table 9, p.15; Sec. 3, p.5 |
| CodeR average on CoIR | 81.77 | Table 2, p.6 |
| CodeR trained on text and synthetic data only / on text and existing code data only (CoIR average) | 70.12 / 79.77 | Table 2, p.6 |
| Strongest baseline average on CoIR (a closed-source model, version in Table 2) / second strongest | 78.53 / 78.20 | Table 2, p.6 |
| CodeR average on CoIR-filter against the strongest baseline (a closed-source model, version in Table 3) | 93.00 against 88.73 | Table 3, p.6 |
| Margin over the best baseline, CoIR then CoIR-filter | 3.2 then 4.3 points | Sec. 5.2, p.7 |
| CodeR average on CodeRAG / two baselines (a closed-source model, version in Table 4; an open 7B model) | 72.8 / 63.7; 67.0 | Table 4, p.7 |
| CodeRAG SWE-bench-Lite column: CodeR | 67.4 | Table 4, p.7 |
| Ablation (text and synthetic data model): full / without Annealing / without text-only stage | 70.12 / 68.49 / 68.89 | Table 7, p.9 |
| Same: without the closed-source filter step / without both the small-encoder filter and that step | 68.97 / 68.25 | Table 7, p.9 |
| Stages of the same model: after stage 1 / 2 / 3 | 63.14 / 69.13 / 70.12 | Table 7, p.9 |
| Task coverage: all four task types against text-to-code only (CoIR average) | 67.64 against 65.65 | Sec. 5.3, p.8 |
| Annotation accuracy of the open generator on pairs labelled 1 / on pairs labelled 0 | 93% / 38% | Sec. 5.3, p.8 |
| Gain from the larger closed-source generator over the open one | 1.66 points | Sec. 5.3, p.8 |
| Hard negatives per kept pair; margin | 15; 95% | Sec. 3 p.5; Appendix E p.16 |
| Temperature | 0.02 | Appendix B, p.13 |
| Training cost | 5 days on 8 GPUs | Appendix C.2, p.13 |

## Method details we need

- **Stage-3 filter (the quality-signal analogue)** (Sec. 4, p.5): a multilingual small encoder retrieves for each query; if the positive is in the top 3 the sample is "simple" and dropped, otherwise kept as "hard". Then a closed-source model (version named in Appendix F, p.21) labels each remaining sample error, simple, medium or hard from the instruction text in Table 17 (p.21); only medium and hard samples are kept for stage 3. Direction: keep what the small retriever ranks low. SweRank and CoRNStack do the opposite for their positives (keep only if the positive ranks within top K), so the two uses of a retriever as a data filter point in opposite directions; they act on different data (LLM-verified synthetic pairs against mined PR pairs).
- **Instructions** are prepended to queries (Appendix B, p.13). Loss: InfoNCE with temperature 0.02 and the mined negatives (Appendix B).
- **Training set composition**: text-only data from public text retrieval and sentence-similarity sets, CoIR training sets as "existing code retrieval data", and the synthetic set (Appendix C.1, p.13).
- **Base and optimisation**: Qwen2.5-Coder-1.5B, LoRA rank 32, alpha 64, maximum length 512, learning rate lowered by 10x in stage 3, 5 days on 8 GPUs (Appendix C.2, p.13).
- **Benchmarks**: CoIR, a de-duplicated "CoIR-filter" built by the authors, and CodeRAG retrieval (Sec. 5.1, p.6).
- **Closed-source models in the paper's tables**: used as baselines and as task designers and judges; written here only as "a closed-source model (version in the paper's Sec. 3, Table 2 or Appendix F)".

## Relation to RQ1 / RQ2 / RQ3

- RQ1: none beyond showing CodeRAG's SWE-bench-Lite column as one more repository-issue retrieval number.
- RQ2: it is the "curriculum inside a recipe" precedent the master document describes. The three-stage order is data-source ordering, and the one sub-experiment that isolates ordering (Table 7, "without Annealing": mixing all stages' data) is a single run with a 1.6-point average difference on a reduced configuration. It supports the statement that a staged schedule did not hurt and may help at one scale; it does not isolate difficulty ordering from the stage-3 filter.
- RQ3: none.

## Discrepancies

- With the project references: wrong arXiv identifier (2508.11442 is CoDiEmb; see above).
- With the master document (`docs/03_literature_map.md`): "across 16 tasks" is 16 datasets (10 from CoIR and 6 from CodeRAG), grouped into more than 16 task names in the paper; the data-synthesis tasks number 47.
- Internal: the text says CodeR trained "exclusively on synthetic data" outperforms a comparably sized baseline by 2.7 points (Sec. 5.2, p.7), where the table gives the synthetic-only average as 70.12 and the baseline as 67.41; the two statements agree.

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| Master document: "Synthetic heterogeneous data + curriculum (annealing)" | confirmed | Sec. 4, p.5 | Three stages ordered by data domain; the synthetic data is the main contribution. |
| Master document: "across 16 tasks" | confirmed as 16 datasets | Sec. 5.1, p.6 | 10 CoIR plus 6 CodeRAG datasets. |
| Master document: "Curriculum inside a recipe, not a controlled arm" | confirmed | Table 7, p.9 | One run per row; ablation on a reduced configuration. |
| Master document and references: arXiv 2508.11442 | contradicted | arXiv listing and first page of 2508.11442v2 | That identifier is CoDiEmb. The CodeR paper is 2505.12697. |
