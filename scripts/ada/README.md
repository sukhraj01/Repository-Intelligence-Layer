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

`scripts/core_bench_listing_tables.py` (run locally, `python3 -I`) turns the listing and the dataset's
`manifest.json` into the count and size tables under `results/tables/`.

### Large fetches not yet done (waiting for an engineer decision or for the next task)

- CORE-Bench corpora beyond the nine samples: L2 + L3 originals total 17.0 GB; use `hf_fetch.py` with
  prefixes, as a CPU job on `u22`; about 6.5 to 9 MB/s measured, so roughly 35 to 45 minutes per 17 GB.
- `gangiswag/train_data` `train.zip` (23.6 GB) is not to be fetched until the engineer decides whether it
  is the intended pool (see Open question Q7); single members can be extracted with `zip_remote_extract.py`.
