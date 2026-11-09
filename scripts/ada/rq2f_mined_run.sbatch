#!/bin/bash
#SBATCH --job-name=rq2f_mined
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --gres=gpu:1
#SBATCH --constraint=2080ti
#SBATCH --exclude=gnode004,gnode044
#SBATCH --cpus-per-task=4
#SBATCH --mem=30G
#SBATCH --time=02:00:00
#SBATCH --output=ril_rq2f/logs/%x_%j.out
# GPU. One run of the RQ2 final experiment on the mined set (account C): the cell RUN_ID (for example
# mined_raw_u100_s100), 100 updates of the 3,000-update schedule on the full mined store's non_test
# directories (cache and BM25 feature table of the prep job), scored on the dev set only (the five repositories
# without ansible, D131). The final model is retained under RETAIN_DIR (D129); the eight repositories and the
# executable 377 are scored later, from the retained models, by rq2f_final_sets.sbatch after the dev analysis.
# Resumable: run-batch skips a run whose results.json holds the evaluation, DATE fixes the result directory
# name, and a failed or node-lost job is simply submitted again. The CUDA gate runs inside the training and
# the evaluation. Checkpoints, float16 copies and encoded stores live in node-local space; the encoded stores
# are removed after the evaluation. $HOME receives the result directory, the retained model and the logs.
# Memory estimate (projected from the pilot's measured per-unit numbers, docs/RQ2_LAUNCH_PLAN.md stage 3): the
# cache of about 5,800 directories is 5.6 GB compressed and 17 GB decoded; training process 3 GB; evaluation
# 6 GB: about 26 GB peak against the 32,000 MB per-user limit; 30 GB requested. Check sacct MaxRSS after the
# first job. GPU 6.9 GB for the shape. Time: 100 x 2.65 s of updates plus one dev evaluation, 0.42 GPU-hours
# measured; two hours requested for cache loading and node variation.
# Submitted by scripts/rq2_submit.py (never by hand):
#   sbatch --export=ALL,RUN_ID=<id>,RIL_COMMIT=<hash>,DATE=<YYYY-MM-DD>,RETAIN_DIR=<abs dir> scripts/ada/rq2f_mined_run.sbatch
set -euo pipefail
W=$HOME/ril_rq2f
X2=$HOME/ril_x2
E=$HOME/ril_e
RUN_ID=${RUN_ID:?set RUN_ID}
DATE=${DATE:?set DATE}
RIL_COMMIT=${RIL_COMMIT:?set RIL_COMMIT}
RETAIN_DIR=${RETAIN_DIR:?set RETAIN_DIR (mined-set models are retained, D129)}
case "$RUN_ID" in mined_*) ;; *) echo "RUN_ID $RUN_ID is not a mined-set run"; exit 4;; esac
case "$RETAIN_DIR" in /*) ;; *) echo "RETAIN_DIR must be absolute"; exit 4;; esac
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$X2/venv_gpu$PYV/bin/python
NODE_FREE=$(df -Pm "${TMPDIR:-/tmp}" | awk 'NR==2{print $4}')
[ "$NODE_FREE" -gt 10000 ] || { echo "node-local space on $(hostname) has only $NODE_FREE MB free"; exit 4; }
CK=${TMPDIR:-/tmp}/ril_rq2f_${SLURM_JOB_ID}
mkdir -p "$W/logs" "$W/out" "$CK/ckpt" "$CK/eval" "$RETAIN_DIR"
cd "$W"
export HF_HOME=$E/hf_cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export PYTHONPATH="$X2/overlay_cre:$W"
export RETAIN_DIR RIL_COMMIT
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv > "out/nvidia_${SLURM_JOB_ID}.txt" || true
{ echo "host=$(hostname)"; echo "ril_commit=$RIL_COMMIT"; echo "run_id=$RUN_ID"; df -h "${TMPDIR:-/tmp}" "$HOME" | tail -2; } \
  > "out/env_${RUN_ID}_${SLURM_JOB_ID}.txt"
# resolve the size-matched subsample's size from the prep summary, render the configurations (hash checked)
FSIZE=$("$PY" -c 'import json; print(json.load(open("work/prep_summary.json"))["filter_size"])')
"$PY" scripts/rq2_plan.py render --out work/configs_resolved --filter-size "$FSIZE" > "out/render_${SLURM_JOB_ID}.json"
CONFIG=work/configs_resolved/${RUN_ID}.yaml
[ -f "$CONFIG" ] || { echo "no configuration for $RUN_ID"; exit 4; }
# dev evaluation set: the five dev repositories of the E3 cache without ansible, as links (no data copied)
"$PY" scripts/curve_subset_cache.py "$HOME/ril_t1/work/e3_cache" work/e3_cache_dev5 \
  internetarchive__openlibrary qutebrowser__qutebrowser streamlink__streamlink conan-io__conan deepset-ai__haystack
"$PY" scripts/train.py run-batch "$CONFIG" \
  --cache work/mined.jsonl.gz --feature-table work/features_mined.csv \
  --results-root "$W/results" --work-root "$CK/ckpt" --date "$DATE" --device cuda --drop-eval-stores \
  --eval-set dev --home "$HOME" --work "$CK/eval" \
  > "out/run_${RUN_ID}_${SLURM_JOB_ID}.json"
du -sh "$CK" >> "out/env_${RUN_ID}_${SLURM_JOB_ID}.txt" || true
rm -rf "$CK"
echo done
