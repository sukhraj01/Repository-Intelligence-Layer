# M4: scale cost of the mining run (E-MINE-PILOT question 5)

Evidence class: **measured at pilot scale, extrapolated linearly** (exploratory). Inputs: the pilot of M2 (200 repositories,
2,000 attempted pull requests; `results/logs/mine_pilot_2026-11-03.json`, `results/logs/mine_pilot_listing_shards_2026-11-02.json`,
`m2_summary.json`). Command (code at the commit of this file):

    python3 -I scripts/mine_pilot.py scale m2_summary.json report.costs.json --listing-seconds 18758.5 \
      --free-bytes 5495586816 --targets 200:23670 1473:20000 1473:100000 2000:20000 2000:100000

(`report.costs.json` is written by `scripts/mine_pilot.py report`; `--free-bytes` is `df -B1 $HOME` at the end of the pilot,
the space free on the shared home file system; `--listing-seconds` is the sum of the listing jobs' seconds.) Full output:
`m4_scale.json`.

## Measured unit costs (pilot)

| quantity | value | from |
|---|---|---|
| merged pull requests per repository | 951 (190,197 over 200; heavy-tailed) | listings |
| linked share of merged pull requests | 12.4% (23,670 of 190,197) | listings |
| listing page (50 pull requests) | 4.55 s, 1 GraphQL point | 4,122 calls, 18,758.5 s summed over jobs |
| REST calls per attempted pull request | 1.007 | 2,014 compare calls for 2,000 |
| mining wall time per attempted pull request | 10.3 s with 6 base commits fetched ahead (2 CPUs) | 20,542 s for 2,000 |
| mined share of attempted | 69.6% (1,391 of 2,000) | state log |
| bytes per mined directory | 1.84 MB compressed, 4 files | `pr/` 2,560,066,615 bytes for 1,391 |
| peak memory of the mining session | 10,001,100 KB of 10 GB requested | `sacct` MaxRSS of job 54612 |

## Extrapolation

| repositories | attempted (linked) pull requests | listing pages | GraphQL points | REST calls | API time at the hourly limit | wall at the measured rate (one process) | 12-hour sessions | mined directories | disk | binding |
|---|---|---|---|---|---|---|---|---|---|---|
| 200 (pilot population, all linked) | 23,670 | 3,804 | 3,804 | 23,836 | 4.8 h | 72 h | 7 | 16,462 | 30.3 GB | disk (5.5 times the 5.5 GB free) |
| 1,473 | 20,000 | 28,016 | 28,016 | 20,140 | 5.6 h | 92.5 h | 8 | 13,910 | 25.6 GB | disk (4.7 times) |
| 1,473 | 100,000 | 28,016 | 28,016 | 100,700 | 20.1 h | 321 h | 27 | 69,550 | 128 GB | disk (23 times) |
| 2,000 | 20,000 | 38,039 | 38,039 | 20,140 | 7.6 h | 105 h | 9 | 13,910 | 25.6 GB | disk (4.7 times) |
| 2,000 | 100,000 | 38,039 | 38,039 | 100,700 | 20.1 h | 334 h | 28 | 69,550 | 128 GB | disk (23 times) |

The population of the 5,000-directory pool has 1,473 repositories after the held-out filter, so a run over 2,000 repositories is
larger than the population; the 1,473-repository rows are the whole population.

## Which constraint binds

1. **Disk first.** At the measured 1.84 MB per mined directory the 20,000-pull-request target needs 25.6 GB and the 100,000 target
   128 GB, against 5.5 GB free on the shared `$HOME` (50 GB file system at 90%). Even the pilot's own 200 repositories mined in full
   would need 30 GB. No full run starts before a place for the output exists (another file system, or a storage form with fewer
   bytes per pull request; the whole corpus of the snapshot is stored per pull request because the pool's format has one corpus per
   directory).
2. **Then wall time of the miner, not the API.** The REST limit (5,000 per hour) needs 20 hours for 100,000 pull requests; the
   miner at 10.3 s per attempted pull request needs 285 hours of mining for the same number, in one process. The time goes to the
   shallow fetch of the base commit (100 to 300 s for a large repository when fetched alone) and the parse of the snapshot
   (about 17 to 32 s for airflow at one commit); the fetch overlaps with parsing at `LOOKAHEAD=6`. Sharding the mining over several
   jobs by repository (not built: sessions share one state log) would divide it by the number of jobs.
3. **Memory.** The mining session held all listings in memory: 10.0 GB peak of 10 GB requested at 200 repositories (120 MB of
   listing files). A run over 1,473 repositories has about seven times the listing volume; it will not fit in 10 GB and needs the
   listings streamed per repository (not built) before it can start.
4. **Listing** is not binding: 28,016 pages for the population at 4.55 s are 35 hours in one job, 12 hours over three shards, and
   the GraphQL budget (5,600 points per hour sustained would be needed to beat the wall time) is the next limit after six shards.

## The command for the full run (not started)

Configuration `configs/mining/full.yaml` (whole population, `max_prs: 20000`; set 100000 for the larger target). After the output
location, the memory change (3) and the sharded mining exist, from `$HOME` on a login with the token:

    for i in 0 1 2 3 4 5; do sbatch --cpus-per-task=1 --mem=3G \
      --export=ALL,CONFIG=configs/mining/full.yaml,RUN=full,CREATED=<YYYY-MM-DD>,LIST_ONLY=1,SHARD="$i 6" \
      ril_mine/scripts/ada/mine_pilot.sbatch; done
    # then chained 12-hour mining sessions of the same configuration (resumable, no call when finished):
    J=$(sbatch --parsable --mem=24G --export=ALL,CONFIG=configs/mining/full.yaml,RUN=full,CREATED=<YYYY-MM-DD>,LOOKAHEAD=6 \
      ril_mine/scripts/ada/mine_pilot.sbatch)
    for k in 2 3 4 5 6 7 8; do J=$(sbatch --parsable --mem=24G --dependency=afterany:$J --export=ALL,CONFIG=configs/mining/full.yaml,RUN=full,CREATED=<YYYY-MM-DD>,LOOKAHEAD=6 ril_mine/scripts/ada/mine_pilot.sbatch); done

Eight sessions of 12 hours cover the 92.5 hours of the 1,473 / 20,000 row. Run as written the first session would run out of memory
(3) and the output would not fit (1); the commands are the exact form once those two are changed, not a statement that they work now.
