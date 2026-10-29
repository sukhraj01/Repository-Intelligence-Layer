#!/bin/bash
#SBATCH --job-name=t3_curve
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --gres=gpu:1
#SBATCH --constraint=2080ti
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=06:00:00
#SBATCH --output=ril_t3/logs/t3_curve_%j.out
# GPU. Learning curve of one seed (E-PILOT-CURVE): one RAW training of 3,000 updates and the dev
# evaluation (units; L2 and L3 over the three dev repositories of configs/experiments/e1_bm25_dev3.yaml)
# inside the run at the update counts of the configuration's curve.steps. The CUDA gate runs first.
# At each such count a float16 copy of the encoder is written to node-local space, evaluated, and
# deleted with the encoded stores; only the per-step tables (about 0.2 MB) go to $HOME. The resumable
# training checkpoint (1.6 GB, one kept) stays in node-local space: a resubmission on the SAME node
# continues from it (fixed directory per seed), on another node the run restarts from update 0
# (docs/COMPUTE.md); step tables already in $HOME are not recomputed.
# Memory estimate (session file): host about 18 GB peak = pool cache of 5,000 directories (1.8 MB each
# measured, 9 GB) + training process (3 GB) + evaluation (6 GB, job 39188); 24 GB requested, QOS
# ceiling 32,000 MB. GPU 6.9 GB measured for the shape (job 38747), evaluation adds under 2 GB.
# Time: 3,000 x 2.65 s = 2.2 h of updates + 6 evaluations of about 8 minutes.
#   sbatch --export=ALL,SEED=0,RIL_COMMIT=<hash> ril_t3/scripts/ada/t3_curve.sbatch
set -euo pipefail
W=$HOME/ril_t3
X2=$HOME/ril_x2
E=$HOME/ril_e
SEED=${SEED:?set SEED}
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$X2/venv_gpu$PYV/bin/python
DATE=${DATE:-2026-10-29}
CK=${TMPDIR:-/tmp}/ril_t3_seed${SEED}
mkdir -p "$W/logs" "$W/out" "$CK/ckpt" "$CK/eval"
cd "$W"
export HF_HOME=$E/hf_cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export PYTHONPATH="$X2/overlay_cre:$W"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv > "out/nvidia_${SLURM_JOB_ID}.txt" || true
{ echo "host=$(hostname)"; echo "ril_commit=${RIL_COMMIT:-none}"; df -h /tmp "$HOME" | tail -2; } \
  > "out/env_curve_${SLURM_JOB_ID}.txt"
"$PY" scripts/train.py curve "configs/experiments/t3/t3_curve_raw_s${SEED}.yaml" \
  "work/pool_A.jsonl.gz:work/pool_T3x.jsonl.gz" \
  --results-root "$W/results" --work-root "$CK/ckpt" --date "$DATE" --device cuda \
  --e1-config configs/experiments/e1_bm25_dev3.yaml --prep "$X2/prep" \
  --e3-cache "$HOME/ril_t1/work/e3_cache" --data-root "$X2/raw" --work "$CK/eval" \
  > "out/curve_${SLURM_JOB_ID}.json"
du -sh "$CK" >> "out/env_curve_${SLURM_JOB_ID}.txt" || true
rm -rf "$CK"
echo done
