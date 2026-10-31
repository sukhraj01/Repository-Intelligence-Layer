#!/bin/bash
#SBATCH --job-name=n0_separation
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=24G
#SBATCH --time=01:00:00
#SBATCH --output=ril_n7/logs/n0_separation_%j.out
# CPU only. Gate N0 of E-PILOT-NOISE: does a teacher's K-rank separate injected from clean pairs?
# Needs work/scores_P5000_<teacher>.jsonl (n0_scores.sbatch). Reports, per teacher, seed and rate, the
# AUC and the share of injected and clean pairs a FILTER at K = 20 drops, and the reproduction of the
# feature table's ranks from the stored scores.
# Memory estimate: the two example caches hold about 9 GB of text; scores 4.9M floats per teacher
# (about 40 MB decoded); 24 GB requested.
#   sbatch --export=ALL,RIL_COMMIT=<hash>,TEACHERS="bm25 swerankembed-small" ril_n7/scripts/ada/n0_separation.sbatch
set -euo pipefail
W=$HOME/ril_n7
X2=$HOME/ril_x2
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$X2/venv_gpu$PYV/bin/python
TEACHERS=${TEACHERS:-"bm25 swerankembed-small"}
cd "$W"
export PYTHONPATH="$W"
ARGS=""
for t in $TEACHERS; do ARGS="$ARGS ${t}=work/scores_P5000_${t}.jsonl"; done
{ echo "host=$(hostname)"; echo "ril_commit=${RIL_COMMIT:-none}"; } > "out/env_n0_sep_${SLURM_JOB_ID}.txt"
"$PY" scripts/n0_separation.py work/pool_A.jsonl.gz:work/pool_T3x.jsonl.gz work/p0_features_5000.csv \
  "out/n0_separation_${SLURM_JOB_ID}.json" --scores $ARGS --rates 0.2 0.4 --seeds 0 1 2 --k 20 > /dev/null
echo done
