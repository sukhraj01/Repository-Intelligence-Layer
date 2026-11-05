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
