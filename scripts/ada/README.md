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

## BM25 reproduction, label noise and the dev sweep (pilot E1/E2, 2026-10-18)

Work directory on Ada: `~/ril_e/` (`ril/`, `scripts/`, `configs/` by `rsync -a --exclude __pycache__ ril scripts configs ada:ril_e/`; `raw/` CORE-Bench folders, `repo_cache/` bare clones, `meta.json`
instance base commits and patches, `out*/` records, `work/` working clones, `logs/`). `meta.json` is built locally from the datasets' parquet metadata (not committed). Records hold ranks, ids, paths and
lines only. Jobs are resumable; set the memory with `--mem=4G` to `8G` (large requests wait behind a running job, see `docs/COMPUTE.md`).

| Script | What | Exact command (from `$HOME`) |
|---|---|---|
| `e_fetch_data.sbatch` | the 12 Verified folders at L2 and L3 and the five dev folders | `sbatch ril_e/scripts/ada/e_fetch_data.sbatch` |
| `e_clone_repos.sbatch` | bare clones of the eight repositories not already in `~/ril_s2/raw/repo_cache` (link that cache's three into `ril_e/repo_cache`) | `sbatch ril_e/scripts/ada/e_clone_repos.sbatch` |
| `e1_run.sbatch` + `../e1_run.py` | `STAGE=chunk` (BM25 per folder) or `STAGE=units` (checkout, parse, unit BM25 per instance); `ONLY=<folder>` limits it | `sbatch --mem=8G --export=ALL,STAGE=chunk,RIL_COMMIT=<hash> ril_e/scripts/ada/e1_run.sbatch` |
| `e1_full_l2.sbatch` + `e1_full_l2.py` | all 632 original L2 folders, one at a time (fetch, score, delete); needs `configs/experiments/e1_bm25_full_l2.yaml` | `sbatch --mem=12G ril_e/scripts/ada/e1_full_l2.sbatch` |
| `e1_dev_sweep.sbatch` + `e1_dev_sweep.py` | k1 x b grid on the dev folders only | `sbatch ril_e/scripts/ada/e1_dev_sweep.sbatch` |
| `e1_confirm.sbatch` + `e1_confirm.py` | one stated (k1, b) on the test folders | `sbatch --export=ALL,K1=2.0,B=0.75 ril_e/scripts/ada/e1_confirm.sbatch` |

Copy `ril_e/out`, `out_full`, `out_sweep` and `out_confirm_*` to `data/processed/e1/`, then locally `python scripts/e1_tables.py data/processed/e1/out results/tables --config ... --seed 0 --sweep-dir ... --full-dir ... --confirm-dir ... --log ...`
(rename case-colliding record files on the cluster first).

## Graph-signal pilots (E3 to E6, 2026-10-18)

Work directory `~/ril_e/` as above (needs `out/units` from the E1 unit stage, `raw`, `repo_cache`, `meta.json`). `e3_cache/` holds one `.npz` per instance (BM25 scores, edge pairs per family, gold unit indices; no text),
`e3_work/` the working clones of the shards, `e3_out/` failure lists and environment files. Evaluation needs only the cache and can run anywhere (`scripts/e3_run.py eval`).

| Script | What | Exact command (from `$HOME`) |
|---|---|---|
| `e3_prepare.sbatch` | cache of every instance of the role (`ROLES=dev` or `ROLES=test`), `SHARDS` processes (default 4), `ONLY=<folder>`, `LIMIT=<n per shard>` | `rsync -a --exclude __pycache__ ril scripts configs ada:ril_e/ && sbatch --export=ALL,ROLES=dev,RIL_COMMIT=<hash> ril_e/scripts/ada/e3_prepare.sbatch` (dev: 25 min, test: 4 min) |
| `e3_eval.sbatch` | one evaluation configuration on the cache (`EVAL_CONFIG`, `OUT`); a configuration that names test instances must be a single-setting confirmation | `sbatch --export=ALL,EVAL_CONFIG=configs/experiments/e3_graph_signal.yaml,OUT=e3_eval_dev ril_e/scripts/ada/e3_eval.sbatch` |
| `e6_probe.sbatch` | builds `venv_dense310` (CPU torch, transformers 4.44.2, sentence-transformers 3.1.1), loads CodeRankEmbed and times 200 chunks on 4 CPUs | `sbatch ril_e/scripts/ada/e6_probe.sbatch` |
| `e6_count.py` | distinct unit texts and characters over a spread of snapshots per dev repository (no model) | `srun -p u22 -A research -q low -c 2 --mem=4G env PYTHONPATH=. venv_ril310/bin/python scripts/ada/e6_count.py e3_cache meta.json repo_cache e3_work 6` from `~/ril_e` |

Copy the caches with `rsync -a ada:ril_e/e3_cache/ data/processed/e3/e3_cache/`; `scripts/e3_add_readings.py` adds gold readings that older cache files lack. Dense scores (`scripts/e6_dense.py`) were not produced.

## Pool check and contamination probe (session X, 2026-10-18)

Work directories on Ada: `~/ril_pc/` (pool check; `ril/`, `scripts/` by `rsync -a --exclude __pycache__ ril scripts ada:ril_pc/`; `work/` caches, `out/`) and `~/ril_c/` (probe; same layout plus `repo_cache/`). Both read `~/ril_s2/raw` (zip listing, CORE-Bench ids, Verified parquet).
Output holds ids, counts and hashes only, never query, function or code text.

| Script | What | Exact command (from `$HOME`) |
|---|---|---|
| `pool_check.sbatch` + `pool_check.py`, `pool_check_ref.py` | queries and qrels of all 24,285 python instance directories of `gangiswag/train_data` by one range request each (about 33 min at 12 threads), corpus of a seeded sample; overlap with CORE-Bench ids and Verified; resumable (`work/pool_meta.jsonl`) | `sbatch --export=ALL,SEED=0,SAMPLE=300,THREADS=12 ril_pc/scripts/ada/pool_check.sbatch`, then `scp ada:ril_pc/out/pool_check.json data/processed/x/` and `python scripts/pool_check_tables.py data/processed/x/pool_check.json results/tables` |
| `contam_build.sbatch` | bare clones of the six Verified repositories not yet on the cluster, then the probe set (hashes of every function and method at all 499 distinct Verified base commits; 29 min) | `sbatch ril_c/scripts/ada/contam_build.sbatch` |
| `contam_measure.sbatch` | throughput of streaming the CoRNStack python shards (first 200 MB of shards 0, 120, 239; 50 MB with negatives scanned) | `sbatch --export=ALL,MB=200,MB_NEG=50 ril_c/scripts/ada/contam_measure.sbatch` |
| `contam_scan.sbatch` + `contam_probe.py scan` | scan of the `document` field of whole shards against the probe set, 4 workers, one output file per shard, finished shards skipped | slice: `sbatch --export=ALL,FIRST=0,LAST=239,STRIDE=10 ril_c/scripts/ada/contam_scan.sbatch`; full scan (about 10 CPU-hours, about 2.6 h on 4 CPUs, 307.6 GB streamed): `--export=ALL,FIRST=0,LAST=239,STRIDE=1` |

Scanning the 100 negatives of every row as well costs about 3.5 s per compressed MB (29 times the documents-only scan), about 300 CPU-hours for the corpus: not run.

## Structure measurements (class-unit source, ambiguous-site policy, L3 census; 2026-10-23)

Work directory `~/ril_x1/` (`ril/`, `scripts/`, `configs/` by `rsync -a --exclude __pycache__ ril scripts configs ada:ril_x1/`). It links
`~/ril_e/{raw,repo_cache,meta.json}` and `~/ril_e/out/units` (the pilot-E1 records) and uses `~/ril_e/venv_ril310`. `x1_cache/` holds one
`.npz` per instance (BM25 scores per class-source form, index sizes, ambiguous sites with evidence, gold indices; no text).

| Script | What | Exact command (from `$HOME`) |
|---|---|---|
| `x1_prepare.sbatch` | extras of every instance of the role (`ROLES=dev` or `test`), `SHARDS` processes (default 4) | `sbatch --cpus-per-task=4 --mem=10G --export=ALL,ROLES=dev,RIL_COMMIT=<hash> ril_x1/scripts/ada/x1_prepare.sbatch` (dev 26 min; test 22 min with 3 shards) |
| `x1_census.sbatch` | pilot-E1 unit stage on the extra L3 folders of `configs/experiments/x1_l3_census.yaml` (fetches the SWE-bench Pro ansible folders, bare clones in `repo_cache_census/`); `FOLDERS="a b"` limits it | `scp data/processed/x1/census_meta.json ada:ril_x1/ && sbatch --export=ALL,RIL_COMMIT=<hash> ril_x1/scripts/ada/x1_census.sbatch` (django alone about 3.5 h) |

`census_meta.json` is built locally (`python scripts/x1_census.py meta data/raw/core_bench/ids_all.json OUT <parquet>... --folders ...`; it holds
patches, so it stays untracked). Locally: `rsync -a ada:ril_x1/x1_cache/ data/processed/x1/x1_cache/`, then `python scripts/x1_run.py eval <config>
data/processed/e3/e3_cache data/processed/x1/x1_cache <out>`, `x1_run.py tables <config> <out> results/tables/<prefix>`, `x1_run.py sizes`, and the
census tables with `python scripts/x1_census.py tables <prefix> <units dir>...`. The readers run locally: `python scripts/x1_readers.py oracle ...`
and `x1_readers.py jedi ...` (commands in the run log).

## Dense encoders, fusion and latency (E-DENSE-FUSION, 2026-10-23 to 2026-10-25)

Work directory `~/ril_x2/` (`ril/`, `scripts/`, `configs/` by `rsync -a --exclude __pycache__ ril scripts configs ada:ril_x2/`). It links
`~/ril_e/{raw,repo_cache,meta.json,e3_cache}`, reuses the pilot-E3 working clones in `~/ril_e/e3_work` and the model cache `~/ril_e/hf_cache`.
`prep/` holds text stores (unit and chunk texts, queries; never copied off the cluster), `enc/<encoder>__t<cut>/` float16 vectors by text hash,
`dense/<encoder>__t<cut>/` per-instance scores, `chunks_out/` chunk-level ranks, `out/` run logs, latency CSVs and query sets.

| Script | What | Exact command (from `$HOME`) |
|---|---|---|
| `x2_prepare.sbatch` | CPU: GPU environment (`venv_gpu310`, CodeRankEmbed overlay `overlay_cre`), model download, unit-text hashes of every cached instance (three class forms, 4 shards), query and chunk stores (about 25 min plus 15 min for the environment) | `sbatch --export=ALL,RIL_COMMIT=<hash> ril_x2/scripts/ada/x2_prepare.sbatch` |
| `x2_encode.sbatch` | GPU (2080 Ti, CUDA gate): `STAGE=dev` dev units at 512 and 1024, queries, GPU latency rows, then Verified-six units and chunks at 512 (2 h 25 min); `STAGE=more ENCODERS=<names> CUTS="512 1024"` further cuts (texts the shorter cut left whole are taken over) | `sbatch --export=ALL,STAGE=dev,RIL_COMMIT=<hash> ril_x2/scripts/ada/x2_encode.sbatch` |
| `x2_score.sbatch` | CPU: unit scores of every encoded variant, chunk ranks (`CHUNK_VARIANTS`), CPU latency and throughput rows (`MEASURE=1`, 4 threads; about 55 min) | `sbatch --export=ALL,MEASURE=1,CHUNK_VARIANTS="coderankembed__t512 qwen3-embedding-0.6b__t512",RIL_COMMIT=<hash> ril_x2/scripts/ada/x2_score.sbatch` |

Locally: `rsync -a ada:ril_x2/dense/ data/processed/x2/dense/`, `rsync -a ada:ril_x2/chunks_out/ data/processed/x2/chunks_out/`, a copy of the E3 cache with
the no-module readings (`scripts/e3_add_readings.py`), then `python scripts/x2_tables.py eval|first|graph|chunks <config> ...` (commands in the run log
`results/logs/x2_dense_fusion_2026-10-25.json` and `docs/EXPERIMENTS.md`). The latency CSVs in `out/latency/` are appended to `results/latency/`.
