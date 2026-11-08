#!/bin/bash
#SBATCH --job-name=ril_rq3_snap
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:30:00
#SBATCH --output=ril_rq3_patch/logs/snapshot_%j.out   # relative to the submit directory ($HOME)
# CPU only (E-RQ3-PATCHAPPLY, D110). Base-commit text of every file the pilot's usable replies name,
# read with `git cat-file` from the bare repository caches; nothing is cloned, no checkout is made.
# Submit from $HOME after: rsync -a --exclude __pycache__ ril scripts ada:ril_rq3_patch/code/
#                          scp needed.json ada:ril_rq3_patch/in/
set -eu
W=$HOME/ril_rq3_patch
PY=$HOME/ril_rq3_exec/venv/bin/python
echo "== node $(hostname) $(date -u +%FT%TZ)"
mkdir -p "$W/out"
"$PY" -I "$W/code/scripts/rq3_patch.py" snapshot "$W/in/needed.json" \
  "$HOME/ril_t1/work/e3_cache" "$HOME/ril_e/repo_cache" "$W/out/snapshots.jsonl"
ls -l "$W/out/snapshots.jsonl"
echo "== done $(date -u +%FT%TZ)"
