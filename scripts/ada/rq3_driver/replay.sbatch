#!/bin/bash
#SBATCH --job-name=ril_rq3_replay
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=06:00:00
#SBATCH --output=ril_rq3_driver/logs/replay_%j.out   # relative to the submit directory ($HOME)
# CPU only, no network call to a model provider (E-RQ3-DRIVER, D113). The 20 gold-derived edit sets of
# E-RQ3-PATCHAPPLY and 10 deliberately broken variants go through the driver in replay mode on the
# real executor; expected classes are compared with the observed ones (replay_table.csv).
# Work, mirrors and package caches live in node-local $TMPDIR; nothing is deleted by this job.
# Submit from $HOME after the rsync of prepare.sbatch and
#   scp validation_draw.json executable_instances_v1.json ada:ril_rq3_driver/in/
#   (set UV_BIN_DIR to the directory of the uv binary)
set -u
W=$HOME/ril_rq3_driver
X=$HOME/ril_rq3_exec
PY=$HOME/ril_e/venv_ril310/bin/python
LOCAL=${TMPDIR:-/tmp}/ril_rq3_driver_${SLURM_JOB_ID}
OUT=$W/out/replay_${SLURM_JOB_ID}
mkdir -p "$LOCAL/work" "$LOCAL/cache" "$LOCAL/mirrors" "$OUT"
echo "== node $(hostname) $(date -u +%FT%TZ)"; df -h "$LOCAL" | tail -1
export PATH="${UV_BIN_DIR:?directory that holds the uv binary}:$PATH"
"$PY" -I "$W/code/scripts/rq3_driver.py" replay "$X/data/specs_v1.jsonl" "$X/data/gold_v1.jsonl" \
  "$W/in/validation_draw.json" "$OUT" --work-root "$LOCAL/work" --cache-root "$LOCAL/cache" \
  --mirror-dir "$LOCAL/mirrors" --local-mirrors "$HOME/ril_e/repo_cache" \
  --subset "$W/in/executable_instances_v1.json" --workers 2 --seed 0
echo "== replay exit $? $(date -u +%FT%TZ)"
du -sh "$LOCAL" 2>/dev/null | tail -1
