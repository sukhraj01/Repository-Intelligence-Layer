read: full — 12 pages incl. appendices, PDF v5, pdftotext -layout (poppler) plus page raster of p.10 (Table V), 2026-10-17

# Jarvis — Huang et al. (arXiv 2305.05949v5, ICSE 2023)

Source file: arXiv PDF v5 (dated 10 Sep 2024), 12 pages (body 9 pages, related work and conclusion pp.10-11, references pp.11-12; no appendix). The text was read from v4 and v5 was then diffed against it: the two differ only in date and whitespace characters, so what was read applies to v5. The extracted text of v5 has 12 pages and no blank page. v1 (10 May 2023, then titled "Scalable Demand-Driven Call Graph Generation for Python") and v2/v3 were fetched only to compare the abstract's recall claim (see Discrepancies); they are not sources. Every table was read; Table V was also looked at as a raster.

## What it established

- A static call-graph generator for Python that is flow-sensitive and works one entry function at a time ("application-centered"): per-function type graphs, intra-procedural analysis with strong updates when no loop intervenes, inter-procedural analysis on demand, and call edges produced on the fly (Sec. III, pp.3-5). The prototype is called Jarvis.
- PyCG, run in whole-program mode (the application plus about 190-237 dependent libraries), exceeds a 24 hour limit on four of six applications, runs out of memory on one and hits a recursion error on one (Table I p.1; Table III p.8).
- Four evaluation scenarios are defined: exhaustive application-only (E.A.), exhaustive whole-program (E.W.), application-centered application-only (A.A.) and application-centered whole-program (A.W.) (Sec. IV-A, p.6).
- A larger macro-benchmark than PyCG's (six applications, 20,085 ground-truth call relations over 5,653 functions) and an extended micro-benchmark (Sec. IV-A, pp.6-7).
- Accuracy: on the exhaustive application-only scenario Jarvis has average precision 0.99 and recall 0.82 against PyCG's 0.99 and 0.76; in A.W. it has 0.35 precision and 0.60 recall against PyCG's 0.19 and 0.48-0.52 (Table V, p.10).

## What it did not establish

- No accuracy number for the exhaustive whole-program scenario (the authors skip it "because of the potentially huge effort in constructing the ground truth", p.7).
- The ground truth is built from test executions plus manual additions by the authors, so it has the limits the Total Recall study describes for test-based baselines (see `total-recall-helm-2024.md`); the paper does not discuss that issue and calls validity of the ground truth its main threat (Sec. IV-E, p.11).
- No confidence interval; one run per cell; no test of significance.
- The macro-benchmark has six projects chosen as "runnable command-line projects" with test cases (p.6); no library-style repository is among them.

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| Macro-benchmark size: applications / ground-truth functions / call relations | 6 / 5,653 / 20,085 | Table II p.6; Sec. IV-A p.7 |
| Ground-truth effort | 6 person months, three authors | Sec. IV-A, p.7 |
| Application-only exhaustive (E.A.) average precision / recall, Jarvis | 0.99 / 0.82 | Table V, p.10 |
| Same, PyCG (one iteration) | 0.99 / 0.76 | Table V, p.10 |
| Application-centered whole-program (A.W.) average precision / recall, Jarvis | 0.35 / 0.60 | Table V, p.10 |
| Same, PyCG after one iteration and after two (four projects) | precision 0.19 and 0.19; recall 0.48 and 0.52 | Table V, p.10 |
| Application-centered application-only (A.A.) average precision / recall, Jarvis | 1.00 / 0.66 | Table V, p.10 |
| Headline gains stated in the abstract | 67% faster, 84% higher precision, at least 20% higher recall | Abstract p.1 |
| Recall gain stated in the body for A.W. (1) and A.W. (2) | 15% and 10% | Sec. IV-C, p.9 |
| Micro-benchmark: programs in Table IV; complete cases PyCG / Jarvis | 138; 113 and 132 | Table IV and Sec. IV-C, p.9 |
| Micro-benchmark: sound cases PyCG / Jarvis | 126 and 134 of 138 | Table IV, p.9 |
| Average time, whole-program one iteration: PyCG / Jarvis | 502.82 s / 301.26 s | Table III, p.8 |
| Jarvis application-centered whole-program time and memory | 8.16 s and 227 MB | Sec. IV-B, p.8 |
| Size of the function type graphs against the assignment graph | 39,714 against 107,499, 63% smaller | Sec. IV-B, p.7 |
| Case study: projects, vulnerabilities, reachable through call chains | 43 projects; 36 vulnerabilities; 6 reachable | Sec. IV-D, p.9 |

## Method details we need (how precision and recall are defined and measured for Python)

- **Definition.** Precision = |CG_Gen.E ∩ CG_GT.E| / |CG_Gen.E| and recall = |CG_Gen.E ∩ CG_GT.E| / |CG_GT.E|, where E is the set of call edges (Eq. 1, p.7). Edges are caller-to-callee pairs; matching is by edge identity (no rule for naming is given, same gap as PyCG).
- **Micro-benchmark.** Complete and sound as in PyCG, plus counts of true positive, false positive and false negative edges per category (Table IV p.9). The ground truth for the PyCG programs is reused; new programs are written by the authors. PyCG totals: 317 true positives, 27 false positives, 27 false negatives; Jarvis: 335, 7, 9 (Table IV, p.9).
- **Macro ground truth.** Step 1: run each application's tests and collect call traces with `python -m trace --listfuncs`; implicit interpreter calls (import machinery) are removed. Step 2: three authors read every application function and add missing call relations (p.7). So the truth is test-executed edges plus hand additions, not an execution-only baseline.
- **Application-centered accuracy counts chains.** In A.A. and A.W. "accuracy is computed by comparing chains of call relations from entry functions"; one wrong edge makes the edges below it wrong too, so the authors say imprecision is "magnified" (p.8). Numbers from E.A. and A.W. are therefore not on the same scale; the drop from 0.99 to 0.35 precision is partly this counting (their own explanation, p.8).
- **PyCG adaptations.** PyCG has no entry-function mode, so its graph is pruned to functions reachable from the entry functions (p.7). PyCG is evaluated after one iteration, two iterations and at its fixed point (E.W. (1), (2), (m)).
- **Entry functions.** Application functions called by test cases plus module-level code run on import (p.6).
- **Hardware.** MacBook Air with an M1 chip and 8 GB memory (p.6).
- **Language features.** New support: context managers, argument handling, assignments, direct calls, imports, control-flow strong updates (p.6). Residual false negatives: functions held in lists, tuples and dicts, and calls into dynamically linked libraries (p.9).

## Relation to RQ1 / RQ2 / RQ3

- RQ1: second Python datapoint for "how much of a call graph a static analysis recovers". It reports 0.76 and 0.82 recall for two tools on the exhaustive application-only scenario, higher than PyCG's own 69.9% (`pycg-2103.00587.md`), on six applications with test-executed plus hand-written truth. It also shows that the same tool drops to 0.48-0.60 recall once dependencies are analysed. The two numbers are not comparable with DyPyBench's 49% (`dypybench-2403.00539.md`).
- RQ2, RQ3: none.
- ADR-012 input (no choice made here): this paper's definition counts edges against a test-executed-plus-hand-checked truth and offers a chain-based variant for entry-function analysis.

## Discrepancies

- Abstract against body: the abstract and p.9 summary say "at least 20% higher in recall", but the text of Sec. IV-C gives 15% for A.W. (1) and 10% for A.W. (2) over the four projects where PyCG does not crash (p.9). Table V averages give +25% (0.60 against 0.48) and +15% (0.60 against 0.52), which is computed here from the table, not stated. v1 said "at least 10% higher in recall" (v1 abstract), so the abstract claim changed between versions without the body text changing.
- Size of the micro-benchmark: abstract and Sec. IV-A say 135 programs (112 plus 23), Table IV is scored out of 138, and the threats section says "23 programs" added and then "these 25 programs" (pp.1, 9, 11).
- With PyCG's own paper: PyCG's recall on its macro-benchmark is 69.9%; Jarvis reports 0.76 for PyCG on its own six applications, with a different ground truth.

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| README table: "Later Python call-graph generator; comparison point" | confirmed | Table V p.10 | Gives the second definition of call-graph precision and recall for Python, with a different ground truth from PyCG's. |
| Master document (`docs/05`): "expect 70-85% edge recovery" | not found in this paper | Table V p.10 | Recall values range from 0.28 to 0.95 per project and scenario; the average is 0.82 for application-only exhaustive and 0.60 for application-centered whole-program. |
