#!/bin/bash
# CPU-only pilot; partition/account/QOS are supplied after account C verification.
#SBATCH --job-name=c-raw-pr-pilot
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=06:00:00
#SBATCH --output=logs/c_raw_pr_%j.log
set -euo pipefail
cd "${RIL_ROOT:?set RIL_ROOT to the staged checkout}"
: "${GITHUB_TOKEN:?read-only token must be set in the submitting environment}"
: "${RIL_PYTHON:?set RIL_PYTHON to the verified Python 3.11 interpreter}"
"$RIL_PYTHON" -c 'import sys; assert sys.version_info[:2] == (3, 11)'
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}" RIL_CLUSTER=1
"$RIL_PYTHON" scripts/c_mine_prs.py mine --live \
  --config configs/experiments/c_raw_pr_pilot.yaml \
  --out "${RIL_OUT:-data/raw/c_raw_pr_pilot}"
"$RIL_PYTHON" scripts/c_mine_prs.py ranks --out "${RIL_OUT:-data/raw/c_raw_pr_pilot}"
