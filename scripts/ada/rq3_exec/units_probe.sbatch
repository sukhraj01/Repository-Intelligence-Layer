#!/bin/bash
#SBATCH --job-name=ril_rq3_units
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --time=04:00:00
#SBATCH --output=ril_rq3_exec/logs/units_%j.out
# Units per snapshot of one base commit per repository (D106, part 4): how many code units a
# stored unit record would hold, the input of the build-cost estimate. CPU only, node-local work.
# From $HOME:  PROBE=data/units_probe.tsv sbatch ril_rq3_exec/units_probe.sbatch   # PROBE is relative to ril_rq3_exec/
# PROBE: lines "owner/name<TAB>base_commit". Output: one stats JSON per repository under
# ril_rq3_exec/out/units_probe/ (small files). Needs code/scripts/parse_repo.py and code/ril.
set -u
cd ~/ril_rq3_exec
PROBE=${PROBE:?probe list}
LOCAL=${TMPDIR:-/tmp}/ril_rq3_units_${SLURM_JOB_ID}
mkdir -p "$LOCAL" out/units_probe
echo "== node $(hostname) $(date -u +%FT%TZ)"; df -h "$LOCAL" | tail -1
PY=$HOME/ril_e/venv_ril310/bin/python
while IFS=$'\t' read -r repo commit; do
  [ -z "$repo" ] && continue
  name=${repo//\//__}
  src="$HOME/ril_e/repo_cache/$name.git"; [ -d "$src" ] || src="https://github.com/$repo.git"
  t0=$(date +%s)
  git clone -q --bare "$src" "$LOCAL/$name.git" && git clone -q --no-checkout "$LOCAL/$name.git" "$LOCAL/$name" \
    && git -C "$LOCAL/$name" checkout -q "$commit" || { echo "clone failed $repo"; continue; }
  t1=$(date +%s)
  "$PY" code/scripts/parse_repo.py "$LOCAL/$name" --repo-id "$repo" --seed 0 --no-history \
    --stats-json "out/units_probe/$name.json" > /dev/null 2> "$LOCAL/$name.err" \
    || { echo "parse failed $repo"; tail -3 "$LOCAL/$name.err"; }
  t2=$(date +%s)
  echo "$repo clone_s=$((t1-t0)) parse_s=$((t2-t1))"
done < "$PROBE"
echo "== done $(date -u +%FT%TZ)"
du -sh "$LOCAL" | tail -1
