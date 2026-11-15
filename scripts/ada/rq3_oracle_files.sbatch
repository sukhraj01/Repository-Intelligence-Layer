#!/bin/bash
#SBATCH --job-name=rq3_oracle_files
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=6G
#SBATCH --time=00:30:00
#SBATCH --output=ril_rq3t/logs/%x_%j.out
# CPU only, no call. For the retrieval-versus-reasoning view of the oracle arm (E-RQ3-ORACLE, D168): the file
# list of the 8,000-token context of the untrained, RAW, FILTER-BM25 and subsample arms, one small JSON each
# (paths only), written to $OUT. The analysis itself runs from stored rows on any machine
# (`scripts/rq3_oracle_arm.py analyse`).
#   sbatch --export=ALL,RIL_COMMIT=<hash> ril_rq3t/scripts/ada/rq3_oracle_files.sbatch
set -euo pipefail
W=${RQ3T_DIR:-$HOME/ril_rq3t}
PY=$HOME/ril_e/venv_ril310/bin/python
OUT=${OUT:-$W/out/oracle_files}
UNTRAINED_CTX=${UNTRAINED_CTX:-$HOME/ril_rq3c/out/ctx}
mkdir -p "$OUT"
cd "$W"
export PYTHONPATH="$W"
$PY -I scripts/rq3_oracle_arm.py context-files "$UNTRAINED_CTX" rrf "$OUT/files_rrf.json"
for pair in raw:mined_raw_u100_s100 filter:mined_filter_bm25_u100_s100 sub:mined_sub_u100_s100; do
  name=${pair%%:*}; rid=${pair#*:}
  $PY -I scripts/rq3_oracle_arm.py context-files "$W/ctx/$rid" "tr_$rid" "$OUT/files_$name.json"
done
ls -l "$OUT"
