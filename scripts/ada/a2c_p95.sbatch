#!/bin/bash
#SBATCH --job-name=a2c_p95
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=ril_aitems/logs/a2c_p95_%j.out
# CPU only. Edge store load and write times with 31 repeats per check level, so the nearest-rank p95
# (30th of 31) is not the maximum (E-A-OWNER-ITEMS item 3). Store directories on node-local scratch.
#   cd ~ && sbatch --export=ALL,RIL_COMMIT=<hash> ril_aitems/scripts/ada/a2c_p95.sbatch
set -euo pipefail
W=$HOME/ril_aitems
PY=$W/venv310/bin/python
SCR=${TMPDIR:-/tmp}/a2c_p95_$SLURM_JOB_ID
mkdir -p "$SCR"
cd "$W"
export PYTHONPATH="$W"
REPOS=""
for pair in psf/requests=psf__requests pallets/flask=pallets__flask django/django=django__django; do
  REPOS="$REPOS --repo ${pair%%=*}=$HOME/ril_p/repos/${pair##*=}"
done
REPOS="$REPOS --repo pytest-dev/pytest=$HOME/ril_p/repos_extra/pytest-dev__pytest"
for r in psf__requests pallets__flask django__django; do echo "$r $(git -C $HOME/ril_p/repos/$r rev-parse HEAD)"; done > g1/a2c_p95_commits.txt
echo "pytest $(git -C $HOME/ril_p/repos_extra/pytest-dev__pytest rev-parse HEAD)" >> g1/a2c_p95_commits.txt
# shellcheck disable=SC2086
$PY scripts/a_edge_store.py $REPOS --work "$SCR" --repeats 31 --host "$(hostname)" \
  --out results_g1/a2c_p95_${SLURM_JOB_ID}.json --table results_g1/a2c_p95_${SLURM_JOB_ID}.csv
sha256sum results_g1/a2c_p95_${SLURM_JOB_ID}.* >> g1/run_files.sha256
echo "scratch left in $SCR (not removed)"
