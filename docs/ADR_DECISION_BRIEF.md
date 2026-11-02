# ADR decision brief

Prepared 2026-11-02 for the lead. One entry per open decision (ADR-001 to ADR-010). Every recommendation below is a **recommendation for the
lead**; none is a decision, and all ten ADRs stay `Proposed`. Evidence class is stated per fact: **measured** (run in this project),
**read in full** (a paper read to the last page), **reasoned** (no data). Every Wave 5 to 8 result is exploratory by its own entry (dev
repositories only, one encoder, 100 updates, CodeRankEmbed base); no result here is a claim about a trained-to-convergence encoder. Python only.

Short file names: `EXP` = `docs/EXPERIMENTS.md`; `B` = `docs/experiments/B.md`; `ADR-0NN` = `decisions/ADR-0NN-*.md` (addendum date given).
Waves: 5 = E-PILOT-ARMS, 6 = E-PILOT-ARMS2, 7 = E-PILOT-NOISE (three seeds at r = 0.4, two at r = 0.2), 8 = E-PILOT-NOISE-SIB.

## Summary

| ADR | Recommendation (for the lead) | Confidence | Blocked by |
|---|---|---|---|
| 001 pool | Both: the published pool as the comparison population, the unfiltered PR-mined set as the pool on which RAW is defined | medium on the design, low on the mined set's yield (unmeasured) | C: mined set needs the read-only token (D2) and its live stages |
| 002 quality signal | K-rank (SweRank's), reported per teacher with BM25 as the teacher the pool's construction does not favour | medium that it is the signal to test; low that it helps on real labels | C for the real-noise test (unfiltered set, noise audit); not A |
| 003 graph role | Signal, specified as same-file expansion by first-stage score; typed edges only if the stacked test shows they add | medium for file-level expansion, low for typed edges | not blocked; A's resolver-recall work could change the edges; C for any agent-tool role |
| 004 granularity | Both: unit level primary on Verified (D12, D18), chunk level with folder means beside it | medium-high | not blocked; A's development runs for the tuned index (Q59) |
| 005 benchmark | L2 primary, L3 for the graph question reported with its repository term, Verified as the final test, Loc-Bench as a held-out check | medium | not blocked for the decision; C for the paired RQ3 runs |
| 006 encoder | CodeRankEmbed trained in RQ2 (D34); Qwen3-Embedding-0.6B zero-shot only; departs from the master's recommendation, no DEV entry yet | high on feasibility, medium on the science | hardware (no card above 11 GB reachable); not A or C |
| 007 scaffold | Agentless (the master's recommendation) | low (no evidence) | C (agent integration) and ADR-008 |
| 008 base LLM | API model with a pinned version, local quantised model if the budget forbids | low (no evidence) | C (agent integration) and the engineer's budget figure |
| 009 rerank | Include as a measured RQ1 row; keep out of the RQ2 and RQ3 arm comparison until measured | low (no real stage measured) | A (real stage and the RQ1 ladder) |
| 010 usable by others | A documented research artefact; a command-line entry only for the demo configuration | low (scoping, no data) | none |

## ADR-001: training pool

1. **Question.** Which pool trains the RQ2 arms: the published candidate (`gangiswag/train_data` python minus the held-out list, provisional since D22), an own PR-mined set, or both.
2. **Evidence.**
   - E-POOL-CHECK, measured, `EXP`: 24,285 directories (one pull request each) and 307,996 positive rows, not the 49,973 instances of SweRank+ Table 1; 60 (repository, PR) pairs coincide with CORE-Bench L2 queries, all in held-out repositories.
   - E-POOL-RANKS, measured (160 directories, 1,522 positives), `EXP`, ADR-001 addendum 2026-10-25: 39.4% [24.1, 48.0] of positives lie outside SweRankEmbed-Small's top 40, so positives are not filtered one by one; 0 of 160 directories lack a top-10 positive under it against 19.3% [15.7, 23.2] on the never-filtered Verified export, so directories look selected with respect to that teacher.
   - E-PILOT-ARMS2, measured, `EXP`: the 5,000-directory pool has 62,238 positives and 0 held-out directories.
   - E-PILOT-LEAK, measured, 63 updates: applying the held-out list changes dev L2 nDCG@10 by +0.18 [-0.25, 0.57], not detectable (ADR-001 addendum 2026-10-29).
   - E-MINE-PILOT, `B`: code and 85 offline tests on hand-built inputs; no number measured, live stages blocked on `GITHUB_TOKEN`.
3. **Not settled.** Whether the selection is a pull-request filter or the checkpoint's fit to these pull requests (E-POOL-DATES not run, needs the token). What RAW is on an unfiltered set. The yield and cost of mining at scale (M2, M4 unrun). The content-overlap audit of mined corpora is not built (`B`, D65). Q7: whether the published pool is the intended one.
4. **Recommendation (for the lead): both.** RAW on the published pool is "RAW given a pre-selected pull request" (D29), and Waves 5 to 7 say supervision quality can only show where harmful noise exists, so the set whose positives no retriever touched is the one on which RAW has a definition. Keep the published pool as the comparison population so the selection stays measurable.
5. **Cheapest flip.** M3 (rank comparison of the mined set against the published pool), limit 2 GPU-hours (`scripts/ada/README.md`, PROJECT_STATE); E-POOL-DATES is 0 GPU-hours. If the mined set's share of directories with no top-10 positive matches the pool's, the pool is not pre-selected and the published pool alone suffices (reasoned reading of the rule in `B`, item 4).
6. **Blocked.** On C (now with the lead): the token (D2, the engineer's action on the cluster) and the live stages M1 to M4. Not on A.

## ADR-002: quality signal

1. **Question.** FILTER and WEIGHT use SweRank's K-rank, a hand-written heuristic, or a language-model judge.
2. **Evidence.**
   - E-POOL-RANKS, measured, ADR-002 addendum 2026-10-25: Spearman 0.855 [0.791, 0.896] between the two dense teachers and kappa 0.64 at K = 20, so the teacher changes which examples are removed.
   - E-PILOT-ARMS2, measured, two seeds, 100 updates, ADR-002 addendum 2026-10-31: no FILTER, WEIGHT or CURRICULUM cell is above RAW at both levels; FILTER cells are -0.70 to -1.10 below the size-matched subsample at L3. E-PILOT-ARMS: NOISE stays at the untrained encoder, so correct positives matter.
   - E-PILOT-NOISE, measured, three seeds at r = 0.4, `EXP`: RAW loses 3.52 [1.55, 4.90] (L2) and 1.86 [0.97, 2.71] (L3) against the clean anchor (two seeds). Against RAW, FILTER K=20 with SweRankEmbed-Small +3.01 / +2.57 (share of the ORACLE-CLEAN recovery 1.13 / 0.87); FILTER with BM25 +1.82 / +1.19 (0.68 / 0.40); WEIGHT +1.87 / +1.14 (0.70 / 0.38). SweRankEmbed-Small shaped the public pool, so its cells are favoured.
   - Minimum detectable difference at three seeds, r = 0.4: 1.40 (L2) and 2.20 (L3) at query level; 2.16 and 4.88 with the repository term (variance components of E-STORED-ANALYSIS; its own Wave 6 values are 1.10 / 1.02 at query level and 1.85 / 3.08 with the repository term, three seeds). FILTER-BM25 and WEIGHT at L3 (+1.19, +1.14) are below both.
   - E-PILOT-NOISE-SIB, measured, two seeds: sibling noise costs RAW -1.01 [-1.77, 0.06] (L2) and -0.52 [-1.14, 0.12] (L3); the pre-registered sanity check failed, so transfer is unanswered. E-STORED-ANALYSIS: no complementarity between arms beyond seed draws.
3. **Not settled.** Whether real labels hold findable harmful noise (the public pool showed none recoverable in Waves 5 and 6). Transfer from uniform to plausible noise. Heuristics and a judge were never measured. K and weight forms beyond those tried; one encoder; five dev repositories.
4. **Recommendation (for the lead): K-rank.** It is the only published continuous signal and it separates known noise (AUC 0.83 BM25, 0.97 SweRankEmbed-Small, uniform noise). Report each teacher separately and make no positive claim on the public pool.
5. **Cheapest flip.** Hand-read 50 high-K positives (0 GPU-hours, about one hour; ADR-002 addendum 2026-10-29), or two more seeds of RAW and ORACLE-CLEAN under sibling noise (about 1.5 GPU-hours; 3.19 left under the cap of 66).
6. **Blocked.** On C only for the real-noise test (unfiltered set, plus a noise audit by a second reader). Not on A.

## ADR-003: graph role

1. **Question.** The graph as a retrieval signal (hop-decay or expansion), as an agent tool, or as training-time structure.
2. **Evidence.**
   - E-DENSE-FUSION, measured, `EXP`, ADR-003 addendum 2026-10-25: on RRF(BM25, dense), Verified-six stated cell, +4.4 [+0.5, +8.8] L3 Recall@100 over the first stage; over the same-file control +1.4 [-2.3, +5.1].
   - E-GRAPH-ROLE, measured, `EXP`, ADR-003 addendum 2026-10-29: same-file expansion ordered by first-stage score gives +6.5 [3.3, 10.1] (Qwen3 first stage) and +7.7 [4.0, 12.2] (CodeRankEmbed) L3 Recall@100 on Verified-six with no graph; the stored graph minus it is -2.7 [-6.0, 0.8] and -2.0 [-5.2, 0.8].
   - Same entry: non-contain edges reach 8% of missed L3 gold units from the top 5 in two hops, but as an expansion are 6 to 7 points below same-file expansion; containment never leaves a file.
   - Roles B (training-time structure) and C (agent tool): no measurement.
3. **Not settled.** Whether typed edges add anything (the interval allows about -6 to +4). Resolver recall (ADR-012). Training-time and agent-tool roles. The samples are 55 Verified L3 queries and two to three dev L3 repositories.
4. **Recommendation (for the lead): signal.** What the data support is file-level expansion by score, which needs no typed edges; the agent-tool role cannot enter RQ3, which holds the agent fixed. Keep typed edges out of the frozen configuration unless the stacked test below shows a gain.
5. **Cheapest flip.** Stacked expansion at equal budget (same-file by score, the lowest 10 and 25 replaced by non-contain neighbours): 0 GPU-hours, about an hour of code and ten minutes of CPU. About 300 L3 queries would be needed to see 2 points (reasoned), against 155 dev and 55 Verified.
6. **Blocked.** No. A's resolver-recall pilots (A2 b) may change the edge set; any agent-tool role waits for C's agent integration.

## ADR-004: retrieval granularity

1. **Question.** Reported metrics at function level, at CORE-Bench chunk level, or both.
2. **Evidence.**
   - E-GRAPH-REACH, measured, three repositories, `EXP`: 160 of 160 positive chunks found by exact text; 16 (10.0%) map only to residual lines; 13% of positives span several units.
   - E-BM25-REPRO, measured, `EXP`: chunk-level BM25 reproduces the published rows (Verified L2 11.94 / 46.74, L3 22.19 / 33.89) only with a mean over folders; the mean over queries gives 42.92 (L2) and 28.79 (L3) Recall@100 (D17).
   - E-LABEL-NOISE, measured: import-only positives are 12.7% (dev L2) and 6.2% (Verified-six); they carry part of the module unit's benefit.
   - D18 check, ADR-004 addendum 2026-10-23: class-source and ambiguity-policy orderings do not flip between gold readings; some edge-subset orderings do, among overlapping intervals.
   - A1-PILOT, measured locally on five checkouts, `docs/experiments/A.md`: identifier splitting +8.9 MRR [+6.9, +10.5]; an upper bound for issue-style queries.
3. **Not settled.** Q11 (the granularity of the reported number overall). How a chunk spanning several units counts beyond D18. Documentation and configuration positives (rule-of-three bound 2.1%). Non-Python. A1 on issue text.
4. **Recommendation (for the lead): both.** Chunk-level folder means are the only reading shown to reproduce the published rows, and unit level is needed for the graph; D12 already makes unit level primary on Verified. Print the averaging convention next to every number.
5. **Cheapest flip.** A reading that counts a class only through lines outside its methods, from the same stored records: minutes, 0 GPU-hours (ADR-004 addendum 2026-10-23).
6. **Blocked.** No. A's development runs (Q59) decide the tuned index, not the granularity. C's Rewrite-split loaders only extend the chunk-level secondary tables.

## ADR-005: primary benchmark

1. **Question.** CORE-Bench L2, L3 or Loc-Bench as primary.
2. **Evidence.**
   - D12 and D3, ADR-005 addenda 2026-10-17: unit level primary on Verified (432 L2, 302 L3 instances); Loc-Bench kept as a switchable held-out tier of 169 repositories, none of which occurs in the candidate pool.
   - E-CONTAM-SCAN, measured: 26,530 of 194,187 probe functions (13.7%) occur in the corpus. E-CONTAM-EDITED: 70 of 783 edited functions (8.9%), difference -4.8 [-9.7, -0.8] points against the other base-commit functions.
   - E-PILOT-NOISE, measured: at L3 the minimum detectable difference with the repository term is 4.88 against 2.20 at query level; the L3 evaluation rests on two repositories (ansible, E-DEV-ANSIBLE, is built but excluded from Waves 5 to 8).
   - Q12, read: L3 labels are model-judged and the combination of the three votes is not stated; L2 positives include import blocks (3 of 53 sampled).
3. **Not settled.** Loc-Bench was never run as a check. Whether contamination inflates arms equally is assumed, not tested. What L3 labels measure.
4. **Recommendation (for the lead): the master's.** L2 primary, L3 reported with the repository term beside the query-level one, Verified as the final test, Loc-Bench as a held-out check once a trained retriever exists. Absolute rates are not capability claims, so equal inflation across arms is enough for the paired design.
5. **Cheapest flip.** Dev L3 interval widths with and without ansible: about 0.33 GPU-hours per checkpoint to encode ansible (`B`, checkpoint inventory).
6. **Blocked.** Not for the decision; the paired RQ3 set (432 / 302 instances) is run by C.

## ADR-006: base encoder

1. **Question.** CodeBERT, UniXcoder or Qwen3-Embedding-0.6B (master); in practice CodeRankEmbed against Qwen3 (D24). CodeBERT and UniXcoder were not measured.
2. **Evidence.**
   - E-ENCODER-NUMBERS, measured, ADR-006 addendum 2026-10-29: RRF(BM25, Qwen3) minus RRF(BM25, CodeRankEmbed) is +4.29 [2.95, 5.74] (dev L2) and +4.08 [2.85, 5.37] (dev L3); on Verified-six +1.85 [-1.67, 5.50] and +3.43 [0.87, 6.33] (clustered [-1.07, 5.68]), so three of four Verified-six intervals include 0.
   - Same entry: at 32 x (1+1), 512 tokens, float16, checkpointing, CodeRankEmbed trains at 12.2 to 12.4 examples/s, peak 6,880 MiB; Qwen3 runs out of memory at every shape from 32 to 1 on 10.57 GiB usable; no card above 11 GB is reachable from account A.
   - Same entry: query encode p50 18.1 ms (CodeRankEmbed) against 45.2 ms (Qwen3) on GPU, 411 against 1,533 ms on CPU; D35 provisional budget is 500 ms median on CPU.
   - E-PILOT-CURVE and E-PILOT-ARMS2, measured: CodeRankEmbed RAW gains +9.6 (L2) and +11.1 (L3) at 100 updates.
3. **Not settled.** The gap after fine-tuning (zero-shot only). Qwen3 under adapters or 8-bit optimiser states (untried). CodeBERT and UniXcoder. The latency budget is provisional.
4. **Recommendation (for the lead): CodeRankEmbed in RQ2 (D34), Qwen3 zero-shot only.** Qwen3 cannot take one optimiser step on the reachable cards, and the Verified-six gap is not separable from zero in most readings. This departs from the master's recommendation; `docs/DEVIATIONS.md` has no entry for it (checked by search), which the lead may want recorded.
5. **Cheapest flip.** A card of about 24 GB plus an adapter recipe tested on RAW only, one day of cluster time (D34); GPU-hours not stated in the source, and no such card is reachable now.
6. **Blocked.** By hardware only; not by A or C.

## ADR-007: agent scaffold

1. **Question.** SWE-agent, OpenHands, Agentless or a custom scaffold, held fixed across arms in RQ3.
2. **Evidence.**
   - E-POWER, calculation, `EXP`, ADR-007 addendum 2026-10-29: exact McNemar at power 0.8 has a minimum detectable effect of 4.5, 5.5, 6.25 and 7.75 points at n = 432 for discordance 10, 15, 20 and 30%, and 3.25 to 5.25 at n = 900.
   - One fixed-agent retrieval swap read in full differs by -0.6 to +1.2 points on 500 instances, one run each (`paper_reported`), derived discordance about 14%: below every cell.
   - No scaffold has been installed, run or timed in this repository.
3. **Not settled.** Whether any scaffold takes a pluggable retriever unchanged. Install and run cost on the cluster. Discordance and run-to-run spread (need a pilot). Q45: whether RQ3 is a test or an estimate with an interval.
4. **Recommendation (for the lead): Agentless.** It is the smallest fixed pipeline, with retrieval as one call, which keeps the retriever as the only varying input (reasoned, no data). Treat RQ3 as an estimate with an interval unless the smallest difference worth reporting is 5 to 6 points or more.
5. **Cheapest flip.** An agent pilot on about 100 instances, two retrievers, two runs each (ADR-007 addendum); GPU-hours are not estimated in any source and depend on ADR-008.
6. **Blocked.** On C (agent integration and the paired RQ3 runs are on C's roadmap list) and on ADR-008.

## ADR-008: base language model

1. **Question.** A hosted API model or a local quantised model, identical across arms.
2. **Evidence.** None measured: no cost per instance, memory figure or run-to-run reproducibility at fixed temperature and seed exists. One fact bears on it: no card above 11 GB is reachable from account A (E-ENCODER-NUMBERS; `docs/COMPUTE.md`), which bounds any local model. The Block 2 GPU cap is 66 hours with 62.81 used (PROJECT_STATE).
3. **Not settled.** Everything: cost, memory, reproducibility, and the budget figure itself, which is the engineer's.
4. **Recommendation (for the lead): an API model with a pinned version id if the budget allows; otherwise a local quantised model, identical across arms.** Reasoned only: a local model on 11 GB cards forces a small model, whose low absolute resolved rate leaves few discordant pairs to test, while a pinned hosted version avoids that limit.
5. **Cheapest flip.** Count retrieval calls and tokens per instance in the ADR-007 pilot; cost follows by arithmetic. GPU-hours: none for an API, not estimated for a local model.
6. **Blocked.** On C (agent integration) and on the engineer's budget figure.

## ADR-009: cross-encoder rerank

1. **Question.** Include a cross-encoder rerank stage over the fused top 100 or exclude it.
2. **Evidence.**
   - The harness has a `cross_encoder_rerank` stage with 20 rows in `results/latency/latency_log.csv`, all from the synthetic query set `synthetic-v1` on the stub stage: they are not measurements of a reranker.
   - The master's hypothesis (about 500 to 1000 ms for 100 candidates, `docs/07_latency_and_profiling.md`) is unmeasured here. The architecture (`docs/09_architecture.md`) includes the step; the experimental design (`docs/08_experimental_design.md`) does not mention it.
   - E-LAT-STAGES is `planned` in `EXP`; ROADMAP leaves the rerank decision item unticked.
3. **Not settled.** Latency with a real model; nDCG@10 at depth 0, 20, 50 and 100; which cross-encoder; whether a shared reranker would dilute differences between retrievers in RQ2 and RQ3 (reasoned, not tested).
4. **Recommendation (for the lead): include as a measured RQ1 row, keep it out of the arm comparison until measured.** A stage applied to every arm re-orders the candidates that the trained retrievers differ on, so it can only shrink the effect RQ2 is trying to see (reasoned).
5. **Cheapest flip.** The depth ladder on the dev queries, about 50,600 pair scores (reasoned count); under 1 GPU-hour, reasoned and not an estimate because the model is not chosen.
6. **Blocked.** On A (the real stage and the RQ1 latency ladder).

## ADR-010: usable by others

1. **Question.** Whether RIL is built for use by others (command line, install story, configuration surface) or as a research artefact.
2. **Evidence.** No measurement applies. The CORE-Bench card states `cc-by-nc-sa-4.0`, so anything derived from it and released needs a licence check (ADR-010 addendum 2026-10-17). The repository already separates `configs/frozen/` from `configs/demo/`.
3. **Not settled.** The effort of packaging and the intended audience; this is a scoping decision, not an empirical one.
4. **Recommendation (for the lead): a documented research artefact with a command-line entry for the demo configuration only.** The contribution is the experiment, and the benchmark licence limits what can be released. This is reasoned scoping.
5. **Cheapest flip.** None; 0 GPU-hours.
6. **Blocked.** No.
