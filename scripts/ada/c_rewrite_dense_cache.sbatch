#!/bin/bash
# GPU preparation only; source/model acquisition must finish in CPU allocations first.
# Pass verified supported-card constraint, partition/account/QOS at submission.
# The 30-minute/one-GPU request reserves .5 GPU-hours; verify the actual submitted limit.
#SBATCH --job-name=c-rewrite-cache
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --gres=gpu:1
#SBATCH --time=00:30:00
#SBATCH --output=logs/c_rewrite_cache_%j.log
set -euo pipefail
: "${SLURM_JOB_ID:?requires Slurm}"
: "${RIL_RESOURCES_VERIFIED:?verify allocation, card, measured memory and actual time limit}"
[[ "$RIL_RESOURCES_VERIFIED" == 1 ]]
cd "${RIL_ROOT:?set staged checkout root}"
: "${RIL_PYTHON:?set verified GPU Python 3.11 interpreter}"
: "${RIL_CONFIG:?set paired dense dev config with unused cache directory}"
: "${RIL_GPU_HOURS_REMAINING:?set verified remaining C GPU-hours}"
: "${RIL_SCORE_BYTES:?set measured score-array ceiling in bytes}"
: "${RIL_BATCH_SIZE:?set measured safe encoding batch size}"
: "${RIL_STAGE_MANIFEST:?set completed source manifest}"
: "${RIL_STAGE_TOTAL_BYTES:?set reviewed total byte bound}"
: "${RIL_STAGE_FILE_BYTES:?set reviewed file byte bound}"
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}" RIL_CLUSTER=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
"$RIL_PYTHON" - "$RIL_CONFIG" "$RIL_GPU_HOURS_REMAINING" <<'PY'
import math
import sys
from pathlib import Path
import yaml
from ril.evaluation.staging import require_cluster
require_cluster(cpu_only=False)
assert sys.version_info[:2] == (3, 11)
remaining = float(sys.argv[2])
if not math.isfinite(remaining) or not .5 <= remaining <= 8:
    raise SystemExit('remaining C budget must cover this .5 GPU-hour reservation')
cfg = yaml.safe_load(Path(sys.argv[1]).read_text())
assert cfg['retriever']['kind'] == 'cached_dense'
root = Path(cfg['retriever']['cache_root'])
if root.exists() and any(root.iterdir()):
    raise SystemExit('use an unused cache directory; preserve earlier artifacts')
PY
"$RIL_PYTHON" scripts/c_stage_rewrite.py verify --config "$RIL_CONFIG" \
  --manifest "$RIL_STAGE_MANIFEST" --max-total-bytes "$RIL_STAGE_TOTAL_BYTES" \
  --max-file-bytes "$RIL_STAGE_FILE_BYTES"
# Existing producer validates the exact cached encoder revision and a real CUDA matmul.
"$RIL_PYTHON" scripts/c_prepare_rewrite_scores.py --config "$RIL_CONFIG" \
  --batch-size "$RIL_BATCH_SIZE" --max-score-bytes "$RIL_SCORE_BYTES"
