read: in full except the numbered source-code listings inside the appendix trajectories (pp. 45 to 116); every agent turn, error message, patch and summary was read — 118 pages incl. appendices, PDF v3, pdftotext -layout (poppler), 2026-11-08

# SWE-agent — Yang, Jimenez, Wettig, Lieret, Yao, Narasimhan, Press (arXiv 2405.15793v3, 11 Nov 2024; NeurIPS 2024)

Source: https://arxiv.org/abs/2405.15793, PDF https://arxiv.org/pdf/2405.15793v3 (v3 is the latest version; v1 has 25 pages and v2
118 pages, neither used), retrieved 2026-11-08. The PDF has 118 pages (body pp.1-10, references pp.10-15, appendix pp.16-118);
the extracted text has 118 pages and no blank page (`scripts/check_paper_note.py`).

**Scope of the reading.** Pages 1-44 and 117-118 (body, all appendix tables, prompts, statements) were read line by line.
Pages 45-116 are four verbatim agent trajectories (Figures 33-36: requests-2317, pylint-5859, sympy-21614, django-14411).
On those pages the issue statements, every agent turn (thought and action), every error message, the final and gold
patches and the authors' summaries were read; the numbered source-code listings inside the observations (repository files
shown to the agent, about 4,000 lines) were not. No claim in the project rests on those listings, and no number in the
table below is taken from pages 45-116. Figures 4 and 8 (pp.6 and 8) and Table 3's page were rendered and looked at;
Figure 4's values are the pass@k row of Table 10.

## What it established

- An agent-computer interface (ACI) for an LM agent: a small set of commands for searching, viewing a 100-line file window,
  and editing lines, with a syntax-check guardrail on edits, concise feedback, and a history that collapses observations
  older than the last five (Sec. 3, pp.3-4; Table 4, p.17).
- With GPT-4 Turbo it resolves 286 of 2,294 SWE-bench test instances and 54 of 300 Lite instances; with a second closed-source model
  10.46% and 13.00% (Table 1, p.6). The interface matters: the same model with only a Linux shell resolves 11.00% on Lite
  (Table 1, p.6), and removing the edit command, linting, the summarised search or the window limit each lowers Lite
  resolved rate (Table 3, p.6).
- Six runs of the main configuration on Lite resolve 17.33 to 18.67% (mean 17.94 with a subscript 0.49 that the paper does not label, read from the
  rendered page), while the share of
  instances resolved by at least one of six runs is 32.67% (Table 10, p.35).
- Resolved runs are cheaper and shorter than unresolved ones; most unresolved runs are incorrect or over-specific
  implementations rather than localization failures (Sec. 5.2, p.8; Figure 8, p.8).

## What it did not establish

- No separable retrieval component. Localization is the agent's own use of `find_file`, `search_dir`, `search_file`, `open`
  and the shell, and the Linux shell stays available (Sec. 3, p.3), so a retriever cannot be swapped under a fixed agent
  inside this system. The only retrieval comparison is against the copied one-call RAG baseline with BM25 (Table 1, p.6).
- No seed: the word does not occur in the 118 pages. Decoding is stated only as temperature 0.0 or 0.2 in a sweep (Table 5,
  p.25).
- No interval or test on any comparison in Table 1 or Table 3; ablation cells are single runs on 300 instances (the six-run
  study is of the main configuration only).
- No per-instance outcome table across the six runs is given; the union figure (pass@6) is the only per-instance view.
- No contamination analysis beyond a year breakdown that shows no trend (Table 7, p.26).
- The tuning set is small (37 dev instances, Sec. B.1, p.25) and the final configuration was also shaped by reading
  trajectories by hand (Sec. 4, p.5).

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| Resolved, full test set (2,294 instances), GPT-4 Turbo: count, share; dollars | 286, 12.47%; $1.59 | Table 1, p.6; Sec. 5, p.5 |
| Resolved, Lite (300), GPT-4 Turbo: count, share; dollars | 54, 18.00%; $1.67 | Table 1, p.6; Sec. 5, p.5 |
| Resolved, full / Lite, second closed-source model (Sec. 4, p.5) | 10.46%; 13.00% | Table 1, p.6 |
| Shell-only agent on Lite, GPT-4 Turbo: with / without a demonstration | 11.00%; 7.33% | Table 1, p.6 |
| One-call RAG baseline (BM25 files) on Lite: GPT-4 Turbo / the second closed-source model | 2.67%; 4.33% | Table 1, p.6 |
| Same RAG baseline on the full test set | 1.31%; 3.79% | Table 1, p.6 |
| Lite ablations, resolved %: edit action without linting / no edit command | 15.0; 10.3 | Table 3, p.6 |
| Lite ablations: iterative search / no search tool (full interface 18.0) | 12.0; 15.7 | Table 3, p.6 |
| Lite ablations: 30-line viewer / full-file viewer | 14.3; 12.7 | Table 3, p.6 |
| Lite ablations: full history / without demonstration | 15.0; 16.3 | Table 3, p.6 |
| Six runs on Lite, resolved % per run | 17.33, 18.00, 18.00, 18.67, 17.33, 18.33 | Table 10, p.35 |
| Mean over six runs (the printed subscript 0.49 is unlabelled; the extracted text reads 17.940.49) | 17.94 | Table 10, p.35 |
| Pass@k, k = 1 to 6 | 17.94, 23.89, 27.35, 29.67, 31.33, 32.67 | Table 10, p.35 |
| Models; per-instance cost budget in dollars | gpt-4-1106-preview; the second closed-source model's dated version is on the same page; 4 | Sec. 4, p.5 |
| Search result cap; file window; observations kept in full | 50; 100; 5 | Sec. 3, pp.3-4 |
| Sweep set size; samples averaged per cell; best GPT-4 Turbo cell (temperature 0.0, window 100, last 5) | 37; 5; 15.1 | Sec. B.1, p.25; Table 5, p.25 |
| Same cell at temperature 0.2 (window 100, last 5) | 12.4 | Table 5, p.25 |
| Trajectories with at least one failed edit, full set: count, share | 1,185, 51.7% | Sec. 5.2, p.8 |
| Chance an edit eventually succeeds / after one failed edit | 90.5%; 57.2% | Sec. 5.2, p.8 |
| Resolved: median cost and steps; unresolved: mean cost and steps | $1.21 and 12; $2.52 and 21 | Sec. 5.2, p.8 |
| Resolved instances submitted before the budget ran out; all instances | 93.0%; 69.0% | Sec. 5.2, p.8 |
| Unresolved Lite trajectories classified; share incorrect or over-specific; failed-edit loops | 248; 52.0%; 23.4% | Sec. 5.2, p.8 |
| Agreement of the classifying model with the authors | 87% | Sec. 5.2, p.8 |
| File-level F1 against the gold patch: agent / BM25 with the second closed-source model | 59.05%; 45.47% | Sec. B.9, p.37 |
| Full set, GPT-4 Turbo, outcome counts: submit / cost exit with a patch / cost exit without / early exit | 1589, 630, 48, 1 | Table 13, p.38 |
| Resolved share among runs that submit / runs that hit the cost limit | 14.3%; 3.1% | Sec. B.9, p.38 |
| HumanEvalFix Python pass@1 (Table 2) / figure in the text | 87.7; 88.3 | Table 2, p.6; Sec. 5, p.5 |

## Method details we need

- **Interface (Sec. 3, pp.3-4; Sec. A, pp.16-24).** Commands `open`, `goto`, `scroll_up`, `scroll_down`, `search_file`,
  `search_dir`, `find_file`, `edit n:m`, `create`, `submit` on top of bash. Search returns at most 50 hits and otherwise asks
  for a narrower query. The edit command replaces a line range and runs a flake8 check on selected error classes; a
  failing edit is reverted and an error message with before and after views is returned (Figure 11, p.19).
- **Loop (Sec. 3, p.4; Sec. C, pp.39-44).** One thought and one command per turn (ReAct); a malformed reply gets an error
  message and a retry, and three malformed replies in a row end the episode; a demonstration trajectory and a list of tips
  are in the prompt.
- **Budget and decoding (Sec. 4, p.5; Sec. B.1, p.25).** Per-instance budget 4 dollars; on exceeding it the existing edits
  are submitted. The configuration was chosen on 37 dev instances (temperature, window, history) averaged over 5 samples.
- **Evaluation (Sec. 4, p.5; Sec. 5, p.5).** Pass@1 / % resolved on SWE-bench and Lite; cost is averaged over resolved
  instances only (Sec. 4, p.5), a convention that makes it lower than an all-instance average.
- **Release (Sec. E.2, p.117).** Code, trajectories, generations and execution traces are released.

## Implications for this project's scaffold (ADR-007, E-POWER, the claim)

Evidence class: read in full for what the paper does; inference for what it means here.

- **Why D113 rejects it holds on the paper's own evidence.** The retriever is not a swappable part of this agent (the shell
  stays open, p.3), and the loop's cost is high relative to a one-call scaffold: 1.59 to 1.67 dollars per instance on the
  resolved subset with 2024 models (Table 1, p.6) against a two-dollar arm-run estimate in `docs/RQ3_PILOT.md` for the
  project's single call at stored prices; per-instance outcomes also flip between runs (next point).
- **Run-to-run variation (an external reference for E-POWER, different scaffold).** The six-run mean carries an
  unlabelled subscript of 0.49 (so the aggregate spread is small at n = 300), but the union of six runs resolves 32.67% against a mean of 17.94% (Table 10, p.35), so
  at least 15.3 points of instances (32.67 minus the lowest single run's 17.33) resolve in some runs and not in others
  (inference; the paper gives no per-instance table). That is the paired-instance noise that k runs per arm in D113
  average over; it was measured here for a multi-turn agent at temperature 0.0 and says nothing about the project's
  single-call replies, whose repeat rate the pilot measured separately (same edits in 63% of usable pairs).
- **Temperature 0 is not deterministic for hosted models.** The dev sweep averages 5 samples per cell even at temperature
  0.0 (Table 5, p.25); this agrees with the pilot's finding and with D113's choice to run each arm more than once.
- **One-call retrieval-supplied baselines are weak in the paper's own table.** The BM25-files, whole-patch RAG baseline
  resolves 2.67% and 4.33% of Lite with 2024 models (Table 1, p.6). That is a different prompt format and weaker models
  than the project's candidates, so it is not a forecast; it is relevant to the ADR-007 revisit condition (a rate near
  zero on the held-out slice would send the decision back).
- **Change suggested, none made.** None to D113.

## Relation to RQ1 / RQ2 / RQ3

- RQ1: lexical search tools with a hard result cap are the agent's only retrieval; the Lite ablation without a search tool
  loses 2.3 points and iterative search loses 6.0 (Table 3, p.6), one run each.
- RQ2: nothing on supervision.
- RQ3: names the agent family that ADR-007 rejects; supplies the six-run variation reference and the no-interval ablation
  pattern. It contains no retriever swap with a fixed agent.

## Discrepancies

- **Internal:** the text gives HumanEvalFix pass@1 as 88.3% (Sec. 5, p.5) and the abstract 87.7% (p.1); Table 2 (p.6) lists
  87.7, 89.7 and 87.9 for Python, JS and Java. The abstract's figure is the Python column.
- **Cost definition:** averaged over resolved instances only (Sec. 4, p.5), so the paper's Table 1 dollar column is not an
  all-instance cost; unresolved runs average 2.52 dollars against a resolved median of 1.21 (Sec. 5.2, p.8). A later paper
  (Agentless, Table 1, p.10) lists SWE-agent with GPT-4 at 2.51 dollars and 245,008 tokens, the same 18.00% but not the
  1.67 here; the cause (a different averaging set or a leaderboard re-run) is not established.
- **Against `docs/EVAL_API.md` ("SWE-agent v3: fixed source, seed/temperature support, complete trajectories, failures and
  spend caps"):** temperature is configurable and trajectories are released (Sec. E.2, p.117); a spend cap exists as the
  per-instance budget (Sec. 4, p.5); a seed is not mentioned anywhere in the paper.
- **Against `docs/EVAL_API.md` ("one replaceable retrieval tool; audit alternative shell/search paths"):** there are three
  search commands and the unrestricted shell (Sec. 3, p.3); the audit for alternative paths is needed and the paper offers
  none, since the shell grep is part of the agent's normal behaviour (Sec. 5.1, p.5).

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| README "alternative scaffold" | confirmed | Abstract, p.1 | A tool-using agent with its own interface. |
| ADR-007: "a tool loop adds variance and cost that the paired design cannot afford" | confirmed for cost, partly for variance | Table 1, p.6; Table 10, p.35 | Cost shown; per-instance flips between runs shown, aggregate spread small. |
| EVAL_API: trajectories and failure records available | confirmed | Sec. E.2, p.117; Sec. B.4, p.32 | Released; failure categories assigned by a model (87% agreement on 15 hand-labelled). |
| EVAL_API: seed support | not found | whole paper | No seed is mentioned. |
| EVAL_API: one replaceable retrieval tool | contradicted for this system | Sec. 3, p.3 | Three search commands and the shell. |
