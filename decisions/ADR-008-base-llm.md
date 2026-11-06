# ADR-008: Base LLM for the agent

- **Status:** Proposed — **not decided**
- **Date opened:** 2026-10-12
- **Decide by:** end of week 2 (all ten decisions)
- **Decided by:** _pending — engineer / team (budget)_
- **Master doc:** open decision #8 (`docs/12_open_decisions.md`)
- **Affects:** RQ3 cost and reproducibility

## Context
A cost and reproducibility decision: hosted API models drift and cost money; local quantized models need Ada GPU time.

## Alternatives considered
- API model
- Local quantized model

## Master doc's recommendation (a recommendation, not a decision)
Decide on budget; if local, quantize identically across all arms.

## Decision
_Pending — the team decides._ If work cannot wait, proceed behind a config flag marked
`provisional: ADR-008` (never in `configs/frozen/`) until the decision is made.

## Rationale
_Pending._

## Trade-offs
_Pending._

## Evidence to gather
- [ ] Cost per instance estimate; GPU memory needed for the candidate local model; reproducibility at fixed temperature/seed.

## Related benchmarks
_None yet._

## References
See `docs/11_references.md`.

## Conditions to revisit
_Pending._

## Addenda
_None._

## Addendum 2026-11-03 — stays open; input it is waiting for

Reviewed with the other nine on 2026-11-03; the status stays Proposed. **Waiting for:** the engineer's dollar budget for agent runs. Without that figure the choice between a pinned hosted model and a local quantised model cannot be made (no card above 11 GB is reachable, which bounds any local model).

## Addendum 2026-11-05 — the label sheet is the human sample any model judge would be checked against

Status unchanged (Proposed). Protocol section 7, method (2), allows a model judge on a larger sample of mined pull-request pairs, to be checked against human labels. The label sheet built for the noise audit (`docs/LABEL_AUDIT.md`, entry E-LABEL-AUDIT-SHEET) is that human sample: 400 pairs, 100 read by both readers, with the three-way verdict and the second question defined there, and the same text a judge would be shown (the readers are told to decide from the sheet alone). **No judge has been chosen, run or priced**; the choice of a hosted or local judge stays inside the open question of this ADR, and a judge's agreement with these labels (percent, kappa) is the measure the scorer already reports for two readers. Evidence class: reasoned only (design); nothing has been read by anyone yet.

## Addendum 2026-11-06 — provider for the pilot (decision D104; status stays Proposed)

**Evidence (read from the provider's console on 2026-11-06; free tier, per project, not guaranteed, can change).**
Gemini 3.5 Flash Lite: 15 requests a minute, 250,000 tokens a minute, 500 requests a day. Gemini 3.6, 3.8, 3 and
2.5 Flash: 5 a minute, 250,000, 20 a day. Gemini 2.5 Flash Lite: 10, 250,000, 20. Gemma 4 26B and 31B: 30, 16,000,
14,400. Pro models: 0.

**Decision D104 (provisional; reasoned only).** The pilot uses Gemini 3.5 Flash Lite on the free tier, the exact model
string and date in every call row, because only it has a daily request limit (500) that lets a multi-call scaffold
finish about 100 instances in a few days; the 20-a-day models cannot finish one instance a day. The pilot measures
cost and variance; it is not the RQ3 result, and this ADR stays open. The declared fallback is a pinned paid
version on Tier 1 billing with a hard spend cap. Gemma 4 is not excluded by its request limit (14,400 a day) but by
its 16,000 tokens a minute: at a budget of 8,000 tokens about one call a minute, none at 16,000 (arithmetic, not
measured); it is a different model family. Adapter, limiter and tests: `ril/agent/providers/`,
`docs/RQ3_PILOT.md`.

**Cheapest flip:** the smoke run of at most three calls and the first day's rows (calls per instance, realised prompt
tokens, unusable-reply rate, 429 count); time-box one day. Not done: no call has been made.
