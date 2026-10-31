# ADR-004: Retrieval granularity

- **Status:** Proposed — **not decided**
- **Date opened:** 2026-10-12
- **Decide by:** end of week 2 (all ten decisions)
- **Decided by:** _pending — team_
- **Master doc:** open decision #4 (`docs/12_open_decisions.md`)
- **Affects:** `CodeUnit`, evaluation, metrics comparability

## Context
L2 retrieves files or chunks (≈15,000 chunks per repository on average); our CodeUnit design is function-level. Reported metrics must be comparable to the benchmark's.

## Alternatives considered
- Function-level units
- CORE-Bench chunks
- Both

## Master doc's recommendation (a recommendation, not a decision)
Both — CORE-Bench chunking for reported metrics so numbers are comparable; function-level units internally for the graph.

## Decision
_Pending — the team decides._ If work cannot wait, proceed behind a config flag marked
`provisional: ADR-004` (never in `configs/frozen/`) until the decision is made.

## Rationale
_Pending._

## Trade-offs
_Pending._

## Evidence to gather
- [ ] CORE-Bench's chunking procedure and chunk-size distribution from `corpus.jsonl` on a sample repository.
- [ ] A mapping between function-level CodeUnits and benchmark chunks, and what is lost in it.

## Related benchmarks
_None yet._

## References
See `docs/11_references.md`.

## Conditions to revisit
_Pending._

## Addenda

## Addendum 2026-10-17 — decisions that bear on granularity (D6, D7, D12; this ADR stays Proposed)

- **D6** adds one residual `module` unit per file, so that about 10% of sampled gold positions that
  overlap no definition are reachable at unit level (16 of 160, three repositories). Flip: pilots M and E1.
- **D7** keeps the chunk-to-unit link out of the CodeUnit: the evaluation loader builds a derived
  mapping at the instance base commit. Reason: chunk definitions differ within one paper (mean length
  1,004.9 characters at evaluation, 2,188.4 in training) and released rows carry only `_id` and `text`.
  Flip: pilot M's match rate.
- **D12** makes unit-level evaluation primary on the Verified instances (432 at L2, 302 at L3, also
  the paired-RQ3 set); the other CORE-Bench sub-datasets stay chunk-level and secondary until base
  commits are obtained from their own metadata (Wave 1 checked Verified only).
  Evidence class: measured (counts, `results/tables/paired_n.json`) and read in full (the evaluation
  scores a repository snapshot at the base commit, Sec. 4.1, p.5). Flip: per-repository variance in
  pilot E (if three to twelve repositories give an interval too wide to rank anything, widen the
  primary set to chunk-level over all sub-datasets). Conditions to revisit: base commits for other
  sub-datasets; the pilot's variance.
- What is still open here: which granularity the reported metrics use overall (this ADR).

## Addendum 2026-10-17 — pilot M measured the chunk-to-unit mapping (evidence only; this ADR stays Proposed)

Exploratory pilot, flask / requests / seaborn, 11 Verified instances (`docs/EXPERIMENTS.md` E-GRAPH-REACH,
`results/tables/m_*.csv`, `RESULTS.md` rows `m-*`):

- **Match rate (flip condition of D7).** 160 of 160 positive chunks (19 at L2, 141 at L3) were found by exact text,
  each at one location; no failure of any kind. A unit-level scoring of chunk qrels is therefore
  mechanically possible on these repositories. Not tested: other sub-datasets, other languages.
- **What a chunk maps to.** One function or method 118, several 21, only a class 5, only residual lines 16
  (10.0%). A unit-level metric must decide how a chunk that spans several units counts (13% of these
  positives) and how a positive inside a nested definition counts (it folds into its parent under D6); neither is
  decided here.
- **Kinds at L3 (141).** Method 101, function 12, class 5, module residual 13, test unit 10, documentation or
  configuration 0. In this sample the L3 labels are code units, so a function-level index covers every
  positive; the benchmark's documentation and configuration chunks are not positives here (rule-of-three
  upper bound 2.1% of L3 positives, 95%).
- Still open for this ADR: the reported-metric granularity overall and the weight to give chunk-level numbers.
  Pilot E1 (BM25 at chunk and unit level, with and without the module unit) is the next evidence.

## Addendum 2026-10-18 — pilot E1 measured BM25 at chunk and unit level (evidence only; this ADR stays Proposed)

Exploratory pilot (`docs/EXPERIMENTS.md` E-BM25-REPRO, `results/tables/e1_*.csv`, `RESULTS.md` rows `e1-*`); dev and test repositories separated before any run.

- **The ruler works.** Chunk-level BM25 under the benchmark protocol reproduces the published BM25 rows to the printed decimal (Verified L2 11.94 / 46.74 against
  11.9 / 46.7, L3 22.19 / 33.89 against 22.2 / 33.9, all 632 L2 folders 13.00 / 38.82 against 13.0 / 38.8), provided the average is taken over folders (and, for the
  whole of L2, over the seven sub-datasets). The query-weighted mean differs by up to 5 Recall@100 points. Whichever granularity is chosen, the averaging
  convention must be written next to every number that is compared with the paper.
- **Unit level is measurable on Python sub-datasets with base commits** (Pro, Live and SWE-Bench++ metadata give them; Verified already did). On the six Verified
  repositories (83 L2 queries) unit-level BM25 gives nDCG@10 16.1 [10.4, 22.3] and Recall@100 43.8 [34.8, 53.3] against chunk-level 13.4 and 44.2 on the same queries;
  on 353 dev L2 queries 15.8 / 33.1 at unit level against 19.3 / 41.8 at chunk level. The two are not on one footing (different candidate sets and numbers of gold items), so
  they say that unit-level evaluation works, not that one granularity retrieves better.
- **The module unit (D6)**, on the same gold: it makes residual-line gold reachable (dev L2 Recall@100 +2.00 [+0.68, +3.25], nDCG@10 +0.68 [+0.16, +1.27]) and costs
  nDCG@10 0.5 to 1.9 points when the gold has none. On six Verified repositories the first effect is not distinguishable from zero (83 queries).
- **Label noise (E2) bears on a granularity choice:** 12.7% of dev L2 positives and 6.2% of the Verified-six ones are import blocks, which only a module-level unit (or a chunk)
  can represent; removing them removes the module unit's measured benefit. An evaluation that keeps them rewards a module unit; one that cleans them does not.
- Still open: the reported-metric granularity overall (Q11), the gold definition for a chunk spanning several units (Q39; `units` and `units_all` give the same signs here), and the
  reading of import-only positives (labels or noise).

## Addendum 2026-10-23 — gold readings (engineer decision D18 of 2026-10-18, closes Q39 and Q41 provisionally; this ADR stays Proposed)

**D18.** (1) A chunk's positive counts as a positive for **every unit it overlaps** (the `units_all` reading of pilot E1).
(2) The reading **without module-residual positives** is primary for design decisions about the graph; the
CORE-Bench-faithful reading (with them) is reported beside it. Provisional until the measurements of the current wave show
whether any ranking of conditions flips between the two readings.
- *Rationale.* Counting every overlapped unit keeps all gold reachable and does not need an overlap threshold no source
  justifies. Without module residuals the gold is function-level, as in SweRank, LocAgent and Loc-Bench, so graph results
  are comparable with that work; it is also the conservative reading for the graph question: the L3 containment gain of
  pilot E3 over same-file chance is +1.2 [-0.4, +2.8] Recall@100 without module units in the gold, not distinguishable from
  zero, while import-only positives (12.7% of dev and 6.2% of Verified-six positives, pilot E2) carry part of the module
  unit's measured benefit.
- *Evidence class.* Measured (pilots M, E1, E2, E3; small samples) and read in full (the gold definitions of the cited papers).
- *Experiment that could flip it.* Every comparison of the current wave (class-unit source, edge policy, dense and fused
  first stages, graph on top) computed under both readings: if the ordering of conditions flips between them, the primary
  reading is reopened. No extra runs are needed; both readings come from the same caches.
- *Conditions to revisit.* A flipped ordering; the reported-metric granularity (Q11) being settled differently.
- *Not decided by D18:* whether reported benchmark numbers are chunk-level, unit-level or both (Q11).

## Addendum 2026-10-23 — D18's revisit condition checked on the structure measurements (evidence only; this ADR stays Proposed)

- D18 is provisional until the wave's measurements show whether an ordering of conditions flips between the two D18 readings
  (`units_all` with and without module units). **Class-source forms and ambiguous-site policies:** no flip (`docs/EXPERIMENTS.md`
  E-CLASS-SOURCE, E-AMBIG-POLICY). **Edge subsets of the pilot-E3 headline:** some flips, all among cells whose intervals overlap;
  the one of substance is at dev L3 against same-file chance, where `invoke` is ahead of `contain` without module units (+2.0 [-0.5,
  +4.4] against +1.6 [+0.0, +3.1]) and behind with them (+0.8 [-1.5, +3.2] against +2.8 [+1.3, +4.2]); sign changes only for cells
  within about a point of zero. Whether this reopens the primary reading is the engineer's call.
- **A dependence D18 did not anticipate.** D18 part 1 (a chunk's positive counts for every unit it overlaps) makes a class gold
  whenever one of its methods is; under that reading the full class text wins Q28 by 2 to 3 points, under pilot M's mapping the
  class-source forms are indistinguishable (ADR-013 addendum of today). The gold reading for classes and Q28 are one question.
- Evidence class: measured (exploratory). Experiment that could flip it: a reading that counts a class only through lines outside
  its methods, computed from the same records (minutes).

### Addendum 2026-10-31: tokenisation evidence from the retrieval-stack pilot (status stays Proposed)

- On a docstring-to-function task over five local checkouts (2,649 queries, docstrings removed from the index), splitting
  identifiers raised MRR from 18.7 to 27.6 (clustered difference +8.9 [+6.9, +10.5]) and a name weight of 2 to 31.9 (+13.1
  [+10.3, +15.9]); query latency unchanged, index build throughput roughly halved. Recomputed from the stored log.
- Evidence class: measured (exploratory, local, not benchmark repositories). The gain is an upper bound for issue-style queries.
  Experiment that could flip it: the development-repository runs with the reference tokenisation as the regression control.
