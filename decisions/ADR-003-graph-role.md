# ADR-003: Graph role: retrieval signal vs agent tool

- **Status:** Proposed — **not decided**
- **Date opened:** 2026-10-12
- **Decide by:** end of week 2 (all ten decisions)
- **Decided by:** _pending — team_
- **Master doc:** open decision #3 (`docs/12_open_decisions.md`)
- **Affects:** `ril/retrieval/hybrid_retriever.py`, RQ1, the graph extension, agent integration

## Context
LocAgent uses the graph as a tool the agent calls; RIL's design uses it as a signal (struct(u) = γ^dist(ℓ,u), γ ≈ 0.5, then possibly personalized PageRank). These are different systems with different latency profiles. Pick deliberately; do not drift between them.

## Alternatives considered
- Retrieval signal (hop-decay score fused with BM25 and dense)
- Agent tool (LocAgent-style TraverseGraph)

## Master doc's recommendation (a recommendation, not a decision)
Signal — matches RIL's architecture and keeps latency predictable.

## Decision
_Pending — the team decides._ If work cannot wait, proceed behind a config flag marked
`provisional: ADR-003` (never in `configs/frozen/`) until the decision is made.

## Rationale
_Pending._

## Trade-offs
_Pending._

## Evidence to gather
- [ ] Measured latency of graph expansion (2 hops) on a real repository.
- [ ] Edge-recovery coverage from `specs/parse_one_repo.md` (static Python call graphs are incomplete).

## Related benchmarks
_None yet._

## References
See `docs/11_references.md`.

## Conditions to revisit
_Pending._

## Addenda

## Addendum 2026-10-17 — what the CodeUnit holds for relations (decision D4, context only)

Decision D4 (`specs/code_unit.md`) does not choose the graph's role. It fixes that relations live in
a separate typed edge store and that the CodeUnit lists `calls`, `called_by`, `tests` and `configs`
are projections of resolved ids only, so that signal-or-tool (this ADR) and the edge taxonomy
(ADR-011) stay open. Experiment that could flip D4: the resolution coverage measured in the first
parse and graph build.

## Addendum 2026-10-17 — what the graph design adds (context only; no decision)

`docs/GRAPH_DESIGN.md` (section 4) describes three roles with the experiment that would show the value
of each, a latency profile for each, and what each needs from the schema. Section 9 lists nine
questions for this ADR; the first four are: which role or roles are in the frozen configuration; how a
graph signal enters a fusion stack fixed to rank-based RRF; whether graph-derived supervision belongs to
RQ2; whether an agent-tool variant belongs to RQ3, which holds the agent fixed. None is answered
there. Evidence still to gather for this ADR: the per-status coverage and the 1- and 2-hop expansion
latency from the first graph build, and pilots M and E3.

## Addendum 2026-10-17 — pilot M: how near L3 positives lie to L2 positives in the graph (evidence only; no choice made)

Exploratory pilot, three repositories, 7 instances, 126 new Python L3 positives (`docs/EXPERIMENTS.md` E-GRAPH-REACH).
Seeds were the gold L2 units, so this bounds what a perfect first stage could seed; it does not measure retrieval.

- Hop distance from the L2 units over the five core families: 88% of new L3 positives within three hops, but a
  random set of units from the same files reaches 78%, and random units of the same kind from the whole repository
  50%. Most of the nearness is file and directory locality.
- Excess over the same-file chance, within three hops: resolved call edges (both directions) +13 points (95%
  bootstrap over positives +6 to +20; over the 7 instances +5 to +27), +5 points at one hop (ratio 1.8); `contain`
  and `import` add nothing over same-file chance; `inherit` reaches 5 of 126; exploratory `tests`, `configures` and
  `co_change` add nothing measurable. Heterogeneous across repositories: the call-edge excess is present in flask
  and requests and absent in seaborn.
- Bearing on the role of the graph (A signal, B training structure, C agent tool): for A, the locality that carries
  most of the reach is also reachable without a graph (same file, same directory); the part only the graph
  provides here is the call-edge excess. For B, 12 of 141 L3 positives are text-identical to an L2 positive and
  7% are test units, which is the scale of "test positives" a graph-derived supervision could add. Evidence class:
  measured, n small; the controlled retrieval-level test is pilot E3.
- Cheapest experiment that could flip an inference from this: E3 (hop-decay expansion from retrieved, not gold,
  seeds against a size-matched random expansion). Conditions to revisit: resolver recall (ADR-012 definitions), more
  repositories (including the non-Verified L3 folders once base commits are obtained).

## Addendum 2026-10-18 — pilots E3 to E5: graph expansion from retrieved seeds (evidence only; no choice made)

Exploratory pilots (`docs/EXPERIMENTS.md` E-GRAPH-SIGNAL, E-GRAPH-WEIGHTS, E-RECENCY): BM25 over the units of the snapshot, hop-decay expansion from the top-C retrieved units
(not gold), compared with BM25 alone and with size-matched random expansions, sweeps on five non-Verified repositories (508 queries), one dev-chosen setting confirmed on six Verified
repositories (83 L2, 55 L3 queries). Evidence class: measured, small samples.

- Role A (retrieval-time signal): expansion over the core families improves BM25 on the dev repositories (L3 Recall@100 +11.9 [+9.6, +14.4], L2 nDCG@10 +1.8 [+1.0, +2.6]); against random
  units of the seeds' files the gain is +5.1 [+2.7, +7.5] and +2.0 [+1.2, +2.9]. On the Verified six the gain over BM25 is +4.4 [+1.1, +8.1] (L3) and 0.0 [-1.4, +1.6] (L2) and is not
  distinguishable from same-file chance. So a graph signal helps a lexical first stage at L3 on these data; whether it helps a dense first stage is untested (E6 not run, Q42).
- Which edges: containment carries most of it (alone +4.3 [+3.2, +5.4] nDCG@10 over same-file chance at L2; leaving it out of all families costs 4.2 [2.7, 5.9] Recall@100 at L3 on dev and
  3.4 [1.5, 5.8] on Verified); call edges add at L3 on dev only; imports, inheritance, tests, configuration and co-change add nothing or hurt. Part of the L3 containment gain is the module unit of a
  file entering the list (without module units in the gold set it is +1.2 [-0.4, +2.8] over same-file chance).
- Entry into a rank-fused stack (Q30): the edited list and the ranked list fused by reciprocal rank give the same L3 Recall@100 and a smaller L2 nDCG@10 gain for the fused form (contain +1.9 against +4.1 on
  dev); neither was chosen.
- Role B (training structure): fitted family weights favour containment and do not change L3; no evidence on supervision was gathered.
- Cheapest experiment that could flip an inference: a fixed-length budget arm and a dense first stage (E6 on a GPU), 1 to 2 hours on Ada once a GPU run is allowed. Conditions to revisit: resolver recall (ADR-012),
  more non-Verified Python repositories with base commits.

## Addendum 2026-10-23 — engineer decisions D14, D18, D19 and D24 of 2026-10-18 as they bear on the graph role (this ADR stays Proposed)

- **D14 (closes Q24): wording.** The master statement that tests and configuration are "covered by nobody" is replaced in
  project text by "no ablation shows the value of test and configuration links" (DEV-006: LARGER builds such links but
  reports no ablation of them). Evidence class: read in full. Flip: a published ablation of test or configuration links.
- **D18: gold for graph decisions.** Design decisions about the graph use the gold without module-residual positives,
  with the CORE-Bench-faithful reading beside it (ADR-004 addendum). Under it the L3 containment gain of pilot E3 is not
  distinguishable from same-file chance.
- **D19: families.** The first stored graph holds `contain`, `invoke`, `import`, `inherit`, `override`; the exploratory
  families are built but off by default (ADR-011 addendum). A training-time use (E-PILOT-L3POS) is the test that could
  bring them back.
- **D24: the role itself (Q30) is not decided in advance.** It is settled by measurement on a dense and a fused first stage:
  the graph as a third ranked list in reciprocal-rank fusion, the edited candidate list, and score-level fusion with weights
  tuned on dev, against the same-file and whole-snapshot chance controls, one pre-stated setting confirmed on Verified.
  Answered pushback from the previous wave: a hop-decay score cannot enter rank fusion as written, hence the three forms;
  structural negatives stay outside the four RQ2 arms (they would break "only supervision varies") and are a separate pilot
  factor with the negative policy held identical across arms.

## Addendum 2026-10-23 — the pilot-E3 headline under decision D18 (evidence only; no choice made)

- Re-read with D18's primary gold (`units_all_nomod`) and the class form and ambiguous-site policy that the stated dev rules kept
  (`full`, `drop`; `docs/EXPERIMENTS.md`, section of 2026-10-23; rows `x1-headline-*`). Containment still carries the signal and is
  clearer on Verified: above same-file chance at L2 on dev and Verified (+3.4 [+2.5, +4.5], +4.4 [+2.6, +6.3]) and at L3 on Verified
  (+4.0 [+0.5, +7.9]; clustered interval [-0.3, +6.3]); at dev L3 at the edge (+1.6 [+0.0, +3.1]). `core` and `all` remain not
  distinguishable from same-file chance at L3 on Verified; without containment nothing is above that chance at L3. Gains over BM25 at
  L2 are smaller than pilot E3 stated (dev `contain` +2.4 rather than +4.1) because BM25 is higher under this gold (21.2 rather than
  15.8). Reading ambiguous call sites as edges does not help expansion (ADR-011 addendum of today).
- Evidence class: measured (exploratory; one stated setting on six Verified repositories, wide clustered intervals).

## Addendum 2026-10-25 — the graph on a dense, fused first stage (E-DENSE-FUSION; evidence only, no choice made)

What changed relative to the BM25-only pilots (`docs/EXPERIMENTS.md`, E-DENSE-FUSION; rows `x2-graph-*`; gold
`units_all_nomod`):

- **The first stage moved.** The graph now sits on RRF(BM25, Qwen3-Embedding-0.6B, k 20), the strongest first stage
  on dev (28.3 L2 nDCG@10, 47.1 L3 Recall@100 against BM25's 21.2 / 37.5). Seeds are its top units.
- **The three forms of D24 give the same answer.** On dev the best core cells of the edited list (+1.4 / +10.7),
  the graph as a third RRF list (+1.5 / +9.9) and score-level fusion with tuned weight (+1.9 / +10.7) overlap; the
  form a rank-fusion stack can take (third RRF list) loses nothing measurable against the others. The stated dev rule
  picked score level (C 5, gamma 0.7, 2 hops, weight 0.5, the edge of the weight grid).
- **The L3 gain survives a stronger first stage; the L2 gain mostly does not.** Verified-six, stated cell, core:
  +0.2 [-1.8, +2.2] at L2 and +4.4 [+0.5, +8.8] at L3 over the first stage, +11.4 over whole-snapshot chance.
- **The same-file question is unchanged.** Over the same-file control the Verified L3 gain is +1.4 [-2.3, +5.1]
  (not distinguishable; dev +2.5 [+0.2, +4.5] with two L3 repositories). `contain` alone carries the effect (dev over
  same-file +2.3 / +3.8); `invoke` alone helps L3 over the first stage but not over same-file chance; `import` lowers
  L2. This matches the BM25-seeded pilots: most of what the graph adds is "other units of the files already found".
- **Evidence class:** measured, exploratory; zero-shot encoders, one seed, 55 Verified L3 queries, two dev L3
  repositories (Q47). **Cheapest experiment that could change the reading:** the same stated cell with a same-file
  expansion that is not random but ordered by the first-stage score (a "file neighbours by score" baseline), from the
  existing dev and Verified evaluation inputs (minutes, no GPU); if it matches the graph, the graph's L3 role reduces
  to file-level expansion.

## Addendum 2026-10-29 — is the graph a retrieval signal beyond same-file expansion? (E-GRAPH-ROLE; evidence only, no choice made)

The cheapest experiment named in the addendum of 2026-10-25 was run (`docs/EXPERIMENTS.md` E-GRAPH-ROLE, rows `s1-*`; minutes of CPU, no GPU): the X2 cell on RRF(BM25, Qwen3-Embedding-0.6B) and on
RRF(BM25, CodeRankEmbed), with same-file expansion ordered by the first-stage score, same-file expansion in random order, non-contain-only and contain-only graphs and a no-file-constraint control at
the same candidate budget (cap 50, sizes matched), plus where the L3 gold units that the first stage misses can be reached. Evidence class: measured, exploratory, one stated cell, 55 Verified L3
queries in six repositories, two dev L3 repositories (clustered dev intervals not informative, Q47); gold `units_all_nomod` with `units_all` beside it (no ordering flips).

**Which roles of the graph have evidence, stated flat.**

- **Role A, retrieval-time signal.** Evidence for *expansion of the first stage's best units with other units of the same files*: Recall@100 at L3 rises by +6.5 [3.3, 10.1] (Qwen3) and +7.7 [4.0, 12.2]
  (CodeRankEmbed) on Verified-six, +11.3 and +13.2 on dev, with no graph at all. **No evidence that graph edges add to that.** The stored graph is level with or below the score-ordered same-file expansion
  (L3: -2.7 [-6.0, 0.8], clustered [-6.5, 3.9] and -2.0 [-5.2, 0.8], clustered [-6.4, 0.6] on Verified-six; -1.0 on dev; at L2 it is ahead by 0.6 to 1.7 points, clustered intervals above 0 for one first stage only).
  Containment-only equals the stored graph; in this graph containment edges never leave a file. Non-contain edges (import, invoke, inherit) reach 8% of the missed L3 gold units from the top 5
  in two hops and not through their files (invoke carries most), but as an expansion they add nothing measurable on Verified-six (-0.5 [-2.0, 1.1]) and are 6 to 7 points below same-file expansion.
  The earlier comparison against *random* same-file units (ADR-003 addenda of 2026-10-18 and 2026-10-23) understated what a file-level baseline reaches. Not shown: that edges add nothing (the
  interval allows about -6 to +4 points).
- **Role B, training-time structure.** No evidence. The only graph-for-supervision measurement is fitted family weights (no effect on L3, no supervision involved); structural negatives and graph-derived
  positives have not been run (E-PILOT-L3POS is the named test).
- **Role C, agent tool.** No evidence. No experiment has been run; the agent is not integrated, and the references on it (GRAPH_DESIGN section 2) are papers read, not project measurements.

**Flip experiment for "the graph is a retrieval signal".** Stacked expansion at equal total budget: same-file units by first-stage score, then replace the lowest-scored 10 and 25 with the best non-contain
neighbours of the seeds, against the unreplaced list; success is a clustered interval above 0 at L3 over dev, Verified-six and the Pro ansible L3 repository (D32). About an hour of code and ten minutes of CPU;
about 300 L3 queries are needed to see a 2-point difference with 80% power (reasoned estimate), against 155 dev and 55 Verified. If it is level or negative, the retrieval role reduces to file-level
expansion. **Conditions to revisit:** a better receiver rule for call sites (Q35), a hop-decay variant ordered by something other than the seeds' score, more L3 repositories.

This addendum decides nothing: the role (Q30) stays with the engineer. Prior statements in this ADR that the graph "helps a lexical first stage at L3" stand for the BM25 seeds and are read together with this one:
the help is the help of file-level expansion.
