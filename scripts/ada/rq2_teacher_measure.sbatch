#!/bin/bash
#SBATCH --job-name=rq2_tmeasure
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --gres=gpu:1
#SBATCH --constraint=2080ti
#SBATCH --exclude=gnode004,gnode044
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=01:30:00
#SBATCH --output=ril_rq2t/logs/%x_%j.out
# GPU. Dense-teacher cost measurement (D125): 100 seeded directories of the mined example cache timed
# on the real encoder (SweRankEmbed-Small, 1,024 tokens, float16), projected over the prepared
# directories with per-repository de-duplicated text counts. The CUDA gate runs before the model
# loads. Memory: the cache is read once with equal strings shared (3 to 6 GB measured in the prep
# job, 5.4 GB MaxRSS), the model and one repository's vectors under 1 GB; 16 GB requested. Time:
# 0.4 GPU-hours expected; 1.5 hours requested.
#   sbatch --export=ALL,RIL_COMMIT=<hash>[,N=100,SEED=0] ril_rq2t/scripts/ada/rq2_teacher_measure.sbatch
set -euo pipefail
W=$HOME/ril_rq2t
X2=$HOME/ril_x2
E=$HOME/ril_e
CACHE=${CACHE:-$HOME/ril_prep/runs/full_v1/non_test/mined.jsonl.gz}
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$X2/venv_gpu$PYV/bin/python
mkdir -p "$W/logs" "$W/out"
cd "$W"
export HF_HOME=$E/hf_cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export PYTHONPATH="$X2/overlay_cre:$W"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv > "out/nvidia_${SLURM_JOB_ID}.txt" || true
{ echo "host=$(hostname)"; echo "ril_commit=${RIL_COMMIT:-none}"; } > "out/env_${SLURM_JOB_ID}.txt"
"$PY" scripts/rq2_teacher_measure.py "$CACHE" "out/teacher_measure_${SLURM_JOB_ID}.json" \
  --teacher swerankembed-small --n "${N:-100}" --seed "${SEED:-0}" --cut 1024 --batch-size 64 --device cuda
echo done
