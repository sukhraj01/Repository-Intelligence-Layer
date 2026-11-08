#!/bin/bash
#SBATCH --job-name=rq3_prepare
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=04:00:00
#SBATCH --output=ril_rq3/logs/prepare_%j.out
# CPU only. E-RQ3-PILOT-PREP: regenerate the assembled contexts of the dev instances (BM25 and
# RRF(BM25, dense) first stages, same assembly for both) and write the pilot's prompt files. No model
# call, no network. Same code path and resources as scripts/ada/assembly_gold.sbatch (8 GB, 2 CPUs).
# Each instance is checked out at its base commit on node-local disk (regenerable).
#   rsync -a --exclude __pycache__ ril scripts configs ada:ril_rq3/
#   sbatch ril_rq3/scripts/ada/rq3_prepare.sbatch
set -euo pipefail
W=$HOME/ril_rq3
PY=${PY:-$HOME/ril_e/venv_ril310/bin/python}
CFG=${CFG:-configs/experiments/rq3_pilot_prepare.yaml}
OUT=${OUT:-$W/prepared_dev100}   # a new directory per draw: prompt files are never overwritten
mkdir -p "$W/logs"
cd "$W"
export PYTHONPATH="$W"
$PY scripts/rq3_pilot.py prepare "$OUT" --from-cache "$CFG" --seed 0
sha256sum "$CFG" > "$OUT/config_hash.txt"
wc -l "$OUT/items.jsonl"
echo done
