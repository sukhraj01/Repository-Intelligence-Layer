# Plan for the full mining run (prepared, not started)

Evidence class: **measured at pilot scale, extrapolated linearly** (exploratory). Unit costs are those of `m4_scale.md` (pilot of 2026-11-02/03: 200 repositories, 2,000 attempted
pull requests). Nothing in this plan has been run at the target scale, and none of the commands below has been run. This version follows the engineer's decisions D93 (de-duplicated
store with a materialise step) and D94 (target 10,000 attempted pull requests, mining on node-local disk, store and run state on account C's home). Earlier versions planned
20,000 attempted pull requests with the run root on a shared area; the 5,000 and 20,000 rows stay in the table for reference only.

## Target sizes (attempted pull requests, of the 1,473 repositories of the population)

| Attempted | Mined (69.55%) | Pool-like directories (a positive outside test files; 64.3% of attempted, from 1,286 of 2,000) | Disk, stored as before (1.84 MB per mined directory) | Disk, de-duplicated store (0.285 MB per mined directory, pilot density) | Mining wall time, one process (10.3 s per attempted) | REST calls (1.007 each) | Time at the REST limit (5,000 per hour) |
|---|---|---|---|---|---|---|---|
| 5,000 | 3,478 | 3,215 | 6.4 GB | 1.0 GB | 14.3 h | 5,035 | 1.0 h |
| **10,000 (D94)** | **6,955** | **6,430** | 12.8 GB | **2.0 GB or less** | **28.5 h** | **10,070** | **2.0 h** |
| 20,000 | 13,910 | 12,860 | 25.6 GB | 4.0 GB | 57.1 h | 20,140 | 4.0 h |

The store figure is the measured store of the pilot, 396,746,195 bytes for 1,391 directories (`docs/experiments/B.md` E-MINE-STORE), times the number of mined directories. The share of the store that
is rows and digests grows more slowly than the number of directories (more pull requests per repository repeat more rows), so 2.0 GB is an upper estimate at this density and not a measurement at
10,000. The `pool_aligned` reading keeps 240 of the 300 directories the `non_test` reading keeps (80%) on the BM25 sample, so about 5,100 of the 6,430 pool-like directories are expected under it (an
estimate from 300 directories).

Listing is the same for every target because the selection is a seeded sample of all linked pull requests of the repositories listed: 1,473 repositories, about 28,016 pages
(950.985 merged pull requests per repository, 50 per page) at 4.55 s per page: 35.4 hours in one process, 11.8 hours over three listing jobs (the pilot's shape), 5.6 hours of GraphQL
budget (one point per page, 5,000 per hour). Linked pull requests expected: about 174,000 (12.4% of about 1.40 million merged). The API limit never binds; the miner's own wall time does.

Yield caveat: the pilot's numbers come from a seeded sample over 200 repositories dominated by a few very large ones (airflow 319 of the first 1,437 attempted); over 1,473 repositories
the mix, and so the yield per attempted pull request and the bytes per directory, will differ. The extrapolation is linear in the pilot's rates and carries no interval.

## Where things live (D94)

| What | Where | Why |
|---|---|---|
| Base-commit working repositories; the run root while it is being mined | node-local `$TMPDIR` of the compute node (1.7 TB free on the node probed; `storage_survey.md`) | large, regenerable, lost with the node |
| De-duplicated store, `pr/<dir>` small files and manifests, listings, `state.jsonl`, logs | `$HOME/ril_mine/store/full` on **account C** (28 GB free on 2026-11-05) | durable; the 10,000 target is about 2 GB |
| Directory layout for a job (ranks, training) | rebuilt on the node-local disk of that job by `materialise` | readers unchanged; byte-identical to the layout the miner wrote before (1,391 of 1,391 pilot directories) |

**Account C has no `GITHUB_TOKEN` in its environment** (presence tested on 2026-11-05, value never printed). A mining job cannot run there until the engineer sets one (read-only, as on
account A). This part of the plan is blocked on that; nothing else waits for it. Account C has no SSH alias in the local configuration; the commands use `<C>` for the alias the engineer adds
(`docs/COMPUTE.md`) and `<A>` for account A's.

## Memory (measured on the pilot, job 58615 at commit 3622e71)

- Mining session (earlier, unchanged): the corpus is streamed (DEV-028), peak 4.0 GB `sacct` MaxRSS on the largest snapshot (630,017 functions). Listings: the 200 pilot listings take 265 MB, about 2 GB for
  1,473 repositories (estimate). Expected peak about 4 GB plus about 2 GB plus the background fetches, below the 12 GB requested (estimate).
- Store writer: the conversion of all 1,391 pilot directories peaked at 2,161 MB (process peak), including the largest corpus (946,825 distinct rows in the largest repository). The writer's own addition
  per directory is the digests of that repository's rows (20 bytes each plus a dictionary slot). The mining session was not run with the new writer, so its combined peak is an estimate (the 4 GB snapshot peak plus this addition).
- `materialise`: 3,435 MB process peak, one repository's decompressed rows at a time (largest: 946,825 rows). Time on node-local disk: **695.5 s for the 1,391 pilot directories** (0.50 s per directory, dominated
  by compressing the 22.7 GB of corpus text at level 6); the first run took 726.2 s. By that rate the 6,430 pool-like directories of the 10,000 target take about 54 minutes per full materialisation (linear estimate),
  so a job should materialise only the directories it needs (`--names`).

## Order of repositories and resumption

- Listing order: `sha256("0:<repository>")` over the 1,473 repositories of the population (the same order as the pilot, so the first 200 are the pilot's repositories and their stored listings can be reused by copying `listing/*.json` into the store directory before the first session; listings are plain JSON, so the copy is exact).
- Mining order: the linked pull requests of all listed repositories sorted by `sha256("0:<repository>#<number>")`; the run mines the first `max_prs` (10,000, `configs/mining/full.yaml`). The first 5,000 of the 10,000
  are the first target: a bounded session (`STOP_AFTER=5000`) attempts 5,000 **more** pull requests in that session, because finished ones are skipped. The configuration hash includes `max_prs`, so a different `max_prs` needs a new store.
- Commit order of a push. A job writes in node-local space and pushes to the durable directory every 25 outcomes or 10 minutes (`SYNC_EVERY`, `SYNC_SECONDS`) and at the end. Each push copies, in this order:
  (1) the repository rows (`cas/*/rows.gz`, `digests.bin`, then `segments.jsonl`, the commit record), (2) the new `pr/<dir>` directories, (3) the new listings, (4) the append-only logs with `state.jsonl` last, (5) the small files.
  A state row is therefore never durable before its directory and rows. A push that finds a destination longer than its source, or whose last bytes differ, stops with an error and overwrites nothing; nothing is ever deleted.
- **Resumption procedure.**
  (a) A job ended before `done` (node lost, wall time, `scancel`): leave the durable directory alone and submit the same `sbatch` command again. The job finds no run root on its new node, restores the durable one into
  node-local space, skips every pull request with a state row, adopts a complete directory that has none, and continues. Work lost: the pull requests mined since the last push (at most 25 outcomes or 10 minutes) and the one in flight.
  (b) Never run two mining jobs on one durable directory (the three listing shards are the exception: they write disjoint files). `squeue -u $USER` must show no mining job before a resubmission.
  (c) To look before resubmitting: `ssh <C> 'wc -l < ril_mine/store/full/state.jsonl; ls ril_mine/store/full/pr | grep -vc "\.tmp$"'`. The directories may exceed the state rows by the ones the next session adopts; the state rows must never exceed the directories.
  (d) Integrity: opening a repository's rows cuts back an unfinished append, so a push interrupted at any byte leaves a readable store. The pilot check (store, rebuild, compare every byte) is `scripts/ada/mine_store_proof.sbatch`.
- The queue limit for these accounts is four days of wall time (`sacctmgr` QOS `low`, MaxWall 4-00:00:00; checked 2026-11-03); 28.5 hours of mining for 10,000 attempted fit in one session after the listing. Chain sessions with
  `--dependency=afterany` so a node loss costs only the unpushed work. Nodes whose file-system client hangs (two observed) are excluded with `--exclude`.

## Order of work and commands (not run)

Prerequisites (**engineer**): `GITHUB_TOKEN` set on account C; an SSH alias `<C>` for it; this branch merged. From the repository root on the engineer's machine:

    # 0. token presence on C (value never printed); must print token_nonempty
    ssh <C> 'if [ -n "${GITHUB_TOKEN:-}" ]; then echo token_nonempty; else echo token_absent; fi'
    # 1. stage the code, configs and held-out files on C; the population listing is read from $HOME/ril_s2/raw/ziplist_train.json, stage it under the same path
    rsync -a --exclude __pycache__ ril scripts configs <C>:ril_mine/ && rsync -a data/held_out/held_out_repos.json data/held_out/rename_cache.json <C>:ril_mine/data/held_out/
    # 2. optional: seed the store directory with the pilot's listings (plain JSON), from A through the engineer's machine
    ssh <A> 'tar cf - -C ril_mine/runs/pilot listing' | ssh <C> 'mkdir -p ril_mine/store/full && tar xf - -C ril_mine/store/full'
    # 3. on C, from $HOME: listing, three jobs (every third repository); each pushes its listing files to the store directory at its end
    for i in 0 1 2; do sbatch --cpus-per-task=1 --mem=3G --time=12:00:00 --exclude=gnode004,gnode044 \
      --export=ALL,CONFIG=configs/mining/full.yaml,RUN=full,CREATED=<YYYY-MM-DD>,LIST_ONLY=1,SHARD="$i 3",DURABLE=$HOME/ril_mine/store/full,RIL_COMMIT=<hash> \
      ril_mine/scripts/ada/mine_pilot.sbatch; done
    # 4. mining, a first session bounded to 5,000 attempted (STOP_AFTER counts the pull requests attempted in that session)
    J=$(sbatch --parsable --mem=12G --time=4-00:00:00 --exclude=gnode004,gnode044 \
      --export=ALL,CONFIG=configs/mining/full.yaml,RUN=full,CREATED=<YYYY-MM-DD>,LOOKAHEAD=6,STOP_AFTER=5000,DURABLE=$HOME/ril_mine/store/full,SYNC_EVERY=25,SYNC_SECONDS=600,RIL_COMMIT=<hash> \
      ril_mine/scripts/ada/mine_pilot.sbatch)
    # 5. the next 5,000 (10,000 in all): the same command with --dependency=afterany:$J, a chain of sessions
    # 6. report, once a stage is finished (reads the durable directory; JSON files only)
    python3 -I ril_mine/scripts/mine_pilot.py report ril_mine/store/full ril_mine/store/full/report.md
    # 7. a job that needs the directory layout (ranks, training) rebuilds it on its own node-local disk, then reads it in the reading it needs
    #    (the primary reading for RQ2 is non_test, the reading of M3 (D96, evidence: measured on 300 directories, exploratory);
    #    pool_aligned is a sensitivity reading, reported on the pilot and not recomputed for the full set unless a later result needs it)
    python3 -I ril_mine/scripts/mine_pilot.py materialise ril_mine/store/full "$TMPDIR/view" \
      && python3 -I ril_mine/scripts/mine_pilot.py rank-prepare "$TMPDIR/view" "$TMPDIR/work" --reading non_test

The pool-like rank measurement (M3) is a separate GPU stage with its own limit and is not part of this plan; its cost at 178 texts per second is in `m3_ranks.md`.

## Step 8 (after mining): content-overlap audit of the full store (E-OVERLAP-AUDIT, D105)

Run once the mining sessions are done. The held-out index is built once and reused (`$HOME/ril_ov/index/v1`; stage the code with `rsync -a --exclude __pycache__ ril scripts <A>:ril_ov/`). The job reads the store and writes only under `$HOME/ril_ov`; the store on C is not read in place from A, so either copy it to A first (a numbered script, engineer runs it) or run the job on C with the same sbatch after staging the held-out inputs there.

    sbatch --export=ALL,STORE=$HOME/ril_mine/store/full,RUN=full,RIL_COMMIT=<hash> ril_ov/scripts/ada/overlap_audit.sbatch

Estimate (linear in distinct rows, from the pilot): the pilot audit took 1,445 s for a 0.44 GB store; the full store is up to 2 GB, so about 1.5 to 2 hours, plus 13 minutes for the index if it is not built; peak 4.84 GB on the pilot, the largest repository decides at full scale (12 GB asked). Then `apply` lists the directories to drop; training reads the store through the reading with those names removed.

