#!/bin/bash
#SBATCH --job-name=e3_eval
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=6G
#SBATCH --time=04:00:00
#SBATCH --output=ril_e/logs/e3_eval_%j.out
# CPU only. Evaluates one experiment configuration on the cache (EVAL_CONFIG=configs/experiments/<name>.yaml,
# OUT=<directory under ril_e>). A specification that touches test instances must be a single-setting confirm
# specification (checked before any file is read). Resumable per instance.
#   sbatch --export=ALL,EVAL_CONFIG=configs/experiments/e3_graph_signal.yaml,OUT=e3_eval_dev ril_e/scripts/ada/e3_eval.sbatch
set -euo pipefail
W=$HOME/ril_e
mkdir -p "$W/logs" "$W/${OUT:?}"
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
cd "$W"
export PYTHONPATH="$W"
"$W/venv_ril$PYV/bin/python" scripts/e3_run.py eval "${EVAL_CONFIG:?}" "$W/e3_cache" "$W/$OUT"
echo done
