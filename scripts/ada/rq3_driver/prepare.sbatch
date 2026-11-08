#!/bin/bash
#SBATCH --job-name=ril_rq3_drvprep
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=ril_rq3_driver/logs/prepare_%j.out   # relative to the submit directory ($HOME)
# CPU only, no network, no model call (E-RQ3-DRIVER, D113). Prompts of the 377 executable instances
# for BM25, untrained dense and RRF at 8,000 tokens, from the stored contexts (E-RQ3-CONTEXTS), through
# the pilot's prompt builder and screen; rejections are reported, not raised.
# Submit from $HOME after:
#   rsync -a --exclude __pycache__ ril scripts configs ada:ril_rq3_driver/code/
#   scp executable_instances_v1.json heldout_v1.json ada:ril_rq3_driver/in/
# (set RIL_FORBIDDEN_EMAILS to the operator's address(es) so that the screen rejects them)
set -eu
W=$HOME/ril_rq3_driver
PY=$HOME/ril_e/venv_ril310/bin/python
OUT=$W/out/prepared_b8000_${SLURM_JOB_ID}
mkdir -p "$OUT"
"$PY" -I "$W/code/scripts/rq3_driver.py" prepare "$HOME/ril_rq3c/out/ctx" "$OUT" \
  --raw "$HOME/ril_e/raw/data" --issues-parquet "$HOME/ril_rq3/data/verified.parquet" --subset "$W/in/executable_instances_v1.json" \
  --heldout "$W/in/heldout_v1.json" --budget 8000 --arms bm25 dense rrf --seed 0
rc=$?
sha256sum "$OUT/items.jsonl" "$W/in/heldout_v1.json" > "$OUT/input_hashes.txt"
echo "== prepare exit $rc $(date -u +%FT%TZ)"; ls "$OUT" | head
