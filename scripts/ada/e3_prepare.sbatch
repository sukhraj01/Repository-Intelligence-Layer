#!/bin/bash
#SBATCH --job-name=e3_prepare
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --time=08:00:00
#SBATCH --output=ril_e/logs/e3_prepare_%j.out
# CPU only. Pilots E3 to E5: per-instance cache (checkout, units, typed graph with history, BM25 scores,
# gold unit indices read from the pilot-E1 records). ROLES=dev (default) or ROLES=test; K shards run as
# K processes with separate working clones. Resumable: a finished cache file with the same configuration
# hash is kept. Needs ~/ril_e/{raw,repo_cache,meta.json,out/units} from the pilot-E1 jobs.
# Submit from $HOME after  rsync -a --exclude __pycache__ ril scripts configs ada:ril_e/ :
#   sbatch --export=ALL,ROLES=dev,RIL_COMMIT=<hash> ril_e/scripts/ada/e3_prepare.sbatch
set -euo pipefail
W=$HOME/ril_e
mkdir -p "$W/logs" "$W/e3_cache" "$W/e3_work" "$W/e3_out"
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
VENV=$W/venv_ril$PYV
"$VENV/bin/pip" freeze > "$W/e3_out/pip_freeze.txt"
{ echo "host=$(hostname)"; echo "python=$("$VENV/bin/python" -V)"; echo "cpus=$(nproc)"; \
  echo "git=$(git --version)"; echo "mem=$(grep MemTotal /proc/meminfo)"; \
  echo "ril_commit=${RIL_COMMIT:-none}"; echo "roles=${ROLES:-dev}"; } > "$W/e3_out/env_prepare_${ROLES:-dev}.txt"
cd "$W"
export PYTHONPATH="$W"
K=${SHARDS:-4}
EXTRA=()
if [ -n "${ONLY:-}" ]; then EXTRA+=(--only "$ONLY"); fi
if [ -n "${LIMIT:-}" ]; then EXTRA+=(--limit "$LIMIT"); fi
pids=()
for i in $(seq 0 $((K-1))); do
  "$VENV/bin/python" scripts/e3_run.py prepare configs/experiments/e1_bm25_reproduction.yaml "$W/raw" "$W/meta.json" \
    "$W/repo_cache" "$W/e3_cache" "$W/e3_work" "$W/e3_out" "$W/out/units" --roles ${ROLES:-dev} --shard $i $K "${EXTRA[@]}" \
    > "$W/logs/e3_prepare_shard$i.log" 2>&1 &
  pids+=($!)
done
rc=0
for p in "${pids[@]}"; do wait "$p" || rc=$?; done
echo "done rc=$rc"
exit $rc
