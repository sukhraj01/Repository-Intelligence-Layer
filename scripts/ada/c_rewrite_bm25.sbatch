#!/bin/bash
# CPU-only. Supply verified partition/account/QOS and memory after a small sizing probe.
#SBATCH --job-name=c-rewrite-bm25
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=logs/c_rewrite_bm25_%j.log
set -euo pipefail
: "${SLURM_JOB_ID:?requires Slurm}"
: "${RIL_RESOURCES_VERIFIED:?verify allocation and measured memory sizing first}"
[[ "$RIL_RESOURCES_VERIFIED" == 1 ]]
cd "${RIL_ROOT:?set staged checkout root}"
: "${RIL_PYTHON:?set verified Python 3.11 interpreter}"
: "${RIL_CONFIG:?set dev config with fresh output and log paths}"
: "${RIL_STAGE_MANIFEST:?set completed source manifest}"
: "${RIL_STAGE_TOTAL_BYTES:?set reviewed total byte bound}"
: "${RIL_STAGE_FILE_BYTES:?set reviewed file byte bound}"
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}" RIL_CLUSTER=1
"$RIL_PYTHON" - "$RIL_CONFIG" <<'PY'
import sys
from pathlib import Path
import yaml
from ril.evaluation.staging import require_cluster
require_cluster()
assert sys.version_info[:2] == (3, 11)
cfg = yaml.safe_load(Path(sys.argv[1]).read_text())
assert cfg['retriever']['kind'] == 'bm25'
for key in ('output', 'log_path'):
    if key in cfg and Path(cfg[key]).exists():
        raise SystemExit('use fresh output and log paths for each registered run')
PY
"$RIL_PYTHON" scripts/c_stage_rewrite.py verify --config "$RIL_CONFIG" \
  --manifest "$RIL_STAGE_MANIFEST" --max-total-bytes "$RIL_STAGE_TOTAL_BYTES" \
  --max-file-bytes "$RIL_STAGE_FILE_BYTES"
"$RIL_PYTHON" -m ril.evaluation.run --config "$RIL_CONFIG"
