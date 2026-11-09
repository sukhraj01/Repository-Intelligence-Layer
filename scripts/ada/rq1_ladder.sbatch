#!/bin/bash
#SBATCH --job-name=rq1_ladder
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=03:00:00
#SBATCH --output=ril_rq1/logs/rq1_ladder_%j.out
# CPU only. RQ1 ladder (E-RQ1-LADDER): inventory of the development cache and stored dense scores,
# then the ladder evaluation for CodeRankEmbed (1,024 tokens, the working default) and
# Qwen3-Embedding-0.6B (512 tokens, labelled secondary). Reads the E3 cache and the X2 dense scores
# only; development role only; resumable (evaluation files carry the configuration hash); nothing
# is deleted.
#   ssh ada mkdir -p ril_rq1/logs
#   rsync -a --exclude __pycache__ ril scripts configs ada:ril_rq1/
#   sbatch --export=ALL,RIL_COMMIT=<hash> ril_rq1/scripts/ada/rq1_ladder.sbatch
set -euo pipefail
W=$HOME/ril_rq1
X=$HOME/ril_x2
E=$HOME/ril_e
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$E/venv_ril$PYV/bin/python
CACHE=${CACHE:-$HOME/ril_t1/work/e3_cache}
cd "$W"
export PYTHONPATH="$W"
OUT=rq1_ladder_v2
mkdir -p $OUT
{ echo "host=$(hostname)"; echo "python=$(python3 -V)"; echo "cpus=$(nproc)"; \
  echo "cpu_model=$(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2)"; \
  echo "ril_commit=${RIL_COMMIT:-none}"; echo "job=${SLURM_JOB_ID:-none}"; \
  echo "cache=$CACHE"; } > $OUT/env.txt
$PY scripts/rq1_ladder.py inventory "$CACHE" "$X/dense" coderankembed__t1024 coderankembed__t512 \
  qwen3-embedding-0.6b__t512 > $OUT/inventory.json
for label in cre qwen3; do
  CFG=configs/experiments/rq1_ladder_$label.yaml
  sha256sum "$CFG" >> $OUT/config_hashes.txt
  /usr/bin/time -v $PY scripts/rq1_ladder.py eval "$CFG" "$CACHE" "$X/dense" "$W/$OUT/$label" \
    2> $OUT/time_$label.txt
done
