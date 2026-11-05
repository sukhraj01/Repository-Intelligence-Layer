#!/bin/bash
#SBATCH --job-name=t2_runs
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --gres=gpu:1
#SBATCH --constraint=2080ti
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=06:00:00
#SBATCH --output=ril_t2/logs/t2_runs_%j.out
# GPU. A batch of smoke-pilot runs (E-PILOT-K, E-PILOT-NEG, E-PILOT-LEAK): the example cache, the
# feature table and the mined file are read once, then each configuration in CONFIGS is trained
# (CUDA gate first) and evaluated by the X2 hook on the development repositories (units; and with
# EXTRA=<override.yaml> also as stated there, e.g. the Verified-six evaluation of the leakage
# pilot); the half-precision model, the checkpoints and the encoded stores stay in node-local
# space and are deleted after the run's evaluation, only the result directory (results.json,
# unit_rows.csv, query_rows.csv) and the run log go to $HOME. Finished runs are skipped, so a
# resubmission continues the batch (a run interrupted mid-training restarts from update 0 on a
# new node).
# Memory estimate (written before the first run): host = the cache (3-4 GB for 2,000 directories;
# replace with the teacher pass's measured peak) + model and evaluation stores (under 2 GB);
# 16 GB requested. GPU: 6.9 GB measured for batch 32 x (1 + 1) at 512 tokens with float16 autocast
# and gradient checkpointing (job 38747). Time per run: about 3 minutes of training (63 updates
# at 2.65 s) plus about 5 minutes of evaluation (about 48,000 dev unit texts at 201 texts/s).
#   sbatch --export=ALL,CONFIGS="configs/experiments/t2/a.yaml ...",CACHE=work/pool_A.jsonl.gz,\
#          FEATURES=work/t2_features_A.csv,MINED=work/mined_A_coderankembed.jsonl.gz,RIL_COMMIT=<hash> \
#          ril_t2/scripts/ada/t2_runs.sbatch
set -euo pipefail
W=$HOME/ril_t2
X2=$HOME/ril_x2
E=$HOME/ril_e
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$X2/venv_gpu$PYV/bin/python
DATE=${DATE:-2026-10-25}
CK=${TMPDIR:-/tmp}/ril_t2_${SLURM_JOB_ID}
mkdir -p "$W/logs" "$W/out" "$CK/dense"
cd "$W"
export HF_HOME=$E/hf_cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export PYTHONPATH="$X2/overlay_cre:$W"
[ -z "${RETAIN_DIR:-}" ] || { mkdir -p "$RETAIN_DIR"; export RETAIN_DIR; }  # final-model retention: checkpoint.retain_final (D76)
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv > "out/nvidia_${SLURM_JOB_ID}.txt" || true
{ echo "host=$(hostname)"; echo "ril_commit=${RIL_COMMIT:-none}"; df -h /tmp "$HOME" | tail -2; } \
  > "out/env_runs_${SLURM_JOB_ID}.txt"
ln -sfn "$X2/dense/coderankembed__t512" "$CK/dense/coderankembed__t512"
FARG=(); [ -n "${FEATURES:-}" ] && FARG=(--feature-table "$FEATURES")
MARG=(); [ -n "${MINED:-}" ] && MARG=(--mined "$MINED")
XARG=(); [ -n "${EXTRA:-}" ] && XARG=(--extra-eval $EXTRA)
"$PY" scripts/train.py run-batch $CONFIGS --cache "$CACHE" "${FARG[@]}" "${MARG[@]}" \
  --results-root "$W/results" --work-root "$CK/ckpt" --date "$DATE" --device cuda \
  --e1-config configs/experiments/e1_bm25_reproduction.yaml --prep "$X2/prep" \
  --e3-cache "$HOME/ril_t1/work/e3_cache" --data-root "$X2/raw" --work "$CK/eval" \
  --dense-root "$CK/dense" --baseline "coderankembed__t512=$X2/enc/coderankembed__t512" \
  "${XARG[@]}" > "out/runs_${SLURM_JOB_ID}.json"
du -sh "$CK" >> "out/env_runs_${SLURM_JOB_ID}.txt" || true
rm -rf "$CK"
echo done
