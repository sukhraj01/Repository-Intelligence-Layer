#!/bin/bash
#SBATCH --job-name=eval_encode
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --gres=gpu:1
#SBATCH --constraint=2080ti
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=03:00:00
#SBATCH --output=ril_eval/logs/eval_encode_%j.out
# GPU. Dense stores of the evaluation repositories (D100, E-EVAL-REPOS-BUILD): the base encoder at
# 512 tokens over the unit-text and query stores of eval_build_cpu.sbatch. Encoding only; no
# retrieval result is computed. The run log records the CUDA gate (a real matrix product checked
# against the CPU) and the seconds per store. Environment and models are those of ril_x2.
#   sbatch --export=ALL,RIL_COMMIT=<hash> ril_eval/scripts/ada/eval_encode.sbatch
set -euo pipefail
W=$HOME/ril_eval
X2=$HOME/ril_x2
E=$HOME/ril_e
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
GV=$X2/venv_gpu$PYV
export HF_HOME=$E/hf_cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
cd "$W"
mkdir -p out
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv > "$W/out/nvidia_${SLURM_JOB_ID}.txt" || true
echo "ril_commit=${RIL_COMMIT:-none}" > "$W/out/env_encode_${SLURM_JOB_ID}.txt"
PYTHONPATH="$X2/overlay_cre:$W" "$GV/bin/python" scripts/x2_run.py encode "$W/prep" "$W/enc" \
  "$W/out/encode_coderankembed_${SLURM_JOB_ID}.json" --cuts 512 --kinds units queries --encoders coderankembed
echo done
