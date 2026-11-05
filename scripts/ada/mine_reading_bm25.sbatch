#!/bin/bash
#SBATCH --job-name=mine_reading
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=1
#SBATCH --mem=10G
#SBATCH --time=06:00:00
#SBATCH --exclude=gnode004,gnode044
#SBATCH --output=ril_mine/logs/reading_bm25_%j.out
# CPU only. E-MINE-STORE: BM25 ranks and the no-positive-in-top-K shares of the SAME directories under
# the readings of ril/data_mining/readings.py. SAMPLE is the selection file of an earlier stage (M3's
# first 300 directories of the non-test reading); every reading is prepared for exactly its directories,
# so a reading that drops a directory is counted, not replaced. All work is on node-local $TMPDIR;
# the only files written to $HOME are the small JSON tables next to the logs.
#   sbatch --export=ALL,RUN=pilot,SAMPLE=ranks/pilot/non_test/limit300/sample.json ril_mine/scripts/ada/mine_reading_bm25.sbatch
set -euo pipefail
M=$HOME/ril_mine
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$HOME/ril_x2/venv_gpu$PYV/bin/python
R=${RUN:?set RUN}
S=${SAMPLE:?set SAMPLE}
cd "$M"
WORK=$(mktemp -d "${TMPDIR:-/tmp}/ril_reading.XXXXXX")
trap 'rm -rf "$WORK"' EXIT
OUT="logs/reading_bm25_${R}_${SLURM_JOB_ID:-local}"
hostname
for READING in non_test pool_aligned unrestricted; do
  D="$WORK/$READING"
  $PY -I scripts/mine_pilot.py rank-prepare "runs/$R" "$D" --reading "$READING" --only-from "$S" | tee "$OUT.$READING.prepare.json"
  $PY -I scripts/mine_pilot.py rank-bm25 "$D" "$D/ranks_bm25.jsonl" > /dev/null
  $PY -I scripts/mine_pilot.py rank-tables "$D" "$OUT.$READING.shares.json" --ranks "$D/ranks_bm25.jsonl" --yield-per-pr 0.643
  cp "$D/ranks_bm25.jsonl" "$OUT.$READING.ranks_bm25.jsonl"
done
echo done
