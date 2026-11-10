#!/bin/bash
#SBATCH --job-name=unit_bm25
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --time=04:00:00
#SBATCH --output=ril_ub/logs/unit_bm25_%j.out
# CPU only, 4 CPUs. Unit-level BM25 variants and field weights on the development set (decision
# D119, E-FREEZE-AND-LATENCY): the unit texts of every development instance are rebuilt at the base
# commit (working clones on node-local scratch), one factor per cell with the E1 default as the
# control, then the fused cell with the stored CodeRankEmbed scores. The control must reproduce the
# stored BM25 scores of the instance cache bit for bit or the instance is listed and not evaluated.
# Reads the cache, the repository cache and the stored dense scores; resumable (evaluation files carry
# their hash); nothing is deleted except the node-local scratch of this job.
#   ssh ada mkdir -p ril_ub/logs
#   rsync -a --exclude __pycache__ ril scripts configs ada:ril_ub/
#   sbatch --export=ALL,RIL_COMMIT=<hash> ril_ub/scripts/ada/unit_bm25.sbatch
set -euo pipefail
W=$HOME/ril_ub
E=$HOME/ril_e
X=$HOME/ril_x2
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$E/venv_ril$PYV/bin/python
CACHE=${CACHE:-$HOME/ril_t1/work/e3_cache}
OUT=$W/unit_bm25_v1
K=4
cd "$W"
export PYTHONPATH="$W"
mkdir -p "$OUT" "$W/logs"
TMPW=$(mktemp -d /tmp/ril_unit_bm25.XXXXXX)
trap 'rm -rf "$TMPW"' EXIT
{ echo "host=$(hostname)"; echo "python=$(python3 -V)"; echo "cpus=$(nproc)"; \
  echo "cpu_model=$(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2)"; \
  echo "ril_commit=${RIL_COMMIT:-none}"; echo "job=${SLURM_JOB_ID:-none}"; \
  echo "cache=$CACHE"; echo "k=$K"; } > "$OUT/env.txt"
sha256sum configs/experiments/unit_bm25_dev.yaml >> "$OUT/config_hashes.txt"
pids=()
for i in $(seq 0 $((K-1))); do
  /usr/bin/time -v "$PY" scripts/rq1_unit_bm25.py eval configs/experiments/e1_bm25_reproduction.yaml \
    "$E/raw" "$E/repo_cache" "$CACHE" "$X/dense" "$TMPW" "$OUT" --shard $i $K \
    > "$W/logs/unit_bm25_shard$i.log" 2> "$OUT/time_s$i.txt" &
  pids+=($!)
done
rc=0
for p in "${pids[@]}"; do wait "$p" || rc=$?; done
echo "unit_bm25 eval rc=$rc"
exit $rc
