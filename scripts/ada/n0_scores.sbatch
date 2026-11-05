#!/bin/bash
#SBATCH --job-name=n0_scores
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=04:00:00
#SBATCH --output=ril_n7/logs/n0_scores_%j.out
# Per-function teacher scores for the 5,000-directory pool (E-PILOT-NOISE, D48): the rank of a
# replacement positive needs the score of every function of its snapshot, and the earlier rank files
# keep only the positives' ranks. TEACHER=bm25 is a CPU job (submit without --gres); a dense teacher
# is a GPU job:
#   sbatch --export=ALL,RIL_COMMIT=<hash>,TEACHER=bm25 ril_n7/scripts/ada/n0_scores.sbatch
#   sbatch --gres=gpu:1 --constraint=2080ti --export=ALL,RIL_COMMIT=<hash>,TEACHER=swerankembed-small \
#     ril_n7/scripts/ada/n0_scores.sbatch
# Output: work/scores_P5000_<teacher>.jsonl (float32, 4.9M functions: about 26 MB per teacher),
# resumable per directory. The CUDA matmul gate runs before the model loads (score_job).
# Memory estimate: the two example caches hold about 9 GB of text in memory (T3), one repository's
# vectors up to 0.2 GB, the model 0.5 GB; 24 GB requested. Time: the rank pass over the same 5,000
# directories took 1.6 GPU-hours per dense teacher (P0).
set -euo pipefail
W=$HOME/ril_n7
X2=$HOME/ril_x2
E=$HOME/ril_e
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$X2/venv_gpu$PYV/bin/python
t=${TEACHER:?set TEACHER}
cd "$W"
mkdir -p out logs
export HF_HOME=$E/hf_cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export PYTHONPATH="$X2/overlay_cre:$W"
DEV=cpu
if [ "$t" != bm25 ]; then
  DEV=cuda
  nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv > "out/nvidia_n0_${SLURM_JOB_ID}.txt" || true
fi
{ echo "host=$(hostname)"; echo "ril_commit=${RIL_COMMIT:-none}"; df -h "$HOME" | tail -1; } > "out/env_n0_${t}_${SLURM_JOB_ID}.txt"
"$PY" scripts/train.py score work/pool_A.jsonl.gz:work/pool_T3x.jsonl.gz "work/scores_P5000_${t}.jsonl" \
  --teacher "$t" --cut 1024 --device "$DEV" --batch-size 64 > "out/n0_scores_${t}_${SLURM_JOB_ID}.json"
echo done
