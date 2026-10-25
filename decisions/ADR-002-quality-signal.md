# ADR-002: Quality signal for FILTER and WEIGHT

- **Status:** Proposed — **not decided**
- **Date opened:** 2026-10-12
- **Decide by:** end of week 2 (all ten decisions)
- **Decided by:** _pending — team_
- **Master doc:** open decision #2 (`docs/12_open_decisions.md`)
- **Affects:** RQ2 FILTER and WEIGHT arms; `ril/training/supervision.py`

## Context
We cannot label examples "noisy" without evidence. SweRank filters by K = minimum rank of the positive relative to negatives under a base retriever; raising K relaxes filtering; optimal at moderate K ≈ 20. Docstring-era heuristics (docstring length, auto-generated detection) were designed for docstring–code pairs and break on issue text. If a learned model computes the signal it must be a separately pretrained encoder, never the model being trained.

## Alternatives considered
- SweRank K-rank
- Hand-written heuristics
- LLM judge

## Master doc's recommendation (a recommendation, not a decision)
K-rank — published, continuous, makes FILTER and WEIGHT the same signal applied as a hard threshold vs a soft weight.

## Decision
_Pending — the team decides._ If work cannot wait, proceed behind a config flag marked
`provisional: ADR-002` (never in `configs/frozen/`) until the decision is made.

## Rationale
_Pending._

## Trade-offs
_Pending._

## Evidence to gather
- [ ] Distribution of K-rank over a sample of the chosen pool under the candidate base retriever.
- [ ] Drop rate at several thresholds; how FILTER's pool size compares with RAW's.
- [ ] Confirmation that the filtering encoder is a different model from the trained encoder (leakage test (c)).

## Related benchmarks
_None yet._

## References
See `docs/11_references.md`.

## Conditions to revisit
_Pending._

## Addenda

## Addendum 2026-10-25 — K-rank in the candidate pool under three teachers (evidence, no decision)

Measured (`docs/EXPERIMENTS.md`, E-POOL-RANKS; tables `results/tables/x3_pool_ranks_*.csv`): rank of each positive among the
non-positive functions of its snapshot (the published SweRank construction), 1,522 positives of 160 pool directories.
- Distribution: median rank 10 (SweRankEmbed-Small), 38.5 (CodeRankEmbed), 33 (BM25); outside the top 20, pool estimates 45.2%
  [29.3, 54.2], 61.6% [48.6, 68.8], 63.5% [51.0, 71.8]. So a FILTER at K = 20 would drop roughly half to two thirds of the positive rows,
  depending on the teacher, and FILTER's pool would be far smaller than RAW's.
- Teachers disagree: Spearman per positive 0.855 [0.791, 0.896] between the two dense teachers, 0.53 between either and BM25; at K = 20,
  267 positives are inside under SweRankEmbed-Small only and 12 under CodeRankEmbed only (kappa 0.64). The choice of teacher changes which
  examples FILTER removes, not only how many.
- Teacher independence: SweRankEmbed-Small ranks this pool's positives far better than its base model, and the directories are selected
  with respect to it (ADR-001 addendum of the same date). If it was trained on these PRs, its K-rank here is a training fit rather than
  an independent quality signal. CodeRankEmbed (pretrained only) does not carry that risk; it is also the SweRank paper's teacher.
- Rank definition: competitors exclude the PR's other positives (`rank`); counting them (`rank_all`) is in the tables. Text form (code
  alone vs the stored `<id>\n<code>`) moves the SweRankEmbed-Small ranks (Spearman 0.90 between forms; kappa 0.85 at K = 20).
- Evidence class: measured (exploratory). Cheapest experiment that could flip a choice: E-PILOT-K (FILTER at K in {10, 20, 40} under
  each teacher and their agreement), which now has a per-positive rank table to draw from (`x3_pool_ranks_features.csv`; full pool by
  `scripts/ada/x3_dense.sbatch` with `SELECT=all`, about 4.9 GPU-hours per dense teacher).

## Addendum 2026-10-25 — what the training stack implements as options (no decision)

The training stack (`ril/training/`, `docs/EXPERIMENTS.md` E-TRAIN-STACK) implements the quality signal and the arms so that each open
choice is one configuration value, none of them set by code defaults:
- *K-rank source:* a precomputed per-positive rank table (the E-POOL-RANKS feature table, any teacher column), never the model being
  trained; an example's K-rank is the minimum over its positives (the best-ranked positive), as in SweRank's definition.
- *FILTER:* threshold `k` under a named teacher, at `level: positive` (drop positives ranked above `k`, keep them out of the loss as
  neither positive nor negative, drop examples left without a positive) or `level: example` (keep a pull request if its best positive
  passes, the PR-level reading of the SweRank+ filter, ADR-001 addendum). `k: null` is the identity.
- *WEIGHT:* `power` (`min(1, (k / rank)^p)`) or `sigmoid` (`1 / (1 + exp((rank - k) / s))`) with a floor; the loss is normalised by the
  batch size or by the weight sum (`loss.normaliser`). Weights that are all 1 are the identity.
- *CURRICULUM:* easy to hard by K-rank as a stable sort of the pass's random permutation, optionally by quantile bucket; repeated each
  pass. A constant difficulty is the identity.
- *Negatives:* held identical across arms (DEV-012, Q46); options listed there.
- *Loss form:* CORE-Bench's multi-positive form (positives summed in the numerator) or the mean over positives with the other positives
  out of each other's denominators (SweRank's per-positive instances).
- Measured property (test, not an experiment): at each hook's identity limit the other arms give bit-identical batches, first gradients
  and trained parameters to RAW's (`tests/unit/test_arms_only_differ_through_hooks.py`).
- Open point raised: if the base encoder is CodeRankEmbed and the K-rank teacher is CodeRankEmbed, the teacher is a frozen copy of the
  starting weights. That is not the "model being trained" (its ranks never move), but it is the model's own starting view of which
  examples are easy, which is close to the self-confirming loop the design warns about (Q52). Evidence class: reasoned only. Cheapest
  experiment: E-PILOT-K under CodeRankEmbed and under BM25 as teachers with CodeRankEmbed as the base, two seeds, dev repositories.
