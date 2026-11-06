#!/bin/bash
#SBATCH --job-name=ril_overlap
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --time=06:00:00
#SBATCH --exclude=gnode004,gnode044
#SBATCH --output=ril_ov/logs/overlap_%j.out
# CPU only. E-OVERLAP-AUDIT (D105): content-overlap audit of a de-duplicated mined store against the
# held-out corpora. Reads the store, the stored Verified probe set and the held-out unit-text stores;
# writes only under $HOME/ril_ov (index, records, summary, drop/flag lists). Nothing is deleted and the
# store is never written.
#   sbatch --export=ALL,STORE=$HOME/ril_mine/store/pilot,RUN=pilot ril_ov/scripts/ada/overlap_audit.sbatch
# The held-out index is built once (INDEX_DIR) and reused; REBUILD_INDEX=1 rebuilds it.
set -euo pipefail
OV=$HOME/ril_ov
cd "$OV"
PY=$HOME/ril_mine/venv_310/bin/python
STORE=${STORE:?set STORE}
RUN=${RUN:?set RUN}
INDEX_DIR=${INDEX_DIR:-$OV/index/v1}
OUT=$OV/out/$RUN
mkdir -p "$OV/logs" "$OUT"
hostname; "$PY" --version
if [ ! -f "$INDEX_DIR/manifest.json" ] || [ "${REBUILD_INDEX:-0}" = 1 ]; then
  "$PY" -I scripts/mine_overlap_audit.py index "$INDEX_DIR" \
    --probe "$HOME/ril_c/out/probe_verified_nodes.json" \
    --texts "$HOME/ril_x2/prep/texts_units" "$HOME/ril_eval/prep/texts_units"
fi
"$PY" -I scripts/mine_overlap_audit.py audit "$STORE" "$INDEX_DIR" "$OUT" ${NAMES_FILE:+--names-file "$NAMES_FILE"}
for F in 10 20 50; do
  "$PY" -I scripts/mine_overlap_audit.py apply "$OUT" --floor "$F"
done
"$PY" -I scripts/mine_overlap_audit.py apply "$OUT" --floor 20 --positives all
"$PY" -I scripts/mine_overlap_audit.py apply "$OUT" --floor 20 --drop-flagged
echo done
