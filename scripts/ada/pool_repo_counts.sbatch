#!/bin/bash
#SBATCH --job-name=ril_pool_counts
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=ril_s2/logs/pool_repo_counts_%j.out
# CPU-only. CodeSearchNet python parquet (580 MB) -> per-repository row counts; then the candidate
# pool directory names from the train.zip listing. The venv is keyed by the interpreter version because
# login nodes run Python 3.9 and compute nodes 3.10 (a venv built on one does not work on the other).
set -euo pipefail
cd "$HOME/ril_s2"
V=venv_pa_$(python3 -c 'import sys;print("%d%d" % sys.version_info[:2])')
if [ ! -x "$V/bin/pip" ]; then python3 -m venv "$V" && "$V/bin/pip" install -q pyarrow; fi
$V/bin/python scripts/pool_repo_counts.py csn raw/csn_python raw/pool_csn_repos.json
python3 scripts/pool_repo_counts.py gangiswag raw/ziplist_train.json raw/pool_gangiswag_repos.json
