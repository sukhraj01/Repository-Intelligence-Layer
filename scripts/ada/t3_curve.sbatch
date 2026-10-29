#!/bin/bash
#SBATCH --job-name=t3_curve
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --gres=gpu:1
#SBATCH --constraint=2080ti
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=04:00:00
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
# Time: 2,000 x 2.65 s = 1.5 h of updates + 4 evaluations of the 3-repository subset (178k unit
# texts, about 13 minutes each at the 229 texts/s measured in job 46827, whose step-0 evaluation of the full
# dev set took 43 minutes). The schedule is that of 3,000 updates; the run stops after 2,000 (GPU budget).
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
# evaluation set: dev repositories openlibrary, qutebrowser, streamlink (configs/experiments/
# e1_bm25_dev3_curve.yaml); step 0 of the full dev set (job 46827) is reused, its per-query rows
# contain these queries. The cache directory is a set of links, no data copied.
"$PY" scripts/curve_subset_cache.py "$HOME/ril_t1/work/e3_cache" work/e3_cache_curve \
  internetarchive__openlibrary qutebrowser__qutebrowser streamlink__streamlink
RD=$("$PY" -c "
import sys
from ril.training.training import RunPaths, load_train_config
c = load_train_config(sys.argv[1])
print(RunPaths.of(c, sys.argv[2], sys.argv[3], sys.argv[4]).result_dir)" \
  "configs/experiments/t3/t3_curve_raw_s${SEED}.yaml" "$W/results" "$CK/ckpt" "$DATE")
OLD=$(ls -d "$W"/results/rq2/t3_curve_raw/*/step_00000 2>/dev/null | head -1 || true)
if [ -n "$OLD" ] && [ ! -d "$RD/step_00000" ]; then mkdir -p "$RD" && cp -r "$OLD" "$RD/step_00000"; fi
"$PY" scripts/train.py curve "configs/experiments/t3/t3_curve_raw_s${SEED}.yaml" \
  "work/pool_A.jsonl.gz:work/pool_T3x.jsonl.gz" \
  --results-root "$W/results" --work-root "$CK/ckpt" --date "$DATE" --device cuda \
  --e1-config configs/experiments/e1_bm25_dev3_curve.yaml --prep "$X2/prep" \
  --e3-cache work/e3_cache_curve --data-root "$X2/raw" --work "$CK/eval" \
  > "out/curve_${SLURM_JOB_ID}.json"
du -sh "$CK" >> "out/env_curve_${SLURM_JOB_ID}.txt" || true
rm -rf "$CK"
echo done
