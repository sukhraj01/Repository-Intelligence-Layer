#!/bin/bash
#SBATCH --job-name=e1_dev_sweep
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=6G
#SBATCH --time=02:00:00
#SBATCH --output=ril_e/logs/e1_dev_sweep_%j.out
# CPU only. BM25 k1 and b sweep (16 cells) on the development folders only (role dev); the test
# folders are not read. Resumable per cell. Needs ~/ril_e/raw. Submit from $HOME after rsync.
set -euo pipefail
W=$HOME/ril_e
mkdir -p "$W/logs" "$W/out_sweep"
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
cd "$W"
export PYTHONPATH="$W"
"$W/venv_ril$PYV/bin/python" scripts/ada/e1_dev_sweep.py configs/experiments/e1_bm25_reproduction.yaml "$W/raw" "$W/out_sweep"
echo done
