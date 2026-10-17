read: full — 12 pages incl. appendices, PDF v1, author copy of the ISSTA 2024 paper from the OPAL project site (no arXiv version found), pdftotext -layout (poppler), 2026-10-17

# Total Recall? How Good Are Static Call Graphs Really? — Helm et al. (ISSTA 2024)

Source file: author copy of the ISSTA 2024 PDF (DOI 10.1145/3650212.3652114), 12 pages (body 10 pages, references pp.11-12; proofs of the theorems are in supplementary material that was not fetched, so the theorems are taken as stated). The extracted text has 12 pages and no blank page. Every page was read, including all tables. The study is about Java; it is a literature-scan source for how to measure static call-graph precision and recall against dynamic baselines, which is the part that carries over to Python.

## What it established

- Three ways the literature has assessed static call graphs are named: micro-benchmarks, call-graph size, and dynamic baselines; the authors argue that each has a flaw (Sec. 2, pp.2-3).
- Definition: the ground-truth call graph is the set of all caller-callee edges over all executions from the chosen entry points; it cannot be computed; a dynamically sampled graph is a subset of it (Definitions 3.1-3.2, p.4).
- Test-based baselines are unreliable: unit tests and benchmarks are entry points that "may not resemble typical use" and can contain edges outside the ground truth for the intended entry points, so a precise static graph can be scored with recall near 0% and an imprecise one with precision near 100% (Sec. 3.3, p.4; Observation 3).
- If the same entry point is used for the static graph and the dynamic sample, precision measured against the sample is a lower bound on precision against the ground truth, and it rises monotonically as the sample grows; recall has no direct bound but is bounded by recall-of-sample products (Theorems 3.3-3.6, pp.5-6; proofs not read).
- Method for building the baseline: public seed corpora, manual extension after inspecting coverage, and coverage-guided fuzzing (Sec. 4.1, p.6), applied to four Java programs from a corpus of 76 and eight static algorithm implementations in four frameworks (Sec. 5, pp.7-8).
- Findings (pp.8-11): call-graph size is not a reliable proxy for precision or recall; precision and recall over edges are often much lower than over reachable methods; implementations of the same algorithm in different frameworks differ widely; one reflective instantiation can empty a whole call graph; conclusions on one program need not carry to others.

## What it did not establish

- Nothing about Python. The authors cite PyCG's micro-benchmark result (103 of 112 programs sound) against its recall on five real applications (about 70%) as an example of the mismatch (Sec. 2, p.2), but did not run any Python tool.
- Four programs and one entry point each (p.11), so the generalisation is the authors' own stated threat.
- The coverage reached is modest: branch coverage 27% to 65% over the four programs, by design restricted to what is reachable from the entry point (Table 2 and p.8).
- The theorems' proofs were not read (supplementary material); they are quoted only as the authors state them.

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| PyCG micro-benchmark programs passed against recall on five real applications (as cited by the authors) | 103 of 112 (92%) against about 70% | Sec. 2, p.2 |
| Programs studied / size of the corpus they were chosen from | 4 / 76 | Sec. 5.1, p.6 |
| Static algorithm implementations studied | eight, in four frameworks | Sec. 1, p.2 |
| Branch coverage of the sampled call graph (combined corpus) | 27% to 65% across the four programs | Sec. 5.3, p.8 |
| Median branch coverage achieved by an earlier test-based baseline, as cited | about 55% | Sec. 2, p.3 |
| Precision and recall on reachable methods, Jasml, across algorithms | precision 95.1% to 96.4%, recall about 100% | Table 3, p.8 |
| Batik, CHA: best method precision / best edge precision | 9.0% / 0.9% | Table 5 and text, p.10 |
| Axion core package, WALA: precision of CHA / of 0-CFA on reachable methods | 73.8% / 63.0% | Sec. 5.4.3, p.10 |
| Fuzzing alone, branch coverage | between 1% and 7% | Sec. 5.3, p.8 |
| Heap and timeout for the static runs | 400 GB; 3 hours | Sec. 5.1, p.7 |

## Method details we need

- **Entry points** are fixed per program and are the same for the static graph and the dynamic sample (Sec. 3.2, p.4); the dynamic sample is recorded by intercepting every method entry (Sec. 4.2, p.7).
- **Matching**: methods by name and signature; edges by caller, callee and call site (line or program counter) when available (Sec. 4.2, p.7).
- **Filtering**: precision and recall are reported over the whole graph including the JDK and over the program's core package only (Sec. 5.4, p.8). The second variant is the analogue of an in-repo-only measure.
- **Measures**: precision = share of static edges that were executed, recall = share of executed edges that are in the static graph (Sec. 1, p.1).

## Relation to RQ1 / RQ2 / RQ3

- RQ1: methodological support for ADR-012 (edge-recovery definitions): (i) use entry points that match how the graph is consumed; (ii) a test-suite oracle can mis-state precision and recall in either direction; (iii) report edges and reachable methods separately; (iv) report a restricted (core package) and an unrestricted version. No choice is made here. These points apply directly to a plan that uses a test-suite tracer as the dynamic oracle for Python repositories.
- RQ2, RQ3: none.

## Discrepancies

- None found internally. The Python numbers it cites for PyCG (103 of 112; about 70%) match PyCG's own Table III and Table IV (`pycg-2103.00587.md`).

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| Statement in the PyCG note that the macro-benchmark recall of about 70% is hand-built | consistent | Sec. 2, p.2 | The paper repeats it as "the authors created reference CGs by hand in a time-consuming process". |
