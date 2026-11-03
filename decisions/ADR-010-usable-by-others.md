# ADR-010: Is RIL meant to be usable by others?

- **Status:** Accepted (2026-11-03)
- **Date opened:** 2026-10-12
- **Decide by:** end of week 2 (all ten decisions)
- **Decided by:** the lead, 2026-11-03
- **Master doc:** open decision #10 (`docs/12_open_decisions.md`)
- **Affects:** Packaging, CLI, configuration (week-1 bootstrap)

## Context
A product/scope decision with no data to gather; it determines whether a CLI, install story and config surface are built.

## Alternatives considered
- Yes
- No

## Master doc's recommendation (a recommendation, not a decision)
Decide now — it changes CLI, config and packaging decisions in week 1, not week 10.

## Decision
RIL is a documented research artefact with a command-line entry for the demo configuration only. The contribution is the experiment; the benchmark licence (cc-by-nc-sa-4.0) limits what derived material can be released.

Recorded 2026-11-03; see the addendum of that date for the evidence and the conditions that reopen it.

## Rationale
See the addendum of 2026-11-03 (evidence it rests on).

## Trade-offs
See the brief (`docs/ADR_DECISION_BRIEF.md`, "Not settled") and the conditions that reopen the decision in the addendum of 2026-11-03.

## Evidence to gather
- [ ] None required; this is a scoping decision for the engineer and team.

## Related benchmarks
_None yet._

## References
See `docs/11_references.md`.

## Conditions to revisit
_Pending._

## Addenda

### 2026-10-17 — licence note
- The CORE-Bench data card states `cc-by-nc-sa-4.0` (non-commercial, share-alike). Anything derived
  from it and released alongside RIL (e.g. a held-out list with identifiers, sampled fixtures) should
  be checked against that licence. The SWE-bench Verified and Loc-Bench pages checked state no licence.

## Addendum 2026-11-03 — decision recorded (status: Accepted)

**Decision.** RIL is a documented research artefact with a command-line entry for the demo configuration only. The contribution is the experiment; the benchmark licence (cc-by-nc-sa-4.0) limits what derived material can be released.

**Decided by** the lead on 2026-11-03, on academic advice; recorded with the evidence ids it rests on. The brief (`docs/ADR_DECISION_BRIEF.md`) recommended this option and it was accepted as recommended.

**Evidence it rests on** (all exploratory or measured in this project unless stated; the Wave 5 to 8 results are dev repositories, one encoder, 100 updates): Reasoned scoping; no measurement applies. The repository already separates `configs/frozen/` from `configs/demo/`; ADR-010 addendum of 2026-10-17 (licence).

**What would reopen it:** the team wants external users; a licence check shows derived artefacts can be released; the demo configuration needs a larger surface than one command.
