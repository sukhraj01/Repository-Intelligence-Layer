#!/bin/bash
#SBATCH --job-name=rq3_units_cpu
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --time=12:00:00
#SBATCH --output=ril_rq3u/logs/rq3_units_cpu_%j.out
# CPU only. Unit records, instance caches and text stores of the executable subset of Verified
# (E-RQ3-UNITS, D107): bare clones on node-local space, then per instance the unit stage (labelled
# instances), the cache (units, graph, BM25 scores) and the unit-text hashes (class form full),
# then the distinct-text count and the encoding rule. Build only: no retrieval result is read.
# Resumable (finished items are read back). Submit from $HOME after
#   rsync -a --exclude __pycache__ ril scripts configs ada:ril_rq3u/
#   scp meta.json queries.json ada:ril_rq3u/
#   sbatch --export=ALL,RIL_COMMIT=<hash> ril_rq3u/scripts/ada/rq3_units_cpu.sbatch
# Optional: REPOS="pylint-dev/pylint ..." restricts the clones and the members (default: the five);
# INSTANCES="id ..." restricts the members further; RQ3U_DIR and RQ3U_CFG name another work directory and
# configuration (the four xarray instances were built that way, in ril_rq3u_x).
set -euo pipefail
W=${RQ3U_DIR:-$HOME/ril_rq3u}
E=$HOME/ril_e
mkdir -p "$W/logs" "$W/out" "$W/e3_cache" "$W/e1_units" "$W/prep"
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$E/venv_ril$PYV/bin/python
CFG=${RQ3U_CFG:-configs/experiments/rq3_units_v1.yaml}
FREE=$(df -Pm "$HOME" | awk 'NR==2{print $4}')
[ "$FREE" -gt 2500 ] || { echo "only $FREE MB free in HOME"; exit 3; }
NODE_FREE=$(df -Pm /tmp | awk 'NR==2{print $4}')
[ "$NODE_FREE" -gt 30000 ] || { echo "node-local /tmp on $(hostname) has only $NODE_FREE MB free"; exit 4; }
TMPW=$(mktemp -d /tmp/ril_rq3u.XXXXXX)
trap 'rm -rf "$TMPW"' EXIT
{ echo "host=$(hostname)"; echo "python=$($PY -V)"; echo "cpus=$(nproc)"; \
  echo "mem=$(grep MemTotal /proc/meminfo)"; echo "cpu_model=$(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2)"; \
  echo "ril_commit=${RIL_COMMIT:-none}"; echo "job=${SLURM_JOB_ID:-none}"; } > "$W/out/env_cpu_${SLURM_JOB_ID:-0}.txt"
cd "$W"
export PYTHONPATH="$W"
DEFAULT_REPOS="django/django sympy/sympy pytest-dev/pytest sphinx-doc/sphinx pylint-dev/pylint"
read -ra REPOS <<< "${REPOS:-$DEFAULT_REPOS}"
mkdir -p "$TMPW/repo_cache" "$TMPW/work" "$TMPW/prep"
# members of the selected repositories only
$PY -I - "$W/meta.json" "$W/meta_run.json" "${REPOS[@]}" <<PY
import json, sys
import os
src, dst, repos = sys.argv[1], sys.argv[2], set(sys.argv[3:])
only = set(os.environ.get("INSTANCES", "").split())
meta = json.load(open(src))
json.dump({k: v for k, v in meta.items() if v["repo"] in repos and (not only or k in only)}, open(dst, "w"), sort_keys=True)
PY
T_CLONE=$(date +%s)
for repo in "${REPOS[@]}"; do
  name=${repo/\//__}
  git clone -q --bare "https://github.com/$repo.git" "$TMPW/repo_cache/$name.git"
  du -sh "$TMPW/repo_cache/$name.git"
done
echo "clone_seconds=$(( $(date +%s) - T_CLONE ))"
K=4
rc=0
# 1. unit stage and caches, K shards (each shard has its own working clones)
pids=()
for i in $(seq 0 $((K-1))); do
  $PY scripts/rq3_units.py prepare $CFG "$E/raw" meta_run.json queries.json "$TMPW/repo_cache" "$W/e3_cache" "$W/e1_units" "$TMPW/work" "$W/out" \
    --shard $i $K > "$W/logs/rq3_units_prepare_s$i.log" 2>&1 &
  pids+=($!)
done
for p in "${pids[@]}"; do wait "$p" || rc=$?; done
echo "prepare rc=$rc caches=$(ls "$W/e3_cache" | wc -l)"
# 2. unit-text hashes and text stores (node-local), class form full only
pids=()
for i in $(seq 0 $((K-1))); do
  $PY scripts/rq3_units.py prep-units $CFG meta_run.json "$TMPW/repo_cache" "$W/e3_cache" "$TMPW/work" "$TMPW/prep" \
    --shard $i $K > "$W/logs/rq3_units_prep_units_s$i.log" 2>&1 &
  pids+=($!)
done
for p in "${pids[@]}"; do wait "$p" || rc=$?; done
$PY scripts/rq3_units.py prep-queries "$W/out" "$TMPW/prep" > "$W/logs/rq3_units_prep_queries.log" 2>&1 || rc=$?
echo "prep rc=$rc"
# 3. counts and the rule (small outputs to HOME)
$PY scripts/rq3_units.py count "$TMPW/prep" "$W/out/distinct_counts.json" > "$W/logs/rq3_units_count.log" 2>&1 || rc=$?
du -sh "$TMPW"/prep/* | tee "$W/out/prep_sizes_${SLURM_JOB_ID:-0}.txt" || true
# 4. keep what the encoding and scoring need: hashes as they are, text stores compressed
mkdir -p "$W/prep/units" "$W/prep/texts_units_gz" "$W/prep/queries"
cp -n "$TMPW"/prep/units/*.npz "$W/prep/units/" || true
cp -n "$TMPW"/prep/queries/*.jsonl "$W/prep/queries/" || true
cp -n "$TMPW"/prep/*.json "$W/prep/" || true
for f in "$TMPW"/prep/texts_units/*.jsonl; do
  [ -e "$f" ] && gzip -c "$f" > "$W/prep/texts_units_gz/$(basename "$f").gz.tmp" && mv "$W/prep/texts_units_gz/$(basename "$f").gz.tmp" "$W/prep/texts_units_gz/$(basename "$f").gz"
done
du -sh "$W"/* || true
echo "done rc=$rc"
exit $rc
