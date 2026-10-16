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
