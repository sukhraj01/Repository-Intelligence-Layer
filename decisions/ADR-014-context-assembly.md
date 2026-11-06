# ADR-014: Context assembly policy

- **Status:** Proposed (`provisional: D102` until the RQ3 pilots)
- **Date:** 2026-11-06
- **Decided by:** lead (design stated in the brief of 2026-11-06); the team settles it
- **Related:** `specs/assembly.md`, ADR-003 (graph role), ADR-004 (granularity), ADR-013 (CodeUnit, class-unit `source`), `docs/09_architecture.md` "Online retrieval", `docs/experiments/B.md` E-ASSEMBLY, DEV-033

## Context
Retrieval, fusion and graph expansion exist as measurement code; nothing turns a ranked list into what an agent reads.
RQ3 and the latency stages `assemble` and `end_to_end` need it. The master document fixes one property: context
assembly is byte-identical across RQ2 arms, so that the only thing RQ3 varies is retrieval. No existing ADR covers
assembly (ADR-004 covers what is retrieved, not what is shown).

## Alternatives considered
- **Rank-order first-fit with a per-unit cap, blocks ordered by file and line (chosen).** Simple, depends on nothing but
  the ranked list, the unit text and the budget; reads each file top to bottom.
- **The master document's description** ("dedupe overlapping units, order for truncation survival, attach callee
  signatures"). Adds a policy (which callee signatures, how many) that is a retrieval-like choice; not adopted (DEV-033).
- **Graph or same-file expansion inside assembly.** E-GRAPH-ROLE found no evidence that typed edges beat the same-file
  control; same-file expansion by score was level with or above the stored graph on the fused first stage. An option that is off
  by default and reported separately if used; not built.
- **Whole files instead of units.** Spends the budget on text no ranker chose; the file-level adapter of the agent apparatus
  already exists for that comparison.
- **Stop at the first unit that does not fit** instead of skipping it: loses small units that would fit; rejected.

## Decision
The policy of `specs/assembly.md`: candidates in rank order; repeated, unknown and empty units skipped; each unit's text cut at
`max_unit_tokens` (1,000, provisional); a unit that does not fit the remaining budget is skipped and the walk continues; included
blocks ordered by file path and line; every block has a header with path, lines, kind, name and retrieval rank; the finished
string is verified against the budget. Class units are shown in header form (the index keeps `full`, D25). No expansion. The
manifest records every included and skipped unit with its reason; `gold_in_context` supports the retrieval-versus-reasoning
breakdown. The budget has no default; the tokenizer is pluggable and the final agent run uses the agent model's own.

## Rationale
- *Inference:* a policy that reads only the ranked order, the text and the budget cannot differ between arms except through
  the ranked list, which is what RQ2 and RQ3 need. Ordering by file and line is for the reader (the agent), not the ranker.
- *Inference:* header form for classes avoids spending budget twice on method text that the same list may include as units.
- *Opinion:* 1,000 tokens as the unit cap: long enough for most functions, short enough that one module unit cannot take a
  small budget. Not tuned; measured only through its effect on the truncated share in E-ASSEMBLY.

## Trade-offs
- A cap cuts the tail of long functions; a gold edit in the cut part counts as present and not intact (`units_intact`).
- The approximate tokenizer is a stand-in; budgets differ from the agent's by the measured ratio.
- No callee signatures or imports: the agent sees less context per unit than a graph-aware assembler would give.
- First-fit favours small units late in the list over a large unit that was skipped; intended.

## Evidence class and the experiment that could change it
- **Evidence class:** reasoned only (policy). The measurements of E-ASSEMBLY (gold in context by budget and first stage,
  measured, exploratory) describe the policy; they do not choose it.
- **Cheapest experiment that could flip it:** E-ASSEMBLY re-run with the cap at 500 and 2,000 tokens on dev only (a few CPU
  minutes per setting on the stored cache; time-box one afternoon) shows whether the cap moves the intact share of gold units;
  an RQ3 pilot of about 100 instances (ADR-007) with the unit cap and the budget varied is the real test. Not run before settling:
  it needs the agent.

## Evidence
`docs/experiments/B.md` E-ASSEMBLY; tests `tests/unit/test_assembly*.py`; E-GRAPH-ROLE (`docs/EXPERIMENTS.md`) for the
expansion option; ADR-013 addendum of 2026-10-23 for the class-unit forms.

## Related benchmarks
Latency rows of the stages `assemble` and `end_to_end` (BM25 only) under the query-set ids `assembly-<repo>-b8000-v1`
(`results/latency/latency_log.csv`; see E-ASSEMBLY for the numbers and hardware).

## References
None read in full for this decision.

## Conditions to revisit
The agent scaffold (ADR-007) or the agent model's tokenizer (ADR-008) is chosen; an RQ3 pilot shows a gold-present failure that
a longer unit or a callee signature would have fixed; the share of truncated gold units in E-ASSEMBLY is large at the budgets
used in the pilot.

## Addenda

### 2026-11-06 evidence from E-ASSEMBLY (measured, exploratory; does not settle the policy)
- Approximate tokens are 1.22 times the count of a 0.6B embedding model's tokenizer on 200 sampled units (median 1.26, 5th to 95th percentile 1.05 to 1.59). The agent model's tokenizer is still to be used at integration time.
- Gold units included but cut by the 1,000-token cap (included minus intact, L2, units_all_nomod, matched queries): Verified-six 7.5 points at B 8,000 under BM25 (30.7 included, 23.2 intact) and 8.9 under RRF (33.1, 24.2); 9.4 and 13.6 points at B 32,000. Dev: about 2 points at both budgets. The cap therefore cuts a visible part of the gold on Verified-six (large units), which is the case the revisit condition names; the cap-500 and cap-2,000 re-run named above was not run (the brief fixed the cap as provisional).
- Verified-six L2 queries with no gold file in the context at B 8,000: 31.3% (BM25), 21.7% (RRF), repository-clustered intervals wide (6 repositories); no budget is chosen.


### 2026-11-06 decision D103: the rule for the unit-cap re-run (evidence class: reasoned; fixed before any number of the re-run exists)
- **Question.** The unit cap cuts gold units that were otherwise included (L2, B 8,000, BM25, Verified-six: 30.7% of gold units included, 23.2% intact). Which of 500, 1,000 (the current default) and 2,000 tokens (the stage's approximate count) keeps the most gold units intact?
- **Data used for the choice: dev instances only** (437 instances, 354 with both first stages). Verified-six was read once in E-ASSEMBLY and is not read again for this choice (read-once rule).
- **Metric.** For a cap, the share of gold units included intact (reading `units_all_nomod`), taken as the mean over queries on the dev queries that have both first stages, then averaged without weights over the eight cells {L2, L3} x B {8,000, 16,000} x first stage {BM25, RRF}.
- **Rule.** The selected cap is the one with the highest value of that metric; if two caps are within 1.0 point of each other at the top, the smaller of them.
- **Nothing else enters the choice.** The share of gold files in the context is reported beside the metric and is not used. B 4,000 and 32,000 are computed (same grid as E-ASSEMBLY) and reported, not used. No confidence interval enters the rule.
- **Consequence.** The default in `specs/assembly.md` changes only if the rule selects a cap other than 1,000; then the assembly version string is bumped. The setting stays `provisional: D102` either way: this re-run does not turn the cap into a tuned result for the agent.
