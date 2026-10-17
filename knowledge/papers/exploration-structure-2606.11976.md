read: full — 22 pages incl. appendices, PDF v1, pdftotext -layout (poppler), 2026-10-17

# Exploration Structure in LLM Agents for Multi-File Change Localization — Fattha et al. (arXiv 2606.11976v1, 10 Jun 2026)

Source file: arXiv PDF v1, 22 pages (body 15 pages, references pp.18-19, appendices A-C pp.20-22: instruction texts, baseline details, the 19 instances with their gold files). arXiv holds only v1. The extracted text has 22 pages and no blank page. Every page was read, including Tables 3-8 and the appendix instance table. Literature-scan source (topic: evolutionary coupling and co-change for localization).

## What it established

- A controlled, small file-localization study on one repository (ansible/ansible; SWE-bench Pro instances), three six-month windows (2020, 2025, 2026) of 19 instances each, each window anchored at one base commit (Sec. 3.2, p.6; RQ5, p.14). Four method families are compared: a plain model call with no repository access, a single-agent model with a persistent code REPL, the authors' domain-scoped parallel agents, an external coding-agent command line, plus BM25 as a swept envelope (Sec. 4, pp.7-9).
- Under the benchmark's curated gold set the best BM25 F1 is 0.235 (at K = 7) and the best language-model F1 is 0.471; under a broader gold set (every file touched by the resolving pull request) 0.241 (K = 12) and 0.523 (Sec. 5.3, p.12). BM25's recall reaches 0.65 at K = 30 but its precision is 0.072; the language-model methods win on precision (p.12).
- The plain model without file access beats the same model with a REPL on the curated gold at both model sizes (Sec. 5.4, p.13); forcing more agent consultation did not help (Sec. 5.5, p.13).
- Documentation files are the systematically missed category: the aggregate miss rate for `docs/docsite/` gold files is 73% against 15%-44% for the code categories (Table 5, p.14). The authors read this as a logical-coupling problem: documentation changes with the source files it describes, but the issue text does not mention it (Sec. 5.6 and 7, pp.14-15).
- The authors name mining co-change and logical-coupling signals from history as a natural extension and do not test it (Conclusion, p.18).

## What it did not establish

- No co-change or history feature is implemented or measured; the sentence quoted above is the only treatment, so the topic remains open in this paper (searched for in all sections).
- Nineteen instances per window in one repository, a handful of runs per method (n = 1 to 5), so intervals are wide; the headline comparison adaptive against no-spawn is significant only under the broad gold (Wilcoxon p = 0.015, Cliff's delta 0.36; Sec. 5.2, p.11) and not under the curated gold (p = 0.16).
- Not a retrieval-model study: all methods are language-model agents or BM25; no embedding retriever is evaluated.
- The 2025 and 2026 gold sets use a programmatic filter the authors invented (source files touched by the resolving pull request), different from the curated 2020 set (Sec. 5.7, p.14), so absolute scores are not comparable across windows; the authors note possible overlap of the 2026 issues with model training data (p.15).
- No resolved-rate measurement ("file localization in isolation", threats, p.16).

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| Instances per window / curated gold files / PR-touched gold files (2020 window) | 19 / 63 / 171 | Sec. 3.2-3.3, p.6 |
| Multi-file share in the source benchmark against Verified | 80% against 14% | Sec. 2, p.3 |
| Files in the repository at the 2020 base commit | about 3,400 Python source files | Sec. 3.2, p.6 |
| Best BM25 F1: curated gold (at K = 7) / broad gold (at K = 12) | 0.235 / 0.241 | Table 3 and Sec. 5.3, pp.11-12 |
| Best language-model F1: curated gold / broad gold | 0.471 / 0.523 | Sec. 5.3, p.12 |
| Plain model with the larger closed-source model, curated micro-F1 | 0.467 | Table 3, p.11 |
| Domain-scoped agents, curated micro-F1 (mean of 5 runs) | 0.447 | Table 3, p.11 |
| External command-line baseline, curated / broad micro-F1 | 0.422 / 0.523 | Table 3, p.11 |
| All-gold instances out of 19: larger plain model / domain agents / command line | 4.0 / 6.4 / 9.2 | Table 3, p.11 |
| Miss rate for documentation gold files | 73% | Table 5, p.14 |
| Resolving pull requests that also modify or add test files | 17 of 19 (89 test-file changes) | Sec. 7, p.16 |
| Adaptive agents against no-spawn ablation under the broad gold: Wilcoxon p / Cliff's delta | 0.015 / 0.36 | Table 4 and Sec. 5.2, pp.11-13 |
| Token use of forced against adaptive consultation | 25.1M against 16.1M | Sec. 5.5, p.13 |
| Reduction of input tokens by compact directory listings | 40.8% (910 against 1,540) | Sec. 4.3, p.9 |

## Method details we need

- **Gold sets**: curated (the benchmark maintainers' file list) and PR-based (every file touched by the resolving pull request); the 108 PR-touched files omitted from the curated list are 48.1% integration-test fixtures, 25.0% unit tests, 9.3% other test paths and 14.8% changelog fragments (Sec. 3.3, p.6). A system that predicts a test or changelog file is penalised under the curated gold.
- **Metrics**: micro-averaged precision, recall and F1 over files; all-gold rate; paired Wilcoxon signed-rank on per-instance F1; Cliff's delta (Sec. 3.1, p.5).
- **BM25 baseline**: 3,547 files (Python, rst, txt, yaml, C# sources) indexed with path tokens and content, k1 = 1.2, b = 0.75; swept over K = 1..30 (Sec. 4.5, p.10).
- **Models**: a small and a larger closed-source model from one vendor family, and a larger external command-line agent (versions in Sec. 4.1 p.8, Sec. 4.4 p.10 and Appendix B p.21); not reproduced here.
- **Co-change mention**: the related-work paragraph ties the finding to the logical-coupling literature (Zimmermann et al. 2005; Gall et al. 1998; p.5) and the conclusion proposes mining it (p.18).

## Relation to RQ1 / RQ2 / RQ3

- RQ1: a negative finding for the project's "co-change as signal" question: the only recent paper in the scan that raises co-change for LLM-agent localization names it as future work and gives no measurement. It adds a concrete failure category (documentation files) that a co-change or "documents" edge might address, and a caution that gold-set definition (tests and changelogs in or out) changes scores by large amounts.
- RQ2: none.
- RQ3: the definition of gold changes rankings between methods (the larger plain model leads on the curated gold and trails under the broad gold), which is a reminder that the qrels' treatment of test and documentation files can flip comparisons; relevant to CORE-Bench Level-3 labels that include them.

## Discrepancies

- None found internally beyond the gold-set differences it reports itself.

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| Search lead: a 2025-2026 study that uses co-change or logical coupling for LLM-agent localization | contradicted as a measurement; present as a proposal | Conclusion, p.18; Sec. 2, p.5 | Proposed as an extension; no experiment. |
