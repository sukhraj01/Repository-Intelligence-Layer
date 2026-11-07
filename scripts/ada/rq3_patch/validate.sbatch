#!/bin/bash
#SBATCH --job-name=ril_rq3_patchval
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=06:00:00
#SBATCH --output=ril_rq3_patch/logs/validate_%j.out   # relative to the submit directory ($HOME)
# CPU only (E-RQ3-PATCHAPPLY, D110, measurement 2). Gold patches of the drawn executable instances
# are turned into edit blocks, converted (exact reading), checked tree-for-tree against the gold
# patch, and the converted patch is run through the executor (one run each, as E-RQ3-EXEC did).
# Work, mirrors and package caches live in node-local $TMPDIR; $HOME gets only the small outputs.
# Submit from $HOME after: rsync -a --exclude __pycache__ ril scripts ada:ril_rq3_patch/code/
#                          scp validation_draw.json ada:ril_rq3_patch/in/
#   (set UV_BIN_DIR to the directory of the uv binary; DRAW names another draw file to rerun a subset)
set -u
W=$HOME/ril_rq3_patch
X=$HOME/ril_rq3_exec
PY=$X/venv/bin/python
LOCAL=${TMPDIR:-/tmp}/ril_rq3_patch_${SLURM_JOB_ID}
OUT=$W/out/validate_${SLURM_JOB_ID}
mkdir -p "$LOCAL/work" "$LOCAL/cache" "$LOCAL/mirrors" "$OUT"
echo "== node $(hostname) $(date -u +%FT%TZ)"; df -h "$LOCAL" | tail -1
export PATH="${UV_BIN_DIR:?directory that holds the uv binary}:$PATH"
"$PY" -I "$W/code/scripts/rq3_patch.py" derive "$X/data/specs_v1.jsonl" "$X/data/gold_v1.jsonl" \
  "$W/in/${DRAW:-validation_draw.json}" "$OUT" --mirror-dir "$LOCAL/mirrors" --local-mirrors "$HOME/ril_e/repo_cache"
rc=$?
echo "== derive exit $rc $(date -u +%FT%TZ)"
for POLICY in latest era; do
  IDS=$OUT/ids_converted_${POLICY}.txt
  [ -s "$IDS" ] || continue
  "$PY" "$W/code/scripts/rq3_exec.py" run-shard "$X/data/specs_v1.jsonl" "$OUT/converted_patches.jsonl" \
    "$OUT/runs/$POLICY" --shard 0 --count 1 --ids "$IDS" --runs 1 --workers 2 --env-policy "$POLICY" \
    --work-root "$LOCAL/work" --cache-root "$LOCAL/cache" --local-mirrors "$LOCAL/mirrors" \
    --commit "$(cat "$W/code/COMMIT" 2>/dev/null)" --clean-cache
  echo "== run-shard $POLICY exit $? $(date -u +%FT%TZ)"
done
du -sh "$LOCAL" 2>/dev/null | tail -1
