#!/bin/bash
#SBATCH --job-name=ril_rq3_floorreplay
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=ril_rq3_driver/logs/floorreplay_%j.out   # relative to the submit directory ($HOME)
# No-call replay of the floor arm's stored replies (E-RQ3-FLOOR addendum, D170): NO PROVIDER CALL. Reads the
# stored replies, the prepared prompts and the base-commit files; writes counts only. Required environment:
# CODE (checkout holding ril/ and scripts/), PREPARED, STAGES (space-separated label=dir), OUT.
set -eu
: "${CODE:?}" "${PREPARED:?}" "${STAGES:?}" "${OUT:?}"
PY=$HOME/ril_e/venv_ril310/bin/python
LOCAL=${TMPDIR:-/tmp}/ril_floor_replay_${SLURM_JOB_ID}
mkdir -p "$LOCAL/mirrors" "$OUT"
ARGS=()
for s in $STAGES; do ARGS+=(--stage "$s"); done
cd "$CODE"
"$PY" -I scripts/rq3_floor_replay.py replay "${ARGS[@]}" --prepared "$PREPARED" \
  --specs "$HOME/ril_rq3_exec/data/specs_v1.jsonl" --mirror-dir "$LOCAL/mirrors" \
  --local-mirrors "$HOME/ril_e/repo_cache" --out-dir "$OUT" --seed 0
echo "== replay exit $? $(date -u +%FT%TZ)"
