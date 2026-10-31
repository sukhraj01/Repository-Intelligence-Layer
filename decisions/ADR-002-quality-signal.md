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

## Addendum 2026-10-29 — smoke pilots E-PILOT-K and E-PILOT-NEG (evidence, no decision; this ADR stays Proposed)

Evidence class: measured, exploratory, 2 seeds, 63 optimizer updates on 2,000 pool directories, CodeRankEmbed base, dev units
(`docs/EXPERIMENTS.md` "E-PILOT-K, E-PILOT-NEG, E-PILOT-LEAK"; rows `t2-*`).
- RAW alone moves the base far (+8.3 dev L2 nDCG@10, +11.0 L3 Recall@100), so the budget is not too small to train.
- Reading, stated flat: no difference between RAW and any FILTER, WEIGHT or CURRICULUM cell is detectable at 63 updates. This is a
  statement about the budget, not about filtering: 63 updates is about 0.3% of a planned run. RAW alone moves the dev numbers well away from
  the untrained base, so the budget is enough to train; it is not shown to be enough for a difference in which examples are used to show. The cells themselves: no FILTER (K 10/20/40
  under CodeRankEmbed, SweRankEmbed-Small, BM25, or CodeRankEmbed+BM25 agreement), WEIGHT or CURRICULUM cell is above RAW at L3; strict
  cells (K = 10, BM25 at any K, agreement at K = 10) are 0.6-1.6 points below it, beyond one retraining's change. With about 60 contrasts,
  a few such flags are expected by chance, and fewer unique positives per update (a strict filter re-visits its examples) is a
  sufficient explanation at this budget; the sign is not evidence that filtering hurts.
  At L2 every cell is within about 0.8 points of RAW. At matched updates a strict filter keeps 12-45% of the positives and re-visits
  its examples (effective epochs up to 1.64).
- Teacher: the self-teacher cells (Q52, CodeRankEmbed = base) do not behave differently from the SweRankEmbed-Small and BM25 cells at
  the same K; SweRankEmbed-Small keeps the most positives (it ranks the pool's positives best, Q50) and costs least.
- Negatives (Q46): CodeRankEmbed top-15 is indistinguishable from random repository-local; the 0.95 positive-aware cut gives +1.1
  [0.35, 1.90] L3 Recall@100 (dense), L2 +0.6 (below the seed difference).
- What it cannot show: a filter's effect at the RQ2 budget (63 updates is about 0.3% of 20,000); seed variance (one difference per cell).
  Cheapest experiment that could show whether a difference exists at all: RAW vs FILTER SweRankEmbed-Small K20 and BM25 K20 at about 2,000
  updates on the same pool, 2 seeds (about 3 GPU-hours with a faster evaluation).

## Addendum 2026-10-29 — twelve papers read in full on supervision quality: what they imply for K, the weight function and the curriculum order (evidence, no decision; this ADR stays Proposed)

Method: each paper was fetched as a PDF, its page count checked against the extracted text, and read in full including appendices and result tables; each has a note under `knowledge/papers/` whose quoted numbers were re-found in the text by `scripts/check_paper_note.py`. Search queries and dates are in `knowledge/papers/LANDSCAPE.md` ("Fifth reading pass"). Evidence class below: **read in full** for what a paper reports (all `paper_reported`, none measured here); **reasoned** for what it implies for this project. None of these studies is a code retriever trained at a matched optimisation budget on repository-level pairs; most are text, three are images, and nearly all are single runs. The arms' definitions are not touched by this section.

| Paper (note) | K (a cut on the positive's teacher rank) | Weight function | Curriculum order | Evidence class and main limit |
|---|---|---|---|---|
| Promptagator (`promptagator-2209.11755.md`) | A pair is kept only if its positive is the top-1 of a retriever trained on the same noisy data; K = 1 tuned on a different task; helps 8 of 11 datasets (+2.5 on average), hurts the two smallest; authors suggest a per-query K | none | none | read in full, text, one run per dataset; the judge is the learner (the self-teacher of Q52), no independent control |
| Noisy Pair Corrector (`npc-2311.03798.md`) | Detection by the trained model's own loss against random (not hard) negatives, a two-component fit per epoch, posterior above 0.5; needs a warm-up (1 to 10 epochs equal, 20 clearly worse); re-estimating each epoch beats once | flagged pairs lose the contrastive term; every pair gets a consistency term towards a moving-average copy (soft label, not a hard drop) | none | read in full, code (MRR +2.4 to +2.7 over the backbone, two code sets) and synthetic text noise; single runs; no label-level precision of the detector |
| GloFND (`glofnd-2502.20612.md`) | A per-anchor learned similarity threshold at a fixed quantile instead of a fixed K; the detector is the model in training and works only after a warm-up (best start at 70 of 200 epochs) | filtering only | none | read in full, images; three seeds with paired tests; shows the cost of a self-judge in numbers |
| ARHN (`arhn-2604.11092.md`) | Edits are decided relative to the positive (a negative above the positive is promoted, one below it with evidence is dropped, the rest kept); relabel-only 0.511 and filter-only 0.510 are near the baseline 0.508, both together 0.521 | none | none | read in full, text; mean of several seeds without intervals; an 8B labeller falls below the baseline (0.501), a 32B one helps: the signal's quality is a precondition |
| Debiased supervised contrastive learning (`debiased-scl-2311.16481.md`) | none | down-weights positives close to the anchor because mislabelled positives are "easy positives" (JSD 0.29 against 0.74); +1.6 on ImageNet-1k over the unmodified loss | none | read in full, images, human-type label noise at 3% to 6%; fails against selection methods at 40% synthetic noise; the signal is the model's own similarity |
| ADAM (`adam-2212.10192.md`) | Keep the share (1 - t/2T) of each batch with the highest teacher confidence, so the kept share shrinks from all to half | weights are teacher soft labels | none (it shrinks rather than grows) | read in full, text; independent cross-encoder teacher; the self-paced part adds 0.03 MRR@10 in the ablation, single run |
| Curriculum learning strategies for IR (`curriculum-ir-1912.08555.md`) | none | none | Easy-to-hard by a previously fine-tuned model's confidence on the labelled pair beat random order (MSDialog +0.0143 MAP, about 2.5 seed SDs; MANtIS +0.0091, about 1 SD); heuristic difficulty (length, counts) did not; a pacing function that gives hard instances time is best; five seeds | read in full, text cross-encoder; the scorer was trained on the data it orders; no reversed-order control |
| CL-DRD (`cl-drd-2204.13679.md`) | Teacher's top K = 5, 10, 30 as the "pseudo-relevant" group per phase | pairs inside the group are ordered, others only by group | The phase changes the fineness of the demanded ordering; the reversed order ends lower (dev MRR@10 0.378 against 0.382, one run) | read in full, text; independent cross-encoder; gives the only reversed-order control in the set |
| MM-IssueLoc (`mm-issueloc-2607.15205.md`) | none | one row per gold unit (multi-positive expansion) | File-level rows first, then function-level rows beats function-only on function Acc@10 (33.86 and 32.36 against 29.15 and 30.03) and loses on file Acc@5 against file-only | read in full, issue retriever, single seeds; not at matched epochs; its negative-policy ablation is mentioned but not shown |
| Self-distillation with adaptive margins (`self-distillation-margins-2407.21515.md`) | none | target margin from the encoder's own similarity of positive and negative (hard pairs weigh more) | none | read in full, text; learning curve peaks inside one epoch and then falls; selection and reporting overlap on TREC-DL 2019 |
| Uncertainty-aware code search (`uncertainty-aware-code-search-aaai2025.md`) | none | none (the lead's "uncertainty" is Gaussian embeddings) | none | read in full; the hard-negative term adds 0.004 MRR in one run |
| When fine-tuning fails (`finetuning-fails-msmarco-2506.18535.md`) | none | none | none | read in full; five single-run cells, one recipe on an already saturated encoder; low weight, contrasts with the project's measured +8.3 dev L2 nDCG@10 in 63 updates |

What the set implies, flat (evidence class "reasoned" unless a note says otherwise):

1. K. The papers that filter by a rank cut judge with the learner (Promptagator, NPC, GloFND) or with an independent model (ADAM, CL-DRD, ARHN). Where the judge is the learner, every one of them adds a warm-up and reports an interior optimum for it; the independent-judge papers have none. The project's K-rank already uses a separate encoder, so this evidence does not bear on K itself; it bears on Q52's self-teacher cells (CodeRankEmbed as both base and teacher) as a design that others had to protect with a warm-up. No paper tunes K on the target task; Promptagator tuned it on another task and found it fixed for all. The smoke pilot's finding that strict cells sit 0.6 to 1.6 points below RAW with a third of the positives kept is in the direction of Promptagator's loss on small sets, not evidence of it.
2. Weight function. The two image papers that analyse which pairs a confidence signal favours report that errors sit among the pairs the model already finds easy (a weight that rises as the K-rank falls, as the `power` and `sigmoid` forms do, favours them in that setting). Text sources use teacher confidence or the positive's rank as a soft target (ADAM, NPC, CL-DRD) instead of a scalar multiplier. No paper compares a power with a sigmoid form. Whether the pool's wrong positives sit at low or high K-ranks is measurable on the existing rank table; if they sit at high K, the image result does not transfer.
3. Curriculum order. The only difficulty-ordered result with several seeds sorts by a fitted model's confidence and adds a pacing function; the unreversed order is compared with random, not with its reverse. The only reversed-order control is for a granularity curriculum. "Curriculum" thus names three different objects across the set (difficulty order with a growing prefix, shrinking confident subset, granularity or file-to-function stages). The project's CURRICULUM arm (a stable sort of each pass, no pacing function, no reversed control) is none of these exactly.
4. Learning curves. For code-retriever fine-tuning none was found (stated in `LANDSCAPE.md`); a self-signal peaked inside one epoch in the text case. Measured here only for RAW at 63 updates.

Designs the papers show that the four arms do not contain (named for the engineer; none is added to the arms, none is run):

- **Re-estimated own-model filter with a warm-up** (NPC, GloFND, Promptagator): the same cut with a judge that is retrained and re-applied each epoch.
- **Soft consistency target to a moving-average copy** instead of dropping flagged pairs (NPC; ADAM uses teacher soft labels).
- **Promotion of high-ranked non-gold units to positives** (ARHN, RLHN): the teacher's ranking edits the positive set as well as the negative set; with several positives per query this is the multi-positive form of "relabel".
- **A pacing function** (curriculum-IR, ADAM, CL-DRD): a schedule for how much of the sorted pool is available, separate from the sort.
- **A reversed-order control for CURRICULUM** (CL-DRD): a control row, not an arm.
- **Granularity curriculum** (CL-DRD, MM-IssueLoc): file-level supervision before function-level supervision; the index has both units.
- **Down-weighting easy positives** (debiased contrastive learning): the opposite sign of the K-rank weight, motivated by label errors that look easy.
- **Per-query or per-anchor cut** (Promptagator's suggestion, GloFND's per-anchor threshold): a threshold that varies with the query rather than a global K.
- **Early stopping or checkpoint selection on a dev score** (self-distillation, fine-tuning failure): a stopping rule that may matter more than the arm when a signal overfits.
- **False-negative control among same-repository non-gold candidates** for the negative policy (MM-IssueLoc mines them without it; ARHN and RLHN show the relabelling cost with language-model judges).

Cheapest experiments that could change a reading above (time-box in brackets, none run): (a) read 50 positives of the pool that sit at high K-rank under the separate teacher, by hand, for whether they are wrong positives (the pool has no label for this, so a hand reading is the proxy; about one hour); this says whether the image finding about easy errors has any counterpart; (b) a reversed-order CURRICULUM cell next to the sorted one at the same updates, two seeds (the 36 pilot runs cost 16.9 GPU-hours in all, about 0.5 each); (c) the self-teacher cell with and without a warm-up of N updates, two seeds (about 1 GPU-hour at the pilot size).

## Addendum 2026-10-29 — engineer decisions D28, D30 and D31 (Q51, Q52, Q53 as defaults; the ADR stays Proposed)

**D28 (Q51; DEV-012 stands).** One negative policy is held identical across all four arms. Primary: random repository-local negatives (the benchmark's own recipe; uses no teacher, so it shares no signal with FILTER). Secondary, labelled exploratory: teacher top-M with the score-relative cut. The arms pilot runs RAW and the best FILTER cell under both.
- **Why.** If RAW differed from the other arms in two things (filter and negatives) a difference could not be attributed to supervision quality. Random local negatives are the only policy independent of every teacher. The secondary policy gained +1.10 [0.35, 1.90] dev L3 Recall@100 in the smoke pilots (63 updates).
- **Evidence class.** Reasoned (identical policy); measured for the +1.10; read in full for the selection-rule effect in text retrieval (`knowledge/papers/nv-retriever-2407.15831.md`).
- **Cheapest experiment that could flip it.** The arms pilot itself: if the order of RAW and FILTER changes between the two policies, the held-identical choice matters for the conclusion and is reported as such.

**D30 (Q52).** Teacher cells are run, not chosen: BM25, SweRankEmbed-Small and CodeRankEmbed, each recorded with `teacher_equals_base` and `teacher_correlated_with_pool_selection` (true for SweRankEmbed-Small). The base for the pilots is CodeRankEmbed (137M parameters, about four times lower CPU latency than the 0.6B encoder, 2.65 s per update measured). No cell is a design choice.
- **Evidence class.** Measured (base cost, E-TRAIN-STACK); reasoned (the two flags).
- **Cheapest experiment that could flip it.** The arms pilot's three teacher cells at the same K; if a self-teacher cell separates from the other two, the self-confirmation concern is measured instead of argued.

**D31 (Q53).** Batch shape held identical in the pilots: 32 x (1+1), float16 autocast, gradient checkpointing, 512 tokens. If any card above 11 GB is reachable it is reported and used only if every run of a comparison can use it.
- **Why.** It is the largest measured shape that fits an 11 GB card for the 137M base (2.65 s per update; about 15 GPU-hours for 20,000 updates). It is smaller than the master's batch and than SweRank's, which is a stated limitation.
- **Evidence class.** Measured (`t1-train-throughput` rows).
- **Cheapest experiment that could flip it.** Run a short comparison of batch 32 against a gradient-cached larger effective batch (not built) on the same cell; or, if a larger card appears, the same cell at the master's shape.

## Addendum 2026-10-30 — learning curve of the RAW arm (E-PILOT-CURVE; evidence only, no decision; this ADR stays Proposed)

**Evidence class.** Measured, small n: RAW only, 2 seeds, a dev subset (3 repositories at L2, 2 at L3), reduced design (2,000 of the planned 3,000 updates; ansible only at step 0). Details and intervals: `docs/EXPERIMENTS.md` E-PILOT-CURVE.

- On the dense column the RAW arm has moved about +10.5 (L2 nDCG@10) and +11.1 (L3 Recall@100) from the untrained encoder by 100 updates, and the change stays between +10.1 and +11.4 at 300, 1,000 and 2,000 updates; increments are within 1.0 point and the seed gap at the same update count is 0.3 to 2.6.
- **Consequence for the 63-update pilots (E-PILOT-K/NEG/LEAK).** They stopped at about the point where RAW itself has already moved nearly all it moves. Differences between arms were not detectable at 63 updates, and this curve says the lack of a visible arm difference there cannot be read as a lack of an effect later: what the pilots could not see is how supervision changes the later part of training, which this RAW-only curve does not cover either.
- **Reasoned, not measured.** If the encoder settles near 100 updates under RAW on this pool and recipe, an RQ2 update count of 20,000 (the target in `docs/08_experimental_design.md`) may be far longer than needed, and matched optimization budgets could be set much shorter. Caveats: the checkpoints sit on a 3,000-update learning-rate schedule, the pool is revisited about 12.8 times by 2,000 updates, the 3,000 point is unmeasured, and a supervision arm may keep moving where RAW stops. Whether an arm difference appears at N = 100 or at a longer N is the open question of the arms pilot (T4, not run).
- Cheapest experiment that could flip this reading: the arms pilot at N = 100 and at one longer N (cost options in the project state).

## Addendum 2026-10-31 — arms pilot (E-PILOT-ARMS), engineer defaults D37 and D38 (evidence only; this ADR stays Proposed)

Recorded as engineer defaults: **D37** adds a reversed-order CURRICULUM cell and a warm-up before the self-teacher cell; **D38** adds a negative control, NOISE (positives replaced by random functions of the same repository, everything else as RAW); **D39** prefers more seeds at short N to fewer seeds at long N once the encoder has plateaued. Evidence class: measured (exploratory, 3 seeds at 100 updates, 2 seeds at 1,000, dev subset, `docs/EXPERIMENTS.md` E-PILOT-ARMS). Cheapest experiment that could flip each: D37 and D38 are controls, nothing to flip; D39 flips if a cell separates from RAW only at long N (stage 2 saw none).

- The self-teacher with a warm-up is not specified in this ADR (it appears only as a candidate experiment) and was not run; the FILTER cell with the CodeRankEmbed teacher is the self-teacher without a warm-up (teacher equals base).
- At 100 updates RAW gains +10.7 (L2) and +11.9 (L3); FILTER (three teachers), WEIGHT and CURRICULUM are 0.1 to 1.4 points below RAW, the reversed curriculum is level with it, NOISE stays at the untrained encoder (share of the RAW gain about 0). At 1,000 updates the two cells re-run (FILTER with the CodeRankEmbed teacher, CURRICULUM) are +0.2 to +0.6 against RAW with intervals that include 0 in all but one clustered case.
- Reading: on this pool, recipe and subset no supervision setting tried raises the plateau or the speed of reaching it; the order of the cells at 100 updates (strict filters lowest) is in the direction of the smoke pilots' finding, and NOISE shows the gain needs real positives. Reading is limited by a 2,000-example pool (RAW falls 2 to 3 points between 100 and 1,000 updates here), three L2 repositories and the choice of settings.
- Open for the engineer: whether RQ2 continues with a larger pool (teacher ranks for the 5,000-directory pool cost about 3 GPU-hours), a different K or weight form, or is reported as a null result with the retrieval-versus-reasoning breakdown at RQ3.

## Addendum 2026-10-31 — matched-pool arms pilot (E-PILOT-ARMS2), engineer defaults D40 to D43 (evidence only; this ADR stays Proposed)

Recorded as engineer defaults: **D40** the self-teacher warm-up cell is dropped from the core RQ2 and kept as a limitation; **D41** RQ2 continues on the 5,000-directory pool (after the held-out filter) and the 2,000-example pool is retired for arm comparisons; **D42** matched budgets mean matched optimizer updates and a stated unique-example count, with every cell reporting unique examples seen, effective epochs and the pool it drew from, and a cell that cannot reach the common count without repeating examples flagged; **D43** a size-matched random subsample of RAW accompanies every FILTER comparison, and "quality beyond quantity" means beating that subsample. Evidence class: measured (exploratory, `docs/EXPERIMENTS.md` E-PILOT-ARMS2). The cheapest experiment that could flip each: D41 and D43 are design choices of the pilot, nothing to flip; D42 flips if a cell cannot reach the common count (none did at 100 updates; the subsample at 1,000 updates did not, flagged).

- **D40 as a limitation.** The FILTER cell with CodeRankEmbed as teacher is the self-teacher without a warm-up (teacher equals base); a self-teacher that is first warmed up on RAW is not specified here and was not run. Specification, to be written and run only if a static-teacher arm (a teacher that is not the model being trained) separates from RAW: the warm-up length in updates, the checkpoint that computes the K-ranks, whether ranks are recomputed once or each epoch, and the same matched updates and unique-example count as the other cells. Flip experiment: one such cell at 100 updates, 3 seeds, about 1.2 GPU-hours. Until a static-teacher arm separates from RAW the warm-up cell has nothing to explain, so it is not run.
- **Result at 100 updates, 5,000-directory pool, 2 seeds (not 3), five dev repositories without ansible.** Every cell saw 3,232 distinct examples, none repeated (effective epochs 0.65 to 0.78). RAW is 9.6 (L2 nDCG@10) and 11.1 (L3 Recall@100) above the untrained encoder. No cell is above RAW at both levels: FILTER (three teachers) -0.53 to -0.60 at L2 and +0.21 to +0.61 at L3, all six intervals include 0; WEIGHT -0.29 / -0.28 (both intervals exclude 0, below RAW); CURRICULUM -0.23 [-1.27, +0.59] / +0.87 [+0.20, +1.56] (L3 excludes 0, L2 does not, opposite signs). Against the size-matched subsample (4,592 of 5,000, one draw) the FILTER cells are -0.70 to -1.10 at L3, two of three excluding 0 (below). The subsample is +1.31 [+0.60, +2.02] above RAW at L3 and -0.33 at L2.
- **Stage 2 (1,000 updates, seed 0 only, partial by budget).** RAW 28.36 / 46.65; WEIGHT -0.22 / -0.03 against RAW; subsample -3.13 [-4.29, -1.98] / -1.70 [-2.71, -0.71] against RAW (and it repeats examples: 4,592 distinct against RAW's 5,000). The sign of the subsample gap at L3 is opposite to stage 1; this inconsistency is unresolved (seed noise, a single subsample draw, or a confound not identified) and is not explained away here.
- **Reading.** No K-rank signal here beats RAW or the size-matched subsample beyond RAW's own seed gap (0.84 L2, 1.45 L3). The minimum detectable difference at three seeds from the observed variance is 1.4 (L2) and 1.7 (L3), larger than every observed gap, so the pilot bounds the effect of FILTER, WEIGHT and CURRICULUM at this scale to about that size at best and cannot detect smaller ones. Intervals with two seeds and two to five clusters carry query sampling only and are descriptive. A null here is a null at this scale: one encoder, one K, one weight form, three cells with teacher equal to base, dev repositories only.
- Trigger rule: the stage-2 trigger of the brief is direction-blind (WEIGHT below RAW by 0.3 fired it). Whether it should fire only on an excess above RAW is the engineer's to change; not changed by a session.
