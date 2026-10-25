#!/bin/bash
#SBATCH --job-name=t2_teachers
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --gres=gpu:1
#SBATCH --constraint=2080ti
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=04:00:00
#SBATCH --output=ril_t2/logs/t2_teachers_%j.out
# GPU. Teacher passes of the smoke pilots over the example cache of selection A (2,000 pool
# directories): for each dense teacher (CodeRankEmbed, SweRankEmbed-Small; pinned snapshots, 1,024
# tokens, float16, as E-POOL-RANKS) one pass that writes the K-rank of every positive (E-POOL-RANKS
# rank rows) and the top 64 non-positive candidates (mined rows for teacher-mined negatives). CUDA
# gate before the model loads. Resumable per teacher and directory (TEACHERS to restrict).
# Memory estimate (written before the first run): the cache holds about 2.0 GB of function text
# (2,000 directories x 1.0 MB mean corpus, measured over the pool) plus Python object overhead,
# so 3-4 GB of host memory, plus one repository's vectors (largest about 0.2 GB) and the model;
# 16 GB requested. GPU: 4.4 GB peak at 1,024 tokens, batch 64 (X2/X3 rows). Wall time: X3's model
# (0.000203 s per function + 0.00355 s per encoded text) with about 2.35 million functions and a
# dedup ratio near 0.35 for a random subset gives about 1 hour per teacher.
#   sbatch --export=ALL,RIL_COMMIT=<hash> ril_t2/scripts/ada/t2_teachers.sbatch
set -euo pipefail
W=$HOME/ril_t2
X2=$HOME/ril_x2
E=$HOME/ril_e
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$X2/venv_gpu$PYV/bin/python
CACHE=${CACHE:-work/pool_A.jsonl.gz}
cd "$W"
export HF_HOME=$E/hf_cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export PYTHONPATH="$X2/overlay_cre:$W"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv > "out/nvidia_${SLURM_JOB_ID}.txt" || true
for t in ${TEACHERS:-coderankembed swerankembed-small}; do
  "$PY" scripts/train.py teacher "$CACHE" "work/ranks_A_${t}.jsonl" "work/mined_A_${t}.jsonl.gz" --teacher "$t" \
    --keep 64 --cut 1024 --device cuda --batch-size 64 > "out/teacher_${t}_${SLURM_JOB_ID}.json"
done
echo done
