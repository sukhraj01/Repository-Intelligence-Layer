#!/bin/bash
#SBATCH --job-name=ril_mine_rank
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --gres=gpu:1
#SBATCH --constraint=2080ti
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --time=02:00:00
#SBATCH --output=ril_mine/logs/ranks_%j.out
# GPU. Stage M3 (E-MINE-PILOT): ranks of the mined positives under BM25, CodeRankEmbed and
# SweRankEmbed-Small with the published definition of the rank (code text, cut 1,024 tokens, float16;
# SweRankEmbed-Small also on the stored text, the form of the Verified reference), through the pool
# rank tooling over a local archive of the run. The CUDA matrix-product gate runs inside the dense
# job before any model loads. Resumable per directory and teacher. Stage limit 2 GPU-hours (the
# --time above). Needs the environment of ~/ril_x2 (models in the offline cache).
# READING=all (default): the corpora as mined, test-file functions and test positives included (D69).
# READING=non_test: the pool-like reading, no test-file function in the corpora, no test positive,
# directories left without a positive dropped (the pool has none of either).
# LIMIT=N: dense passes on the first N directories of the seeded order only (BM25 runs on both sets).
#   sbatch --export=ALL,RUN=pilot,READING=non_test,LIMIT=<N>,RIL_COMMIT=<hash> ril_mine/scripts/ada/mine_ranks.sbatch
set -euo pipefail
M=$HOME/ril_mine
X2=$HOME/ril_x2
E=$HOME/ril_e
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
GV=$X2/venv_gpu$PYV
R=${RUN:?set RUN}
READING=${READING:-all}
W=$M/ranks/$R/$READING
export HF_HOME=$E/hf_cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export PYTHONPATH="$X2/overlay_cre:$M"
cd "$M"
mkdir -p "$W" logs
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv > "$W/nvidia_${SLURM_JOB_ID}.txt" || true
df -h "$HOME" | tail -1 > "$W/disk_${SLURM_JOB_ID}.txt"
PY=$GV/bin/python
DROP=""; [ "$READING" = non_test ] && DROP="--drop-tests"
# BM25 (CPU) on every directory of the reading
$PY scripts/mine_pilot.py rank-prepare "runs/$R" "$W/full" $DROP
$PY scripts/mine_pilot.py rank-bm25 "$W/full" "$W/full/ranks_bm25.jsonl"
# dense passes on the first LIMIT directories of the seeded order (stage limit of 2 GPU-hours); all
# directories if LIMIT is unset
D="$W/full"
if [ -n "${LIMIT:-}" ]; then
  D="$W/limit${LIMIT}"
  $PY scripts/mine_pilot.py rank-prepare "runs/$R" "$D" $DROP --limit "$LIMIT"
  $PY scripts/mine_pilot.py rank-bm25 "$D" "$D/ranks_bm25.jsonl"
fi
$PY scripts/mine_pilot.py rank-dense "$D" "$D/ranks_dense.jsonl" "$D/dense_${SLURM_JOB_ID}.json" \
  --teachers swerankembed-small coderankembed --cut 1024 --form code
$PY scripts/mine_pilot.py rank-dense "$D" "$D/ranks_dense_stored.jsonl" "$D/dense_stored_${SLURM_JOB_ID}.json" \
  --teachers swerankembed-small --cut 1024 --form pool
echo done
