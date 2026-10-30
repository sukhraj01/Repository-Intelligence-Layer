#!/bin/bash
#SBATCH --job-name=t4a_runs
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --gres=gpu:1
#SBATCH --constraint=2080ti
#SBATCH --cpus-per-task=4
#SBATCH --mem=20G
#SBATCH --time=04:00:00
#SBATCH --output=ril_t4/logs/t4a_runs_%j.out
# GPU. Stage 1 of the arms pilot (E-PILOT-ARMS): the cells of one seed, each trained for 100 updates of
# the 3,000-update schedule (configs/experiments/t4/, budget.stop_after) and evaluated on the dev subset of
# the learning curve (openlibrary, qutebrowser at L2 and L3, streamlink at L2; configs/experiments/
# e1_bm25_dev3_curve.yaml, e3 cache of the curve). The CUDA gate runs inside each training and evaluation.
# Checkpoints, float16 copies and encoded stores live in node-local space and are deleted after each run;
# $HOME receives only the per-run result directories (about 0.3 MB) and the Slurm/out files.
# Memory estimate (session file): pool A cache (2,000 directories, about 2 GB) + training process (3 GB)
# + evaluation (6 GB, jobs 39188 and 46827) = about 11 GB peak; 20 GB requested, QOS ceiling 32,000 MB.
# GPU 6.9 GB for the shape (job 38747). Time: 100 x 2.65 s = 4.4 min of updates + one 10-13 minute
# evaluation per cell; 8 cells in under 3 hours.
# Stage 2: PREFIX=t4b CELLS="raw filter_cre curr_cre" (1,000 updates; about 0.9 GPU-hours per run, 2.8 h per seed).
#   sbatch --export=ALL,SEED=0,RIL_COMMIT=<hash> ril_t4/scripts/ada/t4_runs.sbatch
set -euo pipefail
W=$HOME/ril_t4
X2=$HOME/ril_x2
E=$HOME/ril_e
SEED=${SEED:?set SEED}
PREFIX=${PREFIX:-t4a}
CELLS=${CELLS:-raw noise filter_bm25 filter_srs filter_cre weight_cre curr_cre currrev_cre}
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$X2/venv_gpu$PYV/bin/python
DATE=${DATE:-2026-10-30}
CK=${TMPDIR:-/tmp}/ril_t4_${SLURM_JOB_ID}
mkdir -p "$W/logs" "$W/out" "$CK/ckpt" "$CK/eval"
cd "$W"
export HF_HOME=$E/hf_cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export PYTHONPATH="$X2/overlay_cre:$W"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv > "out/nvidia_${SLURM_JOB_ID}.txt" || true
{ echo "host=$(hostname)"; echo "ril_commit=${RIL_COMMIT:-none}"; df -h /tmp "$HOME" | tail -2; } \
  > "out/env_runs_${SLURM_JOB_ID}.txt"
CONFIGS=""
for c in $CELLS; do CONFIGS="$CONFIGS configs/experiments/t4/${PREFIX}_${c}_s${SEED}.yaml"; done
"$PY" scripts/train.py run-batch $CONFIGS --cache work/pool_A.jsonl.gz \
  --feature-table work/t2_features_A.csv \
  --results-root "$W/results" --work-root "$CK/ckpt" --date "$DATE" --device cuda \
  --e1-config configs/experiments/e1_bm25_dev3_curve.yaml --prep "$X2/prep" \
  --e3-cache "$HOME/ril_t3/work/e3_cache_curve" --data-root "$X2/raw" --work "$CK/eval" \
  > "out/runs_${SLURM_JOB_ID}.json"
du -sh "$CK" >> "out/env_runs_${SLURM_JOB_ID}.txt" || true
rm -rf "$CK"
echo done
