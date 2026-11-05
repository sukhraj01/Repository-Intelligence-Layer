# Plan for the full mining run (prepared, not started)

Evidence class: **measured at pilot scale, extrapolated linearly** (exploratory). Unit costs are those of `m4_scale.md` (pilot of 2026-11-02/03: 200 repositories, 2,000 attempted
pull requests). Nothing in this plan has been run at the target scale. Choices marked **engineer** are not made by the session.

## Target sizes (attempted pull requests, of the 1,473 repositories of the population)

| Attempted | Mined (69.55%) | Pool-like directories (with a positive outside test files; 64.3% of attempted, from 1,286 of 2,000) | Disk, stored as now (1.84 MB per mined directory) | Disk, content-addressed store (13.5% of that at pilot density; a lower bound on the saving) | Mining wall time, one process (10.3 s per attempted) | REST calls (1.007 each) | Time at the REST limit (5,000 per hour) |
|---|---|---|---|---|---|---|---|
| 5,000 | 3,478 | 3,215 | 6.4 GB | 0.9 GB | 14.3 h | 5,035 | 1.0 h |
| 10,000 | 6,955 | 6,430 | 12.8 GB | 1.7 GB | 28.5 h | 10,070 | 2.0 h |
| 20,000 | 13,910 | 12,860 | 25.6 GB | 3.5 GB | 57.1 h | 20,140 | 4.0 h |

Listing is the same for every target because the selection is a seeded sample of all linked pull requests of the repositories listed: 1,473 repositories, about 28,016 pages
(950.985 merged pull requests per repository, 50 per page) at 4.55 s per page: 35.4 hours in one process, 11.8 hours over three listing jobs (the pilot's shape), 5.6 hours of GraphQL
budget (one point per page, 5,000 per hour). Linked pull requests expected: about 174,000 (12.4% of about 1.40 million merged). The API limit never binds; disk and the miner's own wall time do.

Yield caveat: the pilot's numbers come from a seeded sample over 200 repositories dominated by a few very large ones (airflow 319 of the first 1,437 attempted); over 1,473 repositories
the mix, and so the yield per attempted pull request and the bytes per directory, will differ. The extrapolation is linear in the pilot's rates and carries no interval.

## Disk and where it goes (see `storage_survey.md`)

- Account A's home has 2.9 GB free: none of the three targets fits as stored now. **Engineer:** the location (recommended: account C's home, which has 28 GB, with the token set there; or a node-local run root with only the de-duplicated store kept on a shared area).
- The de-duplicated store (`dedup_measure.md`: 86.5% saving at pilot density) would bring 20,000 attempted to about 3.5 GB; it needs a build step (not built, **engineer** decision, option B of `dedup_measure.md`).

## Memory (changed in this branch; measured)

- Before: the mining session peaked at 10.0 GB of 10 GB (job 54612, `sacct` MaxRSS). The cause measured on the largest snapshot of the pilot (630,017 functions): the corpus file was built as one string in memory, 3.8 GB after parsing and mining the pull request and **7.8 GB** after building the file bytes.
- Now: the corpus is streamed into its compressed file (`ril/data_mining/files.py`). The same pull request: 3.8 GB python peak, 4.0 GB `sacct` MaxRSS (job 56200), output **byte-identical** to the pilot directory. A repeat of the 462 mined pull requests of the pilot's first 20 repositories (job 55976, 2 h 18 min): **462 of 462 directories byte-identical**, `sacct` MaxRSS **3.16 GB** (that sample does not contain the largest snapshot).
- Listings: the 200 pilot listings take 265 MB in memory (job 55965); 1,473 repositories would take about 2 GB by the same ratio (an estimate, not measured at that scale). So the expected peak of a full session is about 4 GB (largest snapshot) plus about 2 GB (listings) plus the background fetches, below 10 GB, an estimate.
- **Streamed listings were not implemented:** the measurement shows the listings are not the cause of the 10 GB peak (DEV-028). If the engineer wants them anyway, the cost is a change to `select_prs`, the summary and the yield functions; the first measurement to repeat is the full-population listing in memory.

## Order of repositories and resumption

- Listing order: `sha256("0:<repository>")` over the 1,473 repositories of the population (the same order as the pilot, so the first 200 are the pilot's repositories and their stored listings can be reused by copying `listing/` into the new run root).
- Mining order: the linked pull requests of all listed repositories sorted by `sha256("0:<repository>#<number>")`; the run mines the first `max_prs` of that order. **The 5,000 are the first 5,000 of the 20,000**: one run root with `max_prs: 20000` and bounded sessions (`STOP_AFTER=5000` attempts 5,000 **more** pull requests in that session, because finished ones are skipped) gives the three targets after one, two and four such sessions, without a second run (the configuration hash includes `max_prs`, so a different `max_prs` needs a new root and cannot reuse state).
- Resumption: the state log and the directory-per-pull-request layout are resumable and idempotent (a finished pull request is skipped, a directory without a state row is adopted). The queue limit for this account is four days of wall time (`sacctmgr` QOS `low`, MaxWall 4-00:00:00; checked 2026-11-03), so one session can run up to 96 hours: 57 hours of mining for 20,000 attempted fit in one session after the listing; chain sessions with `--dependency=afterany` so a node loss costs only the pull request in flight. Nodes whose file-system client hangs (observed on two nodes of the cluster) are excluded with `--exclude`.

## Order of work and commands (not run)

Prerequisites (**engineer**): the location (above); `GITHUB_TOKEN` on the account that will run it; the configuration `configs/mining/full.yaml` (whole population, `max_prs: 20000`).
From `$HOME` of that account, after staging `ril`, `scripts` and `configs` under `ril_mine/`:

    # 1. listing, three jobs (every third repository); copy the pilot's stored listings into runs/full/listing first if the pilot is on the same account
    for i in 0 1 2; do sbatch --cpus-per-task=1 --mem=3G --time=12:00:00 --exclude=gnode004,gnode044 \
      --export=ALL,CONFIG=configs/mining/full.yaml,RUN=full,CREATED=<YYYY-MM-DD>,LIST_ONLY=1,SHARD="$i 3",RIL_COMMIT=<hash> \
      ril_mine/scripts/ada/mine_pilot.sbatch; done
    # 2. mining, a first session bounded to 5,000 attempted (STOP_AFTER counts the pull requests attempted in that session)
    J=$(sbatch --parsable --mem=12G --time=4-00:00:00 --exclude=gnode004,gnode044 \
      --export=ALL,CONFIG=configs/mining/full.yaml,RUN=full,CREATED=<YYYY-MM-DD>,LOOKAHEAD=6,STOP_AFTER=5000,RIL_COMMIT=<hash> \
      ril_mine/scripts/ada/mine_pilot.sbatch)
    # 3. the next target: the same command with --dependency=afterany:$J (and STOP_AFTER=5000 again for 10,000 in all, 10000 more for 20,000), a chain of sessions
    # 4. report, once a stage is finished: python -I ril_mine/scripts/mine_pilot.py report ril_mine/runs/full ril_mine/runs/full/report.md

The pool-like rank measurement (M3) is a separate GPU stage with its own limit and is not part of this plan; its cost at 178 texts per second is in `m3_ranks.md`.
