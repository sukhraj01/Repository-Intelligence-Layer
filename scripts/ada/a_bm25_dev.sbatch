#!/bin/bash
#SBATCH --job-name=a_bm25_dev
#SBATCH --partition=u22
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --time=04:00:00
#SBATCH --output=ril_a/logs/a_bm25_dev_%j.out
# CPU only. Session A1 on the development folders (A1-DEV, configs/experiments/a_bm25_dev.yaml):
# STAGE=stage1 runs the three tokenizers at k1 1.5 / b 0.75; STAGE=stage2 TOKENIZER=<name> runs the
# k1 x b grid on the tokenizer chosen in stage 1. Resumable per folder, level and cell. Needs
# ~/ril_a/raw and ~/ril_a/venv_a<py> (a_fetch_dev.sbatch). Account and QOS are given at submission:
#   rsync -a --exclude __pycache__ ril scripts configs ada:ril_a/
#   ssh ada 'sbatch -A <account> -q <qos> --export=ALL,STAGE=stage1 ril_a/scripts/ada/a_bm25_dev.sbatch'
set -euo pipefail
W=$HOME/ril_a
STAGE=${STAGE:?set STAGE=stage1 or stage2}
TOKENIZER=${TOKENIZER:-}
cd "$W"
export PYTHONPATH="$W"
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
ARGS=(run configs/experiments/a_bm25_dev.yaml "$W/raw" "$W/out_bm25_dev" --stage "$STAGE")
[ -n "$TOKENIZER" ] && ARGS+=(--tokenizer "$TOKENIZER")
"$W/venv_a$PYV/bin/python" scripts/a_bm25_dev.py "${ARGS[@]}"
echo done
