read: full — 21 pages incl. appendices, PDF v1, pdftotext -layout (poppler) plus page rasters of Table 1 and Figure 1 (p.8) and Figure 4 and Table 11 (p.19), 2026-10-17

# LARGER — Hu, Su, Zhao et al. (arXiv 2605.16352v1, 8 May 2026)

Source file: arXiv PDF v1, 21 pages (body 9 pages, references pp.10-11, appendices A-E pp.12-21). It is a
preprint ("Preprint." on p.1); only one version exists. The extracted text has 21 pages and no blank page
(`scripts/check_paper_note.py`). Every page was read, including the proofs (pp.12-13), the efficiency tables
(pp.14-16), the commit-aware alignment study (pp.17-18) and the instruction templates (pp.20-21). Figure 4
(p.19) was rasterized at 250 dpi to look at the LocBench panel.

## What it established

- A graph exposed to a command-line search agent through its existing text-search output: for each lexical match
  the tool appends confidence-filtered graph neighbours (callers, callees, related tests, documentation,
  configuration, an execution flow and a community label) read from per-file JSON side files. The agent policy,
  step budget and instruction text are the same as the baseline except four lines about how to read the extra block
  (Sec. 4, pp.4-7; App. E.4, pp.20-21).
- On LocBench and MuLocBench at file level, the fixed setting (k = 10, confidence threshold 0.5) beats every
  baseline at Acc@5, with a closed-source CLI agent on a different backbone nearly level on MuLocBench
  (Table 1, p.8).
- Removing graph expansion costs the most among components on MuLocBench Acc@5 (Table 3, p.9).
- Commit-aware graph updates cost tens of milliseconds against minutes for a rebuild (App. D.1, pp.17-18).
- The same graph channel gives small gains on two downstream tasks (Table 2, p.9).

## What it did not establish

- No edge-type ablation. The ablation removes graph expansion, confidence scoring, community priors, or all of
  them (Table 3, p.9); tests, documentation and configuration links are never switched off on their own, so there
  is no evidence in the paper that those links help.
- The headline setting for cross-artifact edges is unclear. The alignment study uses a configuration described as
  "test files dropped, MAX caps at 10, base edges only" (App. D.1, p.17); the paper does not say which edge set
  the Table 1 runs use. The side-file description (App. E.3, p.19) says cross-role links to tests, documentation
  and configuration exist.
- No measurement of edge-resolution accuracy. Confidences are fixed numbers set by edge provenance (Table 11,
  p.19), not estimated from data.
- The "tuned" setting is a per-repository oracle: for each repository the best (k, threshold) pair by Acc@5 over
  a small grid, chosen on the evaluation labels (App. D.2, p.18; Sec. 5.2, p.8). Only the fixed row is a
  setting chosen without the test labels.
- Efficiency telemetry covers 374 of 560 LocBench instances (the others failed with authentication errors;
  App. B.1, p.14), so runtime and token columns for LocBench describe a subset.
- Three runs are averaged (Sec. 5.1, p.7); no standard deviations or intervals are reported.
- The backbone is a closed-source model (version in the paper's Table 1 caption); one baseline row uses a
  different closed-source backbone and is marked as not comparable.

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| LocBench size as stated | 560 issues, 5 repositories | Sec. 5.1, p.7 |
| LocBench described again | five Python repositories | App. C, p.15 |
| MuLocBench size | 1,100 issues, 46 repositories | Sec. 5.1, p.7 |
| LocBench file Acc@5: LARGER fixed / tuned | 87.0 / 89.1 | Table 1, p.8 |
| LocBench file Acc@5: best same-backbone baseline (closed-source CLI agent) | 74.1 | Table 1, p.8 |
| LocBench file Acc@5: closed-source CLI agent on another backbone | 75.2 | Table 1, p.8 |
| LocBench file Acc@5: BM25 / CoSIL / LocAgent | 49.3 / 68.2 / 65.3 | Table 1, p.8 |
| MuLocBench file Acc@5: LARGER fixed / tuned | 55.7 / 60.0 | Table 1, p.8 |
| MuLocBench file Acc@5: best same-backbone baseline / other-backbone agent | 50.0 / 54.9 | Table 1, p.8 |
| MuLocBench file Acc@5: CoSIL / LocAgent | 27.0 / 25.7 | Table 1, p.8 |
| MuLocBench Acc@1, fixed vs same-backbone baseline (difference) | -0.6 | Table 1, p.8 |
| Component ablation on MuLocBench Acc@5: full / without graph expansion | 55.7 / 48.2 (-13.5%) | Table 3, p.9 |
| Without confidence scoring / without community detection / without all modules | 53.1 (-4.7%) / 53.4 (-4.1%) / 46.8 (-16.0%) | Table 3, p.9 |
| Defaults | k = 10, threshold 0.5 | Sec. 5.1, p.7 |
| Wall-clock per instance on MuLocBench, mean / median seconds: LARGER | 99.9 / 71.6 | Table 6, p.15 |
| Same on LocBench: LARGER | 60.0 / 40.9 | Table 6, p.15 |
| Same, LocAgent: MuLocBench / LocBench | 263.4 / 65.7 and 623.6 / 167.6 | Table 6, p.15 |
| Same, CoSIL: MuLocBench / LocBench | 109.7 / 58.1 and 151.9 / 98.8 | Table 6, p.15 |
| Same, same-backbone CLI agent: MuLocBench / LocBench | 139.9 / 132.8 and 129.2 / 122.4 | Table 6, p.15 |
| Tokens per instance, LARGER: MuLocBench / LocBench | 353K / 452K | Table 7, p.15 |
| Efficiency telemetry coverage: MuLocBench / LocBench | 1097 of 1098 / 374 of 560 | App. B.1, p.14 |
| Full graph rebuild, median seconds (pandas / transformers / scikit-learn) | 254 / 123 / 51 | App. D.1, p.17 |
| Commit-aware alignment, median milliseconds (same order) | 53 / 78 / 81 | App. D.1, p.17 |
| Edge confidence by provenance: same-file 1.0, explicit import 0.95, resolved import 0.9, inheritance 0.9 | 1.0; 0.95; 0.9; 0.9 | Table 11, p.19 |
| Edge confidence: Cython 0.85, test link 0.75, documentation 0.6, configuration 0.5, fuzzy name 0.5 | 0.85; 0.75; 0.6; 0.5; 0.5 | Table 11, p.19 |
| Hyperparameter grid for the per-repository oracle | k in 3, 5, 10, 20; threshold in 0, 0.5 | App. D.2, p.18 |
| Downstream: codebase QA / test writing, LARGER fixed | 32.25 / 37.78 | Table 2, p.9 |
| LocAgent function-level LocBench Acc@5 in this paper's re-run | 11.7 | Table 4, p.13 |

## Method details we need

- **Graph (Sec. 3, p.3; App. E.1, p.18).** Typed multigraph over directories, files, classes, functions. A syntactic
  pass extracts containment, import, invocation, inheritance; a second pass adds links to tests, documentation and
  configuration. Edges carry a confidence by provenance (Table 11, p.19); structural edges have confidence 1.
  Files are clustered with Leiden on the projected cross-file graph; the community label is a soft prior.
- **Online step (Sec. 4.1-4.2, pp.4-5).** The agent's search action returns lexical matches, aligned to graph
  nodes (the active set); for each node the top-k neighbours within K hops with confidence above the threshold are
  appended, re-weighted by the community prior. Neighbourhoods are capped at 20 per file (App. E.3, p.20).
- **Maintenance (Sec. 4.4, pp.6-7; App. D.1, pp.17-18).** The graph for a new commit is the previous graph with
  changed files re-parsed; communities are recomputed lazily.
- **Theory (Sec. 4.3, p.5; App. A, pp.12-13).** Recall of the augmented context is at least that of the lexical-only
  context under a monotone-context assumption; this is true by construction and is not an empirical result.
- **Baselines (Sec. 5.1, p.7).** BM25, Agentless, SWE-agent, OpenHands, two closed-source CLI agents, mini-swe-agent,
  CoSIL, LocAgent; all in-house methods use one closed-source backbone and matched step and context budgets.

## Graph facts recorded for this project (R2 fields)

| Field | LARGER |
|---|---|
| Graph role | signal inside an agent's existing search output (neighbour expansion with confidence filter); not a separate graph tool; not learned |
| Edge types used | contains, imports, invokes, inheritance, same-file co-occurrence, fuzzy name match, native-extension link; cross-artifact links tested_by (0.75), documents (0.6), configures (0.5) (Table 11, p.19) |
| Edge types ablated | no; component ablation only (Table 3, p.9); the confidence threshold is swept per repository (p.18) |
| Resolution coverage measured | no; confidences are fixed by provenance |
| Latency | mean and median seconds per instance, end to end including the LLM (Table 6, p.15); graph update time (App. D.1, p.17); LocBench telemetry is a 374-of-560 subset |
| Held-out handling | no training; "tuned" row selects on the evaluation labels; fixed row does not; LocBench and MuLocBench are existing public sets |

## Relation to RQ1 / RQ2 / RQ3

- RQ1: it is the closest published example of a graph channel that includes test, documentation and configuration
  links, and it ships no evidence about whether those links matter. The project's own edge-type ablation would not
  be duplicating it.
- RQ2: nothing on supervision.
- RQ3: the downstream rows (Table 2, p.9) are one backbone and small task counts (90 and 124) with no intervals.
- Latency: its end-to-end seconds are dominated by the LLM calls; they do not bound the cost of the graph step.

## Discrepancies

- **LocBench "560 issues, 5 repositories" against Wave 1's "560 rows over 165 repositories".** The paper states five
  repositories three times (Sec. 5.1, p.7; App. C, p.15; Table 10, p.17) and gives no list. The paper's own figure
  contradicts it: Figure 4(b) (p.19), captioned "each point is one repository", shows far more than five
  LocBench points (the rasterized panel shows several dozen overlapping markers, which cannot be counted exactly),
  and App. D.2 (p.18) sweeps "every repository in MuLocBench and LocBench". The row count 560 matches the benchmark
  (Table 3 of the LocAgent note, p.7) and the measured 165 repositories in the data audit is the consistent number.
  We take "5 repositories" to be an error in the paper (inference; the paper does not explain it).
- The abstract's "+13.9 (tuned) and +11.8 (fixed) points of Acc@5 over the strongest baseline" (p.1) corresponds to
  the closed-source CLI agent on another backbone (Table 1, p.8: +13.9 and +11.8). Against the same-backbone baseline
  the Acc@5 gains are +15.0 and +12.9. The introduction's "+13.9 on Acc@5 and +12.2 on Recall@5" (p.2) matches the
  Table 1 differences for Acc@1 and Recall@1 against the same-backbone baseline (+13.9 and +12.2), not for @5
  (Table 1: Acc@5 +15.0, Recall@5 +9.5).
- LocAgent's own paper reports file Acc@5 83.39 and function Acc@10 59.29 on its 560 issues with a closed-source model
  (LocAgent note, Table 7, p.11); this paper's re-run gives 65.3 file Acc@5 and 11.7 function Acc@5 with another
  backbone (Table 1, p.8; Table 4, p.13). The backbones differ, so the rows are not comparable, and the function-level
  re-run is unusually low.
- Internal: the ablation baseline "55.7" equals the fixed row of Table 1; the text calls it the full system of the
  "ablation-run configuration" (Sec. 5.3, p.9), which suggests a separate run; the paper does not say whether it is
  the same run.

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| G1 typed graph with cross-artifact links to tests (0.75), documentation (0.6), configuration (0.5) | confirmed | Table 11, p.19; App. E.1, p.18; App. E.3, p.19 | Confidences are fixed numbers by provenance. Whether the headline runs enable them is not stated (App. D.1, p.17 uses a test-dropped, base-edges-only configuration). |
| G1 expansion on top of grep | confirmed | Sec. 4.2, p.5; App. E.4, pp.20-21 | Graph block appended to the search output. |
| G1 ablation 55.7 to 48.2 without expansion | confirmed | Table 3, p.9 | MuLocBench Acc@5 only; no LocBench ablation; relative drop 13.5%. |
| G1 no edge-type ablation | confirmed (absence) | Sec. 5.3, p.9; Table 3, p.9 | |
| G1 no edge-resolution coverage reported | confirmed (absence) | Sec. 5, pp.7-9; App. B, pp.14-16; App. E, pp.18-21 | |
| G1 "LocBench has 560 issues in 5 repositories" | confirmed as stated; contradicted by Figure 4(b) | Sec. 5.1, p.7; App. C, p.15; Table 10, p.17; Figure 4, p.19 | See Discrepancies. |
