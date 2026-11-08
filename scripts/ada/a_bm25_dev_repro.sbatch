#!/bin/bash
#SBATCH --job-name=a_bm25_dev_repro
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=ril_a1/logs/a_bm25_dev_repro_%j.out
# CPU only. Reproduction of A1-DEV (configs/experiments/a_bm25_dev.yaml) with the query-level rows stored:
# stage 1 (three tokenizers), stage 2 (k1 x b on `split`), then the summary against the logged run, the
# regression control and the per-query table. Run files are written to node-local scratch and copied to
# $W/out at the end (nothing is deleted). Development folders only, read from ~/ril_e/raw.
#   rsync -aR --exclude __pycache__ ril scripts configs results/tables/e1_dev_sweep.csv ada:ril_a1/
#   ssh ada 'mkdir -p ril_a1/logs && sbatch ril_a1/scripts/ada/a_bm25_dev_repro.sbatch'
set -euo pipefail
W=$HOME/ril_a1
DATA=${DATA:-$HOME/ril_e/raw}
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=${PY:-$HOME/ril_e/venv_ril$PYV/bin/python}
SCRATCH=/tmp/ril_a1_${SLURM_JOB_ID:-manual}
mkdir -p "$SCRATCH" "$W/out" "$W/logs"
cd "$W"
export PYTHONPATH="$W"
echo "host $(hostname) python $("$PY" -V 2>&1) $(date -u +%FT%TZ)"
CFG=configs/experiments/a_bm25_dev.yaml
"$PY" scripts/a_bm25_dev.py run "$CFG" "$DATA" "$SCRATCH/out" --stage stage1
"$PY" scripts/a_bm25_dev.py run "$CFG" "$DATA" "$SCRATCH/out" --stage stage2 --tokenizer split
"$PY" scripts/a_bm25_dev.py summarise "$CFG" "$SCRATCH/out" --log "$SCRATCH/a1_bm25_dev_repro.json" \
  --table "$SCRATCH/a1_bm25_dev_repro.csv" --host "ada-account-A-$(hostname)"
"$PY" scripts/a_bm25_dev.py rows "$CFG" "$SCRATCH/out" --tokenizer split \
  --rows "$SCRATCH/a1_bm25_dev_query_rows.csv" --files "$SCRATCH/a1_bm25_dev_run_files.json"
[ ! -e "$W/out/run_files" ] || { echo "$W/out/run_files exists; move it aside first" >&2; exit 2; }
cp -r "$SCRATCH/out" "$W/out/run_files"
cp "$SCRATCH/a1_bm25_dev_repro.json" "$SCRATCH/a1_bm25_dev_repro.csv" \
  "$SCRATCH/a1_bm25_dev_query_rows.csv" "$SCRATCH/a1_bm25_dev_run_files.json" "$W/out/"
du -sh "$W/out"
echo done
