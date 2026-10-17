read: full — 9 pages incl. appendices, PDF v1, pdftotext -layout (poppler) with the extraction redone page by page; Tables 1-3 read from the extracted text, 2026-10-17

# SemNav — Wei, Lei and Li (arXiv 2609.31176v1, 25 Sep 2026), "SemNav: Semantic Navigation for Repository-Level Issue Localization"

Source file: arXiv PDF v1, 9 pages (body 6 pages, references pp.7-9; no appendix). arXiv holds only v1. The extracted text has 9 pages and no blank page. Every page was read, including the three tables and the ablation figure. Literature-scan source (topic: graph-structured retrieval for issue localization).

## What it established

- A localizer that seeds a broad candidate set with deterministic retrieval and then lets an LLM agent revise it, supported by three components (Sec. "Methodology", pp.2-4): (1) a navigation graph whose edges are either resolved or unresolved, with unresolved targets resolved on demand through a language server (Pyright for Python) and the result cached in the graph; (2) issue-conditioned "cards" that summarise an entity's role; (3) a persistent candidate workspace that keeps each candidate with its status (unverified, plausible, discarded) and its evidence.
- Edge types: Contains, Calls, Imports, Inherits and References (p.3). Resolved edges form E and unresolved edges Ee; an `Expand` tool follows typed one-hop edges, and the retrieval step adds a bonus for entities connected by a resolved edge to the top lexical anchors (Eqs. 5-6, p.3), so the graph is both an agent tool and a retrieval-time score term.
- On SWE-bench Lite (300 issues) with three open models, it ranks first in 24 of the 27 model-metric cells against four agent and workflow baselines; with a 4B model File Hit@10 rises from 68.33% to 82.67% and Function Recall@10 from 32.92 to 40.72 (Table 1, p.5; text p.6). On a second benchmark (821 issues, ranked file localization) it ranks first on five metrics (p.6).
- Ablation (4B model, SWE-bench Lite; Figure 3, p.7): removing the issue-conditioned cards lowers File Hit@10 by 6.00 points; keeping only the offline syntax-derived graph and no online resolution lowers it by 7.00 points; removing the workspace lowers Function Recall@10 by 19.20 points.
- Evidence-quality benchmark (368 instances of SWE-Explore): line-level precision 79.99% against 53.35% for the best baseline (p.6). One-shot repair with each localizer's output as the only context: resolved rate 52.33% against 44.00% for the best baseline with one repair model, 27.67% against 23.33% with another (Table 3, p.7).

## What it did not establish

- No edge-type ablation (the graph ablation is offline against online resolution, not Calls against Contains and so on); no resolution coverage figure (how many call sites the language server resolves) is reported.
- One run per cell, no interval or test; models are small open ones (a 4B model, a 9B model, a 35B-A3B model).
- Quality depends on LLM calls that the paper reports in tokens, not time; no wall-clock latency per issue. The cards cost extra tokens; total cost is 25.4% below full-source reading and 4.8% above truncated reading (p.6).
- Python only for the graph (Pyright).
- Downstream numbers are one deterministic repair attempt on 300 issues; the oracle context (gold files) reaches 39.00% and 67.00% for the two repair models (Table 3, p.7), so even perfect file context leaves a large repair gap.

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| SWE-bench Lite issues / second-benchmark issues / SWE-Explore instances | 300 / 821 / 368 | Sec. "Experimental Setup", p.6 |
| File Hit@10 with the 4B model: best baseline / SemNav | 68.33% / 82.67% | Abstract p.1; Table 1, p.5 |
| Function Recall@10 with the 4B model: best baseline / SemNav | 32.92 / 40.72 | Table 1, p.5; text p.6 |
| Cells where SemNav ranks first on SWE-bench Lite | 24 of the 27 | Sec. "Overall Localization Performance", p.6 |
| Second benchmark, Acc@5: best baseline / SemNav | 60.41 / 67.36 | p.6 |
| Second benchmark, macro recall@5: best baseline / SemNav | 42.07 / 47.45 | p.6 |
| Ablation, File Hit@10: without cards / without online resolution | -6.00 / -7.00 points | Sec. "Component Contributions", p.6 |
| Ablation, Function Recall@10: without seed / without workspace | -13.20 / -19.20 points | p.6 |
| Output size without the workspace against with it | 1.50 against 9.96 functions | p.6 |
| Working-context reduction from cards, against full-source reading | 48.2% | Abstract p.1; p.6 |
| Total token cost of cards against full-source reading and truncated reading | 25.4% below and 4.8% above | p.6 |
| Line-level precision on SWE-Explore: best baseline / SemNav | 53.35% / 79.99% | p.2; p.6 |
| Resolved rate, repair model with the larger backend: best baseline / SemNav | 44.00% / 52.33% | Abstract p.1; Table 3, p.7 |
| Resolved-rate gains over the strongest baseline: two repair models | 4.33 and 8.33 points | Sec. "Downstream Repair Utility", p.7 |

## Method details we need

- **Role of the graph**: agent tool plus a retrieval-time neighbour bonus (above); not learned.
- **Edge status**: explicit resolved and unresolved edges; on-demand go-to-definition for forward edges and find-references for reverse edges; sites the server cannot resolve stay unresolved (p.3). This is the same status scheme the project's graph design already considers; it is a precedent, not a decision.
- **Edge-type ablation**: none. **Resolution coverage measured**: not as a rate; the offline-only variant is the nearest thing (-7.00 points File Hit@10).
- **Latency**: token counts only (Figure 3c, p.7).
- **Held-out handling**: none needed (no training); evaluation sets are public benchmarks.
- **Seeding retrieval**: BM25 over a per-entity text (qualified name, declaration, documentation, implementation) plus exact-cue matches (Eq. 5, p.3).
- **Models**: gemma-4-e4b-it, Qwen3.5 9B, Qwen3.5 35B-A3B for localization; Qwen3.5 35B-A3B and the 4B model as repair backends (pp.6-7).

## Relation to RQ1 / RQ2 / RQ3

- RQ1: evidence that language-server resolution of edges changes localization (7.00 points of File Hit@10 on 300 issues with a 4B model), which is the closest published datapoint to "does edge-resolution coverage matter". It is an LLM-agent setting; it does not say what resolution does for a retriever without an LLM.
- RQ2: none.
- RQ3: it adds a downstream comparison across localizers with fixed repair prompts and one repair attempt, and a gold-context oracle that shows the repair ceiling at 39.00% and 67.00% on SWE-bench Lite for the two repair models.

## Discrepancies

- Naming: this paper calls the 821-issue benchmark "PLocBench" and cites it as "A Benchmark for Localizing Code and Non-Code Issues in Software Projects" (arXiv 2509.25242, p.9); the SWE-Explore paper cites the same arXiv number under the name "MULocBench" (`swe-explore-2606.07297.md`). Same benchmark under two names.

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| Search leads: graph retrieval that resolves unresolved relation targets | present | Eqs. 3-4, p.3 | Online resolution through a language server is the paper's first component and is ablated. |
