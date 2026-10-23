#!/bin/bash
#SBATCH --job-name=x2_encode
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --gres=gpu:1
#SBATCH --constraint=2080ti
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:30:00
#SBATCH --output=ril_x2/logs/x2_encode_%j.out
# GPU. Dense measurements X2, encoding stage; needs the x2_prepare job's stores and environment.
# Starts with a real CUDA matrix product checked against the CPU (the run log records it); the
# models are read from the cache (offline). STAGE=dev: development unit texts at 512 and 1024
# tokens and every query store at both cuts, then the test unit texts and chunk texts at 512, then
# query-encode and flat-search latency on the GPU. STAGE=more with CUTS=...: test units and chunks
# at further cuts (only if a cut other than 512 is selected on dev). Resumable piece by piece.
#   sbatch --export=ALL,STAGE=dev,RIL_COMMIT=<hash> ril_x2/scripts/ada/x2_encode.sbatch
set -euo pipefail
W=$HOME/ril_x2
E=$HOME/ril_e
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
GV=$W/venv_gpu$PYV
export HF_HOME=$E/hf_cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
cd "$W"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv > "$W/out/nvidia_${SLURM_JOB_ID}.txt" || true
DEV="openlibrary qutebrowser conan haystack streamlink"
TEST="astropy matplotlib seaborn flask requests xarray"
run() {  # encoder, then the rest of the x2_run.py encode arguments
  local enc=$1; shift
  if [ "$enc" = coderankembed ]; then PP="$W/overlay_cre:$W"; else PP="$W"; fi
  PYTHONPATH="$PP" "$GV/bin/python" scripts/x2_run.py encode "$W/prep" "$W/enc" "$@" --encoders "$enc"
}
STAGE=${STAGE:-dev}
for enc in coderankembed qwen3-embedding-0.6b; do
  if [ "$STAGE" = dev ]; then
    run $enc "$W/out/encode_${enc}_devunits_${SLURM_JOB_ID}.json" --cuts 512 1024 --kinds units --names $DEV
    run $enc "$W/out/encode_${enc}_queries_${SLURM_JOB_ID}.json" --cuts 512 1024 --kinds queries
  fi
done
if [ "$STAGE" = dev ]; then
  for enc in coderankembed qwen3-embedding-0.6b; do
    if [ "$enc" = coderankembed ]; then PP="$W/overlay_cre:$W"; else PP="$W"; fi
    for cut in 512 1024; do
      PYTHONPATH="$PP" RIL_COMMIT=${RIL_COMMIT:-none} RIL_DIRTY=${RIL_DIRTY:-0} "$GV/bin/python" scripts/x2_run.py measure \
        $enc $cut "$W/prep" "$W/enc/${enc}__t$cut" "$W/out/query_sets" "$W/out/latency" \
        "$W/out/measure_${enc}_t${cut}_gpu_${SLURM_JOB_ID}.json" --device cuda --store streamlink__streamlink --sample 1024
    done
  done
  for enc in coderankembed qwen3-embedding-0.6b; do
    run $enc "$W/out/encode_${enc}_rest512_${SLURM_JOB_ID}.json" --cuts 512 --kinds units chunks --names $TEST $DEV
  done
fi
if [ "$STAGE" = more ]; then
  for enc in ${ENCODERS:-coderankembed qwen3-embedding-0.6b}; do
    run $enc "$W/out/encode_${enc}_more_${SLURM_JOB_ID}.json" --cuts ${CUTS} --kinds units chunks --names $TEST $DEV
  done
fi
echo done
