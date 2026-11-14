read: in full except the example figures and prompt templates of the appendix (pp. 15 to 22); pages 1 to 14 were read — 22 pages incl. appendices, PDF v1, pdftotext -layout (poppler), page counts equal (pdfinfo 22, extracted 22, none blank); appendices A-D (training set-up, extended tables, benchmark details, prompts and examples) read; re-read in full from the stored PDF (SHA-256 b639f109ccf17776ba3f685be545635792b3233c27bf7c6959b603858f2cd710), first read 2026-10-29, 2026-11-14

# MM-IssueLoc — Zhan, Hu, Feng and colleagues (arXiv 2607.15205v1, July 2026), "A Controlled Benchmark for Evaluating Visual Evidence in Multimodal Repository-Level Issue Localization"

Re-read 2026-11-14 from the stored PDF: body and appendices read page by page; the reference list (pp. 9 to 10) was checked for the entries the text cites rather than read entry by entry. Pages 15 to 22 (example figures and prompt templates) were scanned, not read line by line; nothing in the report rests on them. Pages 1 to 14 were read in full, including Tables 5 to 17.

Source file: arXiv PDF v1 (16 Jul 2026), 22 pages (body pp.1-9, references pp.9-11, appendices A-D pp.11-22: training configuration, stratified slices, cross-benchmark results, benchmark details, extraction prompts and examples). Issue localization with attached images, 23 languages. Included because its companion retriever is trained on repository-local hard negatives with one row per gold location and a file-to-function training schedule, with an ablation of that schedule (Appendix B.2).

## What it established

- A benchmark of 652 issue-PR instances over 608 repositories with 1,050 images; file-level gold for all instances, function-level gold for 343; strict all-gold Acc@K (every gold location in the top K) is the primary metric (Sec. 3-4, pp.2-6). Retrieval-based systems are competitive at function level: the best retriever reaches 33.86 function Acc@10, the best agent 22.45 (Table 2, p.7); agents lead at file level (best 38.96 file Acc@5 for an agent, 32.82 for the best retriever).
- Companion training data: 13,196 file-level rows over 7,664 instances and 13,769 function-level rows over 3,999 instances; "multi-positive expansion" emits one row per gold file or function; hard negatives are same-repository non-gold candidates ranked by a general multimodal embedding model (8B), with a temperature 0.05 InfoNCE loss and no stated false-negative removal (Sec. 3.4, p.4). The training data are disjoint from the benchmark at the instance level (Sec. 3.4, p.4; repository-level overlap not discussed).
- Curriculum ablation, single run per cell (Table 12, p.12; training settings Table 5, p.11): training on file-level rows first and function-level rows second ("full curriculum") gives function Acc@10 of 32.36 (2B) and 33.86 (8B) against 30.03 and 29.15 for function-level rows only; file-only training gives the best file Acc@5 (32.36 and 35.12) and the worst function Acc@10 (27.41 and 20.70). The authors call these results "sensitive to curriculum" (B.2, p.11).
- Removing images from the query costs the controlled retriever 4.91 and 4.44 file Acc@5 points; for agents the change is below one point or of mixed sign (Table 3, p.8).

## What it did not establish

- The curriculum here is a data-granularity order (file rows, then function rows), not an order by example difficulty, and it also adds training time (2 + 3 epochs against 3), so its gain over function-only training is not at matched updates; seeds are single (42, 43; Table 5).
- No ablation of the hard-negative policy is shown, although the introduction says the retriever tests "hard-negative design" (Sec. 2, p.3): Appendix B.2 contains only the curriculum and the image-conditioned training ablations (Tables 12-13, p.12). Hard negatives mined from a model that is also the starting checkpoint of the 8B variant are not discussed as a self-teacher risk, and false negatives among same-repository non-gold candidates (with several gold locations per issue, many) are not filtered.
- No intervals, no repository-clustered statistics; Table 3 and Table 12 differences are of the order of 1 to 5 points on 343 to 652 instances.
- The paper's own cross-benchmark rows come from derived gold labels (patch files and functions) and from a harness whose valid-submission rate differs widely between agents (98.6% against 47.1%, Sec. 5.1, p.6).

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| Instances / images / function-level instances | 652 / 1,050 / 343 | Abstract and Sec. 3.2, pp.1-4 |
| Best agent file Acc@5 / best agent function Acc@10 | 38.96 / 22.45 | Table 2, p.7 |
| Best retriever function Acc@10 (8B, trained on the companion data) | 33.86 | Table 2, p.7 |
| Training rows: file-level / function-level | 13,196 / 13,769 | Sec. 3.4, p.4 |
| InfoNCE temperature | 0.05 | Sec. 3.4, p.5 |
| Function Acc@10, 2B: full curriculum / function-only / file-only | 32.36 / 30.03 / 27.41 | Table 12, p.12 |
| Function Acc@10, 8B: full curriculum / function-only / file-only | 33.86 / 29.15 / 20.70 | Table 12, p.12 |
| File Acc@5, 8B: file-only / full curriculum | 35.12 / 32.82 | Table 12, p.12 |
| Effect of removing images on retriever file Acc@5 (2B / 8B) | 4.91 / 4.44 | Table 3, p.8 |
| Valid submission rate of two agent harnesses with the same backend | 98.6% / 47.1% | Sec. 5.1, p.6 |
| Stage-1 / Stage-2 epochs and learning rates | 2 at 1e-5 / 3 at 5e-6 | Table 5, p.11 |
| Global batch size, 2B / 8B | 128 / 64 | Table 7, p.11 |

## Method details we need

- Rows (Sec. 3.4, p.4): anchor = issue text plus at most two images; positive = one gold file or function per row; negatives = same-repository non-gold candidates ranked by a general-purpose embedding model; candidates carry "File:" or "Function:" prefixes.
- Schedule (Table 5, p.11): stage 1 on file rows from the pretrained checkpoint for 2 epochs; stage 2 on function rows from the stage-1 checkpoint for 3 epochs at half the learning rate; the function-only ablation starts from the pretrained checkpoint.
- Hardware (Table 7, p.11): four H200 GPUs; 2B with per-GPU batch 4 and 8 accumulation steps, 8B with per-GPU batch 1 and 16.

## Relation to RQ1 / RQ2 / RQ3

- RQ1: strict all-gold Acc@K and the observation that a trained function-level retriever beats agents at function level are context for the evaluation unit (D12); not a signal ablation.
- RQ2: the only trained repository-issue retriever in the reading list that mixes (a) a data-order schedule, (b) repository-local mined negatives and (c) one-row-per-positive multi-positive expansion; the schedule ablation shows that an order change can move function-level metrics by 3 to 5 points in one run and that the order trades off between file-level and function-level ranking. It does not examine difficulty ordering, filtering or weighting, and it names false negatives only for the benchmark's labels. A reminder that "curriculum" means three different things across the papers read (granularity order, difficulty order, shrinking subset).
- RQ3: none (localization only, no repair).

## Discrepancies

- With the master document: not cited. With the introduction of this paper: it says the retriever tests "stage-curriculum and hard-negative design"; the appendix tables contain only the curriculum and image ablations (see above).
- Internal: the abstract says the strongest retriever reaches 33.86 function Acc@10, consistent with Table 2.

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| File-then-function training improves function ranking | confirmed in one run | Table 12, p.12 | not matched in epochs |
| Hard-negative design tested | not found in the appendices | Tables 12-13, p.12 | only mentioned in the introduction |
| Images help a trained retriever more than agents | confirmed on this benchmark | Table 3, p.8 | single runs |
