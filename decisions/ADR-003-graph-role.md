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
