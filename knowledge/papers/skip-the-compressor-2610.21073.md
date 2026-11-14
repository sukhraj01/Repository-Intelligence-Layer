read: full — 24 pages incl. appendices, PDF v1, pdftotext -layout (poppler); re-read in full from the stored PDF (SHA-256 5b798557d73f31cbdb40b8e6bd67bb0c9117517941fbd0dd5df7a6ac5ad5a3be), first read 2026-11-12, 2026-11-14

# Skip the Compressor: Coding Agents Fix More Issues When They Pick Whole Files — Yang, Chatterjee, Udupi, Ramavarapu and Zhai (arXiv 2610.21073v1, 15 Oct 2026)

Re-read 2026-11-14 from the stored PDF: body and appendices read page by page; the reference list (pp. 9 to 11) was checked for the entries the text cites rather than read entry by entry.

Source file: arXiv PDF v1, 24 pages (body 9 pages with limitations and ethics statement, references pp. 9-11, appendices A to I pp. 11-24). arXiv holds only v1. The extracted text has 24 pages and no blank page. Every page was read, including Tables 1-18, Figures 1-6 (values read from the captions and the extracted labels) and the algorithm listings. Literature-scan source for the refresh of 2026-11-12 (topic: repository context for coding agents at a fixed token budget, graded by the benchmark's tests).

## What it established

- At an equal per-issue token budget, a context made of a few whole files chosen by the model under test (CQ2-CARE) resolved more issues than three prompt compressors and three retrievers, with each of two closed-source models; the budget of every competing method on an issue is the realized size of the selector's context for that issue (Sec. 2-3, pp.3-5; Table 1, p.4).
- The losses separate: retrievers keep text verbatim but often show no file to edit (Table 2, p.5); compressors keep the files but alter the text, so fewer patches apply (Sec. 4.1, p.6). Two post-hoc controlled tests change one factor at a time: deleting 20% of the tokens of the selector's own contexts costs 9.7 points, and a compressor that cuts whole lines from the selector's own candidate files matches the selector (Sec. 4.2, p.6; Table 8, p.17).
- A trained retriever of whole functions (SweRank, added after the main results) is within two points of the selector with both models, and a trained line pruner trails (Table 1, p.4).
- Context methods should be compared end to end with the benchmark's tests: grading by test-command exit code credited an empty patch on 4 of 6 issues checked (Sec. 5, p.8; Appendix C, p.13).
- A second patch sample of the same contexts flips 8.7 to 18.9% of outcomes, and most cells have one sample (Limitations, p.9; Appendix G, p.16).

## What it did not establish

- A multi-turn agent loop: one patch call per context, Python only, one benchmark, 300 issues (Limitations, p.9). The authors say whether an agent that can re-open files recovers the losses needs a full agent loop (Sec. 5, p.8).
- That a selector beats a code-aware compressor that starts from the same files: given the selector's own candidates, LongCodeZip matched it (Sec. 5, p.8; Table 8, p.17).
- Anything about retrieval supervision: the retrievers are used as published (BM25, CodeRankEmbed, SweRank); nothing is trained here (Sec. 3.2, p.5).
- The four planned hypotheses were not pre-registered: the written plan was not frozen or time-stamped (Appendix D, p.14); several comparisons, including the two trained methods and file-level BM25, are post hoc.
- SweRank may have trained on other pull requests from the evaluated repositories, so its small gap does not show equal performance (Limitations, p.9).
- Contamination is not ruled out; the gaps do not shrink detectably on newer issues (Limitations, p.9; Table 18a, p.24).

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages. Resolved rates are in percent of 300 issues.

| Claim | Value | Where |
|---|---|---|
| Issues in the study, one per repository | 300 | Sec. 1, p.2; Sec. 3.1, p.4 |
| Benchmark leaderboard population and repositories | 860 tasks, 413 repositories | Sec. 3.1, p.4 |
| Candidates drawn / passing the gold-patch eligibility check | 340 / 328 | Sec. 3.1, p.4 |
| Selector resolved, first model / second model | 43.7 / 46.7 | Table 1, p.4 |
| Lead over the best compressor, either model | 6.3 points | Abstract, p.1; Sec. 3.3, p.5 |
| Lead over the best of three retrievers | 9.3 and 12.7 points | Abstract, p.1; Sec. 3.3, p.5 |
| Trained retriever of functions, resolved (two models); gap to the selector | 43.0 and 45.0; 0.7 and 1.7 points | Table 1, p.4 |
| Gold files as context / no source, first model | 49.3 / 8.7 | Table 1, p.4 |
| File-level BM25 (the benchmark's own retrieval baseline), resolved, first model | 34.3 | Table 1, p.4 |
| Patches that apply: selector / token compressor with the most deletion, first model | 98.0 / 70.7 | Table 1, p.4 |
| Deleting 20% of the tokens of the selector's contexts: patches applying, resolution change | 78.7, 9.7 points | Sec. 4.2, p.6 |
| Second patch sample on intact contexts: resolution difference | 0.0 | Appendix G, p.15 |
| Share of outcomes flipped by a second patch sample | 8.7 and 18.9 | Limitations, p.9 |
| Exit-code grading credited an empty patch on issues checked | 4 of 6 | Sec. 5, p.8 |
| Selector's tokens against the uncompressed single draw, first model | 0.68 | Sec. 4.4, p.7 |
| Mean context tokens of the selector, first model (thousands) | 13.8 | Table 1, p.4 |
| Bootstrap resamples; Holm-adjusted one-sided exact McNemar | 20,000 | Appendix B, p.12 |
| API cost, whole study, first model / second model (dollars) | 830 / 1,438 | Appendix B, p.13 |

## Method details we need

- **Budget matching** (Sec. 2-3, pp.3-4; Appendix B, p.12): the selector's context is built first and its realized token count (o200k tokenizer, headers included) is the budget of every compressor and retriever on that issue; compressors search only their own rate setting for a result within 2% of the budget and miss the window on a quarter to a third of issues, almost always by landing under it (Sec. 4.3, p.7).
- **Selector** (Algorithm 1, p.3): the model sees a path inventory only, names which files must change in independent draws, keeps the files two draws agree on outside test and documentation directories, then requests up to four typed searches whose matches add short evidence spans; files are shown whole, capped at 60K tokens, and a block that would exceed 80K tokens is dropped.
- **Grading** (Sec. 3.2, p.5; Appendix B, p.12): the benchmark's own harness fork with the issue's tests; patches that fail to parse or apply count as unresolved; every issue was checked in advance to be resolved by its gold patch and not by an empty one; paired exact McNemar tests with Holm correction and issue-level bootstrap intervals.
- **Statistics caveat** (Sec. 3.2, p.5; Appendix D, p.14): the issue is the unit, repositories are one per issue, so intervals are over issues drawn from distinct repositories.

## Relation to RQ1 / RQ2 / RQ3

- RQ1: a precedent for the assembly stage. The project's assembly packs ranked units to a token cap and orders them by file and line; this paper shows that for a repair call the text of what is shown must be verbatim and that a budget spent on the right files matters. The project's context is verbatim by construction (units are source spans); the project does not test whole-file selection against unit packing.
- RQ2: none (no training).
- RQ3: (i) a second source for a fixed-budget, test-graded comparison of context methods with a paired design; (ii) a measured run-to-run flip share of 8.7 to 18.9% of outcomes between two patch samples, in the range the project's pilot saw for repeated replies (inference; different model and benchmark); (iii) it warns that exit-code grading can credit an empty patch, while the project's executor runs the named tests and reads per-test outcomes, with no exit-code rule (project entry E-RQ3-EXEC, D106; the paper does not describe that executor).

## Discrepancies

- The earlier landscape lead (an open question on whole-file selection against retrievers at a fixed budget, from a listing only) is answered in part: the paper's answer is yes on one benchmark and one patch call, with the selector choosing files by model calls, not by a retriever.
- The paper calls its three compressors and three retrievers "drop-in baselines"; SweRank and the line pruner were added after the main results and their tests are labelled post hoc by the authors (Table 1 caption, p.4).
- No contradiction with the project's text was found. The project's retrievers differ: units rather than chunks or whole files, and fused scores.

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| Lead (landscape, listing only): whole-file selection beats retrievers at a fixed token budget | confirmed for one benchmark, single patch call | Table 1, p.4 | CQ2-CARE selects files by the model's own answers; the retrievers it beats are file-level BM25, chunk BM25, chunk dense. |
| Lead: "a second sample flipped 8.7 to 18.9% of outcomes" | confirmed | p.9 | Same figure on p.16 is 8.7 to 10.0% for one 100-issue subset. |
| Paper states that the plan was pre-registered | not found | Appendix D, p.14 | The authors state they do not claim pre-registration. |
