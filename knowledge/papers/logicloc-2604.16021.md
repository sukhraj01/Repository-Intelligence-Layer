read: full — 22 pages incl. appendices, PDF v2, pdftotext -layout (poppler), Figures 2 and 4 (pp.8, 18) rendered and looked at, 2026-10-23

# LogicLoc and KA-LogicQuery — Xu, Wu, Zhang and Li (arXiv 2604.16021v2, 2026), "Neurosymbolic Repo-level Code Localization"

Source file: arXiv PDF v2 (dated 20 Apr 2026; highest version that resolves), 22 pages: body pp.1-21, references pp.21-22; no appendix. The extracted text has 22 pages and no blank page. Figure 1 (p.6) is a code listing; Figure 2 (p.8) is the system diagram with no numbers; Figure 4 (p.18) carries per-system execution times and token counts and was looked at (only the two LogicLoc values the text also states are quoted below). Read because the earlier scan listed it abstract-only with a claim about keyword shortcuts in issue-localization benchmarks, and because it is a repository-graph (program-fact) method.

## What it established

- On SWE-bench Lite, "over 50%" of issue descriptions explicitly mention identifying information of the ground-truth location (file, class or function names) (p.13). The paper names this the "keyword shortcut". The method of this count is not described beyond one sentence.
- A Datalog fact base extracted from Python ASTs (entities: files, modules, functions, classes, variables; relations: containment, inheritance, import/use, call, reference; control and data flow "when available") queried by Datalog programs that an LLM writes, executed by the Soufflé engine, with parser-gated repair and mutation-based diagnosis of empty intermediate relations (Sec. 3, pp.7-12).
- On the authors' diagnostic benchmark of 225 structural queries (25 query templates over 9 repositories at SWE-bench Lite base commits, ground truth gathered from several LLM agents and checked by two authors), LogicLoc reaches function-level success rate 57.14 to 58.67 and precision 62.11 to 66.98, while every baseline (SweRank, Agentless, LocAgent, CoSIL) is at or below 11.73 success rate at function level and 0 perfect-location rate (Table 2, p.16).
- On 274 SWE-bench Lite instances, the SweRank retrieve-and-rerank system is ahead of LogicLoc at every level (function Acc@5 79.56 small / 81.39 large against 68.98 for LogicLoc; with the same LLM, LocAgent 73.36 and Agentless 58.76), and LogicLoc returns about 2 candidates per issue on average (Table 3, p.17; p.16).
- Ablation on the first 25 queries: validation and repair, then intermediate-rule feedback, raise function-level success rate from 20.00 to 56.00 (one LLM) and from 44.00 to 61.90 (another) (Table 4, p.19).

## What it did not establish

- **No measurement of the graph itself.** No edge precision or recall, no resolution rule for calls, no ablation of relation types. Which relations the issue-benchmark runs used is not reported.
- **Keyword-agnostic queries are not issues.** The 225 queries are structural predicates ("functions with more than 15 parameters that are not constructors"), solvable by exact queries over AST facts by construction; the large gap over retrieval baselines on them says nothing about issue-to-code retrieval. The paper argues the queries test "a necessary condition" (p.12); that is an argument, not a measurement.
- The "over 50%" keyword figure has no method, no denominator stated beyond SWE-bench Lite, and no breakdown by identifier type; it is a lead for the project's own measurement, not a usable rate.
- One run per configuration, no seeds or intervals; LLM temperature 0.3, at most 20 iterations (p.15). Ground truth for the diagnostic benchmark was proposed by closed-source models (versions on p.12 and pp.19-20) before human checking, which bounds recall of the gold sets by what those agents found.
- Nothing about training retrievers.

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| SWE-bench Lite issues whose text names the ground-truth location (file, class or function) | over 50% | p.13 |
| SWE-bench Lite instances kept (patches modify existing functions or classes) | 274 of 300 | Sec. 4.1.1, p.12 |
| Diagnostic benchmark: query templates / repositories / queries | 25 / 9 / 225 | Sec. 4.1.1, p.12 |
| Mean ground-truth locations per SWE-bench Lite instance | 1.15 | p.15 |
| LogicLoc mean candidates per issue on SWE-bench Lite | 2 | p.16 |
| SWE-bench Lite function Acc@5, SweRank small / large / LogicLoc | 79.56 / 81.39 / 68.98 | Table 3, p.17 |
| SWE-bench Lite file Acc@1, SweRank small / large | 78.10 / 83.21 | Table 3, p.17 |
| Diagnostic benchmark, function-level SR, LogicLoc (two LLMs) | 57.14 / 58.67 | Table 2, p.16 |
| Diagnostic benchmark, function-level SR, SweRank small / large | 1.02 / 1.53 | Table 2, p.16 |
| Diagnostic benchmark, function-level hit rate, LocAgent best | 40.82 | Table 2, p.16 |
| Abstention on the empty-gold variant: queries answered "no match" by LogicLoc | over 70% | p.16 |
| LogicLoc mean time per query / mean tokens per query (one LLM) | 39.3 s / 16.2k | p.18 |
| Ablation, function-level SR Base / VAL / Full (first LLM) | 20.00 / 40.00 / 56.00 | Table 4, p.19 |
| LLM temperature / maximum iterations | 0.3 / 20 | Sec. 4.2.1, p.15 |

## Method details we need

- **Fact extraction** (Sec. 3.1, p.7): enumerate files honouring ignore rules; parse Python to AST; emit facts with source locations and stable identifiers; relations containment, inheritance, import/use, call, reference. Call resolution is not described.
- **Agent tools** (p.8): execute a Datalog program; get file contents; get source line ranges. Output is a variable-size set, not a ranked list.
- **Metrics** (Sec. 4.2, pp.14-15): Acc@k requires all gold locations in the top k; recall, precision, Jaccard, exact-set rate, hit rate, per file, module and function.

## Relation to RQ1 / RQ2 / RQ3

- RQ1: two leads. (a) The keyword shortcut: a large share of issues name the location, which is why lexical retrieval is strong at L2 and why the project should measure, per query, whether the gold unit's name occurs in the issue, and report graph and dense gains separately on queries with and without that overlap. (b) A structured fact base answers structural predicates exactly; that is a different role from a ranking signal. On real issues it was weaker than a trained dense retrieve-and-rerank system (Table 3).
- RQ2: none.
- RQ3: none directly; abstention and small candidate sets are argued to help downstream agents, with no resolved-rate measurement.
- Graph role (Q30): one more instance of the graph as an LLM agent's tool (here through a query language), not as a retrieval signal.

## Discrepancies

- With the earlier scan entry in `LANDSCAPE.md`: the abstract's "saturated with keyword references" is backed in the body by a single unexplained "over 50%" on SWE-bench Lite (p.13).
- Internal: the contributions list says KA-LogicQuery "contains 25 high-quality purely logical queries" (p.3) while Sec. 4.1.1 says 225 queries (25 templates over 9 repositories) (p.12). Figure 4 labels the system "DataLoc" (p.18). The text gives the time as "39s" (p.17) and "39.3s" (p.18).

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| Earlier scan (abstract only): benchmarks are saturated with keyword references | partly | p.13 | one figure, "over 50%" of SWE-bench Lite issues, method not given |
| Abstract: LogicLoc "competitive" on issue benchmarks | qualified | Table 3, p.17 | below SweRank at every level on SWE-bench Lite; with the same LLM, between Agentless (58.76) and LocAgent (73.36) at function Acc@5 |
| Graph helps localization | not tested as a signal | — | the fact base is used through an LLM agent; no ablation of relations |
