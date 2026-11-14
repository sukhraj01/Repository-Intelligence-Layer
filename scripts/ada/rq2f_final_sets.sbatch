#!/bin/bash
#SBATCH --job-name=rq2f_final
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --gres=gpu:1
#SBATCH --constraint=2080ti
#SBATCH --exclude=gnode004,gnode044
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=08:00:00
#SBATCH --output=ril_rq2f/logs/%x_%j.out
# GPU. Final sets of the RQ2 experiment for one retained model (account C): the eight evaluation repositories (D100)
# and the executable 377 of Verified (D127), role test, scored once, after the dev analysis. The script refuses to
# start without FOLLOWS (the id of the dev-analysis entry) and a matching complete record that covers the run
# (scripts/rq2_final_sets.py, ril/evaluation/final_sets.py); every score row is written next to that id. A finished
# (model, part) pair is skipped on a rerun. Unit texts of the built parts are stored gzipped and are unpacked to
# node-local space first. Memory: encoding and scoring only (no training cache), 16 GB as the evaluation jobs of the
# earlier waves. Time: 0.178 GPU-hours measured for the eight, 0.377 measured for the 341 built instances, up to 0.292
# projected for the 36 earlier ones (the whole six-folder store is encoded unless restricted): about 0.85 per model.
# The per-instance scores of the executable 377 are kept in $RETAIN_DIR/exec377_scores (checkpoint hash and SHA-256 in a record; DEV-042;
# pass --no-retain-scores to the script to turn it off; the eight repositories are not kept).
# Not submitted by scripts/rq2_submit.py: the engineer submits it after the dev analysis, one job per seed (its retained models; D141):
#   sbatch --export=ALL,ONLY=<run id:run id:...>,FOLLOWS=<dev-analysis id>,RIL_COMMIT=<hash>,RETAIN_DIR=<abs dir> scripts/ada/rq2f_final_sets.sbatch
set -euo pipefail
W=$HOME/ril_rq2f
X2=$HOME/ril_x2
E=$HOME/ril_e
ONLY=${ONLY:?set ONLY (the run ids of the retained models of one seed, joined by colons)}
FOLLOWS=${FOLLOWS:?the final sets follow the dev analysis: set FOLLOWS to its id}
RIL_COMMIT=${RIL_COMMIT:?set RIL_COMMIT}
RETAIN_DIR=${RETAIN_DIR:?set RETAIN_DIR}
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$X2/venv_gpu$PYV/bin/python
NODE_FREE=$(df -Pm "${TMPDIR:-/tmp}" | awk 'NR==2{print $4}')
[ "$NODE_FREE" -gt 20000 ] || { echo "node-local space on $(hostname) has only $NODE_FREE MB free"; exit 4; }
CK=${TMPDIR:-/tmp}/ril_rq2f_final_${SLURM_JOB_ID}
mkdir -p "$W/logs" "$W/out" "$CK"
cd "$W"
export HF_HOME=$E/hf_cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export PYTHONPATH="$X2/overlay_cre:$W"
export RIL_COMMIT
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv > "out/nvidia_${SLURM_JOB_ID}.txt" || true
{ echo "host=$(hostname)"; echo "ril_commit=$RIL_COMMIT"; echo "run_id=$ONLY"; echo "follows=$FOLLOWS"; df -h "${TMPDIR:-/tmp}" "$HOME" | tail -2; } \
  > "out/env_final_${SLURM_JOB_ID}.txt"
# The built parts stored query texts at L2 only; the L3 stores (same text, checked against the caches) are added here, idempotently,
# so that the dense stage writes dense_L3 for the members labelled at L3 (DEV-043).
for part in ril_rq3u ril_rq3u_x; do
  "$PY" scripts/rq3_units.py prep-l3-queries "$HOME/$part/e3_cache" "$HOME/$part/prep" --seed 0
done
"$PY" scripts/rq2_final_sets.py run --retained-root "$RETAIN_DIR" --only ${ONLY//:/ } \
  --follows-dev-analysis "$FOLLOWS" --dev-record "$W/results/rq2_final/dev_analysis_record.json" \
  --out "$W/results/rq2_final/final_sets" --home "$HOME" --work "$CK" --device cuda \
  > "out/final_${SLURM_JOB_ID}.json"
rm -rf "$CK"
echo done
