#!/bin/bash
#SBATCH --job-name=e1_confirm
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=ril_e/logs/e1_confirm_%j.out
# CPU only. One run of the stated BM25 setting on the test folders (SWE-bench Verified, chunk level).
# K1 and B are exported by the submitter and recorded beforehand; they are never chosen on these folders.
#   sbatch --export=ALL,K1=2.0,B=0.75 ril_e/scripts/ada/e1_confirm.sbatch
set -euo pipefail
W=$HOME/ril_e
mkdir -p "$W/logs" "$W/out_confirm_k1_${K1:?}_b_${B:?}"
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
cd "$W"
export PYTHONPATH="$W"
"$W/venv_ril$PYV/bin/python" scripts/ada/e1_confirm.py configs/experiments/e1_bm25_reproduction.yaml \
  "$W/raw" "$W/out_confirm_k1_${K1}_b_${B}" "$K1" "$B"
echo done
