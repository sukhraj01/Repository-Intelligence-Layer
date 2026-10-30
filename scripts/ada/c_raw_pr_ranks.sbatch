#!/bin/bash
# Submit only after account C, a supported card, data size and remaining budget are verified.
#SBATCH --job-name=c-raw-pr-ranks
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --gres=gpu:1
#SBATCH --time=00:30:00
#SBATCH --output=logs/c_raw_pr_ranks_%j.log
set -euo pipefail
cd "${RIL_ROOT:?set RIL_ROOT to the staged checkout}"
: "${RIL_PYTHON:?set RIL_PYTHON to the prepared interpreter}"
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
export HF_HUB_OFFLINE=1
"$RIL_PYTHON" scripts/c_mine_prs.py dense --out "${RIL_OUT:-data/raw/c_raw_pr_pilot}"
"$RIL_PYTHON" scripts/c_mine_prs.py ranks --out "${RIL_OUT:-data/raw/c_raw_pr_pilot}" \
  --dense-scores "${RIL_OUT:-data/raw/c_raw_pr_pilot}/dense_scores.json"
