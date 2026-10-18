#!/bin/bash
#SBATCH --job-name=ril_pool_check
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=04:00:00
#SBATCH --output=ril_pc/logs/pool_check_%j.out
# CPU-only. Metadata of gangiswag/train_data (python) by HTTP range requests: queries and qrels of
# every instance, corpus of a seeded sample. Idempotent: finished instances are skipped on rerun.
# Needs ~/ril_s2/raw/{ziplist_train.json,ids_all.json,meta_sets} and ~/ril_pc/{ril,scripts}.
# Usage: cd ~ && sbatch --export=ALL,SEED=0,SAMPLE=300 ril_pc/scripts/ada/pool_check.sbatch
set -euo pipefail
cd "$HOME/ril_pc"
V="$HOME/ril_s2/venv_pa_$(python3 -c 'import sys;print("%d%d" % sys.version_info[:2])')"
if [ ! -x "$V/bin/pip" ]; then python3 -m venv "$V" && "$V/bin/pip" install -q pyarrow; fi
mkdir -p work out logs
"$V/bin/python" -I scripts/ada/pool_check_ref.py \
  "$HOME/ril_s2/raw/meta_sets/princeton-nlp_SWE-bench_Verified/data/test-00000-of-00001.parquet" work/verified_ref.json
python3 scripts/ada/pool_check.py work "$HOME/ril_s2/raw/ziplist_train.json" "$HOME/ril_s2/raw/ids_all.json" \
  work/verified_ref.json out/pool_check.json "${SEED:-0}" "${SAMPLE:-300}" "${THREADS:-8}"
