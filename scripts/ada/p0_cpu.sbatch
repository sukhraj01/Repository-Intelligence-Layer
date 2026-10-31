#!/bin/bash
#SBATCH --job-name=p0_cpu
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --time=01:00:00
#SBATCH --output=ril_t3/logs/p0_cpu_%j.out
# CPU only. STAGE=bm25: BM25 teacher pass over the 3,000 directories of work/pool_T3x.jsonl.gz
# (T2 measured 123 s for 2,000; about 3 minutes expected). STAGE=features: feature table of the
# 5,000-directory pool from the rank rows of selection A (ril_t2) and of the new directories.
# Memory estimate: cache about 4.5 to 6 GB plus one directory's index; 12 GB requested.
#   sbatch --export=ALL,RIL_COMMIT=<hash>,STAGE=bm25 ril_t3/scripts/ada/p0_cpu.sbatch
set -euo pipefail
W=$HOME/ril_t3
T2=$HOME/ril_t2/work
X2=$HOME/ril_x2
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$X2/venv_gpu$PYV/bin/python
cd "$W"
export PYTHONPATH="$W"
if [ "${STAGE:?}" = bm25 ]; then
  "$PY" scripts/train.py teacher work/pool_T3x.jsonl.gz work/ranks_T3x_bm25.jsonl work/mined_T3x_bm25.jsonl.gz \
    --teacher bm25 --keep 64 > "out/p0_teacher_bm25_${SLURM_JOB_ID}.json"
else
  "$PY" scripts/train.py features "$T2/ranks_A_coderankembed.jsonl" work/ranks_T3x_coderankembed.jsonl \
    "$T2/ranks_A_swerankembed-small.jsonl" work/ranks_T3x_swerankembed-small.jsonl \
    "$T2/ranks_A_bm25.jsonl" work/ranks_T3x_bm25.jsonl --out work/p0_features_5000.csv \
    --teachers coderankembed swerankembed-small bm25 --held-out data/held_out/held_out_repos.json \
    --rename-cache data/held_out/rename_cache.json > "out/p0_features_${SLURM_JOB_ID}.json"
  for t in coderankembed swerankembed-small bm25; do
    cat "$T2/ranks_A_$t.jsonl" "work/ranks_T3x_$t.jsonl" > "work/ranks_P5000_$t.jsonl"
  done
  "$PY" scripts/t2_tables.py teachers work/ranks_P5000_coderankembed.jsonl work/ranks_P5000_swerankembed-small.jsonl \
    work/ranks_P5000_bm25.jsonl --teachers coderankembed swerankembed-small bm25 --k 10 20 40 \
    --out-dir out/p0_tables --log out/p0_teachers_tables.json > /dev/null
  "$PY" - <<'PY' > "out/p0_loader_${SLURM_JOB_ID}.json"
import json
from ril.training.pool_reader import load_feature_table
from ril.training.train_jobs import signals_from_table
table = load_feature_table("work/p0_features_5000.csv")
sig = signals_from_table("work/p0_features_5000.csv")
print(json.dumps({"teachers": sorted(sig), "table_teachers": list(table.teachers)}, default=str))
PY
fi
echo done
