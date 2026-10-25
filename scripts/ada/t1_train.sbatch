#!/bin/bash
#SBATCH --job-name=t1_train
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --gres=gpu:1
#SBATCH --constraint=2080ti
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=04:00:00
#SBATCH --output=ril_t1/logs/t1_train_%j.out
# GPU template of one training run (and optionally its evaluation) of the training stack. The run
# starts with the real CUDA matrix-product gate (compute capability >= 7.0, result checked against
# the CPU; ril.evaluation.x2_jobs.cuda_gate) before any data is read, so a bad card fails in seconds.
# Inputs come from CPU stages run before (no GPU held while they run): the example cache
# (scripts/train.py select + cache), and for teacher-mined negatives the mined file (mine; a dense
# teacher's mining is its own GPU job with DEVICE=cuda). Resumable: resubmitting the same command
# continues from the newest step checkpoint (the batch plan is replayed, not recomputed).
# Checkpoints of a 137M encoder with optimizer state take about 1.6 GB each; $HOME had under 2 GB
# free on 2026-10-25, so CKPT defaults to node-local temporary space and the final model is copied
# to $HOME only in half precision (checkpoint.final_dtype). Charge the job's GPU-hours from sacct in
# docs/COMPUTE.md. Evaluation (EVAL=1) reads ~/ril_t1/work/e3_cache, the E3 cache with the D18
# no-module readings (rsync -a data/processed/x2/e3_cache/ ada:ril_t1/work/e3_cache/).
#   sbatch --export=ALL,CONFIG=configs/experiments/<exp>.yaml,CACHE=work/pool.jsonl.gz,\
#          MINED=work/mined_<teacher>.jsonl.gz,EVAL=1,RIL_COMMIT=<hash> ril_t1/scripts/ada/t1_train.sbatch
set -euo pipefail
W=$HOME/ril_t1
X2=$HOME/ril_x2
E=$HOME/ril_e
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$X2/venv_gpu$PYV/bin/python
FT=${FEATURES:-$W/results/tables/x3_pool_ranks_features.csv}
DATE=${DATE:-$(date -u +%F)}
CKPT=${CKPT:-${TMPDIR:-/tmp}/ril_t1_ckpt}
mkdir -p "$W/logs" "$W/out" "$CKPT"
cd "$W"
export HF_HOME=$E/hf_cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export PYTHONPATH="$X2/overlay_cre:$W"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv > "$W/out/nvidia_${SLURM_JOB_ID}.txt" || true
MARG=(); [ -n "${MINED:-}" ] && MARG=(--mined "$MINED")
"$PY" scripts/train.py train "$CONFIG" "$CACHE" --results-root "$W/results" --work-root "$CKPT" \
  --date "$DATE" --device cuda --feature-table "$FT" "${MARG[@]}" > "out/train_${SLURM_JOB_ID}.json"
FINAL=$("$PY" -c 'import json,sys; r=json.load(open(sys.argv[1])); print(r.get("final_model",""))' "out/train_${SLURM_JOB_ID}.json")
RES=$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1]))["result_dir"])' "out/train_${SLURM_JOB_ID}.json")
if [ -n "$FINAL" ]; then
  KEEP=$W/models/$(basename "$(dirname "$FINAL")")
  mkdir -p "$KEEP" && rsync -a "$FINAL/" "$KEEP/final/"
  if [ "${EVAL:-0}" = 1 ]; then
    mkdir -p work/dense && ln -sfn "$X2/dense/coderankembed__t512" work/dense/coderankembed__t512
    "$PY" scripts/train.py eval "$CONFIG" "$KEEP/final" "$RES" \
      --e1-config configs/experiments/e1_bm25_reproduction.yaml --prep "$X2/prep" --e3-cache "$W/work/e3_cache" \
      --data-root "$X2/raw" --work "$W/work/eval" --dense-root "$W/work/dense" --device cuda \
      --baseline "coderankembed__t512=$X2/enc/coderankembed__t512" > "out/eval_${SLURM_JOB_ID}.json"
  fi
fi
echo done
