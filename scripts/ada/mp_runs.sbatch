#!/bin/bash
#SBATCH --job-name=mp_runs
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --gres=gpu:1
#SBATCH --constraint=2080ti
#SBATCH --exclude=gnode004,gnode044
#SBATCH --cpus-per-task=4
#SBATCH --mem=20G
#SBATCH --time=06:00:00
#SBATCH --output=ril_mp/logs/mp_runs_%j.out
# GPU. Mined-set integration pilot (E-MINED-PILOT): the cells of one seed (RAW, FILTER K = 20 with the BM25
# teacher, RAW on a random subset of FILTER's size), each trained for 100 updates of the 3,000-update
# schedule on the pool-like mined directories (cache and BM25 feature table of mp_prep.sbatch) and evaluated
# on the five dev repositories without ansible exactly as in E-PILOT-ARMS2 (configs/experiments/mp/). The CUDA
# gate runs inside each training and evaluation. Checkpoints, float16 copies and encoded stores live in
# node-local space; --drop-eval-stores removes a run's encoded stores after its evaluation. $HOME receives
# only the per-run result directories and the Slurm/out files.
# Memory estimate (new scale: the mined cache replaces the 5,000-directory pool): cache of about 1,290
# directories, 1.3 GB compressed on disk (measured on the first 300 directories: 302 MB), decoded about
# 4 GB at the 3x the earlier pool showed (9 GB on disk to the 3 GB training process); training process 3 GB;
# evaluation 6 GB: about 13 GB peak; 20 GB requested, QOS ceiling 32,000 MB. GPU 6.9 GB for the shape.
# Time: per cell 100 x 2.65 s of updates (fewer if the set is small) + one evaluation of 316k unit texts
# (about 23 min), 0.45 GPU-hours per cell measured in E-PILOT-NOISE.
#   sbatch --export=ALL,SEED=0,RIL_COMMIT=<hash>,CELLS="raw filter_bm25 sub" ril_mp/scripts/ada/mp_runs.sbatch
set -euo pipefail
W=$HOME/ril_mp
X2=$HOME/ril_x2
E=$HOME/ril_e
SEED=${SEED:?set SEED}
CELLS=${CELLS:-raw filter_bm25 sub}
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$X2/venv_gpu$PYV/bin/python
DATE=${DATE:-2026-11-03}
CK=${TMPDIR:-/tmp}/ril_mp_${SLURM_JOB_ID}
mkdir -p "$W/logs" "$W/out" "$CK/ckpt" "$CK/eval"
cd "$W"
export HF_HOME=$E/hf_cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export PYTHONPATH="$X2/overlay_cre:$W"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv > "out/nvidia_${SLURM_JOB_ID}.txt" || true
{ echo "host=$(hostname)"; echo "ril_commit=${RIL_COMMIT:-none}"; df -h /tmp "$HOME" | tail -2; } \
  > "out/env_runs_${SLURM_JOB_ID}.txt"
# evaluation set: the five dev repositories of the E3 cache without ansible, as links (no data copied)
"$PY" scripts/curve_subset_cache.py "$HOME/ril_t1/work/e3_cache" work/e3_cache_dev5 \
  internetarchive__openlibrary qutebrowser__qutebrowser streamlink__streamlink conan-io__conan deepset-ai__haystack
CONFIGS=""
for c in $CELLS; do CONFIGS="$CONFIGS configs/experiments/mp/mp_${c}_s${SEED}.yaml"; done
"$PY" scripts/train.py run-batch $CONFIGS \
  --cache work/mined.jsonl.gz --feature-table work/features_mined.csv \
  --results-root "$W/results" --work-root "$CK/ckpt" --date "$DATE" --device cuda --drop-eval-stores \
  --e1-config configs/experiments/e1_bm25_reproduction.yaml --prep "$X2/prep" \
  --e3-cache work/e3_cache_dev5 --data-root "$X2/raw" --work "$CK/eval" \
  > "out/runs_${SLURM_JOB_ID}.json"
du -sh "$CK" >> "out/env_runs_${SLURM_JOB_ID}.txt" || true
rm -rf "$CK"
echo done
