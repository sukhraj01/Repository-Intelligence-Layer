#!/bin/bash
#SBATCH --job-name=ril_rq3_pseudo
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=06:00:00
#SBATCH --output=ril_rq3_driver/logs/pseudonym_%j.out   # relative to the submit directory ($HOME)
# CPU only, no model call (E-RQ3-PSEUDONYMISE, D120). For the prompts that the transform touched:
# (1) quote, restore and convert an edit on every excerpt line that holds a placeholder, and the
# gold-derived edit blocks with the prompt's placeholders, and compare trees with the gold patch;
# (2) replay 10 touched instances (the gold reply and the broken variants, quoted in placeholder form)
# through the driver on the real executor, which restores them before converting.
# Work, mirrors and package caches live in node-local $TMPDIR; nothing is deleted by this job.
# Required environment: PREPARED (prepared directory of prepare.sbatch). UV_BIN_DIR (directory of the uv binary).
set -u
W=$HOME/ril_rq3_driver
X=$HOME/ril_rq3_exec
PY=$HOME/ril_e/venv_ril310/bin/python
: "${PREPARED:?prepared directory of prepare.sbatch}"
LOCAL=${TMPDIR:-/tmp}/ril_rq3_driver_${SLURM_JOB_ID}
OUT=$W/out/pseudonym_${SLURM_JOB_ID}
mkdir -p "$LOCAL/work" "$LOCAL/cache" "$LOCAL/mirrors" "$LOCAL/scratch" "$OUT"
echo "== node $(hostname) $(date -u +%FT%TZ)"; df -h "$LOCAL" | tail -1
export PATH="${UV_BIN_DIR:?directory that holds the uv binary}:$PATH"
"$PY" -I "$W/code/scripts/rq3_driver.py" pseudonym-check "$PREPARED" "$OUT" \
  --specs "$X/data/specs_v1.jsonl" --gold "$X/data/gold_v1.jsonl" \
  --subset "$W/in/executable_instances_v1.json" --mirror-dir "$LOCAL/mirrors" \
  --local-mirrors "$HOME/ril_e/repo_cache" --scratch "$LOCAL/scratch" --sample 10 --seed 0
echo "== check exit $? $(date -u +%FT%TZ)"
"$PY" -I "$W/code/scripts/rq3_driver.py" replay "$X/data/specs_v1.jsonl" "$X/data/gold_v1.jsonl" \
  "$OUT/pseudonym_draw.json" "$OUT/replay" --prepared "$PREPARED" \
  --work-root "$LOCAL/work" --cache-root "$LOCAL/cache" \
  --mirror-dir "$LOCAL/mirrors" --local-mirrors "$HOME/ril_e/repo_cache" \
  --subset "$W/in/executable_instances_v1.json" --workers 2 --seed 0
echo "== replay exit $? $(date -u +%FT%TZ)"
du -sh "$LOCAL" 2>/dev/null | tail -1
