#!/bin/bash
# CPU-only acquisition. Supply verified partition/account/QOS when submitting.
# Resource/time requests below are envelopes, not measured source costs.
#SBATCH --job-name=c-rewrite-stage
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=01:00:00
#SBATCH --output=logs/c_rewrite_stage_%j.log
set -euo pipefail
: "${SLURM_JOB_ID:?requires a Slurm CPU allocation}"
: "${RIL_RESOURCES_VERIFIED:?verify allocation, quota, disk and source bounds first}"
[[ "$RIL_RESOURCES_VERIFIED" == 1 ]]
cd "${RIL_ROOT:?set staged checkout root}"
: "${RIL_PYTHON:?set verified Python 3.11 interpreter}"
: "${RIL_DATA_REVISION:?set full pinned dataset commit SHA}"
: "${RIL_STAGE_MANIFEST:?set persistent manifest path}"
: "${RIL_STAGE_TOTAL_BYTES:?set explicitly reviewed total source byte bound}"
: "${RIL_STAGE_FILE_BYTES:?set explicitly reviewed individual file byte bound}"
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}" RIL_CLUSTER=1
"$RIL_PYTHON" -c 'import sys; assert sys.version_info[:2] == (3, 11)'
CONFIG=${RIL_CONFIG:-configs/experiments/c_rewrite_bm25_dev.yaml}
ARGS=(--config "$CONFIG" --manifest "$RIL_STAGE_MANIFEST" --revision "$RIL_DATA_REVISION"
      --max-total-bytes "$RIL_STAGE_TOTAL_BYTES" --max-file-bytes "$RIL_STAGE_FILE_BYTES")
if [[ ! -e "$RIL_STAGE_MANIFEST" ]]; then
  "$RIL_PYTHON" scripts/c_stage_rewrite.py manifest "${ARGS[@]}"
fi
"$RIL_PYTHON" scripts/c_stage_rewrite.py plan "${ARGS[@]}"
"$RIL_PYTHON" scripts/c_stage_rewrite.py fetch "${ARGS[@]}"
"$RIL_PYTHON" scripts/c_stage_rewrite.py verify "${ARGS[@]}"
