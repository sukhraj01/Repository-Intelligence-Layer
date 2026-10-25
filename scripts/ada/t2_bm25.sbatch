#!/bin/bash
#SBATCH --job-name=t2_bm25
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=10G
#SBATCH --time=03:00:00
#SBATCH --output=ril_t2/logs/t2_bm25_%j.out
# CPU only. BM25 teacher pass of the smoke pilots over the example cache of selection A: K-rank of
# every positive and the top 64 BM25 candidates, then (FEATURES=1, after the dense passes) the
# feature table of the three teachers. Memory estimate (before the first run): the cache, 3-4 GB
# (see t2_teachers.sbatch), plus one directory's BM25 index (largest snapshots tens of thousands of
# functions, well under 1 GB); 10 GB requested. Time: X3 measured 124 s for 188,566 functions on
# one process, so about 26 minutes for about 2.35 million functions.
#   sbatch --export=ALL,RIL_COMMIT=<hash> ril_t2/scripts/ada/t2_bm25.sbatch
set -euo pipefail
W=$HOME/ril_t2
X2=$HOME/ril_x2
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$X2/venv_gpu$PYV/bin/python
CACHE=${CACHE:-work/pool_A.jsonl.gz}
cd "$W"
export PYTHONPATH="$W"
if [ "${FEATURES:-0}" != 1 ]; then
  "$PY" scripts/train.py teacher "$CACHE" work/ranks_A_bm25.jsonl work/mined_A_bm25.jsonl.gz --teacher bm25 \
    --keep 64 > "out/teacher_bm25_${SLURM_JOB_ID}.json"
else
  "$PY" scripts/train.py features work/ranks_A_coderankembed.jsonl work/ranks_A_swerankembed-small.jsonl work/ranks_A_bm25.jsonl --out work/t2_features_A.csv \
    --teachers coderankembed swerankembed-small bm25 --held-out data/held_out/held_out_repos.json \
    --rename-cache data/held_out/rename_cache.json > "out/features_${SLURM_JOB_ID}.json"
  "$PY" scripts/t2_tables.py teachers work/ranks_A_coderankembed.jsonl work/ranks_A_swerankembed-small.jsonl work/ranks_A_bm25.jsonl --teachers coderankembed swerankembed-small bm25 \
    --k 10 20 40 --out-dir out/tables --log out/t2_teachers_tables.json > /dev/null
fi
echo done
