read: full — 25 pages incl. appendices, PDF v2, pdftotext -layout (poppler); re-read in full from the stored PDF (SHA-256 1675c2dcd5ecaef47e8a4356062f60be642cee82e1bbacb044c9d047dce4c856), first read 2026-11-08, 2026-11-14

# Agentless — Xia, Deng, Dunn, Zhang (arXiv 2407.01489v2, 29 Oct 2024)

Re-read 2026-11-14 from the stored PDF: body and appendices read page by page; the reference list (pp. 19 to 25) was checked for the entries the text cites rather than read entry by entry.

Source: https://arxiv.org/abs/2407.01489, PDF https://arxiv.org/pdf/2407.01489v2 (v2 is the latest version; v1 has 17 pages and is
not used), retrieved 2026-11-08. The PDF has 25 pages (body 19 pages, references pp.19-25, no appendix); the extracted text has
25 pages and no blank page (`scripts/check_paper_note.py`). Every page was read. Figures 6 and 7 (p.14) were rendered and
looked at; their plotted points carry no printed numbers beyond those in the surrounding text, so only text values are quoted.
Figure 5 (a Venn diagram of fixed issues, p.11) was read from the page text and is not quoted.

## What it established

- A three-phase pipeline for issue resolution with no tool loop: hierarchical localization (files, then classes and
  functions, then edit locations), repair that samples edits in a search/replace block format, and patch selection by
  regression tests, a generated reproduction test and majority vote (Sec. 3, pp.5-9; Figure 1, p.5).
- With GPT-4o it resolves 96 of 300 SWE-bench Lite instances at 0.70 dollars each, the highest among the open-source
  entries of its own Table 1, whose other rows are copied from leaderboards or papers (Table 1, p.10).
- Within the pipeline each stage is ablated: file localization by prompt, by embeddings, and combined (Table 2, p.12);
  repair by how edit locations are sampled (Table 3, p.13); selection by test type (Table 4, p.14).
- A manual classification of the 300 Lite problems finds exact patches, missing information and misleading solutions in
  the issue text, from which the authors build a 249-problem subset, Lite-S (Sec. 6.1-6.2, pp.15-17).
- The same pipeline resolves 194 of 500 SWE-bench Verified instances (Table 6, p.18).

## What it did not establish

- No run-to-run variance: every table cell is one run; the words seed, variance, confidence and standard deviation do not
  occur. The default decoding is greedy but 39 of the 40 patches per issue are sampled, so the pipeline is stochastic and
  its end-to-end spread is never measured (Sec. 4, p.9). A later paper re-ran it and obtained 86 against the published
  96 resolved (CoSIL note, Table IX, p.10).
- No retrieval swap measured by resolved rate. The localization ablation (Table 2, p.12) reports whether the ground-truth
  location is contained, not whether the issue is resolved; the only resolved-rate ablation near retrieval is the way
  edit locations are sampled for repair (Table 3, p.13).
- No policy for an edit that does not apply: the paper says the search text is matched and replaced and gives no handling
  for a miss, a repeated match or a malformed block (Sec. 3.2, pp.7-8). No follow-up or retry call exists in it.
- No cost definition: "average inference cost" (Sec. 4, p.10) is not said to include every sampled attempt, the
  reproduction-test generation, or the localization stage; the stage costs in Tables 2 to 4 are separate columns.
- No statistics beyond counts and percentages; no repository-clustered view; the per-repository split is absent.
- Contamination of GPT-4o with the benchmark is acknowledged and not measured (Sec. 7, p.18).

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| Resolved, Lite (300), GPT-4o: count, share, dollars, tokens per instance | 96, 32.00%, $0.70, 78,166 | Table 1, p.10 |
| Resolved, Lite-S (249 problems), same system: count, share | 84, 33.73% | Table 5, p.17 |
| Resolved, Verified (500), same system: count, share | 194, 38.80% | Table 6, p.18 |
| Size of Lite and of Lite-S | 300; 249 | Sec. 4, p.9; Sec. 6.2, p.16 |
| Copied baselines on Lite: SWE-agent with a closed-source model, count, share, dollars | 69, 23.00%, $1.62 | Table 1, p.10 |
| Copied baselines on Lite: RAG with BM25 files, two models, count | 13; 8 | Table 1, p.10 |
| Model and decoding: model string; sampling temperature | gpt-4o-2024-05-13; 0.8 | Sec. 4, p.9 |
| Embedding model, chunk size, overlap | text-embedding-3-small; 512; 0 | Sec. 4, p.9 |
| Files localized per issue; location sets sampled; context lines around a location | 3; 4; 10 | Sec. 4, p.9 |
| Patches per location set (1 greedy, 9 sampled); patches per issue; reproduction-test samples | 10; 40; 40 | Sec. 4, p.9 |
| If the benchmark's own regression-test list were used directly, resolved on Lite | 98 | Sec. 4, footnote 1, p.9 |
| File-level localization, ground truth contained: prompt / embedding without folder filter / embedding with filter / combined | 78.67% / 67.67% / 70.33% / 81.67% | Table 2, p.12 |
| Repair by edit-location handling, resolved: greedy location / merged samples / four sampled sets | 88 / 85 / 96 | Table 3, p.13 |
| Same, dollars: greedy / merged / four sampled sets | $0.22 / $0.24 / $0.29 | Table 3, p.13 |
| Selection, resolved: majority vote only / plus regression tests / plus reproduction test | 77 / 81 / 96 | Table 4, p.14 |
| Selection cost, dollars: majority / plus regression / plus reproduction | $0.00 / $0.01 / $0.25 | Table 4, p.14 |
| One greedy sample per location set (four samples) already fixes | 80 | Sec. 5.2.2, p.14 |
| Upper bound if any of all patch samples counts (count, share) | 126, 42.0% | Sec. 5.2.2, p.14 |
| With one reproduction test per issue, resolved | 90 | Sec. 5.2.3, p.14 |
| Reproduction tests that print the issue message on the original repository; of those, that also pass the gold patch | 213; 94 | Sec. 5.1.3, pp.11-12 |
| Lite problems with the exact patch in the issue / not enough information / misleading solution | 4.3% / 10.0% / 5.0% | Sec. 1, p.3 |
| Copied baseline on Verified (500): SWE-agent with a closed-source model, count, share | 168, 33.60% | Table 6, p.18 |

## Method details we need

- **Localization (Sec. 3.1, pp.6-7).** Step 1: the issue and a `tree`-style repository listing go to the LLM, which ranks the
  top N suspicious files; independently the LLM names irrelevant folders, the remaining files are chunked and embedded,
  and files are ranked by cosine similarity to the issue; the two lists are merged by taking the files common to both.
  Step 2: a skeleton of each file (class and function headers, signatures only, comments) goes to the LLM, which lists
  classes and functions to inspect. Step 3: the code of those elements goes to the LLM, which picks edit locations (lines,
  functions or classes). All greedy except the edit-location step, which is sampled four times.
- **Repair (Sec. 3.2, pp.7-8).** A window of the location plus 10 lines each side is the context; several locations are
  concatenated with "..." between them. The model returns SEARCH/REPLACE blocks (the format of an earlier tool, cited
  as [37]); the search text is matched in the file and replaced. Greedy first, then temperature 0.8.
- **Validation (Sec. 3.3, pp.8-9).** The LLM writes a reproduction test that prints "Issue reproduced" or "Issue resolved";
  tests that do not reproduce the issue on the original code are dropped; the most frequent normalised test is kept.
  Existing passing tests are listed and the LLM removes those that the fix may legitimately change (the benchmark's own
  PASS_TO_PASS list is not used, at the benchmark maintainers' request); patches are filtered by fewest regression
  failures, then by the reproduction test, then majority vote over AST-normalised patches (docstrings dropped).
- **Evaluation (Sec. 4, pp.9-10).** The benchmark's evaluation setup was modified so that arbitrary regression and
  reproduction tests can be executed; metrics are % resolved, average dollars, average tokens, and % correct location at
  line, function and file level. Baseline rows come from the leaderboard or the tools' papers (Table 1, p.10).

## Implications for this project's scaffold (ADR-007, E-POWER, the claim)

Evidence class: read in full for what the paper does; inference for what it means here.

- **What the project's scaffold shares.** A repair stage that is separate from retrieval; SEARCH/REPLACE edit blocks;
  greedy decoding as the default. The paper itself treats localization as a stage whose output feeds repair, so
  "retrieval supplied" is a faithful reading of the pipeline's shape, with the project's retriever in place of the paper's
  localization.
- **What it does not share (the project's former label "Agentless-style", retired in favour of "retrieval-supplied one-shot repair", covered only the repair half).** The paper's repair context is
  the localized snippets with 10 lines each side (p.9); the project passes an assembled context of ranked units under an
  8,000-token budget (`docs/RQ3_PILOT.md`). The paper samples 40 candidates and selects by executing tests (pp.8-9);
  the project makes one call per run and executes nothing before grading. The paper has no follow-up call; D113's up to
  two follow-ups for an unusable reply are the project's own addition and are applied equally to every arm.
- **Cost of dropping selection.** Selection is the largest single contributor in the paper: 77 resolved by majority voting
  alone against 96 with regression and reproduction tests (Table 4, p.14), and four greedy samples give 80 (p.14). A
  one-call, no-selection scaffold is therefore a weaker repair stage than the paper's, and its absolute resolved rates
  are not comparable with Table 1. This does not break the paired contrast between retrievers (the repair stage is the
  same for every arm), but it bounds the claim: a retriever difference measured under a weak repair stage may be
  smaller or larger under a strong one (stated limitation, nothing measured).
- **Power.** The paper's own single-run ablations differ by up to 11 instances of 300 (88 / 85 / 96, Table 3, p.13) and
  carry no interval, so differences of a few points between pipeline variants in the literature are not evidence of
  effect sizes for E-POWER.
- **Change suggested, none made.** None to D113 (see the ADR-007 addendum of 2026-11-08, second entry).

## Relation to RQ1 / RQ2 / RQ3

- RQ1: a lexical-plus-embedding localization recipe with a measured containment rate (Table 2, p.12); no latency, no
  fusion rule (files common to two lists), no per-signal resolved-rate ablation.
- RQ2: nothing on retriever supervision; the embedding model is an off-the-shelf API model.
- RQ3: the scaffold family named in ADR-007; the paper contains no retriever swap under a fixed repair stage, so it
  supplies no precedent for the size of a resolved-rate effect.

## Discrepancies

- **Against OpenHands (read in full, Table 3, p.7):** that paper lists Agentless with GPT-4o at 27.3 on Lite; this paper
  (v2) says 96 of 300 = 32.00% (Table 1, p.10). The two differ by 4.7 points. The difference is unexplained: OpenHands does not state which version of Agentless its
  row comes from, and no earlier version of Agentless was read (v1 is 17 pages).
- **Against the project's decision brief:** it says Agentless has "retrieval as one call" (`docs/ADR_DECISION_BRIEF.md`,
  ADR-007 recommendation). In the paper localization is several calls: a file-ranking prompt, an irrelevant-folder prompt,
  a skeleton prompt, an edit-location prompt sampled four times, plus embedding retrieval (Sec. 3.1, pp.6-7).
- **Against the project's former wording "Agentless-style, one repair call" (retired):** the paper's repair stage makes 40 calls per issue
  and selects among them (Sec. 4, p.9).
- Internal: Table 2's edit-location rows list four unlabelled "Multi-samples" values (49.67, 49.33, 49.33, 48.33 percent, one per
  sampled location set) under one label; only the named rows are quoted here.

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| README "Candidate agent scaffold (ADR-007)" | confirmed | Abstract, p.1 | Pipeline without agent decisions; see Implications for how much of it the project uses. |
| Master: "simplest to hold constant; complexity is a liability" (ADR-007) | partly confirmed | Sec. 3, pp.5-9; Sec. 4, p.9 | No tool loop, but the default configuration runs 40 repair samples and 40 reproduction-test samples with test execution; 78,166 tokens per instance (Table 1, p.10). |
| Brief: "retrieval as one call" | contradicted | Sec. 3.1, pp.6-7 | Several localization calls plus embedding retrieval. |
| EVAL_API: "fixed sampling/selection policy; all-attempt cost" | partly confirmed | Sec. 4, p.9; Tables 3-4, pp.13-14 | Sampling and selection policy stated; whether the average cost covers every attempt is not stated. |
| D113: one repair call at temperature 0 with follow-ups | not found | Sec. 3.2, pp.7-8 | The paper has neither follow-ups nor a single-call setting; greedy is the first of several samples. |
| OpenHands Table 3: Agentless 27.3 on Lite | contradicted for v2 | Table 1, p.10 | v2 reports 32.00%. |
