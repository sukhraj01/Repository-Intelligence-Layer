read: full — 11 pages incl. appendices, PDF v1, pdftotext -layout (poppler) with the extraction redone page by page, 2026-10-17

# Cost-Effective Repository Exploration for Agentic Issue Localization — Al Awad and Ivanov (arXiv 2608.29675v1, 30 Aug 2026; AgenticDev '26)

Source file: arXiv PDF v1, 11 pages (body 10 pages, data availability on p.10 and references on p.11; no appendix). arXiv holds only v1. The extracted text has 11 pages and no blank page. Every page was read, including Tables 1-5. Literature-scan source (topic: follow-ups on retrieval for coding agents); the paper compares explorer models, not retrievers, and is listed mainly for its statistics.

## What it established

- IssueLoc-Bench: file-level localization under a fixed read-only shell interface, with two arms scored separately: 499 instances derived from SWE-bench Verified (12 repositories) and 500 instances from 153 other repositories, using the repository state just before the resolving commit (Sec. 4, pp.4-5; Table 1, p.5).
- Five open explorer models are compared with the highest-quality one as the reference. Cheaper models keep about 78-94% of the reference's Hit@3 and 73-92% of its F1 while using 41-88% less agent time and 84-95% fewer tokens (abstract, p.1; Table 5, p.8).
- Paired bootstrap intervals (10,000 resamples, fixed seed) and a repository-clustered bootstrap show that cost reductions are stable, while the quality ordering on the Verified-derived arm is weaker when whole repositories are resampled: several Hit@3 and F1 intervals then include zero (Sec. 7, pp.6-7).
- The authors distinguish a soft handoff (ranking and coverage metrics) from a hard gate (F1 and exact match) as consumers of a localization output (Sec. 3.2, p.4).

## What it did not establish

- Nothing about retrievers or supervision; the experimental variable is the explorer language model with a fixed shell-based interface.
- No repair or resolved-rate measurement; the authors say a fixed-repairer study is future work (Sec. 9-10, p.10).
- Possible exposure of public repositories to the explorer models' training data cannot be measured from the artifact (threats, p.10).
- Variation between repeated executions is not measured; the intervals are over instances or repositories of recorded runs (p.6).

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| Instances: Verified-derived arm / random-repository arm | 499 / 500 | Sec. 4.2, p.5 |
| Repositories: random-repository arm / Verified-derived arm | 153 / 12 | Table 1, p.5 |
| Average gold files per instance: Verified-derived / random-repository | 1.24 / 2.27 | Table 1, p.5 |
| Average repository size (paths): Verified-derived / random-repository | 3,898.5 / 614.2 | Table 1, p.5 |
| Hit@3 retained by cheaper explorers | 78-94% of the reference | Abstract, p.1 |
| F1 retained by cheaper explorers | 73-92% of the reference | Abstract, p.1 |
| Agent time and token reductions | 41-88% and 84-95% | Abstract, p.1 |
| Paired bootstrap resamples; seed | 10,000; 1729 | Sec. 5.2, p.5 |
| Per-instance time limit | 600 seconds | Sec. 6.2, p.6 |
| Hit@3 gap of the best open alternative on the Verified-derived arm (paired, instance level) | -0.044 | Table 4, p.7 |
| Hit@3 gap of the smallest model on the random-repository arm | -0.186 | Table 4, p.7 |

## Method details we need

- **Interface**: a mini-agent runner restricted to `ls`, `find`, `grep`, `cat`, `nl` and `sed -n`; the explorer returns an ordered list of repository-relative files (Sec. 3.2 p.4; Sec. 6.2 p.6).
- **Labels**: files modified by the resolving commit after filters that drop added or removed files, binary-like files and entirely text-like targets (Sec. 4.1, p.5). The labels are the historical footprint, not a minimal causal set.
- **Metrics**: Hit@1/3/5, MRR, R@3, macro F1 and exact match; empty or invalid predictions score zero and stay in the denominator (Sec. 5, pp.5-6).
- **Statistics**: instance-level percentile bootstrap, repository-clustered bootstrap, exact McNemar tests with Holm adjustment over 32 binary comparisons (Sec. 5.2, pp.5-6).
- **Serving**: four GPUs, models served locally (Sec. 6.1, p.6); five checkpoints named in Sec. 6.2 (p.6).

## Relation to RQ1 / RQ2 / RQ3

- RQ1: none.
- RQ2: none.
- RQ3: a methodological precedent: with only 12 repositories in a Verified-derived arm, instance-level intervals look decisive and repository-clustered intervals do not. The project's paired-set statistics (432 and 302 instances over 12 repositories) have the same structure, so a repository-clustered sensitivity analysis is a cheap addition (no design change is made here).

## Discrepancies

- None found.

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| Search lead: 2026 follow-up evaluating retrieval stage for coding agents with Verified-derived data | present | Sec. 4.2, p.5 | Explorer models, not retrievers; no resolved rate. |
