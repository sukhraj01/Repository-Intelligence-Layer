#!/bin/bash
#SBATCH --job-name=n8_runs
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --gres=gpu:1
#SBATCH --constraint=2080ti
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=06:00:00
#SBATCH --output=ril_n7/logs/n8_runs_%j.out
# GPU. Sibling-noise pilot (E-PILOT-NOISE-SIB): the five cells of one seed at noise rate 0.4, each trained for
# 100 updates of the 3,000-update schedule on the 5,000-directory pool with the pairs noised as in
# ril/training/noise.py, kind sibling (configs/experiments/n8/), K-ranks of FILTER recomputed on the noised positives from work/scores_P5000_<teacher>.jsonl
# (n0_scores.sbatch), evaluated on the five dev repositories without ansible as in E-PILOT-ARMS2. The CUDA
# gate runs inside each training and evaluation. Checkpoints, float16 copies and encoded stores live in
# node-local space; --drop-eval-stores removes a run's encoded stores after its evaluation. $HOME receives
# only the per-run result directories and the Slurm/out files.
# Memory estimate: as t5_runs.sbatch (pool caches 9 GB + training 3 GB + evaluation 6 GB = about 18 GB peak)
# plus the two score stores (about 80 MB decoded) and one noised copy of the pool's id tuples (about
# 0.4 GB); 24 GB requested, QOS ceiling 32,000 MB. GPU 6.9 GB for the shape.
# Time: 5 cells x (100 x 2.65 s of updates + one evaluation of 316k unit texts, about 23 min) = about
# 2.25 GPU-hours per job (E-PILOT-NOISE measured 0.37 to 0.45 per run).
#   sbatch --export=ALL,SEED=0,RIL_COMMIT=<hash> ril_n7/scripts/ada/n8_runs.sbatch
set -euo pipefail
W=$HOME/ril_n7
X2=$HOME/ril_x2
E=$HOME/ril_e
SEED=${SEED:?set SEED}
RATE=40
CELLS=${CELLS:-raw oracle sub filter_bm25 filter_srs}
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$X2/venv_gpu$PYV/bin/python
DATE=${DATE:-2026-11-01}
CK=${TMPDIR:-/tmp}/ril_n7_${SLURM_JOB_ID}
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
for c in $CELLS; do CONFIGS="$CONFIGS configs/experiments/n8/n8_r${RATE}_${c}_s${SEED}.yaml"; done
"$PY" scripts/train.py run-batch $CONFIGS \
  --cache work/pool_A.jsonl.gz:work/pool_T3x.jsonl.gz --noise-scores bm25=work/scores_P5000_bm25.jsonl swerankembed-small=work/scores_P5000_swerankembed-small.jsonl \
  --results-root "$W/results" --work-root "$CK/ckpt" --date "$DATE" --device cuda --drop-eval-stores \
  --e1-config configs/experiments/e1_bm25_reproduction.yaml --prep "$X2/prep" \
  --e3-cache work/e3_cache_dev5 --data-root "$X2/raw" --work "$CK/eval" \
  > "out/runs_${SLURM_JOB_ID}.json"
du -sh "$CK" >> "out/env_runs_${SLURM_JOB_ID}.txt" || true
rm -rf "$CK"
echo done
