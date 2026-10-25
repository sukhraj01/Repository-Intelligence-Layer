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
