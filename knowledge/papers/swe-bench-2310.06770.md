read: full — 52 pages incl. appendices, PDF v3, pdftotext -layout (poppler), 2026-10-17

# SWE-bench — Jimenez, Yang et al. (arXiv 2310.06770v3, ICLR 2024 version, 11 Nov 2024)

Source file: arXiv PDF v3 (latest of three; the unversioned URL returned the identical file). 52 pages: body
11, ethics and reproducibility statements p.11, references pp. 12-15, appendices A-F pp. 16-52 (the last
twenty pages are model-output case studies). The extracted text has 52 pages, none blank. The appendix
section A.7 (SWE-bench Lite) is cut off mid-sentence in the PDF ("SWE-bench is", p.25); the Lite criteria are
therefore not recoverable from this paper.

**SWE-bench Verified is not described in this paper**: the string "Verified" occurs once, in the generic sense
"verified by running unit tests" (p.2). Verified is a later, separately released human-validated subset; its
construction must be read from its own source before anything about it is cited from this paper. In the
CORE-Bench paper it appears as 500 raw instances of which 432 are kept (Table 12, p.17 of that paper).

## What it established

- A benchmark of 2,294 task instances from 12 popular Python repositories, built by a three-stage pipeline:
  scrape merged PRs, keep those that resolve a linked issue and change test files, then keep those with at
  least one fail-to-pass test after execution in an installed environment (Sec. 2.1, pp.2-3; Appendix A).
- Funnel (Table 10, p.20): 93,139 PRs crawled, 11,407 after conversion to candidate tasks, 2,294 after
  execution validation.
- An instance is: repository, base commit, problem statement (issues' title and body plus comments written
  before the PR's first commit), gold patch (non-test files), test patch, fail-to-pass and pass-to-pass tests
  (Table 9, p.17; A.2, pp.17-18). The codebase is the repository at the base commit, reproduced from the
  authors' mirror (p.18).
- Resolved = all fail-to-pass and all pass-to-pass tests pass after applying the model patch (A.4, p.21).
- Baseline difficulty in 2023: with BM25 file retrieval the best model resolves 1.96% (p.5, Table 2).
- A separate training set of about 19,000 issue-PR pairs from 37 other repositories (no test-change
  requirement), disjoint from the 12 evaluation repositories (Sec. 3, p.4).

## What it did not establish

- Anything about the Verified subset (see above) or the Lite subset's criteria (truncated).
- Whether resolved rate measures retrieval quality: the paper's own analysis shows resolution depends on
  context length, edit size and issue content (Sec. 5, pp.6-7), not on a retrieval metric.
- Contamination: the temporal analysis (Table 7, p.7; Table 21, p.28) finds no strong date dependence for the
  models of 2023 but does not test for memorized repositories.
- Run-to-run variance: single greedy runs per instance (D.2, p.30).

## Numbers we may quote

Values are `paper_reported`. Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| Task instances; repositories | 2,294; 12 | Abstract, p.1 |
| PRs crawled / after conversion / final | 93,139 / 11,407 / 2,294 | Table 10, p.20 |
| Final count, flask / requests / seaborn | 11 / 44 / 22 | Table 10, p.20 |
| Final count, django / sympy / scikit-learn / matplotlib | 850 / 386 / 229 / 184 | Table 10, p.20 |
| Final count, sphinx / pytest / xarray / astropy / pylint | 187 / 119 / 110 / 95 / 57 | Table 10, p.20 |
| Candidate tasks removed by execution validation | half | A.3, p.19 |
| Mean issue length (words); mean files in codebase; mean gold files / functions / lines edited | 195.1; 3,010; 1.7 / 3 / 32.8 | Table 1, p.4 |
| Instances with at least two fail-to-pass tests | 40% | Sec. 2.3, p.3 |
| Training set: issue-PR pairs; repositories; instances kept after the 30,000-token cut | 19,000; 37; 10,000 | Sec. 3, p.4 |
| Development set: instances; repositories | 225; 6 | A.6, p.24 |
| Best 2023 model with BM25 context, resolved rate (percent) | 1.96 | Sec. 5, p.6 |
| Same model with the oracle files, resolved rate (percent) | 4.8 | Sec. 5, p.6 |
| Package ranking used to pick repositories: packages considered / selected | 5,000 / 100 | A.1, p.16 |

## Method details we need

- **Selection (A.1, p.16).** From the top 5,000 most downloaded PyPI libraries (August 2023) the top 100 whose
  repositories are licensed for free use; all PRs collected through the GitHub API.
- **Candidate PRs (A.1, p.16).** Merged, resolve at least one issue (keywords such as closes, fixes, resolves
  in title, body or commit messages), and add or change a file under a path with a test-related keyword.
- **Validation (A.3, pp.19-20).** Per release version an installed environment; apply the test patch, run,
  apply the gold patch, run; discard on any failure, on `ImportError` / `AttributeError` in the pre-patch log
  (naming errors), and when no test goes from fail to pass. Instances whose tests call newly created functions
  or classes are removed.
- **Fields (Table 9, p.17).** `created_at` is the PR creation time (not merge time); `version` the repository
  release; `env_install_commit` the commit used to install dependencies.
- **Dev repositories (Table 15, p.25):** astroid, marshmallow, pvlib-python, pydicom, pyvista, sqlfluff.
- **Evaluation repositories (Table 12, p.23):** astropy, django, flask, matplotlib, pylint, pytest, requests,
  scikit-learn, seaborn, sphinx, sympy, xarray.

## Relation to RQ1 / RQ2 / RQ3

- RQ3: defines the outcome measure and its failure modes (patch not applying, no-op, regression: Tables 22-23,
  pp.28-29). The agent-held-fixed design must keep the same harness for every retriever.
- RQ2 data: the held-out repository list must contain these 12 repositories (the paper's evaluation set) and,
  for the project's choice, also the six development repositories if the dev split is to stay clean (decision
  for the engineer; the paper only says training and evaluation repositories are disjoint).
- Leakage: instances are keyed by `repo` and `base_commit`; a training pool built from PRs of the same repositories
  contaminates at repository level even when instances differ.
- Base commits and `created_at` per instance are what the CORE-Bench chunk-to-unit mapping and any recency prior
  need (the data audit found them in the Verified parquet).

## Discrepancies

- With the project's brief, which names a "Verified section" of this paper: there is none (see top).
- Internal: Table 29 (p.42) lists a fail-to-pass test from the seaborn example under the pylint instance; the
  link labels in Tables 25 and 26 are swapped (issue and PR). Case-study typos, no effect on any number.
- Internal: the Abstract and Sec. 1 state 2,294 instances and Table 10's total is 2,294 (consistent). The
  "~90,000 PRs" of Sec. 2.1 is 93,139 in Table 10.

## Claims checked

No numbered lead from the brief targets this paper. Checks done for the note:

| Claim | Verdict | Where | Note |
|---|---|---|---|
| The paper describes SWE-bench Verified | not found | whole paper | One generic use of "verified" (p.2). |
| Construction funnel 93,139 to 11,407 to 2,294 | confirmed | Table 10, p.20 | |
| Evaluation and training repositories are disjoint | confirmed | Sec. 3, p.4 | For the 37-repository training set only; says nothing about third-party pools. |
| Resolved requires all fail-to-pass and pass-to-pass tests | confirmed | A.4, p.21 | |
| Lite subset criteria | not recoverable | Sec. 2.4, p.4; A.7, p.25 | Appendix text cut off in the PDF. |

## Figures looked at

Figure 3 (p.4): pie of instances per repository, matches Table 10. Figure 9 (p.22) cumulative distributions of
instance attributes; medians quoted in text (140 words, about 1,900 files) are not used here. Figures 4-5
(pp.6-7) bar plots without quoted numbers.
