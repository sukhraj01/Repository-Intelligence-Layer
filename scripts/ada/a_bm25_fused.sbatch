#!/bin/bash
#SBATCH --job-name=a_bm25_fused
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=logs/a_bm25_fused_%j.out
# CPU only. E-A1-FUSED (configs/experiments/a_bm25_fused.yaml): the default BM25 and two `split` variants
# alone and inside RRF(BM25, dense) on the five development folders, from the stored encoded chunk and
# query vectors of E-DENSE-FUSION (nothing is encoded). Run files go to node-local scratch and are copied
# to $W/out_fused at the end; nothing is deleted. Submit from $W:
#   rsync -aR --exclude __pycache__ ril scripts configs ada:ril_a1/
#   ssh ada 'cd ril_a1 && mkdir -p logs && sbatch scripts/ada/a_bm25_fused.sbatch'
set -euo pipefail
W=$HOME/ril_a1
DATA=${DATA:-$HOME/ril_e/raw}
ENC=${ENC:-$HOME/ril_x2/enc}
STORED=${STORED:-$HOME/ril_x2/chunks_out}
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=${PY:-$HOME/ril_e/venv_ril$PYV/bin/python}
SCRATCH=/tmp/ril_a1_fused_${SLURM_JOB_ID:-manual}
mkdir -p "$SCRATCH" "$W/out_fused"
cd "$W"
export PYTHONPATH="$W"
echo "host $(hostname) python $("$PY" -V 2>&1) $(date -u +%FT%TZ)"
CFG=configs/experiments/a_bm25_fused.yaml
"$PY" scripts/a_bm25_fused.py run "$CFG" "$DATA" "$ENC" "$SCRATCH/out"
"$PY" scripts/a_bm25_fused.py summarise "$CFG" "$SCRATCH/out" "$STORED" \
  --log "$SCRATCH/a1_bm25_fused.json" --table "$SCRATCH/a1_bm25_fused.csv" \
  --rows "$SCRATCH/a1_bm25_fused_query_rows.csv" --files "$SCRATCH/a1_bm25_fused_run_files.json" \
  --host "ada-account-A-$(hostname)"
[ ! -e "$W/out_fused/run_files" ] || { echo "$W/out_fused/run_files exists; move it aside first" >&2; exit 2; }
cp -r "$SCRATCH/out" "$W/out_fused/run_files"
cp "$SCRATCH"/a1_bm25_fused*.json "$SCRATCH"/a1_bm25_fused*.csv "$W/out_fused/"
du -sh "$W/out_fused"
echo done
