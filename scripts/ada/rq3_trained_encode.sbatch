#!/bin/bash
#SBATCH --job-name=rq3_trained_enc
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --gres=gpu:1
#SBATCH --constraint=2080ti
#SBATCH --exclude=gnode004,gnode044
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=03:00:00
#SBATCH --output=ril_rq3t/logs/%x_%j.out
# GPU, FALLBACK ONLY (E-RQ3-SCORE-RETENTION, D152): the final-sets job keeps the executable-377 scores of every model
# it scores (DEV-042), and the context pass reads them at no cost. Run this for a model whose retained scores are
# missing or do not verify, within the Block 4 cap; `rq3_trained_arm.py plan` lists exactly those models (cost 0 for
# the others) in the order of Q73.
# One retained RQ2 model, encoded against the six-folder store of the executable 377 (E-RQ3-TRAINED-ARMS):
# the unit texts of the three stored parts (36 earlier instances, 337 built, 4 xarray) and the issue texts are
# encoded at 512 tokens, scored per instance in the layout of the stored untrained scores, and the 377 score
# files are copied to $HOME/ril_rq3t/scores/<run id>/dense_scores with a model record (checkpoint folder,
# manifest SHA-256, configuration hash, commit, CUDA gate, seconds) and a DONE marker. Encoding and scoring
# only: no retrieval metric, no context, no model call. Nothing is deleted on $HOME; node-local scratch is
# removed by the job at exit.
# Sealed order (D100, D127): the script refuses to start without FOLLOWS (the id of the dev-analysis entry) and
# a matching complete record that covers the run, exactly as rq2f_final_sets.sbatch does; the scores are scores
# of the executable 377. One model per job, one GPU job per account at a time (D141): submit only after the
# account's RQ2 training jobs have finished. Cost: 0.68 GPU-hours per model (planning constant; measured parts
# 0.377 for the 341 built instances, about 0.29 projected for the 36 earlier ones), Block 4 cap 6.0 with 0.377
# spent: eight models. A finished model (DONE.json) is skipped on a rerun; finished stores and score files of an
# interrupted job are reused.
# Plan first (prints jobs and cost, submits nothing):
#   python3 -I scripts/rq3_trained_arm.py plan --retained-root $RETAIN_DIR
# Submit one job per model, by hand or by sessions/engineer/rq3_trained_arms_1.sh:
#   sbatch --export=ALL,RUN_ID=<run id>,FOLLOWS=<dev-analysis id>,RIL_COMMIT=<hash>,RETAIN_DIR=<abs dir> scripts/ada/rq3_trained_encode.sbatch
set -euo pipefail
W=${RQ3T_DIR:-$HOME/ril_rq3t}
X2=$HOME/ril_x2
E=$HOME/ril_e
RUN_ID=${RUN_ID:?set RUN_ID (one retained model, for example mined_raw_u100_s100)}
FOLLOWS=${FOLLOWS:?the scores follow the dev analysis: set FOLLOWS to its id}
RIL_COMMIT=${RIL_COMMIT:?set RIL_COMMIT}
RETAIN_DIR=${RETAIN_DIR:?set RETAIN_DIR}
case "$RETAIN_DIR" in /*) ;; *) echo "RETAIN_DIR must be absolute"; exit 4;; esac
DEV_RECORD=${DEV_RECORD:-$HOME/ril_rq2f/results/rq2_final/dev_analysis_record.json}
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$X2/venv_gpu$PYV/bin/python
FREE=$(df -Pm "$HOME" | awk 'NR==2{print $4}')
[ "$FREE" -gt 2000 ] || { echo "only $FREE MB free in HOME"; exit 3; }
NODE_FREE=$(df -Pm "${TMPDIR:-/tmp}" | awk 'NR==2{print $4}')
[ "$NODE_FREE" -gt 20000 ] || { echo "node-local space on $(hostname) has only $NODE_FREE MB free"; exit 4; }
CK=${TMPDIR:-/tmp}/ril_rq3t_${SLURM_JOB_ID}
mkdir -p "$W/logs" "$W/out" "$W/scores" "$CK"
trap 'rm -rf "$CK"' EXIT
cd "$W"
export HF_HOME=$E/hf_cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export PYTHONPATH="$X2/overlay_cre:$W"
export RIL_COMMIT
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv > "out/nvidia_${SLURM_JOB_ID}.txt" || true
{ echo "host=$(hostname)"; echo "ril_commit=$RIL_COMMIT"; echo "run_id=$RUN_ID"; echo "follows=$FOLLOWS"; \
  df -h "${TMPDIR:-/tmp}" "$HOME" | tail -2; } > "out/env_encode_${SLURM_JOB_ID}.txt"
"$PY" scripts/rq3_trained_arm.py encode --retained-root "$RETAIN_DIR" --only "$RUN_ID" \
  --follows-dev-analysis "$FOLLOWS" --dev-record "$DEV_RECORD" \
  --out "$W/scores" --home "$HOME" --work "$CK" --device cuda \
  > "out/encode_${RUN_ID}_${SLURM_JOB_ID}.json"
ls "$W/scores/$RUN_ID/dense_scores" | wc -l
du -sh "$W/scores/$RUN_ID"
echo done
