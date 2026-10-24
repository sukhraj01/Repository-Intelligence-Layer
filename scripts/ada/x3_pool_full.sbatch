#!/bin/bash
#SBATCH --job-name=x3_pool_full_bm25
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=6G
#SBATCH --time=24:00:00
#SBATCH --output=ril_x3/logs/x3_pool_full_bm25_%j.out
# CPU only. BM25 ranks of every positive of the whole pool (24,285 directories), one shard of the
# repositories (SHARD="i n"); resumable per directory. The dense ranks of the whole pool come from
# x3_dense.sbatch with SELECT=all and the same SHARD. Not run by the measurement itself; the cost
# estimate is in scripts/ada/README.md.
#   sbatch --export=ALL,SHARD="0 4" ril_x3/scripts/ada/x3_pool_full.sbatch
set -euo pipefail
W=$HOME/ril_x3
E=$HOME/ril_e
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$E/venv_ril$PYV/bin/python
SHARD=${SHARD:-"0 1"}
cd "$W"
export PYTHONPATH="$W"
$PY scripts/pool_ranks.py bm25 "$HOME/ril_s2/raw/ziplist_train.json" "$W/work/full_ranks_bm25_s${SHARD// /of}.jsonl" \
  --meta "$HOME/ril_pc/work/pool_meta.jsonl" --shard $SHARD --ahead 4
echo done
