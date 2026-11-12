read: full — 13 pages incl. appendices, PDF v1, pdftotext -layout (poppler), 2026-11-12

# UTBoost: Rigorous Evaluation of Coding Agents on SWE-Bench — Yu, Zhu, He and Kang (arXiv 2506.09289v1, 10 Jun 2025; ACL 2025)

Source file: arXiv PDF v1, 13 pages (body 9 pages, references pp. 10-11, appendix A leaderboard tables pp. 12-13). The extracted text has 13 pages and no blank page. Every page was read, including both leaderboard tables. Literature-scan source for the refresh of 2026-11-12 (topic: evaluations on the human-validated subset of the benchmark whose tests are executed; test adequacy and the harness's log parser).

## What it established

- A method (UTGenerator and UTBoost) that adds test cases to benchmark instances and checks, by comparing the gold patch with an agent's patch on the new tests, whether the original tests were too weak (Sec. 3, pp.3-5).
- Applied to the lite subset (300 instances) and the human-validated subset (500 instances) of the benchmark, it found instances whose tests accept patches that do not fix the issue: 170 of 599 and 92 of 584 submitted patches that passed the original tests failed the new ones, in 23 lite and 26 verified-subset instances (Sec. 4.2, p.6).
- The official harness parses test logs with per-repository regular expressions that fail on multi-line log entries; an improved parser changed the stored pass-to-pass and fail-to-pass annotations of 54.7% of lite and 54.2% of verified-subset instances and exposed 64 and 79 further wrongly passed patches (Sec. 3.4, p.5; Sec. 4.3, p.7). Django and sympy account for most of the affected patches (82.6% of the 92 in the verified subset, Sec. 4.2, p.7).
- With both corrections the leaderboard changed: 24.4% (11 of 45) of entries in the verified subset changed rank (Sec. 4.4, p.8; Appendix A, pp.12-13).

## What it did not establish

- Anything about retrieval or context construction.
- That the benchmark's resolved rates are wrong in general: the finding concerns patches that pass the original tests and fail added tests; the added tests were reviewed by two authors, not by independent readers (Sec. 4.1, p.6).
- Coverage beyond instances at least one submitted agent resolved: the method needs a patch that passes the original tests, so 74.6% (224 of 300) and 81.6% of instances can be tested (Limitations, p.9).
- Results for more than one test generator model: one closed-source model only (Limitations, p.9).
- Any run-to-run variance: each submitted patch is one run (the patches come from the public leaderboard repository, Sec. 4.1, p.6).

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| Human-validated subset: instances; annotating developers | 500; 93 | Sec. 2, p.3 |
| Instances with insufficient tests: lite / verified subset | 23 / 26 | Sec. 4.2, p.6 |
| Share of the verified subset with insufficient tests | 5.2% (26 of 500) | Sec. 1, p.2 |
| Erroneous patches among patches passing the original tests: lite / verified subset | 28.4% (170 of 599) / 15.7% (92 of 584) | Sec. 4.2, p.6 |
| Instances whose stored annotations the improved parser changed: lite / verified subset | 54.7% (164 of 300) / 54.2% (271 of 500) | Sec. 4.3, p.7 |
| Extra wrongly passed patches found with the improved parser: lite / verified subset | 64 / 79 | Sec. 4.3, p.7 |
| Total erroneous patches after both corrections: lite / verified subset | 176 / 169 | Sec. 4.4, p.7 |
| Leaderboard entries whose rank changed, verified subset | 24.4% (11 of 45) | Sec. 4.4, p.8 |
| Share of the verified-subset erroneous patches in two projects | 82.6% (76 of 92) | Sec. 4.2, p.7 |
| Cost of generating tests per instance (dollars) | 1.6 | Sec. 4.1, p.6 |
| Evaluation time on the cloud servers (hours) | 300 | Sec. 4.1, p.6 |

## Method details we need

- **Oracle** (Sec. 3.1-3.2, pp.3-4): intramorphic testing; the gold patch and the agent's patch are expected to behave the same on every issue-related test; a mismatch on a generated test marks the instance suspicious, and two authors review the test and the patch before the test is kept (Sec. 4.1, p.6).
- **Generator** (Sec. 3.3, pp.4-5; Sec. 4.1, p.6): file, function and line localization of where tests go, then test generation with temperatures 0, 0.8, 0.9 and 0.99; 10 lines of context; one closed-source model.
- **Parser** (Sec. 3.4, p.5; Listings 5-7, pp.5-6): the original per-repository regular expressions split a multi-line log entry at the last occurrence of a pass suffix and take the wrong text as the test name; the improved parser tracks neighbouring lines.
- **Leaderboard** (Sec. 4.4, p.8; Appendix A, p.12): the original leaderboard is the version dated 15 December 2024; agents that published no patches are excluded (44 and 45 agents).

## Relation to RQ1 / RQ2 / RQ3

- RQ1, RQ2: none.
- RQ3: a documented source of evaluation noise on the very benchmark and projects (django and sympy dominate both here and in the project's executable subset: django 228 and sympy 75 of 377, project entry E-RQ3-EXEC): tests that accept some wrong patches, and log parsing that mislabels pass-to-pass tests. The project's executor runs the named tests itself and reads per-test outcomes (E-RQ3-EXEC, D106); it does not use the official regular-expression parser. Whether the project's per-instance lists of tests equal the improved parser's corrected lists was not checked (inference, to be checked before the final claim). Test insufficiency would raise resolved rates equally across arms in expectation (inference); it is a threat to absolute rates, not to paired contrasts, unless the wrong patches differ by arm.

## Discrepancies

- The abstract says 36 task instances with insufficient tests, while the body states 23 lite and 26 verified-subset instances (Sec. 4.2, p.6), a sum of 49; the two counts are not reconciled in the paper (the instances may overlap between the two subsets, which the paper does not say).
- The abstract gives 54.6% (164 of 300) for the lite subset, and Sec. 4.3 (p.7) 54.7%; 164 of 300 is 54.67%.
- The abstract's 345 erroneous patches is the sum of 176 and 169 (Sec. 4.4, p.7); the same text separately reports 170 and 92 found with the added tests and 64 and 79 with the improved parser, which sum to 234 and 171, not to 176 and 169; the paper does not explain the remainder (overlap between the two causes is the likely reading; inference).

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| The human-validated subset has 500 instances and 93 developers | confirmed (as a citation of the benchmark's announcement) | Sec. 2, p.3 | Described from the announcement, not measured here. |
| Official parser defects affect most stored test lists | confirmed for this paper's improved parser | Sec. 4.3, p.7 | 54.2% of the verified subset. |
| Verified-subset tests are "comprehensive" | contradicted for 26 instances | Sec. 4.2, p.6 | By this paper's generated tests, reviewed by two authors. |
