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
**Scaffold (D113, `provisional: ADR-007`, never in `configs/frozen/`).** Retrieval-supplied one-shot repair (edit blocks as in Agentless, no candidate selection): one prompt
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

Reviewed with the other nine on 2026-11-03; the status stays Proposed. **Waiting for:** the choice of the base LLM (ADR-008) and a pilot that installs and times the retrieval-supplied one-shot repair scaffold with a pluggable retriever (about 100 instances, two retrievers, two runs each, ADR-007 addendum of 2026-10-29); also Q45 (whether RQ3 is a test or an estimate with an interval).

## Addendum 2026-11-06 — pilot design and what the cluster can execute (decision D104; status stays Proposed)

**Decision D104 (provisional; reasoned from limits read on 2026-11-06, no call made).** The pilot scaffold is
retrieval-supplied one-shot repair (edit blocks as in Agentless): one prompt with the issue and the assembled context (the same for
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

## Addendum 2026-11-08 (second) — the five scaffold papers read in full; the scaffold as chosen against how they use it (D116; the decision is unchanged)

**Evidence class: read in full**, each from the paper's own arXiv page, PDF fetched 2026-11-08: Agentless v2 (25 pages, 29 Oct 2024), SWE-agent v3 (118 pages, 11 Nov 2024), OpenHands v3 (38 pages, 18 Apr 2025), LocAgent v2 (18 pages) and CoSIL v3 (17 pages); notes with checked quote tables in `knowledge/papers/` (`agentless-2407.01489.md`, `swe-agent-2405.15793.md`, `openhands-2407.16741.md`, `locagent-2503.09089.md`, `cosil-2503.22424.md`). The five are the scaffold table of `docs/EVAL_API.md`, which Q63 and this ADR name (the ADR lists SWE-agent, OpenHands and Agentless; the table adds LocAgent and CoSIL). LocAgent and CoSIL had checked notes from 2026-10-17; they now carry a scaffold section re-checked against freshly fetched PDFs, not a second full reading. One caveat on SWE-agent: its 70 trajectory pages were read without the repository source listings inside the observations (see the note's depth caveat).

**Does the scaffold as chosen (D113) match how the papers use it?** Partly.
- *Repair format.* Matches Agentless: SEARCH/REPLACE edit blocks, greedy decoding as the default (Agentless v2, Sec. 3.2, Sec. 4). The papers give no rule for a block that does not apply; D110's exact rule is the project's own.
- *Retry or follow-up policy.* Does not match: neither Agentless nor CoSIL's use of its repair stage has a follow-up call after an unusable reply; both sample ten candidates per location set (one greedy, nine at temperature 0.8; Agentless takes four sets, 40 patches) and select by executing LLM-chosen regression tests and a model-written reproduction test, then a majority vote. D113's up to two follow-ups are the project's addition, equal for all arms, and the label "Agentless-style" covers the edit format and the separation of retrieval from repair only.
- *Temperature.* Greedy as the first sample matches; the papers' sampled candidates at 0.8 have no counterpart (D113 repeats whole runs at temperature 0 instead, which SWE-agent's dev sweep, averaged over 5 samples at temperature 0.0, supports as necessary for hosted models).
- *Retrieval stage.* In the papers retrieval is a multi-call localization (Agentless: file ranking, folder filter, skeleton, edit locations sampled four times, plus embeddings) whose output is cut to the localized snippets with 10 lines on each side; the project supplies one assembled context under an 8,000-token budget. So the repair stage here sees more text of a different shape than in any paper.
- *SWE-agent, OpenHands (rejected).* The paper-level reasons hold: the shell stays open in both, so a retriever cannot be the only thing that changes; the loops cost about 1.6 to 1.7 dollars per Lite instance on the resolved subset (SWE-agent) and 1.72 (OpenHands); no paper in the five measures a retriever swap with a fixed agent.

**What the reading adds for power and the claim (inference).** Selection by executed tests is the largest component of Agentless (77 resolved by majority vote alone, 96 with regression and reproduction tests; Table 4), so a one-call, no-selection scaffold is a weaker repair stage and absolute resolved rates will not be comparable with published pipelines (already a scoped claim; the wording should say "one-shot repair without candidate selection"). The published fixed-repair swaps show small resolved-rate gains for large localization gains (LocAgent: +15 points of Acc@5 gives +1.6 points of Pass@1, one run; CoSIL: 14 instances of 300 between four localizers, against a reproduction spread of ten instances for the same pipeline), which the power table of D113 (4.4 to 9.7 points at N = 327) cannot see; D113's single primary contrast and intervals-only reading of the rest already follow from that.

**Proposals (evidence class: read in full for the facts, reasoned for the proposals; none is a decision; D113 is not changed).**
1. *Wording.* Replace "Agentless-style" in the report and in `docs/RQ3_PILOT.md` by "retrieval-supplied one-shot repair (edit blocks as in Agentless)", and state in the threats that no candidate selection is used. Cost: wording only. Cheapest experiment: none.
2. *A sensitivity at no extra calls.* Report the any-of-k resolved share (an instance counts when at least one of its k runs resolves) beside the mean per-arm score, labelled a sensitivity and not a test. Evidence that it moves: SWE-agent Table 10 (mean 17.94% against pass@6 of 32.67%) and Agentless Fig. 6 text (80 against an any-sample bound of 126). Cost: none beyond analysis code. Cheapest experiment: the same runs D113 already plans.
3. *If the held-out slice shows a rate near zero.* The ADR's revisit condition stands. The only retrieval-supplied one-shot baseline in the five papers (BM25 files, whole-patch generation, 2024 models) resolves 2.67 and 4.33% of Lite (SWE-agent Table 1), a different prompt format and weaker models, so it is no forecast; the graded model check decides.

**Contradictions with statements already in the project's documents** (none changes a decision; each is listed in the paper's note under Discrepancies): `docs/ADR_DECISION_BRIEF.md` ADR-007 point 4 says Agentless has "retrieval as one call" (it is several localization calls plus embedding retrieval); the wording "Agentless-style, one repair call" in D104 and D113 describes the project's scaffold, not the paper's; `docs/EVAL_API.md`'s scaffold table asks for seed support in SWE-agent (none is mentioned in the paper), a replaceable retrieval tool in SWE-agent (three search commands plus the shell), a retrieval extension and bypass policy in OpenHands (none described), whole-repair cost in LocAgent and CoSIL (localization only), and all-attempt cost in Agentless (not stated); and the first line of that section, that the five full readings were unverified, is now answered (those pages belong to the C workstream and are not edited here). Between the papers: OpenHands Table 3 lists Agentless at 27.3 on Lite, Agentless v2 reports 32.00% (OpenHands's version not stated); OpenHands Table 3 and Table 4 give 6.3 and 7.0 for the same small model; SWE-agent's cost column averages resolved instances only.

## Addendum 2026-11-08 (third) — rulings on the scaffold-paper reading: name, note headers, secondary reading (D121; D113 is not changed)

**Evidence class: read in full**, per the five notes (SWE-agent: in full except the numbered source listings inside the appendix trajectories, pp. 45 to 116; every agent turn, error message, patch and summary was read, and no claim in the project rests on those listings). Reasoned for the rulings themselves; no experiment could flip them cheaply, and none is needed (wording and an analysis column).

1. **Header of a partly read note.** The reading stands; the header now says what was and was not read: `read: in full except <part> (pp. A to B); <what was read of it> was read — N pages ...`. `scripts/check_paper_note.py` accepts and requires this form: a header that says `read: full` above a note that describes a skipped part fails, and so does a number cited from a skipped page. All other tracked notes were checked against the same rule (none skipped part of its own document; mentions of other, unread versions are not skips).
2. **Name.** The scaffold is **retrieval-supplied one-shot repair**: one repair call at temperature 0 with a fixed edit format, up to two follow-ups after an unusable reply, no candidate selection. "Agentless-style" is retired as a description of it, because the paper's pipeline localizes in several calls and samples 40 candidates that it selects by executed tests, none of which the scaffold does. "Agentless" stays wherever the paper itself is meant (citations, comparison with its pipeline); the edit-block format is credited to it. The wording in the D113 statement above, in the D104 addendum, in `docs/RQ3_PILOT.md` and in the log entry E-LIT-SCAFFOLD was replaced; the proposal quoted in the addendum of 2026-11-08 (second) keeps the old phrase because it quotes it. Ids, entry names and file paths are unchanged.
3. **Secondary reading.** The RQ3 analysis reports the any-of-k resolved share (an instance counts if at least one of its k runs resolves) beside the mean resolved fraction for every arm, and the paired difference of that share beside each contrast, at no extra calls, labelled secondary and exploratory, with bootstrap intervals and no test. The primary contrast of D113 (RAW against the untrained encoder, mean fraction, paired bootstrap and sign-flip) is unchanged. Code: `ril/analysis/rq3_results.py`, tests on synthetic rows. The RQ2 analysis does not share that code, so its scope is unchanged.
4. **Unexplained difference.** OpenHands Table 3 lists Agentless at 27.3 on Lite, Agentless v2 reports 32.00%. The difference is unexplained: OpenHands does not say which version its row comes from and no earlier version of Agentless was read. No reason is offered here or in the notes.

**Trade-offs.** The longer name costs words; it states the claim's scope in the term itself, which the report's limitation (one-shot repair without candidate selection) needs anyway. The any-of-k share can be read as a capability claim; the label and the absence of a test are the guard.

**Conditions to revisit.** If a version of Agentless before v2 is read and explains the 4.7-point difference, record it in the notes. If the graded model check shows a near-zero rate, the revisit condition of D113 applies as before.

## Addendum (2026-11-12, D152): the form of a trained arm

**Context.** D150 built the trained arm as the retained model's scores alone, beside the untrained encoder's `dense` arm, and left the form open as Q74.

**Decision (provisional, with D150).** A trained arm is RRF of the stored BM25 scores and the model's scores, at the constant and assembly of the untrained `rrf` arm (the frozen RQ3 context configuration); the comparator of every trained arm is the untrained `rrf` arm. Reason: the frozen configuration fuses BM25 and dense, and a trained arm that used its scores alone would change the fusion structure as well as the retriever, so a difference could not be attributed to the training supervision. Evidence class: reasoned (the contrast's definition), with an equality test in code (a model with the untrained scores reproduces the untrained arm's contexts and prompts byte for byte). The cheapest experiment that could flip it: build the dense-only contexts of one model beside the fused ones and compare overlap (CPU, no calls); not run, because the choice follows from what the contrast must hold fixed.

**Trade-offs.** The fused form needs the stored BM25 scores for the 377 (they exist with the instance caches); the dense-only form is not built for trained arms. The earlier statement that the primary pair compares with the arm `dense` is superseded: the pair compares with `rrf`.

**Conditions to revisit.** If the lead wants the dense component's effect alone, a dense-only trained arm is one more `Arm` in the same builder (no new stage), with the untrained `dense` arm as its comparator.

**Addendum (2026-11-14).** The SWE-agent note's exception is narrowed: pages 45 to 71 of its appendix trajectories were read in full on a re-read of the stored PDF, and only the numbered source-code listing lines of pages 72 to 116 remain unread; nothing in the project rests on them. The Agentless and OpenHands notes were re-read in full as well, with no change to the rulings above.
