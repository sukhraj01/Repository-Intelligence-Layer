read: full — 11 pages incl. appendices, PDF v1, pdftotext -layout (poppler); the figures are program listings and graph sketches without numbers, 2026-10-23

# NoCFG — Abadi, Makovitzki, Shemer and Tyszberowicz (arXiv 2105.03099v1, 2021), "NoCFG: A Lightweight Approach for Sound Call Graph Approximation"

Source file: arXiv PDF v1 (the only version), 11 pages: body pp.1-10, references pp.10-11; no appendix. The extracted text has 11 pages and no blank page. The earlier scan had read the first three pages only; this is the full read. Read because it reports precision and recall of a Python call graph against dynamic call graphs, which is the kind of number ADR-012 (edge recovery) compares.

## What it established

- A call-graph approximation that drops control flow (each method body becomes a cycle of assignment, call and return nodes iterated to a fixed point), infers sets of possible types per variable interprocedurally, and connects each call site to every target its receiver's type set allows; soundness relative to the language subset modelled is proved (Sec. 2, pp.3-6).
- On five small Python projects (573 to 12,336 lines), with each project's tests as entry points for both the static graph and a dynamic graph recorded by `pycallgraph`, precision against the dynamic graph is 83.33% to 95.89% and recall 81.40% to 100.00%; weighted averages 89.66% precision and 89.01% recall (Table 3, p.9; p.8).
- Missed edges are attributed to the lack of reflective-call support in the implementation (p.9); over-approximated edges are argued to be mostly correct but untested paths (for example error constructors on paths no test executes) (p.9).
- At C# scale (up to about 2 million lines including decompiled dependencies) the analysis ran in 41 s to about 20 minutes per project on an 8 GB heap (Table 4, p.10).

## What it did not establish

- **Small Python sample.** Five projects, 1,361 matched edges in all; the largest is 12,336 lines. Nothing at the scale of the project's repositories (django has 35,860 units in the project's parse).
- **Precision is a lower bound only against test-driven dynamic graphs.** The dynamic graph covers only what the tests execute; the paper itself notes untested feasible paths (p.8, footnote 8). The Java study of test-based baselines (`total-recall-helm-2024.md`) shows such baselines can mis-state both precision and recall.
- Edge scope is not stated precisely: whether calls into the standard library and third-party packages are counted, and how `pycallgraph` names are matched to static nodes, is not described.
- The reflective-call extension (Sec. 3.1) was not implemented for the evaluation (p.8), so its effect is not measured.
- No comparison with PyCG or any other Python call-graph tool on the same projects.

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| Python projects evaluated / largest project lines of code | 5 / 12336 | Table 2, p.8 |
| Weighted average precision / recall against dynamic graphs from tests | 89.66% / 89.01% | p.8 |
| Precision range over the five projects | 83.33% to 95.89% | Table 3, p.9 |
| Recall range over the five projects | 81.40% to 100.00% | Table 3, p.9 |
| Largest project (algorithms): matched / over-approximated / missed edges | 810 / 94 / 109 | Table 3, p.9 |
| Abstract's precision claim (lower bound) | 90% | Abstract, p.1 |
| C# projects analysed / largest size in lines | 11 / 2,017,040 | p.9; Table 4, p.10 |
| C# projects found to reach the vulnerable method, of those referencing the package | 4 out of the 11 | p.9 |

## Method details we need

- **Precision and recall definition** (Table 3, p.9): matched = edges in both graphs; over-approximated = static only; missed = dynamic only; precision = matched / (matched + over-approximated); recall = matched / (matched + missed). The rows reproduce from the counts (for example 60 / 72 = 83.33%). Both graphs are restricted to what is reachable from the tests used as entry points.
- **Type sets, not single targets** (Sec. 2.2, p.4): a call site gets an edge to every target in its receiver's type set; this is the counterpart of the project's `ambiguous` bucket (several candidate targets), resolved by type propagation rather than by name.
- **Flow insensitivity** (Sec. 2.1, p.3): statements of a method are iterated to a fixed point with control-flow order discarded; the paper claims "little to no effect" on precision, shown only on the five projects.

## Relation to RQ1 / RQ2 / RQ3

- RQ1 / graph (ADR-012, Q35, Q36): a fourth published operating point for Python call-graph accuracy, under a fifth definition (test-entry dynamic graph, both graphs restricted to test reachability). It sits beside PyCG (hand-built truth), Jarvis (test plus manual truth) and DyPyBench (all executed edges, built-ins included) in the definitions table of `LANDSCAPE.md`. Its type-set propagation is one concrete way to re-bucket `ambiguous` sites by receiver evidence (one of the X1.3 policies), though the paper gives no per-site precision of multi-target sets.
- RQ2: none.
- RQ3: none.

## Discrepancies

- With the earlier scan entry ("first three pages read; its evaluation was not read, so no number is quoted"): now read in full; the evaluation is five small projects.
- Internal: the abstract's "high precision rate of 90% (lower bound)" rounds the 89.66% weighted average (p.8); the per-project lower bounds go down to 83.33% (Table 3). The paper calls the recall shortfall a consequence of missing reflection support (p.9) without counting how many missed edges are reflective.

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| Abstract: "precision rate of 90% (lower bound)" | confirmed as a rounded weighted average | p.8; Table 3, p.9 | five projects of at most 12,336 lines |
| Sound call graphs for Python | qualified | Sec. 2, pp.3-6; p.9 | proved for the modelled subset; recall below 100% in four of five projects because reflection is not handled |
| Usable as an edge-recovery reference for the project's repositories | not established | Table 2, p.8 | scale and edge scope differ; no comparison with other tools |
