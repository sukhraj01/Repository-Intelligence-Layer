read: full — 20 pages incl. appendices, PDF v1, pdftotext -layout (poppler) with the extraction redone page by page, 2026-10-17

# SWE-Explore — Zhang et al. (arXiv 2606.07297v1, 5 Jun 2026), "SWE-Explore: Benchmarking How Coding Agents Explore Repositories"

Source file: arXiv PDF v1, 20 pages (body 10 pages, references pp.11-13, appendices A-G pp.13-20: benchmark composition, ground-truth construction, metric definitions, restricted-context protocol, explorer implementation, a case study, reproducibility). arXiv holds only v1. The extracted text has 20 pages; the last page is short (end of the reproducibility and limitations appendix) but not blank. Every page was read except for the numeric cells of Tables 5-6, whose rows were read from the extracted text only for the qualitative claims quoted below. Literature-scan source (topic: follow-ups to CORE-Bench-style evaluation of retrieval for coding agents).

## What it established

- A benchmark that scores an explorer's ranked list of line regions for an issue under a line budget, with ground truth taken from agent runs that solved the issue: 848 instances from SWE-bench Verified, SWE-bench Pro and SWE-bench Multilingual, 203 repositories, 10 languages (Sec. 3.2, p.4); the ground-truth "core" regions are the file-wise line intersection of reads across at least two successful trajectories by strong closed-source agents, refined by a model and audited by the authors (Sec. 3.3, pp.4-5; Appendix B, pp.14-15).
- A metric set (line-level precision, recall, F1, file hit, region hit, nDCG under a line budget, first useful hit, context efficiency, noise rate; Sec. 3.4, p.6) and a one-time restricted-context repair experiment in which a fixed patcher sees only the explorer's regions (Sec. 3.4, p.6; Appendix D).
- Across 14 explorers on a shared 150-instance subset, the explorer-level correlation between upstream metrics and the downstream resolve rate (averaged over two patchers) is high for context efficiency (Pearson 0.950), first useful hit (0.928), Recall@100 (0.926) and file hit (0.925), with Recall@100 the strongest rank correlation (Spearman 0.845) (Table 4 and Sec. 4.2, pp.7-8).
- Sparse and lightweight dense retrievers "remain close to Random on most metrics" at five regions per instance; every agentic explorer is well above them; the general coding agents have similar profiles with high file hit and line recall only about 0.14-0.19; a code-graph agent (CoSIL) has by far the highest non-oracle line recall (Sec. 4.3, p.9).
- Controlled degradation (Figure 5, p.10): missing core context hurts more than extra irrelevant context once the essential evidence is visible; at no context the stronger patcher does better than with a small incomplete slice, and the authors suggest empty-context baselines on canonical repositories "may be inflated" (memorisation; p.10).

## What it did not establish

- Not a retriever-training study and not an embedding comparison: the dense baseline is a static word-embedding retriever (Potion), and no trained code embedding model is scored.
- The ground truth is what successful agents read, conditioned on the issue being solved by at least two trajectories; unsolved issues are excluded (Limitations, p.19), and the labels are an approximation of useful context.
- The correlations are across explorers (n = 14), computed on 150 instances with two patchers averaged; they are not per-instance and carry no interval. Explorers are agents and scaffolds mostly, so the correlation says little about how much a better embedding retriever would raise resolved rate for a fixed agent.
- No training data, no seeds, no interval on any table.

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| Benchmark size: instances / repositories | 848 / 203 | Sec. 3.2, p.4 |
| Python instances | 547 | Figure 3 and Appendix A, pp.5, 14 |
| Ground truth per instance: files / regions / lines | 4.3 / 4.7 / 1,578 | Table 2, p.5 |
| Repository size, non-test average | 759 files; 179.6K lines | Table 2, p.5 |
| Successful trajectories required per instance | at least two | Sec. 3.3, p.5 |
| Subset used for the downstream validation | 150 instances | Sec. 4.2, p.7 |
| Pearson correlation of context efficiency with resolve rate (explorer level) | 0.950 | Table 4 and text, pp.7-8 |
| Pearson correlation of first useful hit / Recall@100 / file hit | 0.928 / 0.926 / 0.925 | Table 4, p.7 |
| Spearman correlation of Recall@100 | 0.845 | Sec. 4.2, p.8 |
| General coding agents: line-level recall range | 0.14 to 0.19 | Sec. 4.3, p.9 |
| Regions returned per instance (K) | 5 | Sec. 4.1, p.7 |
| Line budget for the primary ranking score | 500 | Sec. 3.4, p.6 |
| Resolve-rate drop from random non-core padding at no true context | 7 to 9 points | Sec. 4.4, p.10 |

## Method details we need

- **Ground truth**: read actions (editor views with ranges, `cat/head/tail/sed -n` reads, `grep -n` hits) are mapped to repository-relative closed line intervals; intersection across trajectories gives core, the rest gives optional context; a model promotes some optional reads to core; the authors audit every promoted region (Sec. 3.3 and Appendix B, pp.4-5, 14-15).
- **Budgeted nDCG**: gain per region is the number of core lines it covers, processed in predicted order within a line budget (B = 500; 100 and 300 also computed), normalised by a greedy ideal order for the same budget (Appendix C, p.16).
- **Restricted-context validation**: every line outside the explorer's regions is blanked; a fixed patcher and test harness are used; resolved means the benchmark tests pass (Appendix D, p.17).
- **Instance sources**: Verified, Pro and Multilingual; the Verified repositories among them are the project's evaluation repositories, so this benchmark must never feed a training pool (`specs/held_out_repos.md`).
- **Agents used for ground truth and baselines**: closed-source and open coding agents; versions are listed in Sec. 3.3 (p.5) and Table 6 (p.8) and are not reproduced here.

## Relation to RQ1 / RQ2 / RQ3

- RQ1: a datapoint that file-level hit is high for many explorers while line-level recall is low, and that a code-graph agent has the highest recall; it supports reporting recall at several granularities and a budgeted rank metric, which is relevant to how CORE-Bench chunk-level labels would be mapped to units.
- RQ2: none.
- RQ3: the explorer-level correlation between an upstream retrieval metric and resolved rate across 14 systems is evidence for the project's assumption that retrieval metrics track resolved rate across very different systems; it is not evidence about a retriever whose only difference is its training supervision, and it comes with the memorisation caveat above.

## Discrepancies

- Name of a benchmark it cites: the paper cites arXiv 2509.25242 as "MULocBench" (reference 35, p.13), while the SemNav paper calls what is apparently the same benchmark "PLocBench" (`semnav-2609.31176.md`).
- With CORE-Bench: SWE-Explore describes itself as a line-level, trajectory-grounded alternative; it does not compare against CORE-Bench labels.

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| Search lead: a 2026 benchmark that ties exploration metrics to downstream repair | confirmed | Sec. 4.2, pp.7-8 | Explorer-level correlations over 14 explorers, 150 instances. |
| Lead: ground truth from independent successful trajectories | confirmed | Sec. 3.3, p.5 | At least two, line-level intersection, then a model refinement and a human audit. |
