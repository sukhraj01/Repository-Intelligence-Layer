# M3: rank measurement of the mined set (E-MINE-PILOT question 4)

Evidence class: **measured, exploratory** (live data of the pilot of M2; ranks by the published definition of
`ril.training.pool_ranks`: 1 plus the non-positive functions scored strictly higher, minimum over a directory's positives; code text,
cut 1,024 tokens, float16). Tables: `m3_rank_shares.json` (pool-like reading), `m3_rank_shares_as_mined.json`. Run log
`results/logs/mine_ranks_2026-11-03.json`. Commands: `mine_ranks_cpu.sbatch` and `mine_ranks.sbatch` (`scripts/ada/README.md`), tables with

    python3 -I scripts/mine_pilot.py rank-tables <work dir> m3_rank_shares.json --ranks ranks_bm25.jsonl ranks_dense.jsonl --yield-per-pr 0.643

Reading rule (written before the run, `README.md` of this folder): compared only with at least 100 directories that have a positive;
two shares differ only if each lies outside the other's interval. Reading rule met: 300 directories (BM25, SweRankEmbed-Small),
254 (CodeRankEmbed) with a positive.

## What was measured, and what was not (DEV-027)

- **Pool-like reading**: corpora without test-file functions, positives without test positives (the pool has neither; M1). Of the
  1,391 mined directories 1,286 keep a positive. The first 300 of them in the seeded order `sha256("0:<directory>")` (89 repositories)
  are the set. BM25 ran on all 300; SweRankEmbed-Small on all 300; CodeRankEmbed on **254** (72 repositories): the job reached its
  time limit (1 h 18 min) in the second teacher, and the directories are processed repository by repository, so the 254 are whole
  repositories, not a random part of the 300.
- **Not measured**: SweRankEmbed-Small on the stored text (the form of the 19.3% Verified row; the third pass did not start inside the
  limit), and the dense teachers in the as-mined reading (3.3 GPU-hours estimated for three passes at 320 texts per second on the first 252
  directories; the measured rate was 178 texts per second, so the estimate was low).
- GPU: 1.99 GPU-hours of the stage limit 2.0 (jobs 54914, 54915, 54936, 55027; two of them produced nothing, one was held idle by a
  file-system hang on a node; the ledger has the rows). Block 2 ledger total 64.80 of the cap 66.

## Share of directories with no positive in the top K (pool-like reading)

| teacher (code text) | K | mined set | published pool (E-POOL-RANKS, pool estimate) | never-filtered Verified export |
|---|---|---|---|---|
| BM25 | 10 | **53.3%** [47.7, 58.9] (160 of 300; repository-clustered [40.9, 60.6]) | 23.2% [16.4, 31.0] | no row |
| CodeRankEmbed | 10 | **40.2%** [34.3, 46.3] (102 of 254; clustered [30.3, 45.7]) | 15.3% [8.8, 22.2] | 35.7% [31.3, 40.3] |
| SweRankEmbed-Small | 10 | **31.3%** [26.4, 36.8] (94 of 300; clustered [25.8, 36.5]) | 1.7% [0.2, 3.9] | 19.3% (stored text, not the form measured here) |
| BM25 | 40 | 36.3% [31.1, 41.9] | 13.4% [8.0, 19.6] | |
| CodeRankEmbed | 40 | 25.2% [20.2, 30.9] | 4.3% [1.6, 8.0] | 17.5% [14.1, 21.3] |
| SweRankEmbed-Small | 40 | 21.3% [17.1, 26.3] | 1.3% (exact [0.15, 4.4]) | 9.4% (stored text) |

Intervals of the mined set: directory-level Wilson (K = 20 and the clustered bootstrap are in the JSON). Pool and Verified values are quoted from
`docs/EXPERIMENTS.md` E-POOL-RANKS (`results/tables/x3_pool_ranks_topk.csv`, `x3_pool_ranks_reference.csv`; `paper_reported` does not apply, they are
measured earlier in this project). The as-mined reading with BM25 on 300 directories (87 repositories, test functions in the corpora,
test positives kept): 53.3% [47.7, 58.9] at K = 10, the same count as the pool-like reading.

## Reading

By the stated rule, the mined set and the published pool **differ** under all three teachers: each point estimate of the mined set lies
outside the pool's interval and conversely (BM25 53.3% against 23.2%; CodeRankEmbed 40.2% against 15.3%; SweRankEmbed-Small 31.3% against 1.7%).
Under CodeRankEmbed, the one teacher with a Verified row of the same text form, the mined set (40.2% [34.3, 46.3]) and the never-filtered
Verified export (35.7% [31.3, 40.3]) are **indistinguishable at this size**. The gap to the pool is largest for the teacher that is
the pool's own filter (SweRankEmbed-Small: 31.3% against 1.7%). This is what the earlier finding (E-POOL-RANKS: directories look
selected with respect to SweRankEmbed-Small) predicts for an unfiltered set; it is consistent with it and does not prove the pool's selection rule.

Caveats, all stated before reading the numbers: (1) the candidate sets are built differently (the pool has nested functions and no
`async def`; the miner the reverse; M1); (2) the mined positives include pure insertions and removed functions that the pool does not
label (M1), which can make a directory easier or harder; (3) the CodeRankEmbed set is 254 whole repositories, not a random part;
(4) the mined repositories are those of the pool, the Verified export is a different repository set, so no difference between the mined set and
Verified is attributed to selection; (5) one pilot, one seed. The comparison is exploratory and outside the pre-registered RQ tables.
