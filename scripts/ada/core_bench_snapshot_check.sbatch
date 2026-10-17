#!/bin/bash
#SBATCH --job-name=ril_cb_snapshot
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=ril_s2/logs/core_bench_snapshot_check_%j.out
# CPU-only. Tests whether each Verified query's candidate list equals the snapshot at the instance base
# commit (flask, requests, seaborn; the samples fetched by fetch_core_bench_samples.sbatch). Needs git and
# pyarrow (venv keyed by interpreter version as in pool_repo_counts.sbatch). Idempotent: clones are cached.
set -euo pipefail
cd "$HOME/ril_s2"
V=venv_pa_$(python3 -c 'import sys;print("%d%d" % sys.version_info[:2])')
if [ ! -x "$V/bin/pip" ]; then python3 -m venv "$V" && "$V/bin/pip" install -q pyarrow; fi
mkdir -p raw/repo_cache
$V/bin/python scripts/core_bench_snapshot_check.py raw/core_bench_samples \
  raw/meta_sets/princeton-nlp_SWE-bench_Verified/data/test-00000-of-00001.parquet \
  raw/repo_cache raw/snapshot_check.json 17 1500 pallets__flask psf__requests mwaskom__seaborn
