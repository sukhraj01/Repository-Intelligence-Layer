# Disk de-duplication of the mined corpora: a measured proposal (nothing was changed)

Evidence class: **measured, exploratory**. Command (job 55964, code of this branch; reads the finished pilot run root, writes one JSON file):

    python3 -I scripts/mine_pilot.py dedup-measure runs/pilot runs/pilot/dedup_measure.json

Method (`ril/data_mining/dedup.py`): for each repository, every corpus row of every one of its mined directories is hashed (SHA-1 of the row's bytes); a store that keeps
each distinct row once per repository (one deflate stream per repository, level 6) and, per directory, the list of row indices (4 bytes per row, deflated) is sized
and compared with the bytes of the corpora as stored now (one gzip file per directory). The repository is the key: a row shared by two repositories is stored twice.

| | value |
|---|---|
| directories, repositories | 1,391, 156 |
| corpus rows over all directories | 18,998,175 |
| distinct rows per repository, summed | 1,985,700 (10.5%) |
| plain bytes, all rows / distinct rows | 22.74 GB / 3.04 GB |
| corpora stored now (compressed) | 2,547,895,175 bytes (2.55 GB) |
| de-duplicated store: blobs / manifests / total | 311,643,699 / 32,627,356 / 344,271,055 bytes (0.34 GB) |
| **saving** | **86.5%** (7.4 times smaller) |

The saving is measured on the pilot only (12 mined directories per repository on average). It rises with the number of directories per repository, so the figure is a lower bound
for a larger run of the same repositories and is not extrapolated beyond that statement.

## Can the readers use it unchanged?

- `ril/training/pool_reader.py` and the rank tooling (`ril/training/pool_ranks.py`) read per-directory members through a zip member listing with byte offsets (`pool_check`), one
  `corpus.jsonl`, `queries.jsonl` and `qrels/test.tsv` per directory. A content-addressed store is **not** in that layout, so they cannot read it as it is.
- A **build step** can materialise the layout from the store on the node-local disk of a job (read the manifest of a directory, copy the rows from the repository's
  stream in order, write `corpus.jsonl`, then run `pack_zip`, which the rank jobs already do for the run root). The readers stay unchanged. This materialisation was **not built or timed** here;
  it needs random access into the per-repository stream (seekable blocks, or the whole repository stream held in memory: the largest repository's stream is the cost to check).

## Options (the choice is a lead decision; none is implemented)

| Option | Disk | Reader change | Cost |
|---|---|---|---|
| A. Keep the per-directory gzip files (now) | 2.55 GB per 1,391 directories | none | disk binds first at 20,000 attempted (25.6 GB) |
| B. Content-addressed store plus a materialisation step on the node-local disk of each job | about 0.34 GB per 1,391 directories at pilot density | none (the step produces today's layout) | a new build step to write, test and time; one more thing to keep in sync with the miner |
| C. Content-addressed store read directly by new readers | same as B | `pool_reader` and the rank tooling change | a change to the readers (lead decision), and a second code path for the same data |
| D. Store file-level blobs of the snapshot (each source file once) instead of function rows | not measured (the miner stores function rows, not files; a file store needs the snapshot kept) | none with a materialisation step | not measured here |
