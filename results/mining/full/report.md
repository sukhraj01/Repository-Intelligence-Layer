# Full mined set: yield, timeouts, overlap audit and preparation (E-MINE-FULL-RESULT)

Every figure below is read from a stored file. Sources: `yield_report.json` (computed from `state.jsonl` of the finished store; SHA-256 of
`state.jsonl` `4982251f706d55e383b8456ee81d2f6a22ec3bf735809493bb7113fa449cecd2`, of `sessions.jsonl`
`97ef0a38a6b1a5e107be2c66a20499ddad4b193b2077a4ae0a0eee3f3ebe5d31`, of `summary.json`
`f8c0da11910759f07f2b2a2d4f39f2a9c38f13fa89249715e72ba7765577ad7c`, of `run.json`
`f84bc25b004aff949f023f3d5852d1a7df52563284e47bf860d771e94c6b3b93`; mining configuration hash `33b7336093995d0722cd41fed36f3f90c561a01b07639fe8dcbf2bc10ff9def4`),
`overlap_audit/full/`, `check.json`, `non_test/` and `pool_aligned/` (this directory). Hardware of every job: CPU nodes of partition u22 (40 visible
CPUs, 125 GB, Python 3.10.12); seed 0. Evidence class: measured, exploratory (data), unless a row says projected.

## A. Yield (both readings)

| | Full run (10,000 attempted) | Pilot (2,000 attempted) |
|---|---|---|
| mined | 6,230 (62.30%) | 1,391 (69.55%) |
| no Python change | 2,607 (26.07%) | 386 (19.3%) |
| no positive | 1,040 (10.40%) | 206 (10.3%) |
| quarantined | 123 (1.23%) | 17 (0.85%) |
| positives, unrestricted | 54,700 (8.78 per mined directory) | 7,081 pool-like |
| repositories with an attempt / with a mined directory | 1,102 / 1,013 of 1,473 listed | 156 |

Quarantine by reason (123): changed file unparseable 48 (Python 2 syntax 21, `syntax-other` 26, mixed tabs and spaces 1), old file missing at
base 26, patch missing 23, diff truncated 14, unit id rejected 8, snapshot unavailable 3, compare not found 1, **snapshot timeout 0**, corpus error 0.

Per run segment (rows in state order): rows 1 to 2,214 (the two sessions that stopped on a fetch timeout, DEV-036): 1,378 mined (62.24%), 31
quarantined (1.40%); session 1 of the relaunch (5,000 rows): 3,114 mined (62.28%), 62 quarantined (1.24%); session 2 (2,786 rows): 1,738 mined
(62.38%), 30 quarantined (1.08%). Per quarter of the log the mined share is 62.3, 63.0, 61.4 and 62.6% and the quarantine share 1.24, 1.44, 1.12 and 1.12%.

Readings (D96; `non_test` is primary, `pool_aligned` a labelled sensitivity reading), before and after the audit's drop list:

| Reading | Directories before / after drop | Positives before / after drop | G2 (at least 10,000 positives) |
|---|---|---|---|
| unrestricted (all mined) | 6,230 | 54,700 | **pass** (5.5 times) |
| `non_test` (primary) | 5,802 / 5,789 | 36,046 / 35,804 | **pass** (3.6 times) |
| `pool_aligned` | not counted before the drop / 4,935 | not counted before the drop / 29,473 | **pass** (2.9 times) |

`non_test` keeps 93.13% of the mined directories before the drop (Wilson 92.5 to 93.7; the pilot 92.5%); `pool_aligned` keeps 85.25% of the
`non_test` directories after the drop (84.3 to 86.1; the pilot 80%, the 200-directory trial 84.6%). Intervals treat directories as independent and
are narrower than a repository-clustered interval would be.

Drift against the pilot. The mined share is 7.2 points lower and the whole difference is in the no-Python-change class (26.07 against 19.3%); the
no-positive share is the same (10.4 against 10.3%) and the quarantine share is 0.4 points higher. The share is flat across the three segments and
four quarters of the log (61.4 to 63.0%), so it is a property of the sampled population (1,102 repositories against 200), not of a time order or a
session. The early readings of this same run did not drift: 62.24% mined and 1.40% quarantined at 2,214 rows, 62.57% and 1.20% at 2,835 rows (the 62.6%
quoted for the 2,214-row mark is the 2,835-row figure), against 62.30% and 1.23% at 10,000. The pilot's own yields are the right comparison for the
population effect: 69.55% mined and 0.85% quarantined at 2,000 attempts.

Repository mix. Largest repositories by attempted pull requests: openmetadata 397 (3.97%), airflow 315 (3.15%), connectedhomeip 257 (2.57%),
policyengine-us 171, jupyterlab 161, gradio 140, esphome 140, phoenix 135, azure-cli 132, lakefs 122. Shares of attempts: largest 1 repository 3.97%,
largest 5 13.0%, largest 10 19.7%, largest 20 26.9%; of mined positives: 3.12, 11.6, 17.8 and 26.9%. Airflow holds 44 of the first 1,437 rows of this
run against 319 of the pilot's first 1,437 attempts (22%): the skew of the pilot is gone. Median 3 attempts per repository; 264 repositories have one.

Store and time. Store on disk: `pr` 103,254,746 bytes, `cas` 1,035,445,221, `listing` 723,776,294, together 1,862,476,261 bytes (1.86 GB):
**299 KB per mined directory** (183 KB without the listings) against the 2.0 GB planned, the 3.7 GB projected and the pilot's 285 KB. Mining time
34,382.7 s (9.55 h: 21,596.2 s and 12,786.5 s in the two sessions of the relaunch); listing time inside those sessions 21.5 s and 19.2 s because
all 1,473 listings were reused. API: 7,841 compare calls, 1,433 rate-limit sleeps (30.7 s), 1 retry.

Lost schedule (Slurm accounting, wall hours). Launch 2026-11-05 15:31, last job end 2026-11-08 20:54: 77.4 h. Mining that counts: 9.55 h. Failed runs:
the three listing jobs, 2.96 h (DEV-034); the second listing round and the session that listed the rest, 14.5 h (DEV-035); two mining sessions on a
fetch timeout, 4.1 h (DEV-036): 21.6 h of failed wall time. Waiting between a failure and the next submission (diagnosis, fix, queue): 22.6, 13.8 and
9.5 h = 45.9 h. The remaining 0.3 h is the listing-completion job. The plan had put mining at 28.5 h; it took 9.55 h.

## B. Timeouts and the partial-fetch rule (decision D146)

Snapshot timeouts: **0 of 10,000** attempted pull requests (rule threshold: more than 2%, with five or fewer repositories accounting for more than
half). The rule's first branch is not met, so no second pass with a partial fetch is scoped and nothing is built. The three snapshot-unavailable
rows (gradio, pyannote-audio, py-shiny) are not timeouts. Largest repositories are not lost to quarantine: classed by the mean snapshot size of a
repository's non-quarantined rows (functions per snapshot), the quarantine rate is 1.16% for under 2,000 functions (869 repositories, 4,904 rows),
1.03% for 2,000 to 10,000 (172, 4,267), 0.82% for 10,000 to 50,000 (16, 729) and 0 of 35 for the one repository above 50,000 (`yield_report.json`,
`size_classes`). Rows of repositories with no readable snapshot at all have 24.6% quarantine (16 of 65 rows, 44 repositories); that class is defined
by the quarantine and cannot be sized. Who is under-represented, stated for the paper: pull requests that touch 300 or more files (14 rows
`diff_truncated`: openmetadata 2, mteb 2, connectedhomeip 1 and others), Python 2 code (21), repositories whose old file is absent at the base
commit (26; hdmf 7), and non-ASCII identifiers (8: debugpy 6, pythainlp 2). Eighteen repositories account for half of the 123 quarantines; the
largest shares are scanpy 7, hdmf 7 (5.7% each), connectedhomeip 6, debugpy 6 and hahomematic 5.

## C. Overlap audit and drop list (D105; account C; CPU)

Held-out index (27 MB: `ast.json.gz` `8e80bdce…cb9`, `lines.bin` `f90d4b6b…14b`, `manifest.json` `e61a4bea…b9`): copied from account A to C earlier
by the byte-verified rule (SHA-256 manifest, nothing overwritten); re-verified now on both sides, all three hashes equal the manifest. Audit of
**6,230 directories**, floor 20 syntax-tree nodes, flag share 5%, eight shards (a repository is never split), 4,366.9 s, peak 3.5 GB; records
SHA-256 `1b49b698e973f74186d0b6f4baff4120c406a7e644679acb1009e5749aa69155`.

| Rule | Directories dropped | Positives left (`non_test` pool-like, of 36,046) | Directories left (of 5,802) |
|---|---|---|---|
| floor 20, positives outside tests (primary) | 13 | 35,804 | 5,789 |
| floor 20, all positives | 16 | 35,714 | 5,786 |
| floor 10 | 34 | 33,091 | 5,768 |
| floor 50 | 9 | 35,932 | 5,793 |
| floor 20 and every flagged directory (corpus share above 5%) | 138 | 35,348 | 5,685 |

Primary drop list: 13 directories of 11 repositories, 0.21% of the mined directories and 0.67% of the `non_test` positives (242 of 36,046), applied to
the training manifest (`names_kept.txt`: 6,217 of 6,230); the store was not modified (`drop_manifest.json`: `store_modified` false). The list is
`overlap_audit/full/drop_f20_non_test.txt`, SHA-256 `36e3a144d2d7154c3abc0df8fc31e8ec11e3777b07cf5ef030401f63881d9f44` (equal to the hash in both
preparation summaries). The matched held-out repositories of the dropped positives: scikit-learn (6 directories: scikeras, autogluon, pyftpdlib, three
of joblib), ansible (2), matplotlib (2), requests (2), astropy (2), sphinx, xarray and django (one each); one directory can match several held-out repositories. Vendored
scikit-learn code recurs, as in the pilot (three directories of the vendored joblib copy). Pilot recurrence: of the pilot's three drops, one
(`autogluon__autogluon-510`) is in this store and is dropped again; the other two (`rasbt__mlxtend-1018`, `sktime__skbase-107`) are not in this
store's sample of pull requests. 125 directories are flagged and kept at the primary rule. Matched functions of the held-out repositories in the
corpora: 71,594 (58,545 under 20 nodes, 6,089 of 20 to 49, 6,960 of 50 and more).

Coverage limit (Q68): the audit sees 26 of the 605 held-out repositories (those with unit records), so a leak into the other 579 is not detectable
here. Cost: 4,366.9 s of the job's 4 h 09 m 57 s, 2 CPUs used of 6 allocated.

## D. Preparation of the full mined set (account C; CPU; job 66544, elapsed 4 h 09 m 57 s)

| Stage (both readings where it applies) | Seconds | Peak MB (child) | Projection in the preparation entry |
|---|---|---|---|
| overlap (8 shards, merge, apply) | 4,366.9 | 3,510 | 1,578 to 14,967 s |
| materialise and byte check | 1,939.5 | 5,484 | 1,350 to 2,913 s |
| rank inputs | 2,831.7 | 2,882 | 1,398 to 1,428 s (non_test only) |
| BM25 teacher scores (K = 20, positive level) | 2,973.9 | 5,243 | about 1,605 s |
| feature table | 2.7 | 73 | 5 to 22 s |
| cache and FILTER size | 2,671.6 | 5,449 | 1,238 to 1,426 s |
| check | 208.3 | 1,523 | 96 to 189 s |
| whole chain, both readings | 14,996 (4.17 h) | | 2.7 to 7.0 h (two readings) |

Chain wall time sits inside the projected range. Stage times for the rank inputs, teacher and cache steps are about 1.9 to 2.2 times the `non_test`-only
projection because they now include the second reading; the audit is 2.8 times the two-point reading and well under the linear bound. Memory: the
largest child peak is 5.5 GB (materialise); the cache read with shared strings peaks at 5.4 GB, inside the projected 3 to 6 GB. Slurm's `MaxRSS`
for the batch step reads 12,581,160 KB, the whole of the 12 GB request (it is not the sum of the children and may include file pages); the job did
not fail, but the request has no demonstrated headroom: ask 16 GB for a rerun.

| Reading | Directories (examples) | Positives | Repositories | Candidates | Cache bytes | Cache SHA-256 |
|---|---|---|---|---|---|---|
| `non_test` (primary) | 5,789 | 35,804 | 991 | 14,877,729 | 2,397,015,492 | `e4171e66…3afc` |
| `pool_aligned` | 4,935 | 29,473 | 962 | 10,954,545 | 1,733,576,224 | `1e674df2…4278` |

Checks. (1) Held-out rows in the training manifest and the cache: 0 of 5,789 and 0 of 4,935; dropped names in the cache: 0 (`check.json`). (2)
Second run on a seeded sample of 200 directories (names SHA-256 `88fbe6d6…b717`; jobs 67054 and 67055, 10 min 59 s each, both readings): 13 of
13 files per reading and 59 of 59 audit files equal byte for byte between the two runs (rank rows without timing fields, gzip by content); each run
equals the full run on the same directories: rank rows 189 of 189 (`non_test`) and 173 of 173 (`pool_aligned`), feature rows 984 of 984 and 831 of 831,
audit records 200 of 200. The sample holds none of the 13 dropped directories, so the drop decision itself is tested by the full run's list only.
(3) Directories common with the pilot (job 67056): `non_test` 912 common directories, 912 of 912 rank rows identical (rank and rank_all of every
positive, function counts), 5,106 of 5,106 feature rows equal. For `pool_aligned` the same comparison against the pilot's `non_test` files finds 166 of 740 directories
identical; this is not a like-for-like check (the reading drops positives and candidates, 872 of 4,837 pilot rows have no counterpart), so it is
reported and not read as a failure; the pilot's `pool_aligned` values exist for 300 directories only, as shares. (4) Independent recount of the
FILTER step from the feature table: 3,885 examples and 11,380 positives with `rank_bm25` at most 20 (any kept positive keeps the example), equal to
the job's `filter_size.json`.

Space on account C: 50 GB home, 27 GB used before and 31 GB after (20 GB free): the full run 3.9 GB, the two 200-directory runs 0.1 GB each, 0.2 GB
logs and inputs; node-local scratch left on the nodes: 8.86 GB (full run) and 2 x 0.21 GB (repeat runs).

FILTER pool against the visits of a 100-update run (3,200 = 100 x 32 directories; D140):

| | Examples (pool) | FILTER keep rate | FILTER pool | Margin over 3,200 | Passes at 100 updates: RAW / FILTER |
|---|---|---|---|---|---|
| pilot keep rate (59.49%) on 5,789 | 5,789 | 59.49% | 3,444 | +244 (+7.6%) | 0.553 / 0.929 |
| measured BM25 keep rate, `non_test` | 5,789 | 67.11% (clustered 95%: 64.0 to 70.0) | **3,885** | **+685 (+21.4%)**; +505 at the interval's lower end | 0.553 / 0.824 |
| measured, `pool_aligned` | 4,935 | 67.27% | 3,320 | +120 (+3.8%) | 0.648 / 0.964 |

The share of FILTER at which the pool equals the visits is 55.3%; the pilot's keep rate lies below the full set's interval (the full set keeps
more), so the pilot understated the pool. Rule (a) of the launch plan (N = min(100, floor(F / 32))) gives N = 100 for the `non_test` reading
(F = 3,885, floor(F / 32) = 121). Distinct examples per arm at 3,200 visits and 100 updates (the plan tool's counts, `rq2_plan.py plan --filter-size
3885 --pool-examples 5789`): FILTER 3,200 of 3,885 (0.82 passes, no repeats), RAW 3,200 of 5,789 (0.55 passes, no repeats), size-matched subsample 3,200
of 3,885 (it draws as many as FILTER keeps), shortfall 0. The 1,000-update sensitivity still cannot be met (32,000 visits against 3,885).
`pool_aligned`: F = 3,320 gives floor(F / 32) = 103, so N = 100 holds there too, with a 3.8% margin.

## Not done

No partial-fetch pass (not triggered). No dense-teacher ranks. No `resolve` step, registration, preflight or launch. No answer to Q68. No GPU time.
`pool_aligned` counts before the drop list were not computed (the drop is 13 directories). The report's mined-set text is not edited.
