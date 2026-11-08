# ADR-007: Agent scaffold

- **Status:** Accepted, `provisional` (D113, 2026-11-08; settled by the engineer, reasoned, not yet measured on graded replies)
- **Date opened:** 2026-10-12
- **Decide by:** end of week 2 (all ten decisions)
- **Decided by:** engineer (2026-11-08), provisional until the graded model check (D112)
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
**Scaffold (D113, `provisional: ADR-007`, never in `configs/frozen/`).** Retrieval-supplied, Agentless-style: one prompt
with the issue and the assembled context (byte-identical text before the excerpts for every arm), one repair call at
temperature 0, up to two follow-ups for an unusable reply (same for all arms), edit blocks applied under D110. The
retriever is the only thing that changes between arms. Unit of analysis, number of runs, the one primary contrast and
the statistics are fixed in `docs/RQ3_PILOT.md` ("Driver, held-out slice and analysis plan"). Q45 is answered by that plan.
The scaffold is not a tool-using agent; this is a scope statement for the claim (a retrieval-supplied one-shot repair),
not only a design choice. Rejected for now: SWE-agent and OpenHands (a tool loop adds variance and cost that the
paired design cannot afford on the free or a capped paid tier); revisit if the resolved rate under this scaffold is near
zero on the held-out slice for every candidate model.

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

## Addendum 2026-11-06 — pilot design and what the cluster can execute (decision D104; status stays Proposed)

**Decision D104 (provisional; reasoned from limits read on 2026-11-06, no call made).** The pilot scaffold is
Agentless-style with retrieval supplied: one prompt with the issue and the assembled context (the same for
every arm, ADR-014), one repair call at temperature 0 asking for edits in a fixed format, up to two follow-ups
after an unusable reply; expected 1 to 3 calls per instance. About 100 instances, two first stages, two runs
each. Full text, flip experiment and open points: `docs/RQ3_PILOT.md`.

**Evidence (measured, account A, 2026-11-06; `results/rq3_pilot/part_a/`).** No container runtime is usable by the
engineer on the cluster (no runtime on the PATH; the listed container module's directory is absent from the
nodes; extracted node-locally it builds an image but cannot run it because user namespaces are disabled).
Without a container, an environment per (repository, version) can be built with `uv` and the benchmark
package's own install specification for 263 of the 500 Verified instances; 143 need a Python older than 3.8, 59
a pre-install step, 35 `apt-get`. The gold patch passes its FAIL_TO_PASS tests on requests-6028,
seaborn-3187 and xarray-7393 (1 to 5 minutes and under 0.3 GB each); the specification leaves pytest unpinned,
so a flask instance failed until pytest was pinned below 8. PASS_TO_PASS was not checked. What this does to the
choice of scaffold: none; it bears on whether resolved rate can be measured on the cluster (options in
`docs/RQ3_PILOT.md`, none chosen).

**Cheapest flip, still open:** the pilot itself (calls per instance, unusable-reply rate, run-to-run
agreement); it needs the engineer's key file.

## Addendum 2026-11-08 — scaffold accepted `provisional`; driver and analysis plan (D111 to D114)

**Evidence class: reasoned (design), pipeline checks measured on gold-derived and deliberately broken edits.** The
engineer settled the scaffold as piloted (D113). What changed in the record: the status above; the analysis plan (one
primary contrast, RAW against the untrained encoder, paired bootstrap interval and sign-flip permutation test over
instances on the 327 confirmatory instances; k runs per arm, an instance's score the fraction of its runs that resolve);
a held-out slice of 50 executable instances reserved for the model check and kept out of every confirmatory analysis
(D111); the driver and its replay test (`ril/agent/providers/driver.py`, E-RQ3-DRIVER); a power table with run-to-run
noise (minimum detectable difference 4.4 to 9.7 points at N = 327, k = 1 to 3, scenario assumptions listed beside it).
**Cheapest flip:** the graded model check on the held-out slice (time-box: one day of calendar time); if every
candidate model resolves under 5% there, the scaffold, not only the model, is the thing to change.
