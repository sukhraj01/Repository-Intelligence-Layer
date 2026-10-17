read: NOT READ (the identifier 2508.11442 given in the project references for the CodeR paper resolves to a different paper, CoDiEmb; only its abstract and the first pages were looked at to establish that, and the paper is off topic for this project)

# CoDiEmb — Zhang et al. (arXiv 2508.11442v2), "CoDiEmb: A Collaborative yet Distinct Framework for Unified Representation Learning in Information Retrieval and Semantic Textual Similarity"

Source file: arXiv PDF v2 (dated 29 Sep 2025), 22 pages; fetched, the first pages read, the rest not read. No number from it is quoted anywhere in this repository.

## What it established

- Not assessed beyond the abstract: a framework for training one text encoder jointly on retrieval and sentence-similarity data with task-specific losses, a sampler that builds single-task batches, and a checkpoint-merging step (abstract, p.1). No code, no repository-level retrieval, no issue localization.

## What it did not establish

- Anything about code retrieval, data synthesis or curricula. It does not contain the "annealing" curriculum the project references attribute to CodeR; that paper is arXiv 2505.12697 (`coder-2505.12697.md`).

## Numbers we may quote

| Claim | Value | Where |
|---|---|---|

## Method details we need

- Not extracted.

## Relation to RQ1 / RQ2 / RQ3

- None. Listed only because the project references point to this identifier.

## Discrepancies

- Project references (`docs/11_references.md`, `docs/03_literature_map.md`) and the master document name 2508.11442 as "CodeR / Towards a Generalist Code Embedding Model Based on Massive Data Synthesis" (Li et al., NeurIPS 2025). That title and author list correspond to arXiv 2505.12697. The derived documents are not edited (see `PROJECT_STATE.md`, open questions).

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| arXiv 2508.11442 is CodeR | contradicted | p.1 of the PDF | The title page names CoDiEmb and authors from Tsinghua University and Tencent Youtu Lab. |
