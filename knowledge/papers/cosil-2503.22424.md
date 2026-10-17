read: full — 17 pages incl. appendices, PDF v3, pdftotext -layout (poppler), 2026-10-17

# CoSIL — Jiang, Ren, Yan, Jiang, Li, Liu (arXiv 2503.22424v3, 10 Oct 2025; published at ASE 2025 according to a later paper's reference list)

Source file: arXiv PDF v3, 17 pages (body 11 pages, references pp.11-12, supplementary appendix A-E pp.13-17: graph
construction, search algorithm, component examples, extra LLM families, instruction templates). The extracted text has
17 pages and no blank page (`scripts/check_paper_note.py`). Every page was read; the paper's figures contain no
numbers beyond those in its tables, so no raster was needed. Version v3 is the only one used.

## What it established

- A training-free, index-free function-level issue localizer in two stages: the file stage widens the search from the
  files named in the issue to files linked by import relations (a "module call graph"), then the function stage walks
  a function call graph step by step with search tools, a pruner that rejects irrelevant nodes, and a final
  "reflective alignment" query that reformats the answer (Sec. III, pp.4-5; Figure 2, p.3).
- With open coder models of 7B, 14B and 32B the function-level Top-1 on SWE-bench Lite and Verified is higher than
  three prior localizers, and the empty-result rate is near zero, while one agent baseline returns an empty list for
  12.80% to 27.20% of issues depending on the model (Tables II-III, pp.6-7).
- Every component helps in the 32B Lite ablation; iterative search contributes most (Table IV, p.8).
- With a fixed Agentless repair stage, the localization lifts resolved rate on both benchmarks with two backbones
  (Table VI, p.8).
- Across other model families and small samples it remains the most accurate and among the cheapest agents (Table VII, p.9).

## What it did not establish

- No static call-graph accuracy: the module and function graphs are built by asking the LLM to read the imports and
  code of one node and emit its neighbours (Sec. II-B, pp.3-4; Appendix A, p.13), and the correctness of the
  emitted edges is never measured.
- No edge-type ablation: the module graph has import edges, the function graph has invoke and inherit edges, and the
  ablation removes whole graphs, not edge types.
- No wall-clock latency of CoSIL; tokens and dollars only (Table VII, p.9). A 15-minute search cap is set for the agent
  baselines (Sec. IV-E, p.6).
- No seeds or intervals; the iteration-count study is non-monotone and unexplained (Table V, p.8).
- A localization gain over a strong pipeline does not appear as a resolved-rate gain in one comparison
  (Table VIII-IX, p.10; see Discrepancies).
- No repository-level held-out analysis; leakage is discussed only as a model-pretraining risk (Sec. VI-B, p.10).

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages. Function-level
numbers are for the 32B open backbone on SWE-bench Lite unless stated.

| Claim | Value | Where |
|---|---|---|
| Function Top-1 / Top-3 / Top-5 / MAP / MRR, Lite | 0.433 / 0.547 / 0.580 / 0.465 / 0.493 | Table II, p.6 |
| Function Top-1 of Agentless-FL / OrcaLoca / LocAgent, Lite | 0.247 / 0.217 / 0.103 | Table II, p.6 |
| File Top-1, Lite: CoSIL / LocAgent | 0.613 / 0.647 | Table II, p.6 |
| Empty rate, Lite: CoSIL / LocAgent | 0.00% / 13.67% | Table II, p.6 |
| Function Top-1, Verified: CoSIL / Agentless-FL / OrcaLoca / LocAgent | 0.446 / 0.326 / 0.254 / 0.250 | Table III, p.7 |
| File Top-1, Verified: CoSIL / LocAgent | 0.640 / 0.686 | Table III, p.7 |
| Ablation, function Top-1: full / without module call graph / without iterative search | 0.433 / 0.383 / 0.320 | Table IV, p.8 |
| Ablation, function Top-1: without pruning / without reflective alignment | 0.413 / 0.390 | Table IV, p.8 |
| Ablation, file Top-1: full / without module call graph / without reflective alignment | 0.613 / 0.540 / 0.577 | Table IV, p.8 |
| Function Top-1 by maximum iterations 1 / 3 / 5 / 7 / 10 | 0.383 / 0.347 / 0.370 / 0.407 / 0.430 | Table V, p.8 |
| Resolved %, Lite, 32B open backbone: Agentless / with OrcaLoca / with LocAgent / with CoSIL | 17.33 / 17.00 / 19.00 / 21.67 | Table VI, p.8 |
| Resolved %, Verified, same four | 27.40 / 27.20 / 29.40 / 30.00 | Table VI, p.8 |
| Resolved %, Lite, closed-source backbone: same four | 22.33 / 19.67 / 21.00 / 25.67 | Table VI, p.8 |
| Tokens and dollars per instance, Lite mini sample, open large model: CoSIL / LocAgent | 0.07M and 0.022 / 0.53M and 0.055 | Table VII, p.9 |
| Same with a closed-source model: CoSIL / LocAgent | 0.14M and 0.341 / 2.07M and 4.004 | Table VII, p.9 |
| Maximum search iterations; search time cap for agent baselines | 10; 15 minutes | Sec. IV-E, p.6 |
| Size of each "mini" sample | 50 | Sec. V-D, p.9 |
| End-to-end comparison with a closed-source model: resolved %, CoSIL@40 vs Agentless-1.5 (published) vs reproduced | 31.3 vs 32.0 vs 28.3 | Table VIII, p.10; Table IX, p.10 |
| Function Top-1, CoSIL vs Agentless-1.5 in that comparison | 0.480 vs 0.250 | Table IX, p.10 |
| Resolved instances of 300, CoSIL@40 vs Agentless-1.5 (published) vs reproduced | 94 vs 96 vs 86 | Table IX, p.10 |

## Method details we need

- **Graphs (Sec. II-B, pp.3-4; Appendix A, p.13).** Module call graph: nodes are modules, edges are import
  relations; function call graph: nodes are classes and functions inside the modules, edges are invoke and inherit
  relations. Both are produced per node by an LLM given the node's code and parsed import statements and rendered
  as text (Figure 3, p.4), not computed by a static analyser.
- **File stage (Sec. III-A1, p.4).** The LLM pre-selects files from the issue and the repository structure tree; imports
  of those files give a first-order module subgraph; the LLM re-selects and re-ranks files; reflective alignment
  reformats the list.
- **Function stage (Sec. III-A2, pp.4-5; Algorithm 2, p.13).** Initial points chosen from a file-structure tree; at each
  step the agent picks a visible node, fetches its code with one of three search tools, a pruner returns true or
  false for relevance, accepted nodes add their call-graph neighbours; at most 10 steps; a summary step ranks
  suspicious functions.
- **Reflective alignment (Sec. III-C, p.5).** A second, independent short-context query that corrects the answer format
  at the end of each stage; removing it costs 6 to 10 percent (Table IV, p.8).
- **Setup (Sec. IV, pp.5-6).** Greedy decoding; Agentless, OrcaLoca and LocAgent as baselines; Top-N, MAP, MRR and empty
  rate for localization; Agentless-1.5's repair stage fed the top-3 locations for resolved-rate comparisons.

## Graph facts recorded for this project (R2 fields)

| Field | CoSIL |
|---|---|
| Graph role | agent tool (LLM-driven iterative search over LLM-built call graphs, with a pruner); training-free; no index; not learned |
| Edge types used | module graph: import; function graph: invoke and inherit (Sec. II-B, p.3-4) |
| Edge types ablated | no; graphs removed as wholes (module call graph; function search) (Table IV, p.8) |
| Resolution coverage measured | no; the call graphs are LLM output and are never compared with an oracle |
| Latency | tokens and dollars (Table VII, p.9); no seconds for CoSIL; 15 minute cap on agent baselines |
| Held-out handling | no training; evaluation on SWE-bench Lite and Verified; models released after the benchmark used; leakage called a threat (Sec. VI-B, p.10) |

## Relation to RQ1 / RQ2 / RQ3

- RQ1: it shows a graph can be a search-space constraint with no index and no static analysis, at a cost of LLM
  calls; it supplies no edge-type or latency evidence for an offline-built graph signal.
- RQ2: nothing on supervision.
- RQ3: this paper contains both directions: with a fixed repair stage, resolved rate rises with its localization
  (Table VI, p.8), and in one end-to-end comparison a 23-point function Top-1 gain gives no resolved-rate gain
  (Table IX, p.10). The authors suggest file and function match rates do not track resolved rate across different
  patch pipelines (Sec. VI-A, p.10). This is evidence of the retrieval-versus-reasoning gap the project is built to
  measure, with only one run per row.

## Discrepancies

- **Localization gain without a resolved-rate gain.** CoSIL@40 has function Top-1 0.480 against 0.250 for Agentless-1.5
  yet resolves 94 of 300 against 96 (published) or 86 (reproduced) (Table IX, p.10; Table VIII, p.10). The
  authors attribute the gap to sampling randomness in patch generation (p.10); the paper does not test that.
- The reproduced Agentless-1.5 resolves 86 while the published run resolves 96 with the same code (Table IX, p.10), so
  run-to-run variation in the end-to-end pipeline is about ten instances (inference from that pair), comparable to the
  8 to 13 instances that separate the localizers in Table VI on Lite (17.33 to 21.67 percent of 300).
- Table V (p.8): CoSIL@10 gives function Top-1 0.430 while the main 32B result is 0.433 (Table II, p.6); the
  difference is a re-run and shows the size of run-to-run variation at 300 instances (one instance is 0.0033).
- Cross-paper: LARGER's re-run of CoSIL reports lower file Acc@5 than non-graph agents on another benchmark and
  backbone (LARGER note, Table 1, p.8); the two papers use different backbones and benchmarks.

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| README "graph as agent tool, training-free" | confirmed | Abstract, p.1; Sec. III, p.4 | "without training or indexing"; graphs are LLM-built. |
| README "function-level localization improves Top-1 over prior localizers" | confirmed | Tables II-III, pp.6-7 | 0.433 vs 0.247 (Agentless-FL) on Lite, 32B. |
