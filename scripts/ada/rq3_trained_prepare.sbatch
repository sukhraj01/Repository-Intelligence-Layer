#!/bin/bash
#SBATCH --job-name=rq3_trained_prep
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=ril_rq3t/logs/%x_%j.out
# CPU only, no network, no model call. Pseudonymised, screened prompts of the trained arms (E-RQ3-TRAINED-ARMS,
# D120): for every model in MODELS (run ids joined by colons) the driver's own `prepare` is run on that model's
# contexts at BUDGET (default 8,000) with the arm name tr_<run id>, so a trained arm's prompts come from the
# untrained arms' builder, screen and pseudonymisation unchanged. One prepared directory per model (the driver's
# `run` takes one prepared directory per arm), under $W/out/prepared_trained_b<BUDGET>_<job>/<run id>. Each
# directory gets the same ids_heldout.txt and ids_confirmatory.txt as the untrained set (D111). Set
# RIL_FORBIDDEN_EMAILS to the operator's address(es) so that the screen rejects them. Inputs on the account that
# builds the prompts: $HOME/ril_e/raw/data, the Verified table (VERIFIED_PARQUET), the subset and the held-out
# file ($W/in).
#   sbatch --export=ALL,RIL_COMMIT=<hash>,MODELS=<id:id:...>[,BUDGET=16000] ril_rq3t/scripts/ada/rq3_trained_prepare.sbatch
set -euo pipefail
W=${RQ3T_DIR:-$HOME/ril_rq3t}
PY=${PY:-$HOME/ril_e/venv_ril310/bin/python}
[ -x "$PY" ] || PY=$HOME/ril_x2/venv_gpu310/bin/python   # account C has the GPU environment only
MODELS=${MODELS:?set MODELS (run ids joined by colons)}
BUDGET=${BUDGET:-8000}
VERIFIED_PARQUET=${VERIFIED_PARQUET:-$HOME/ril_rq3/data/verified.parquet}
OUT=$W/out/prepared_trained_b${BUDGET}_${SLURM_JOB_ID:-0}
mkdir -p "$OUT" "$W/logs"
cd "$W"
for RID in ${MODELS//:/ }; do
  [ -d "$W/ctx/$RID/instances" ] || { echo "no contexts for $RID under $W/ctx"; exit 4; }
  "$PY" -I scripts/rq3_driver.py prepare "$W/ctx/$RID" "$OUT/$RID" \
    --raw "$HOME/ril_e/raw/data" --issues-parquet "$VERIFIED_PARQUET" \
    --subset "$W/in/executable_instances_v1.json" --heldout "$W/in/heldout_v1.json" \
    --budget "$BUDGET" --arms "tr_$RID" --seed 0
  sha256sum "$OUT/$RID/items.jsonl" > "$OUT/$RID/items.sha256"
done
sha256sum "$W/in/heldout_v1.json" > "$OUT/input_hashes.txt"
echo "== prepare done $(date -u +%FT%TZ)"; ls "$OUT"
