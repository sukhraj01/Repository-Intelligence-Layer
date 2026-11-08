#!/bin/bash
#SBATCH --job-name=t5a_runs
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --gres=gpu:1
#SBATCH --constraint=2080ti
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=06:00:00
#SBATCH --output=ril_t5/logs/t5a_runs_%j.out
# GPU. Stage 1 of the matched-pool arms pilot (E-PILOT-ARMS2): the cells of one seed, each trained for 100
# updates of the 3,000-update schedule (configs/experiments/t5/, budget.stop_after) on the 5,000-directory pool
# (caches pool_A + pool_T3x, linked from ~/ril_t3/work; K-rank table p0_features_5000.csv) and evaluated on the
# five dev repositories without ansible (openlibrary, qutebrowser at L2 and L3; conan, haystack, streamlink at
# L2; configs/experiments/e1_bm25_reproduction.yaml, role dev, over a link-only copy of the E3 cache). The CUDA
# gate runs inside each training and evaluation. Checkpoints, float16 copies and encoded stores live in
# node-local space; --drop-eval-stores removes a run's encoded stores after its evaluation. $HOME receives
# only the per-run result directories and the Slurm/out files.
# Memory estimate: pool cache of 5,000 directories 9 GB (1.8 MB each, T3) + training process 3 GB
# + evaluation 6 GB = about 18 GB peak; 24 GB requested, QOS ceiling 32,000 MB. GPU 6.9 GB for the shape.
# Time: 100 x 2.65 s = 4.4 min of updates + one evaluation of 316k unit texts at 229 texts/s (about 23 min).
#   sbatch --export=ALL,SEED=0,RIL_COMMIT=<hash>,CELLS="raw sub_d0" ril_t5/scripts/ada/t5_runs.sbatch
set -euo pipefail
W=$HOME/ril_t5
X2=$HOME/ril_x2
E=$HOME/ril_e
SEED=${SEED:?set SEED}
PREFIX=${PREFIX:-t5a}
CELLS=${CELLS:-raw sub_d0 filter_cre filter_bm25 filter_srs weight_cre curr_cre}
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$X2/venv_gpu$PYV/bin/python
DATE=${DATE:-2026-10-31}
CK=${TMPDIR:-/tmp}/ril_t5_${SLURM_JOB_ID}
mkdir -p "$W/logs" "$W/out" "$CK/ckpt" "$CK/eval"
cd "$W"
export HF_HOME=$E/hf_cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export PYTHONPATH="$X2/overlay_cre:$W"
[ -z "${RETAIN_DIR:-}" ] || { mkdir -p "$RETAIN_DIR"; export RETAIN_DIR; }  # final-model retention: checkpoint.retain_final (D76)
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv > "out/nvidia_${SLURM_JOB_ID}.txt" || true
{ echo "host=$(hostname)"; echo "ril_commit=${RIL_COMMIT:-none}"; df -h /tmp "$HOME" | tail -2; } \
  > "out/env_runs_${SLURM_JOB_ID}.txt"
# evaluation set: the five dev repositories of the E3 cache without ansible, as links (no data copied)
"$PY" scripts/curve_subset_cache.py "$HOME/ril_t1/work/e3_cache" work/e3_cache_dev5 \
  internetarchive__openlibrary qutebrowser__qutebrowser streamlink__streamlink conan-io__conan deepset-ai__haystack
CONFIGS=""
for c in $CELLS; do CONFIGS="$CONFIGS configs/experiments/t5/${PREFIX}_${c}_s${SEED}.yaml"; done
"$PY" scripts/train.py run-batch $CONFIGS \
  --cache work/pool_A.jsonl.gz:work/pool_T3x.jsonl.gz --feature-table work/p0_features_5000.csv \
  --results-root "$W/results" --work-root "$CK/ckpt" --date "$DATE" --device cuda --drop-eval-stores \
  --e1-config configs/experiments/e1_bm25_reproduction.yaml --prep "$X2/prep" \
  --e3-cache work/e3_cache_dev5 --data-root "$X2/raw" --work "$CK/eval" \
  > "out/runs_${SLURM_JOB_ID}.json"
du -sh "$CK" >> "out/env_runs_${SLURM_JOB_ID}.txt" || true
rm -rf "$CK"
echo done
