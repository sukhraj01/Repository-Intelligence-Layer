#!/bin/bash
#SBATCH --job-name=rq2f_injected
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --gres=gpu:1
#SBATCH --constraint=2080ti
#SBATCH --exclude=gnode004,gnode044
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=18:00:00
#SBATCH --output=ril_rq2f/logs/%x_%j.out
# GPU. One seed of the RQ2 final experiment in the injected-noise family (account A), all nine arms of the seed in
# the fixed interleaved order of the cell table (D140): RUN_IDS lists the run ids joined by colons (for example
# inj_raw_u100_s100:inj_filter_bm25_u100_s100:...): the three cells at r = 0.4 controls and exploratory, the clean RAW cell
# (rate 0, D136) and RAW and FILTER-BM25 at r = 0.1 (D137), 100 updates of the 3,000-update schedule on the 5,000-directory pool with the pairs noised at
# r = 0.4 under a fresh realisation (the noise draw is keyed on the run's seed, D82; seeds 100 to 102 are outside the
# exploratory waves), K-ranks of FILTER and WEIGHT recomputed on the noised positives from the stored score stores,
# scored on the dev set only (D131). These models are not retained (D129). Resumable as the mined script: DATE
# fixes the result directory name and run-batch skips a finished run. Checkpoints, float16 copies and encoded
# stores live in node-local space and are removed. $HOME receives the result directory and the logs.
# The pool caches (symbolic links into the earlier pilot directories) and the score stores are read in
# place from the noise pilot's work directory; nothing is copied (account A has about 5 GB free).
# Memory estimate: as n1_runs.sbatch (pool caches 9 GB + training 3 GB + evaluation 6 GB = about 18 GB measured
# peak) plus the two score stores and one noised copy of the pool's id tuples; 24 GB requested.
# Time: 0.42 GPU-hours measured per arm, nine arms; two hours per arm requested (set by scripts/rq2_submit.py).
# Submitted by scripts/rq2_submit.py (never by hand):
#   sbatch --export=ALL,SEED=<s>,RUN_IDS=<id:id:...>,RIL_COMMIT=<hash>,DATE=<YYYY-MM-DD> scripts/ada/rq2f_injected_run.sbatch
set -euo pipefail
W=$HOME/ril_rq2f
POOLW=$HOME/ril_n7/work  # pool caches and noise score stores of the noise pilots, already on the account
X2=$HOME/ril_x2
E=$HOME/ril_e
SEED=${SEED:?set SEED}
RUN_IDS=${RUN_IDS:?set RUN_IDS (run ids joined by colons)}
DATE=${DATE:?set DATE}
RIL_COMMIT=${RIL_COMMIT:?set RIL_COMMIT}
IDS=${RUN_IDS//:/ }
for RID in $IDS; do
  case "$RID" in inj_*_u100_s${SEED}) ;; *) echo "run id $RID is not an injected-noise run of seed $SEED at 100 updates"; exit 4;; esac
done
[ -z "${RETAIN_DIR:-}" ] || { echo "injected-noise models are not retained; unset RETAIN_DIR"; exit 4; }
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$X2/venv_gpu$PYV/bin/python
NODE_FREE=$(df -Pm "${TMPDIR:-/tmp}" | awk 'NR==2{print $4}')
[ "$NODE_FREE" -gt 10000 ] || { echo "node-local space on $(hostname) has only $NODE_FREE MB free"; exit 4; }
CK=${TMPDIR:-/tmp}/ril_rq2f_${SLURM_JOB_ID}
mkdir -p "$W/logs" "$W/out" "$CK/ckpt" "$CK/eval"
cd "$W"
export HF_HOME=$E/hf_cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export PYTHONPATH="$X2/overlay_cre:$W"
export RIL_COMMIT
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv > "out/nvidia_${SLURM_JOB_ID}.txt" || true
{ echo "host=$(hostname)"; echo "ril_commit=$RIL_COMMIT"; echo "seed=$SEED"; echo "run_ids=$RUN_IDS"; df -h "${TMPDIR:-/tmp}" "$HOME" | tail -2; } \
  > "out/env_injected_s${SEED}_${SLURM_JOB_ID}.txt"
# the injected family has no size to resolve: the committed configuration is the one that trains
CONFIGS=""
for RID in $IDS; do
  [ -f "configs/experiments/rq2_final/${RID}.yaml" ] || { echo "no configuration for $RID"; exit 4; }
  CONFIGS="$CONFIGS configs/experiments/rq2_final/${RID}.yaml"
done
# dev evaluation set: the five dev repositories of the E3 cache without ansible, as links (no data copied)
"$PY" scripts/curve_subset_cache.py "$HOME/ril_t1/work/e3_cache" work/e3_cache_dev5 \
  internetarchive__openlibrary qutebrowser__qutebrowser streamlink__streamlink conan-io__conan deepset-ai__haystack
"$PY" scripts/train.py run-batch $CONFIGS \
  --cache "$POOLW/pool_A.jsonl.gz:$POOLW/pool_T3x.jsonl.gz" \
  --noise-scores "bm25=$POOLW/scores_P5000_bm25.jsonl" \
  "swerankembed-small=$POOLW/scores_P5000_swerankembed-small.jsonl" \
  --results-root "$W/results" --work-root "$CK/ckpt" --date "$DATE" --device cuda --drop-eval-stores \
  --eval-set dev --home "$HOME" --work "$CK/eval" \
  > "out/run_injected_s${SEED}_${SLURM_JOB_ID}.json"
du -sh "$CK" >> "out/env_injected_s${SEED}_${SLURM_JOB_ID}.txt" || true
rm -rf "$CK"
echo done
