#!/bin/bash
#SBATCH --job-name=x1_prepare
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --time=06:00:00
#SBATCH --output=ril_x1/logs/x1_prepare_%j.out
# CPU only. Structure measurements X1: per instance, the BM25 scores of the three class-unit source
# forms, index sizes and times, ambiguous invoke sites with receiver evidence, and four gold readings.
# ROLES=dev (default) or ROLES=test; K shards as K processes with separate working clones. Resumable:
# a finished file with the same configuration hash is kept. Reads ~/ril_e/{raw,repo_cache,meta.json,out/units}
# through links made below. Submit from $HOME after
#   rsync -a --exclude __pycache__ ril scripts configs ada:ril_x1/
#   sbatch --export=ALL,ROLES=dev,RIL_COMMIT=<hash> ril_x1/scripts/ada/x1_prepare.sbatch
set -euo pipefail
W=$HOME/ril_x1
E=$HOME/ril_e
mkdir -p "$W/logs" "$W/x1_cache" "$W/work" "$W/out"
for d in raw repo_cache meta.json; do [ -e "$W/$d" ] || ln -s "$E/$d" "$W/$d"; done
[ -e "$W/e1_units" ] || ln -s "$E/out/units" "$W/e1_units"
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
VENV=$E/venv_ril$PYV
"$VENV/bin/pip" freeze > "$W/out/pip_freeze.txt"
{ echo "host=$(hostname)"; echo "python=$("$VENV/bin/python" -V)"; echo "cpus=$(nproc)"; \
  echo "git=$(git --version)"; echo "mem=$(grep MemTotal /proc/meminfo)"; \
  echo "cpu_model=$(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2)"; \
  echo "ril_commit=${RIL_COMMIT:-none}"; echo "roles=${ROLES:-dev}"; } > "$W/out/env_prepare_${ROLES:-dev}.txt"
cd "$W"
export PYTHONPATH="$W"
K=${SHARDS:-4}
EXTRA=()
if [ -n "${ONLY:-}" ]; then EXTRA+=(--only "$ONLY"); fi
if [ -n "${LIMIT:-}" ]; then EXTRA+=(--limit "$LIMIT"); fi
pids=()
for i in $(seq 0 $((K-1))); do
  "$VENV/bin/python" scripts/x1_run.py prepare configs/experiments/e1_bm25_reproduction.yaml "$W/raw" "$W/meta.json" \
    "$W/repo_cache" "$W/x1_cache" "$W/work" "$W/out" "$W/e1_units" --roles ${ROLES:-dev} --shard $i $K "${EXTRA[@]}" \
    > "$W/logs/x1_prepare_${ROLES:-dev}_shard$i.log" 2>&1 &
  pids+=($!)
done
rc=0
for p in "${pids[@]}"; do wait "$p" || rc=$?; done
echo "done rc=$rc"
exit $rc
