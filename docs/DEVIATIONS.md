# Deviations from the Master Project Document

Append-only. Every place this repository departs from the master doc (rev 16, 2026-10-11) gets an
entry **before the code lands**, with a rationale. The master doc is the plan; this file is the
audit trail of where reality forced a change. Departures from *published* recipes (SweRank,
CoRNStack, LocAgent, CORE-Bench) are recorded here too.

Entry format:

```
## DEV-NNN — <short title>        (date · status: proposed | accepted | reverted)
- Master says: <quote or section>
- We do:       <what we do instead>
- Why:         <evidence, not preference>
- Impact:      <which RQ / result / claim this touches; does it change what is controlled?>
- Reversible:  <yes/no, and cost>
- Related:     ADR-0NN
```

A deviation that changes **what an experiment measures or what is held identical** needs an ADR and
engineer sign-off — it is a design decision.

---

*No deviations yet.*
