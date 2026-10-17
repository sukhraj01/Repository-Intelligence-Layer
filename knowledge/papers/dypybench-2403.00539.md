read: full — 21 pages incl. appendices, PDF v1, pdftotext -layout (poppler) plus page raster of p.11 (Figure 5, Venn diagrams), 2026-10-17

# DyPyBench — Bouzenia, Krishan and Pradel (arXiv 2403.00539v1, FSE 2024)

Source file: arXiv PDF v1, 21 pages (body 18 pages, references pp.18-21; no appendix). arXiv holds only v1. The extracted text has 21 pages and no blank page. Every page was read; the reference list was read for the works it names. This paper is a literature-scan source (topic: static against dynamic call-graph accuracy for Python); only Section 4.1 bears on the project.

## What it established

- A benchmark of 50 executable Python projects (681k lines, 29,511 test cases, 82% statement coverage when the test suites run) integrated with a dynamic-analysis framework (Sec. 2-3, pp.3-9; Table 2, p.6). The project list includes `requests`, `seaborn`, `click` and `flask-api` (Table 1, p.5), so two of the SWE-bench Verified repositories are among them.
- The first comparison of static and dynamic call graphs for Python (Sec. 4.1, pp.9-12): the static graph is PyCG's, the dynamic one comes from running each project's tests under the instrumentation framework; edges are caller-callee pairs of fully qualified function names, deduplicated per project; calls made by the test runner or directly inside a test function are ignored.
- Result on the 39 projects for which PyCG finishes: only 49% of the dynamically observed edges, and 48.5% of the observed callees, are in the static graph, although 95% of the dynamic callers are (p.11). Of the dynamic edges missing from the static graph, 92% have a callee that is absent from the static graph and 8% have both ends present but no edge (p.11).
- Causes found by inspecting a sample of 97 differences (p.10): calls to methods of built-in types (for example `str.strip`) account for 59% of the callees missing from the static graph, calls through `super` are missed, and differences in how the two tools name the same function account for about 12% (p.12).
- Two other uses of the benchmark (training data for a value-prediction model; mined call-sequence patterns) are not relevant here.

## What it did not establish

- Not a measure of precision: the dynamic graph is incomplete (tests only), so static edges absent from it are not false positives; the paper reports no precision (it notes the static graph has far more edges because it considers all code, p.11).
- Not restricted to in-repo callees: the dynamic graph contains built-in and standard-library callees, and they are the largest single cause of "missing" static edges (p.12). The 49% is therefore not "recovery of in-repo call edges"; a version restricted to project-internal callees is not reported.
- The test suites are the entry points. Test-based dynamic baselines can give arbitrarily wrong precision and recall (see `total-recall-helm-2024.md`); the paper does not discuss this limitation.
- One static tool (PyCG), one dynamic tool, no second static tool, no flow-sensitive analysis (Jarvis is not evaluated).
- PyCG fails on 11 of 50 projects (6 time out at six hours, 3 exceed 60 GB, 2 crash; p.10), so the 39-project result is conditional on PyCG finishing.

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| Projects / lines of Python / test cases / coverage | 50 / 681k / 29,511 / 82% | Table 2, p.6 |
| Projects on which PyCG produced a call graph | 39 of 50 | Sec. 4.1.2, p.10 |
| Static edges over the 39 projects / average per project | 60,565 / 1,552 | Sec. 4.1.2, p.10 |
| Dynamic edges over all 50 projects / average per project | 9,575 / 191 | Sec. 4.1.2, p.10 |
| Dynamic edges over the 39 projects: edges / callers / callees | 6,306 / 2,049 / 3,741 | Sec. 4.1.2, p.11 |
| Share of dynamic edges present in the static graph | 49% | Sec. 4.1.2, p.11 |
| Share of dynamic callers / callees present in the static graph | 95% / 48.5% | Sec. 4.1.2, p.11 |
| Dynamic edges absent from the static graph | 51%, of which 92% have the callee missing | Sec. 4.1.2, p.11 |
| Missing callees that are built-in types' methods | 59% | Sec. 4.1.2, p.12 |
| Missing callees due to differing function names | about 12% | Sec. 4.1.2, p.12 |
| Sample of differences inspected by hand | 97 | Sec. 4.1.1, p.10 |
| Average time to collect a dynamic call graph per project | 215 minutes | Sec. 4.1.2, p.10 |

## Method details we need

- **Static side**: PyCG run with the project path and all Python files of the project (p.10), six hours and 60 GB per project.
- **Dynamic side**: instrumentation applied to the application code only (not the tests), test suite run under pytest, 30 seconds per test case, one core per suite for the timings; Python 3.10; versions of the instrumentation framework stated in Sec. 3.3 (p.9).
- **Set comparison**: edges, callers and callees are each compared as sets per project and summed (Venn diagram, Figure 5, p.11: dynamic only 3,232, both 3,074, static only 57,491 edges; callers 97, 1,997, 31,798; callees 2,018, 1,723, 8,814 — read from the raster, not in the text).
- **Naming**: both tools resolve fully qualified names; the authors list "a uniform way of resolving functions into a fully qualified name" as an open problem for any later study (p.12).
- **Artifacts**: a container image and the dynamic call graphs are released (Data availability, p.18).

## Relation to RQ1 / RQ2 / RQ3

- RQ1: it is the only source read so far that measures recall of a Python static call graph against executed edges on many real projects. The 49% is much lower than the 69.9% hand-truth recall of PyCG on five small packages (`pycg-2103.00587.md`), because the dynamic edges include built-in callees and the entry points are test suites. For ADR-012 it shows that "edge recovery against a dynamic oracle" has at least two natural versions (all callees; in-repo callees only) that give different numbers, and that the oracle's coverage matters (`total-recall-helm-2024.md`). No choice is made here.
- RQ2, RQ3: none.

## Discrepancies

- With the master document (`docs/05_structural_signals.md`, "expect 70-85% edge recovery"): the one real dynamic comparison reports 49% of dynamic edges for PyCG, counting built-in callees. Restricting to in-repo callees might raise it; not measured in the paper.
- With PyCG's own report (69.9% recall on hand-built graphs): different ground truth, different callee scope; the two numbers are not comparable.
- Internal: the text says 49% of dynamic edges are in the static graph; the Venn counts give 3,074 of 6,306 = 48.7%, which rounds to the stated 49%.

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| README table: no statement about DyPyBench (not a listed paper) | not applicable | p.1 | Added as a literature-scan source. |
| Master document: "70-85% edge recovery" is realistic for Python static call graphs | not supported by this source | Sec. 4.1.2, p.11 | 49% of dynamic edges (all callees, test-suite entry points). |
