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

## Addendum 2026-11-06 (second) — terms of use of the unpaid quota

**Evidence class: read on the provider's terms page on 2026-11-06.** For the unpaid Gemini API quota the terms say
submitted content and responses may be used to improve the provider's products and may be read by human reviewers
(disconnected from the account, key and project), and advise not to submit sensitive, confidential or personal
information. **Decision:** the pilot submits public repository text only; a prompt-preparation test rejects a home
directory path, an unreviewed e-mail address or a credential-shaped string (`docs/RQ3_PILOT.md`, "Terms of use"). The
terms are a second reason, beside the limits, for the declared paid fallback (a pinned version on billed use, whose
terms differ and are to be read before use).

## Addendum 2026-11-08 — model-choice rule, spend guard, stored prices (D112, D114; status stays Proposed)

**Evidence class: reasoned (the rule); prices are unverified third-party figures read on 2026-11-08, tokens per unit are measured in the pilot.** The model is chosen on graded results from a held-out slice of 50 executable instances (D111), by a rule fixed before any model call: candidates are the cheapest model that can plausibly work and the next one or two stronger models on the same API; each runs the RRF 8,000-token arm once, temperature 0, same prompt, same follow-up policy and same thinking configuration (recorded, with the thought tokens billed); the cheapest candidate whose resolved rate on the slice is at least 15% is chosen; if none reaches 15% the strongest is taken and the floor is reported as not met, so the resolved-rate contrast is reported as low-power and the retrieval-side readings carry the weight. No other selection on resolved results is allowed (`ril/agent/providers/model_choice.py`). The 15% floor is the resolved rate at which a discordance of 10% or more between arms is attainable at N = 327. The driver keeps its own running cost at the stored dated prices (`configs/agent/prices.yaml`, `verified: false`), refuses to start without a cap, and stops before a call whose worst case would pass it (D114); the provider-side hard cap is the engineer's second layer. Cost model: `results/rq3_driver/rq3_cost_model.csv` (one arm-run of 327 about 2 dollars on the cheapest candidate at the stored prices, estimated). **Not decided:** the model, the dollar budget; the selection is run by the engineer's graded check. A third candidate has no stored price.

## Addendum 2026-11-12 — the check spans two providers; capability first, cost as a constraint (D155; status stays Proposed)

**Evidence class: reasoned (the rule); nothing measured, no price or resolved rate stored.** The candidates are `gemini-3.5-flash-lite`, `gemini-3.8-flash` and two models of a second provider (closed; strings in the lead's local limits file). The rule replaces the cheapest-first selection of D112: discard a candidate whose projected whole-study cost exceeds the budget B (150 USD unless the limits file says otherwise) or whose resolved fraction on the 50 held-out instances is below 15%; take the highest resolved count of the rest; candidates within 2 instances of it are indistinguishable and the cheaper is taken. Prices come from each provider's own page, written by the lead into the limits file at run time. The instrument is the same across providers; thinking is pinned per candidate at the lowest fixed setting the scaffold works with. Alternatives not taken: keep cheapest-first (rejected by the lead: capability matters for a model that is widely used for repair); add a larger flagship model (whole-study cost beyond any reasonable budget). Cheapest flip: the check itself. Text, pushback and tests: `docs/RQ3_PILOT.md` ("Model check across providers"), `docs/experiments/B.md` E-RQ3-MODEL-CHECK-PLAN.
