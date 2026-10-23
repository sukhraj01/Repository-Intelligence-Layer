# ADR-005: Primary benchmark

- **Status:** Proposed — **not decided**
- **Date opened:** 2026-10-12
- **Decide by:** end of week 2 (all ten decisions)
- **Decided by:** _pending — team_
- **Master doc:** open decision #5 (`docs/12_open_decisions.md`)
- **Affects:** Evaluation, RQ1, RQ3 pairing

## Context
L2 is issue-to-edit localization; L3 scores broader context (tests, docs, configuration), which is exactly what our graph extension adds; Loc-Bench (660 examples, post-Oct-2024) checks contamination and category balance.

## Alternatives considered
- CORE-Bench L2
- CORE-Bench L3
- Loc-Bench

## Master doc's recommendation (a recommendation, not a decision)
L2 primary, L3 for the graph question, Loc-Bench as contamination check.

## Decision
_Pending — the team decides._ If work cannot wait, proceed behind a config flag marked
`provisional: ADR-005` (never in `configs/frozen/`) until the decision is made.

## Rationale
_Pending._

## Trade-offs
_Pending._

## Evidence to gather
- [ ] Instance and repository counts per level; overlap with SWE-bench Verified; evaluation cost per level.

## Related benchmarks
_None yet._

## References
See `docs/11_references.md`.

## Conditions to revisit
_Pending._

## Addenda

### 2026-10-17 — Loc-Bench against the held-out list (evidence, no decision)
- Loc-Bench V1 has 165 repositories: 37 are already in the held-out list (CORE-Bench L2/L3 or Verified), 128 are not. V0.2 has 210: 41 in the list, 169 not.
- If Loc-Bench repositories were also held out, CodeSearchNet python would drop from 449,440 to 445,640 instances (13,546 to 13,534 repositories); the `gangiswag/train_data` python candidate would not change (none of the 169 outside repositories occurs in it).
- Not decided here: whether Loc-Bench is held out (Open question Q9). Source: `data/held_out/report.md`, `knowledge/datasets/loc_bench.md`.

## Addendum 2026-10-17 — Loc-Bench tier, Rewrite qrels, primary set (decisions D3, D12, D13)

**D3 (closed Q9): Loc-Bench repositories are held out as a separate, switchable tier** of
`held_out_repos.json` (169 repositories outside the core list, union of both versions). *Why.* The
original SweLoc excluded them (`knowledge/papers/swerank-2505.07849.md`, Sec. 3.1, p.4); none of the
169 occurs in the candidate pool, so the cost there is zero (CodeSearchNet python loses 3,800
instances, 12 repositories); and it keeps the comparison with SweRank clean. *Evidence class.*
Measured (`data/held_out/report.md`) and read in full. *Flip experiment.* If a later pool contains
many Loc-Bench repositories and the switch costs more data than the leakage it prevents, measure the
inflation on Loc-Bench with and without them (E-PILOT-LEAK variant). *Conditions to revisit.* A pool
with substantial Loc-Bench overlap; a decision to report Loc-Bench as a contamination check, where
the tier must then be off for the training of that run.

**D12 (closed Q21):** unit-level evaluation is primary on the Verified instances (432 at L2, 302 at
L3); see the ADR-004 addendum for the reasoning, evidence and flip experiment.

**D13 (closed Q23): Rewrite runs are scored against the original qrels** (same query ids in every
folder); the 158 folders whose Rewrite qrels differ from the originals (81 Multilingual folders with
no qrels file, 13 with fewer rows) are reported as a packaging defect. *Why.* The card says Rewrite
shares qrels with the originals; the labels belong to the query ids, not to the wording. *Evidence
class.* Measured (`results/tables/core_bench_card_vs_measured.csv`, DEV-002). *Flip experiment.*
BM25 on original against Rewrite queries scored with both qrels sets; if the choice flips a
conclusion, report both. Time-box: one BM25 run per sub-dataset (pilot E1 infrastructure).
*Conditions to revisit.* The dataset authors fixing the qrels; a flipped conclusion.

## Addendum 2026-10-23 — averaging and the contamination probe (engineer decisions D17 and D23 of 2026-10-18; this ADR stays Proposed)

**D17 (closes Q40): averaging convention.** The primary number is the mean over queries, with bootstrap intervals that
resample repositories (clusters) and the queries inside them. The mean of folder means appears only in the table that
reproduces the published BM25 rows.
- *Rationale.* The claim is about queries (issues), and queries of one repository are not independent, so a
  repository-clustered interval is the honest one; the folder mean weights a folder of 2 queries like a folder of 80. The
  folder mean is kept where the purpose is to match the published numbers, which use it.
- *Evidence class.* Measured: on Verified the two conventions differ by 3.8 Recall@100 points at L2 (46.74 against 42.92)
  and 5.1 at L3 (33.89 against 28.79) for BM25 (`docs/EXPERIMENTS.md`, E-BM25-REPRO); only the folder mean reproduces the
  published rows.
- *Experiment that could flip it.* Compute both conventions on every comparison table of the current wave (no extra runs);
  if the ordering of two conditions differs between them, both are reported in the main table and the convention is
  reopened.
- *Conditions to revisit.* A flipped ordering; a reviewer or the benchmark authors fixing a different convention.

**D23 (closes Q44 as a decision; the run is pending).** The full documents-only contamination scan runs in the background,
with hits restricted to functions at the instance's own base commit and above a size floor chosen from the slice before
the full result is read. It is **not part of the frozen evaluation**; it supports the contamination statement in the report.
- *Rationale.* In the slice 73% of hits were functions under 20 syntax-tree nodes and the probe set was the union of 499
  snapshots, so unrestricted counts overstate exposure; the restriction makes a hit specific to the evaluated code. A
  frozen-evaluation component would have to be rerun for every encoder, at about 10 CPU-hours per run.
- *Evidence class.* Measured (slice of 24 of 240 shards, `docs/EXPERIMENTS.md`, E-CONTAM-PROBE).
- *Experiment that could flip it.* The full scan finding a large share of the Verified instances' own edited functions
  (above the floor) in the corpus, concentrated in a few repositories: then a per-repository sensitivity row (results with
  and without those repositories) would be considered for the evaluation.
- *Interpretation rule.* A hit is not proof that the (query, document) pair was trained on; a non-hit is not proof of absence.
