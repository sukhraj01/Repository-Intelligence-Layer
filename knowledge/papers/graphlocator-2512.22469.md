read: full — 21 pages incl. appendices, PDF v1, pdftotext -layout (poppler) plus page raster of p.17 (Table 5), 2026-10-17

# GraphLocator — Liu et al. (arXiv 2512.22469v1, 27 Dec 2025), "GraphLocator: Graph-guided Causal Reasoning for Issue Localization"

Source file: arXiv PDF v1, 21 pages (body 19 pages, references pp.19-21; no appendix; prompt templates are in the released artifact, not in the paper). arXiv holds only v1. The extracted text has 21 pages and no blank page. Every page was read, including Tables 2-5 (Tables 2-3 as extracted text). Literature-scan source (topic: graph-structured retrieval for issue localization).

## What it established

- A training-free, LLM-driven localizer over a repository graph. The graph (called RDFS) has four layers (package or directory, file, class, function or method or field), vertex types dir, pkg, file, class, interface, enum, field, method, func, global_var, and edge types HasMember, ImportedBy, ExtendedBy, ImplementedBy and UsedBy (Sec. 2.1, pp.4-5). It is built with a syntax-tree parser; the containment skeleton is built first and the inter-layer dependency edges are added lazily as the agent visits vertices.
- Phase I finds "symptom" vertices with two graph-search tools (`search_vertex`, `search_edge`, wildcard matching and an edit-distance fallback); Phase II expands a "causal issue graph" of LLM-proposed sub-issues attached to repository vertices, expanding the sub-issue with the highest LLM-estimated causal probability first (Sec. 3, pp.6-8).
- On 987 issues (SWE-bench Lite 300, Loc-Bench 559, Multi-SWE-bench Java 128; Sec. 4.1, p.9) against retrieval, procedural and agent baselines, it gives higher function-level F1 and much higher precision than the agent baselines, and lower token use than the graph-agent LocAgent (Tables 2 and 4, pp.12, 16).
- A downstream pilot with two repair frameworks improves resolved rate with each localizer's output as context (Table 5, p.17).

## What it did not establish

- No edge-type ablation: the ablation removes the two search tools, the priority queue and the causal-graph context in the prompt (Table 3, p.15), not any edge type. Which of the five edge types matters is unknown.
- No resolution coverage: the paper does not report how many call or use edges its static analysis resolves, misses or gets wrong.
- Not a retriever comparison under matched cost: the agent methods use closed-source models (versions in Sec. 4.4, p.11); the embedding baseline is much cheaper and is run at top-10.
- The headline "+19.49% recall, +11.89% precision" is an average of absolute differences against a set of baselines for one of the two LLMs, mixed over three datasets (Sec. 5.1, p.13); it is not a gain over the best baseline in each cell. The embedding baseline wins at file and module level in recall (p.11).
- The downstream "28.74%" is not a measured resolved rate: it is the mean of the four relative improvements in Table 5 (13.19, 22.68, 63.68 and 15.41), computed here from the table; three of the four are on small absolute counts (one cell is a rise from 8.59% to 14.06% on 128 issues).
- Single-sample, greedy decoding (temperature 0); one run per cell; no interval or test (Sec. 4.4, p.11; Sec. 6.1, p.16).
- Possible benchmark contamination of the closed-source models; the authors chose models released before Loc-Bench was collected and argue the consistent gains make memorisation unlikely (Sec. 6.2, p.17).

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| Issues evaluated: SWE-bench Lite / Loc-Bench / Multi-SWE-bench Java / total | 300 / 559 / 128 / 987 | Sec. 4.1, p.9; Table 3, p.15 |
| Loc-Bench instances, repositories (one instance dropped as unreachable) | 560 instances in 164 repositories | Sec. 4.1, p.9 |
| Headline function-level gains for the closed-source model of Sec. 4.4 | +19.49% recall and +11.89% precision | Abstract p.1; Sec. 5.1, p.13 |
| Gains under symptom-to-cause and one-to-many mismatches | recall +16.44% and +19.18%; precision +7.78% and +13.23% | Abstract, p.1 |
| Function-level F1 gain over baselines, averaged: one model, file / module / function | 21.33% / 14.18% / 8.16% | Sec. 5.1, p.11 |
| Embedding baseline function-level precision on SWE-bench Lite / Loc-Bench | 6.57% / 7.88% | Sec. 5.1, p.11 |
| Ablation: removing `search_vertex`, function-level F1 | 30.91% to 14.23% | Sec. 5.3, p.15 |
| Graph construction: skeleton for a repository of 10k functions | under 20 seconds | Sec. 5.4.1, p.16 |
| Inter-layer static analysis of one function | 0.5 to 5 seconds | Sec. 5.4.1, p.16 |
| Input tokens against the graph-agent baseline, one model | 99.44k against 211.23k (52.9% less; cost 43.5% less) | Sec. 5.4.2, p.16 |
| Same, other model: input tokens and cost reduction | 32.3% and 22.9% | Sec. 5.4.2, p.16 |
| Repair framework on SWE-bench Lite: resolved without and with the causal graph as structured context | 25.00% to 30.67% | Table 5 and text, p.17 |
| Recall at symptom-to-cause distance 0 | 95.59% | Sec. 5.2.1, p.14 |
| Abstract's downstream figure | 28.74% | Abstract, p.1 |

## Method details we need

- **Role of the graph**: agent tool (the LLM calls graph search and is shown graph neighbours); not a score fused with BM25 or dense retrieval and not learned.
- **Edge types used**: HasMember (containment), ImportedBy, ExtendedBy, ImplementedBy, UsedBy (calls and field use) (p.4). No test, configuration, document or co-change edges.
- **Edge-type ablation**: none (see above). **Resolution coverage measured**: no.
- **Latency**: reports graph construction time against LocAgent (Figure 8, p.16) and token use and cost per approach (Table 4, p.16); no per-query wall-clock distribution.
- **Held-out handling**: not applicable (no training). The leakage discussion concerns the closed-source models' training data (p.17).
- **Metrics** (Sec. 4.2, p.10): success location (all gold covered), recall, precision and F1 per instance at file, module and function level; ground truth is re-extracted from the patch on the authors' graph, so it differs from the ground truth in earlier papers (Sec. 4.1, p.9).
- **Symptom-to-cause distance** (Sec. 5.2.1, p.13): the largest over gold functions of the shortest-path distance, in the authors' graph, to a vertex whose name is a keyword from the issue (keywords extracted by the model); this is a hop distance on the project's own kind of graph and is comparable in spirit to KGCompass's hop distribution (`kgcompass-2503.21710.md`).
- **Settings**: Phase I up to 5 search iterations, Phase II up to 20 turns; baselines run with their official default settings; 64-core CPU server (Sec. 4.4, p.11).

## Relation to RQ1 / RQ2 / RQ3

- RQ1: another system where a graph is used as a tool by an LLM and reaches higher function-level precision than embedding retrieval, at much higher cost; it gives no evidence on whether graph edges raise retrieval ranking quality for an embedding model, and no edge-level ablation. It adds a second source (with `semnav-2609.31176.md`) that builds call edges with a static analyser or a language server and treats unresolved edges as a separate case.
- RQ2: none.
- RQ3: the downstream pilot shows resolved rate rising with localization quality for two repair frameworks, with one sample per cell; the one exception the authors point out (Table 5 text, p.17) is a localizer with higher function-level success but lower precision (LocAgent) giving a lower resolved rate than a localizer with lower success and higher precision (SWERank-Large); it is one more datapoint that precision rather than recall may drive the downstream effect (compare `codegrep-2608.05886.md`).

## Discrepancies

- Loc-Bench size: 560 instances in 164 repositories after one is dropped (p.9); Wave 1 measured 560 rows over 165 repositories in the V1 release (`PROJECT_STATE.md`, Q25), which agrees once the one unreachable repository is removed.
- Internal: the abstract's downstream gain of 28.74% is the mean of four relative improvements computed from Table 5 (see above), not a single resolved-rate change.

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| Search leads: graph-structured retrieval for issue localization in 2025-2026 | present | Secs. 2-3, pp.4-8 | Graph used as an LLM agent's tool with five edge types; no edge ablation, no resolution coverage. |
| Abstract: downstream resolving improvement of 28.74% | traced to Table 5 | p.17 | Mean of four relative gains; the absolute SWE-bench Lite change is 25.00% to 30.67% (single sample, 300 issues). |
