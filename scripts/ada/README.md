# scripts/ada/ — Slurm jobs for the Ada cluster

Read `docs/COMPUTE.md` first; it holds the inherited cluster lessons and is the place to record
what you verify.

## Conventions for every job script

1. **All `#SBATCH` lines first**, before any shell command.
2. Check `sinfo` for the real partition name and `myallocation` / `sacctmgr show qos` for current
   limits **before** writing resource lines; do not trust numbers in older notes.
3. **CPU-only jobs for data work.** Never hold a GPU while downloading or preparing data. Chain a GPU
   stage after it with `--dependency=afterok:<jobid>`.
4. **GPU jobs start with a capability gate:** run a real CUDA matmul (not just
   `torch.cuda.is_available()`), and request a supported card with `--constraint=` when needed.
5. **Idempotent and resumable:** re-running a finished job is a no-op; downloads use
   `wget -c --tries=10 --retry-connrefused` (or the library's resume path).
6. **Self-contained data access:** `/ssd_scratch` is node-local and `/share1` was not mounted on
   compute nodes. Stage into `$HOME` (NFS) or let the job fetch what it needs.
7. Write `data/raw/<dataset>/provenance.json` (source, date, sha256, counts) for every fetch.
8. Log stdout/stderr to a named file, not only `slurm-*.out`; record the job id, config hash, seed
   and hardware spec in the run log (`results/logs/`).
9. Record the first-line outcome (job id, runtime, result) in `RESULTS.md`; add a line to
   `docs/COMPUTE.md` → "Log of cluster verification" for anything you learned about the cluster.

## Naming

`<purpose>_<stage>.sbatch`, e.g. `fetch_core_bench_index.sbatch`, `train_arm.sbatch`. A job that
needs another job's output declares the dependency in a comment and in the submit helper.

## Data-source probes and fetches (stdlib only, Python 3.9)

Ada's system Python has no `huggingface_hub`, `pyarrow` or `uv`; the scripts below use only the
standard library. Work directory on Ada: `~/ril_s2/` (`scripts/`, `raw/`, `logs/`). Copy scripts with
`scp scripts/ada/*.py scripts/ada/*.sbatch ada:ril_s2/scripts/`. Submit batch jobs from `$HOME`.

| Script | What | Exact command |
|---|---|---|
| `probe_net.py` | reachability and Range throughput | `python3 ril_s2/scripts/probe_net.py 50000000` (login) or via `srun -p u22 -A research -q low -c 2 --mem=4G` |
| `hf_list_tree.py` | tree listing with sizes | `python3 hf_list_tree.py zhangfw123/CORE-Bench "" raw/listing_root.json` |
| `hf_fetch.py` | resumable, size-checked fetch of path prefixes + `provenance.json` | `python3 hf_fetch.py <repo> <listing.json> <dest> <prefix>...` |
| `fetch_core_bench_samples.sbatch` | the 9 small Verified sample folders | `cd ~ && sbatch ril_s2/scripts/fetch_core_bench_samples.sbatch` |
| `analyze_core_bench_sample.py` | field/format statistics (numbers only) | `python3 -I analyze_core_bench_sample.py <data root> out.json` |
| `zip_remote_listing.py`, `zip_remote_extract.py` | list or extract single members of a remote zip by Range request | `python3 zip_remote_listing.py <url> out.json` |

Held-out list and audit jobs (all CPU, streamed, numbers and ids only; each skips finished work):

| Script | What | Exact command |
|---|---|---|
| `core_bench_instance_ids.py` / `.sbatch` | query ids and qrels counts of every L2/L3/Rewrite folder (6.1 GB streamed) | `cd ~ && sbatch ril_s2/scripts/core_bench_instance_ids.sbatch`, then `python3 -I ril_s2/scripts/merge_json_dir.py ril_s2/raw/ids ril_s2/raw/ids_all.json` |
| `core_bench_corpus_stats.py` / `.sbatch` | corpus rows, characters and longest chunk per L2/L3 folder (13.8 GB streamed) | `sbatch ril_s2/scripts/core_bench_corpus_stats.sbatch`, then `merge_json_dir.py` on `raw/corpus_stats` |
| `core_bench_query_stats.py` / `.sbatch` | mean query length and candidate-list sizes | `sbatch ril_s2/scripts/core_bench_query_stats.sbatch` (writes `raw/query_stats_all.json`; rerun to retry folders that failed) |
| `pool_repo_counts.py` / `.sbatch` | per-repository counts: CodeSearchNet python (580 MB parquet, deleted afterwards) and the `gangiswag/train_data` candidate (from the zip listing) | `sbatch ril_s2/scripts/pool_repo_counts.sbatch` |
| `export_meta_ids.py` | (repo, instance_id) pairs of Verified and Loc-Bench | `venv_pa/bin/python -I ril_s2/scripts/export_meta_ids.py out.json <parquet>...` |
| `label_quality_sample.py` | seeded sample of L2 instances, positive chunks classified, counts only | `python3 -I label_quality_sample.py <root> out.json 0 30 <repo>...` |
| `core_bench_snapshot_check.py` / `.sbatch` | tests that each Verified query's candidate list is the checkout at the instance base commit (flask, requests, seaborn samples; clones cached in `raw/repo_cache`, counts only) | `cd ~ && sbatch ril_s2/core_bench_snapshot_check.sbatch` (needs `raw/core_bench_samples`, the Verified parquet, git, pyarrow; the clones take minutes, the check 20 s) |
| `github_repo_check.py` | current name, fork status and fork-network root of a short repository list (unauthenticated, 60 per hour) | `python3 -I github_repo_check.py repos.txt out.json` |
| `resolve_renames.py` | current GitHub name and fork flag of held-out and pool repositories into `data/held_out/rename_cache.json` (reads `GITHUB_TOKEN` if set, never prints it; stops at the rate limit and resumes on rerun) | `rsync -a ril ada:ril_d/ && python3 -I ril_d/scripts/resolve_renames.py ~/ril_d <cache> <pool_repos.json> <held_out_repos.json> <stats.json> <date> [max_requests]` |
| `content_overlap_audit.py` | content-overlap audit of pool repositories against the nine sample corpora, with a positive control and a random-sample baseline; also checks the pool-id converter (counts only) | `srun -p u22 -A research -q low -c 2 --mem=4G python3 -I ril_d/scripts/content_overlap_audit.py ~/ril_d ~/ril_s2/raw/core_bench_samples/data ~/ril_s2/raw/ziplist_train.json <pool_repos.json> <out.json> 0 40` |
| `validate_is_test_rule.sbatch` + `../validate_is_test_rule.py` | the D9 `is_test` rule against `pytest --collect-only` on flask, requests and seaborn (bare clones in `raw/repo_cache`; builds a venv in the job) | `cd ~ && sbatch ril_d/scripts/validate_is_test_rule.sbatch` |
| `merge_json_dir.py` | merges per-folder JSON into one file keyed by path (case-variant folder names collide on macOS) | `python3 -I merge_json_dir.py <dir> <out.json>` |

Locally, `python -I scripts/build_held_out.py` turns the merged files into `data/held_out/` and `results/tables/`.

`scripts/core_bench_listing_tables.py` (run locally, `python3 -I`) turns the listing and the dataset's
`manifest.json` into the count and size tables under `results/tables/`.

### Large fetches not yet done (waiting for an engineer decision or for the next task)

- CORE-Bench corpora beyond the nine samples: L2 + L3 originals total 17.0 GB; use `hf_fetch.py` with
  prefixes, as a CPU job on `u22`; about 6.5 to 9 MB/s measured, so roughly 35 to 45 minutes per 17 GB.
- `gangiswag/train_data` `train.zip` (23.6 GB) is not to be fetched until the engineer decides whether it
  is the intended pool (see Open question Q7); single members can be extracted with `zip_remote_extract.py`.

## Parse and graph build (first build of 2026-10-17, `docs/COMPUTE.md` log)

Work directory on Ada: `~/ril_p/` (`ril/`, `scripts/` copied with `rsync -a --exclude __pycache__ ril scripts ada:ril_p/`;
`repos/`, `repos_extra/`, `out/`, `logs/`). Create `~/ril_p/logs` first (Slurm does not create the `--output` directory).
The cluster nodes run Python 3.10: `ril/parsing`, `ril/evaluation/dynamic_trace.py` and `ril/bench` are written to run there;
each job builds its own venv keyed by the interpreter version.

| Script | What | Exact command (from `$HOME`) |
|---|---|---|
| `trace_flask_suite.sbatch` + `trace_pytest.py` | flask test suite at the pallets__flask-5014 base commit under the function-level tracer, and again under coverage.py | `sbatch ril_p/scripts/ada/trace_flask_suite.sbatch` (writes `ril_p/out/flask_trace.json`, `flask_coverage.json`) |
| `clone_django.sbatch` | full clone of django/django, checkout of the django__django-16145 base commit | `sbatch ril_p/scripts/ada/clone_django.sbatch` |
| `graph_measure.sbatch` | statistics of the three graphs (`parse_repo.py`), then the storage and expansion measurement, determinism rerun, through the latency harness | `sbatch --export=ALL,RIL_COMMIT=<hash>,RIL_DIRTY=1 ril_p/scripts/ada/graph_measure.sbatch` |
| `configures_pool.sbatch` + `configures_pool.py` | shallow fetch of four more Verified base commits (parsing only) and rendering of every exploratory `configures` edge for the precision sample | `sbatch ril_p/scripts/ada/configures_pool.sbatch` |

Copy results back with `scp ada:ril_p/out/<file> data/processed/p_graph/`.

## Chunk-to-unit mapping and graph reach (pilot M, 2026-10-17)

Work directory on Ada: `~/ril_m/` (`ril/`, `scripts/`, `out/`, `work/`, `logs/`). Needs the nine sample folders in
`~/ril_s2/raw/core_bench_samples`, the bare clones in `~/ril_s2/raw/repo_cache` and the Verified parquet in
`~/ril_s2/raw/meta_sets`. The job checks out each instance's base commit in a working clone, locates the positive chunks, maps them
to units, builds the graph and writes ids, paths, lines and unit ids only (no chunk text). A finished instance is read back from
`out/instances`; delete `out/instances` to redo.

| Script | What | Exact command (from `$HOME`) |
|---|---|---|
| `m_chunk_unit_reach.sbatch` + `../m_chunk_unit_reach.py` | the pilot for flask, requests and seaborn (about 35 s on 2 CPUs) | `rsync -a --exclude __pycache__ ril scripts ada:ril_m/ && sbatch --export=ALL,RIL_COMMIT=<hash> ril_m/scripts/ada/m_chunk_unit_reach.sbatch` |

Copy `ril_m/out/records.json` and `env.txt` to `data/processed/m_pilot/`, then locally
`python scripts/m_tables.py data/processed/m_pilot/records.json results/tables --seed 0 --rerun <second records> --log <log>`.
