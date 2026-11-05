# ADR-007: Agent scaffold

- **Status:** Proposed — **not decided**
- **Date opened:** 2026-10-12
- **Decide by:** end of week 2 (all ten decisions)
- **Decided by:** _pending — team_
- **Master doc:** open decision #7 (`docs/12_open_decisions.md`)
- **Affects:** RQ3, the agent integration module (not written yet)

## Context
RQ3 needs one fixed scaffold, one fixed base model, fixed temperature and seed, over the same instances, with the retriever as the only thing that changes.

## Alternatives considered
- SWE-agent
- OpenHands
- Agentless
- Custom

## Master doc's recommendation (a recommendation, not a decision)
Agentless — simplest to hold constant; complexity is a liability for a controlled study.

## Decision
_Pending — the team decides._ If work cannot wait, proceed behind a config flag marked
`provisional: ADR-007` (never in `configs/frozen/`) until the decision is made.

## Rationale
_Pending._

## Trade-offs
_Pending._

## Evidence to gather
- [ ] Whether the scaffold accepts a pluggable retriever without other changes; install and run cost on Ada.

## Related benchmarks
_None yet._

## References
See `docs/11_references.md`.

## Conditions to revisit
_Pending._

## Addenda

### 2026-10-29 — RQ3 sample-size note (Q45; evidence and a question, nothing decided)

The planned paired comparison of resolved rate has a minimum detectable effect of 4.5 to 7.75 points at n = 432 for discordance 10 to 30% (exact McNemar, power 0.8, alpha 0.05), 5.5 to 9.25 points at n = 302, and 3.25 to 5.25 points even at n = 900 (`docs/EXPERIMENTS.md`, E-POWER update of 2026-10-29; calculation, `ril/analysis/rq3_power.py`). The one published fixed-agent retrieval swap read in full reports differences of -0.6 to +1.2 points on 500 instances in one run per configuration (`paper_reported`), with a derived discordance of about 14%; effects of that size are far below the table, so a test has no power for them at any listed n. Evidence class: calculation plus one read source. Cheapest experiment that could flip the reading: one agent pilot on about 100 instances with two retrievers and two runs each, which gives the discordance and the run-to-run SD (this ADR owns the scaffold, so the pilot waits for it). The question for the engineer is whether RQ3 is a hypothesis test or an effect estimate with an interval, and the deciding number is the smallest resolved-rate difference worth reporting as positive (about 5 to 6 points or more: a test is feasible at n = 432; 3 points or less: only an estimate is).

## Addendum 2026-11-03 — stays open; input it is waiting for

Reviewed with the other nine on 2026-11-03; the status stays Proposed. **Waiting for:** the choice of the base LLM (ADR-008) and a pilot that installs and times the Agentless scaffold with a pluggable retriever (about 100 instances, two retrievers, two runs each, ADR-007 addendum of 2026-10-29); also Q45 (whether RQ3 is a test or an estimate with an interval).
