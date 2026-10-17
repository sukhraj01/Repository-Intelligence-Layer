read: full — 29 pages incl. appendices, PDF v1, pdftotext -layout (poppler) with the extraction redone page by page; tables read from the extracted text, 2026-10-17

# Agent Retrieval Bench — Qin and Xie (arXiv 2607.24882v1, 27 Jul 2026), "Agent Retrieval Bench: Evaluating Repository Context Retrieval for Coding Agents"

Source file: arXiv PDF v1, 29 pages (body 20 pages, appendices A-E and references pp.20-29: repository table, sample schema and one real sample per task, embedding set-up, edit2ripple numbers, a closed-tool diagnostic). arXiv holds only v1. The extracted text has 29 pages and no blank page. Every page was read, including all 28 tables; the long reference list was read for the works it names.

## What it established

- A file-level benchmark of context a coding agent needs next, built from workflow signals rather than issue texts: 427 samples over 25 repositories, split into code2test (106; find tests linked to an implementation change), comment2context (80; additional files for a review comment), trace2code (101; root-cause source for a reproduced failure), edit2ripple (58; files affected by a given edit), 50 natural no-gold cases and 32 wrong-repository controls (Table 2, p.7). Each sample is scored against the repository at the base commit (Sec. 3, pp.4-5).
- Static results over 345 positive samples: the best sample-weighted MRR is an embedding model (Qwen3-Embedding-4B, 0.2379), the best Recall@20 is the 8B sibling (0.7029), and the best Budgeted Context Yield at 8k tokens is an "aider-style" repository-map baseline (0.3788) (Table 4, p.9). The ranking changes under repository weighting (Table 5, p.10).
- On trace2code the repository-map baseline wins by a wide margin (MRR 0.2742 against 0.0827 for the 4B embedding model; Table 20, p.18); on the other tasks embeddings win (Table 6, p.10).
- A reciprocal-rank fusion of the 8B embedding model and the repository map beats both on three tasks (overall MRR 0.2713 against a best single run of 0.2296; Recall@20 0.7331 against 0.7070; Sec. 8.4, p.12).
- Logged agent trajectories on the three tasks never touch a gold file on 35.2% of samples for one closed-source agent and 27.2-29.3% for two others (Sec. 8.7, pp.13-14); a 45-sample, one-run-per-cell seed pilot gives higher File F1 with retrieval-derived context than with random non-gold context (Table 16, p.15).
- Natural no-gold abstention fails: no ranker improves selective success once wrong-repository controls are removed (Table 19, p.16).

## What it did not establish

- No claim about resolved rate, and it says so: "We do not claim that retrieval is the dominant cause of patch failure ... or that the present results estimate the effect of retrieval on patch success" (Sec. 1, p.2); no patch-success label exists for these samples, and the paper reports neither patch success nor a correlation with SWE-bench success (Sec. 8.7, p.15).
- No ablation of retrieval signals inside one retriever and no latency measurement; "structural" and "semantic" are two different systems compared and fused, not one system with a signal switched on and off. The repository map ranks files using "path, symbol, reference, and repository graph signals" (Sec. 7, p.8) and is a heuristic, not a typed edge graph.
- No issue-to-edit localization: queries are pull-request summaries, review comments, failure output and anchored edits; gold files include tests and context files that are not edited.
- No training: every retriever is used zero-shot with no instruction prefix, which the authors call "prompt-free" and not each model's best configuration (Appendix C, p.26). Nothing is said about supervision or data quality.
- No confidence intervals or paired tests; the seed pilot has one trajectory per sample and arm, and the authors say small differences between retrieval arms "should not be interpreted as statistically resolved" (Sec. 8.7, p.15).
- The sample is small and uneven: one repository (Gin) supplies 88 of the 345 positive samples and the four largest supply 203 (58.8%) (Sec. 8.1, p.10).

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| Samples: total / positive / natural no-gold / wrong-repository controls | 427 / 345 / 50 / 32 | Table 2, p.7 |
| Positive samples by task: code2test / comment2context / trace2code / edit2ripple | 106 / 80 / 101 / 58 | Table 2, p.7 |
| Corpus manifest: base-commit snapshots; files; chunks | 308; 391,932; 7,922,369 | Sec. 5.1, p.7 |
| Snapshots used by the released samples | 271 | Sec. 5.1, p.7 |
| Duplicate chunk-text fraction over the 287-sample evaluation corpora | 81.99% | Sec. 5.1, p.8 |
| 8B embedding model: Recall@20 / MRR (all 345 positive samples) | 0.7029 / 0.2336 | Table 4, p.9 |
| 4B embedding model: Recall@5 / Recall@10 / Recall@20 / MRR / BCY@8k | 0.3182 / 0.4434 / 0.6306 / 0.2379 / 0.3409 | Table 4, p.9 |
| Repository-map baseline: Recall@20 / MRR / BCY@8k | 0.6333 / 0.2158 / 0.3788 | Table 4, p.9 |
| BM25 baseline: Recall@20 / MRR | 0.4452 / 0.1520 | Table 4, p.9 |
| Repository-macro Recall@20 (4B / 8B) and MRR (4B / 8B) | 0.6344 / 0.6193; 0.2501 / 0.2238 | Table 5, p.10 |
| Repository concentration: four largest repositories | 203 samples (58.8%) | Sec. 8.1, p.10 |
| trace2code MRR: repository map / 4B embedding | 0.2742 / 0.0827 | Table 20, p.18 |
| trace2code Recall@20: repository map / 8B embedding | 0.8366 / 0.7970 | Sec. 8.4, p.12 |
| Fusion of the 8B embedding and the repository map: overall MRR / Recall@20 | 0.2713 / 0.7331 | Sec. 8.4, p.12 |
| Best single run for comparison: MRR / Recall@20 | 0.2296 / 0.7070 | Sec. 8.4, p.12 |
| Trace2code Recall@20 of the fusion | 0.8795 | Table 9 and Sec. 8.4, pp.11-12 |
| Agents never touching any gold file | 35.2%; 27.2-29.3% | Sec. 1, p.2; Sec. 8.7, p.14 |
| Seed pilot, final File F1: no seed / random non-gold / lexical / hybrid / oracle gold | 0.3222 / 0.3437 / 0.3981 / 0.3967 / 0.6337 | Table 16, p.15 |
| Seed pilot size | 45 samples, one trajectory per cell | Sec. 8.7, pp.14-15 |
| Selective success, natural-only protocol, with abstention against none: lexical | 0.294 against 0.499 | Table 19, p.16 |
| Same, embedding model (Jina 0.5B) | 0.334 against 0.489 | Table 19, p.16 |
| Gold files over 500 lines / median labelled evidence as a share of its file | 51.8% / 4.7% | Sec. 8.6, p.13 |
| Line-level F1 of the strongest line scorer (4B embedding) / of the 8B embedding | 0.0276 / 0.0165 | Table 12, p.13 |

## Method details we need

- **Protocol** (Sec. 3, pp.4-6): sample = repository, base commit, query, gold files; corpus = repository at the base commit, chunked for scoring and de-duplicated to files by the highest chunk score; metrics Recall@5/10/20, MRR, and Budgeted Context Yield (BCY@B, the share of gold files that appear, at least by one content token, in a greedy packing of the ranked files into B tokens with a fixed regex tokeniser); on trajectories, a 2x2 table of retriever hit against agent touch and a "potential exploration savings" upper bound.
- **Leakage controls** (Sec. 6, p.8; Table 3): exact gold path, raw patch or diff, fix-commit hash and generated review artifacts are counted as fatal shortcuts and are reported as zero; this is traceability of labels, not proof that every useful file is labelled.
- **Labels and audit** (Sec. 5.1, p.7): evidence-linked gold files; a "model-assisted evidence audit" that does not write queries; mechanism labels (direct, structural, workflow, causal) are deterministic rules and are not a gold definition (Sec. 3, p.5).
- **Baselines** (Sec. 7, pp.8-9): BM25; a path-aware TF-IDF "lexical" heuristic ("should not be read as standard BM25"); the repository-map baseline; five open embedding models with no instruction prefix and normalised dot-product scoring (Appendix C, p.26); closed-source agents appear only in the trajectory track (Table 10 p.12 and Table 13 p.13; version strings are in those tables).
- **Hardware**: an NVIDIA H20 GPU for the edit2ripple runs (Appendix C, p.26).
- **Repositories** (Appendix A, p.21): 25, of which 13 are Python (including pytest, which is also one of the SWE-bench Verified repositories; see `data/held_out/held_out_repos.json`).

## Relation to RQ1 / RQ2 / RQ3

- RQ1: supports the weak form of the premise that different retrievers find different files and that a rank fusion helps: complementarity is shown across systems (trace2code in the repository map's favour, other tasks for embeddings; fusion gains in Sec. 8.4; the 2x2 matrices in Table 15). It does not provide the thing RQ1 asks for, an incremental signal ablation on a dense baseline with latency per row, and its structural system is a path-and-symbol heuristic, not an edge-typed call graph.
- RQ2: nothing about supervision. It is a reminder that zero-shot rankings are sensitive to the missing instruction prefix.
- RQ3: it is explicit that file retrieval quality and patch success are separate quantities and measures only the former plus a 45-sample agent pilot; it reports that interactive agents miss gold in 27-35% of samples even with exploration, which is relevant to how much headroom a better retriever can give an agent.

## Discrepancies

- With the master document (`docs/03_literature_map.md`): "semantic and structure-aware retrieval are complementary" is supported (Sections 8.2-8.4, 9.1), but the structural system is a repository map from agent practice, and the evidence is per-task winners and one two-system fusion. "Supports RQ1's premise" is true only in the sense above (see Claims checked).
- Internal: the text reports "best single-run value of 0.2296" MRR and 0.7070 Recall@20 for the fusion comparison (p.12), which come from the 287-sample three-task subset, while Table 4 gives 0.2336 and 0.7029 for the 345-sample set; the two numbers describe different sample sets.
- Internal: the abstract and Sec. 1 say Qwen3-Embedding-4B has the best sample-weighted MRR and the 8B model the best Recall@20; under repository weighting the 4B model leads both (Table 5, p.10), which the paper states (p.10).

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| Master document: "File-level repository context retrieval" | confirmed | Sec. 3, p.4 | Ranked files; chunks only for scoring. Queries come from PR, review, failure and edit signals, not issue texts. |
| Master document: "semantic and structure-aware retrieval are complementary" | confirmed at system level | Tables 4, 6, 9, 15; Sec. 8.4 p.12; Sec. 9.1 p.18 | Different winners by task; trace2code reverses the aggregate order; fusion of two systems beats both. The structural system is a path, symbol, reference and graph heuristic, so this says nothing about call-graph edges as a signal inside one retriever. |
| Master document: "Supports RQ1's premise" | partly supported | Sec. 7 p.8; Sec. 8.4 p.12 | No signal ablation on a shared retriever and no latency column; n is 345 positive samples in 25 repositories, concentrated in a few. |
| Statement that Agent Retrieval Bench shows retrieval quality matters for agent outcomes (paraphrase of how the paper is sometimes summarised) | not supported as stated | Sec. 1 p.2; Sec. 8.7 p.15 | The paper disclaims a retrieval-to-patch-success claim and offers a 45-sample single-run pilot on File F1, not on patches. |
