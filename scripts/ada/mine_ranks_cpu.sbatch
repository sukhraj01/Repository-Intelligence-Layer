#!/bin/bash
#SBATCH --job-name=ril_mine_rankc
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=1
#SBATCH --mem=10G
#SBATCH --time=06:00:00
#SBATCH --output=ril_mine/logs/ranks_cpu_%j.out
# CPU. Stage M3 (E-MINE-PILOT), the parts that need no GPU: the archive and selection file of a reading
# (READING=all or non_test, the latter without test-file functions and test positives), BM25 ranks
# of every directory, and for LIMIT=N the archive of the first N directories of the seeded order
# (the dense passes of mine_ranks.sbatch run on it) with their BM25 ranks. Resumable.
# FULL=0 skips the archive of every directory (it is as large as the mined set itself); use it with LIMIT.
#   sbatch --export=ALL,RUN=pilot,READING=non_test,LIMIT=300 ril_mine/scripts/ada/mine_ranks_cpu.sbatch
set -euo pipefail
M=$HOME/ril_mine
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$HOME/ril_x2/venv_gpu$PYV/bin/python
R=${RUN:?set RUN}
READING=${READING:-all}
W=$M/ranks/$R/$READING
cd "$M"
mkdir -p "$W" logs
DROP=""; [ "$READING" = non_test ] && DROP="--drop-tests"
if [ "${FULL:-1}" = 1 ]; then
  [ -f "$W/full/mined.listing.json" ] || $PY scripts/mine_pilot.py rank-prepare "runs/$R" "$W/full" $DROP
  $PY scripts/mine_pilot.py rank-bm25 "$W/full" "$W/full/ranks_bm25.jsonl"
fi
if [ -n "${LIMIT:-}" ]; then
  D="$W/limit${LIMIT}"
  [ -f "$D/mined.listing.json" ] || $PY scripts/mine_pilot.py rank-prepare "runs/$R" "$D" $DROP --limit "$LIMIT"
  $PY scripts/mine_pilot.py rank-bm25 "$D" "$D/ranks_bm25.jsonl"
fi
echo done
