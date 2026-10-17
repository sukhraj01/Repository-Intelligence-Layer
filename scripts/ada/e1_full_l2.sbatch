#!/bin/bash
#SBATCH --job-name=e1_full_l2
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=12:00:00
#SBATCH --output=ril_e/logs/e1_full_l2_%j.out
# CPU only. Chunk-level BM25 over all 632 original L2 folders, one at a time (fetch, score, delete),
# for the comparison with the benchmark card's BM25 average. Resumable (finished folders are skipped).
# Needs ~/ril_s2/raw/listing_root.json and ~/ril_s2/scripts/hf_fetch.py; about 12.5 GB is streamed
# in total, never more than one folder on disk. Submit from $HOME after rsync of ril, scripts, configs.
set -euo pipefail
W=$HOME/ril_e
mkdir -p "$W/logs" "$W/out_full" "$W/full_raw"
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
VENV=$W/venv_ril$PYV
{ echo "host=$(hostname)"; echo "python=$("$VENV/bin/python" -V)"; echo "cpus=$(nproc)"; \
  echo "mem=$(grep MemTotal /proc/meminfo)"; echo "ril_commit=${RIL_COMMIT:-none}"; } > "$W/out_full/env.txt"
cd "$W"
export PYTHONPATH="$W"
"$VENV/bin/python" scripts/ada/e1_full_l2.py configs/experiments/e1_bm25_full_l2.yaml \
  "$HOME/ril_s2/raw/listing_root.json" "$HOME/ril_s2/scripts/hf_fetch.py" "$W/full_raw" "$W/out_full"
echo done
