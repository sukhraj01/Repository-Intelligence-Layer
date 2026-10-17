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
