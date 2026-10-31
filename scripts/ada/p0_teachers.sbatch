#!/bin/bash
#SBATCH --job-name=p0_teachers
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --gres=gpu:1
#SBATCH --constraint=2080ti
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:30:00
#SBATCH --output=ril_t3/logs/p0_teachers_%j.out
# GPU. Teacher pass of one dense teacher (TEACHER=coderankembed|swerankembed-small, 1,024 tokens,
# float16) over the example cache of the 3,000 pool directories not covered by selection A
# (work/pool_T3x.jsonl.gz; A's ranks are reused from ril_t2). Writes the K-rank of every positive and
# the top 64 non-positive candidates. The CUDA matmul gate runs before the model loads. Resumable per
# directory. Memory estimate: cache about 4.5 to 6 GB of text, one repository's vectors up to 0.2 GB,
# the model; 16 GB requested. Wall time: T2 measured 3,940 s (CodeRankEmbed) and 3,918 s
# (SweRankEmbed-Small) for 2,000 directories, so about 1.7 h for 3,000.
#   sbatch --export=ALL,RIL_COMMIT=<hash>,TEACHER=<name> ril_t3/scripts/ada/p0_teachers.sbatch
set -euo pipefail
W=$HOME/ril_t3
X2=$HOME/ril_x2
E=$HOME/ril_e
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$X2/venv_gpu$PYV/bin/python
CACHE=${CACHE:-work/pool_T3x.jsonl.gz}
t=${TEACHER:?set TEACHER}
cd "$W"
export HF_HOME=$E/hf_cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export PYTHONPATH="$X2/overlay_cre:$W"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv > "out/nvidia_p0_${SLURM_JOB_ID}.txt" || true
"$PY" scripts/train.py teacher "$CACHE" "work/ranks_T3x_${t}.jsonl" "work/mined_T3x_${t}.jsonl.gz" --teacher "$t" \
  --keep 64 --cut 1024 --device cuda --batch-size 64 > "out/p0_teacher_${t}_${SLURM_JOB_ID}.json"
echo done
