# Storage survey for the full mining run (read-only; 2026-11-03)

Evidence class: **measured** (`df`, `quota -s`, `ls -ld`, `test -w`, `sinfo`, one compute-node probe job, job 55961). No login names or home paths are given; accounts are
the letters of `docs/COMPUTE.md`. Nothing was written to any file system for this survey and nothing was deleted. The cluster's own documentation pages were not
reachable from the machines used; **backup and purge policies are not stated anywhere reachable, so they are unknown** (marked below), not assumed.

## Table

| Area | Type, size | Free (account A's view) | Per-user limit | Writable by account A | Visible on login node | Visible on compute nodes | Backup, purge |
|---|---|---|---|---|---|---|---|
| Home file system of account A | network file system, one 50 GB dataset per user, shared server | **2.9 GB** (95% used) | the dataset size (50 GB) | yes | yes | yes | unknown |
| Per-user area on the first shared mount (`share1`) | network file system, 95 TB mount | **3.1 GB below the soft quota** (21.8 GB of 25 GB used by older project files that are not part of this work) | quota 25 GB soft, 27 GB hard; 3,000 files soft, 3,200 hard | yes | yes | **no** (the mount is absent on the node probed) | unknown |
| Other shared mounts (`share2`, `share3`, `share6`, a 82 TB mount used by another group) | network file systems, 13 to 95 TB | 7.5 TB, 0.5 TB (98% used), 46 TB, 4.3 TB (95% used) | none seen | **no** (root-owned, no directory for account A) | yes | **no** | unknown |
| Datasets mount (`share7`) | network file system, 29 TB | 7.8 TB | none seen | **no** (root-owned) | yes | yes | unknown |
| Software mounts (`software`, a 49 TB mount named for the partition) | network file systems | 440 GB and 49 TB | none seen | no (root-owned, software only) | yes | yes | not applicable |
| Node-local `/tmp` | ext4 disk of each compute node, 1.8 TB (7% used on the node probed) | 1.7 TB | none seen | yes | a different disk on the login node (222 GB free, not shared) | yes, **this node only**, not shared between nodes | unknown; this project deletes its files at job exit |
| `/dev/shm` | memory, 63 GB | 63 GB | counts against the job's memory | yes | yes | yes, this node only | lost at job exit |
| Home of account B (course account) | network file system, 25 GB | **22 GB** | the dataset size | yes, as B | yes | yes | unknown |
| Home of account C | network file system, 50 GB | **28 GB** (45% used; the owner's files are in it) | the dataset size | yes, as C (work only under the `ril_*` directories) | yes | yes | unknown |
| Per-user area of account C on `share1` | network file system | 25 GB (4 KB used) | quota 25 GB soft; 3,000 files | yes, as C | yes | no | unknown |

Accounts B and C have **no `GITHUB_TOKEN`** in their environment (presence tested, never printed); a mining job cannot run on either until the engineer sets one.
Cross-account writes are not possible (each home is private to its owner); data moves between accounts through the engineer's machine or a shared readable area.

## What is needed

| Target | Output as stored now (compressed, 1.84 MB per mined directory, 69.6% of attempted mined) | With a content-addressed store (measured saving 86.5% on the pilot; extrapolation to larger runs is **not measured**: the saving grows with the number of pull requests per repository) |
|---|---|---|
| 20,000 attempted | 25.6 GB | about 3.5 GB (13.5% of 25.6 GB) |
| 100,000 attempted | 128 GB | about 17 GB (same ratio, a lower bound on the saving) |

## Recommendation (marked as a recommendation; the choice of location is the engineer's)

- **No area writable by account A can hold either target in the form stored now.** Account A's home has 2.9 GB free.
- **25.6 GB (20,000 attempted):** produce the output on the node-local disk of the compute node (1.7 TB free; the run root is rebuilt from the state log if a
  node is lost, so keep the state log and the packed result on a shared area), and keep on a shared area only the compressed, de-duplicated store (about 3.5 GB;
  `results/mining/dedup_measure.md`). That fits account C's home (28 GB free) with a margin, and account A's home only if the engineer first frees about 1 GB of
  superseded run roots (cleanup commands in the session notes of 2026-11-03).
- **128 GB (100,000 attempted):** the stored form does not fit any area we can write (the largest, 28 GB on account C). The de-duplicated form (about 17 GB, an extrapolation)
  fits account C's home. If the de-duplicated store is not adopted, a quota or a project area from the cluster administrators is needed; no such area exists today.
- Whatever the location, a mining job must run as the account that owns it and that account needs the token.

## Commands for the engineer (nothing here was run)

    # 1. token on account C (read-only token, never printed): add to the login environment of account C, then check presence only:
    ssh <alias-C> 'if [ -n "${GITHUB_TOKEN:-}" ]; then echo token_nonempty; else echo token_absent; fi'
    # 2. stage the code and the held-out files on account C (from the repository root on the engineer's machine):
    rsync -a --exclude __pycache__ ril scripts configs <alias-C>:ril_mine/ && rsync -a data/held_out/held_out_repos.json data/held_out/rename_cache.json <alias-C>:ril_mine/data/held_out/
    # 3. move the archived pilot (2.5 GB) from account A to account C through the engineer's machine, only if it is wanted there:
    ssh <alias-A> 'tar cf - -C ril_mine/runs pilot' | ssh <alias-C> 'mkdir -p ril_mine/runs && tar xf - -C ril_mine/runs'
    # 4. free space on account A by removing the superseded run roots and partial archives (the commands are in the session notes of 2026-11-03).
