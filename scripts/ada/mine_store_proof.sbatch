#!/bin/bash
#SBATCH --job-name=mine_store
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --time=06:00:00
#SBATCH --exclude=gnode004,gnode044
#SBATCH --output=ril_mine/logs/store_proof_%j.out
# CPU only. E-MINE-STORE: build the de-duplicated store from a finished run root, rebuild every
# directory from it, and compare the rebuilt directories with the originals byte by byte (SHA-256 of
# the relative paths and bytes of every file). Everything is written to node-local $TMPDIR and removed
# at exit; nothing is written to $HOME except the three small JSON results next to the logs.
# Optional STORE_OUT=<dir>: after the comparison succeeds, copy the store there (needs its size free on
# the target file system: about 0.4 GB for the pilot); the original run root is never touched.
#   sbatch --export=ALL,RUN=pilot ril_mine/scripts/ada/mine_store_proof.sbatch
set -euo pipefail
cd "$HOME/ril_mine"
V="$HOME/ril_mine/venv_$(python3 -c 'import sys;print("%d%d" % sys.version_info[:2])')"
RUN=${RUN:-pilot}
WORK=$(mktemp -d "${TMPDIR:-/tmp}/ril_store.XXXXXX")
trap 'rm -rf "$WORK"' EXIT
OUT="logs/store_proof_${RUN}_${SLURM_JOB_ID:-local}"
hostname; df -h "$WORK" | tail -1
"$V/bin/python" -I scripts/mine_pilot.py store-convert "runs/$RUN" "$WORK/store" | tee "$OUT.convert.json"
du -sb "$WORK/store" | cut -f1
"$V/bin/python" -I scripts/mine_pilot.py materialise "$WORK/store" "$WORK/view" | tee "$OUT.materialise.json"
"$V/bin/python" -I scripts/mine_pilot.py compare-roots "runs/$RUN" "$WORK/view" "$OUT.compare.json" | tee "$OUT.compare.stdout.json"
if [ -n "${STORE_OUT:-}" ]; then
  mkdir -p "$STORE_OUT" && cp -a "$WORK/store/." "$STORE_OUT/"
  du -sb "$STORE_OUT" | cut -f1
fi
echo done
