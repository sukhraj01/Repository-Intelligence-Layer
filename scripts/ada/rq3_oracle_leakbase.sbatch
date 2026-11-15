#!/bin/bash
#SBATCH --job-name=rq3_oracle_leakbase
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=6G
#SBATCH --time=00:30:00
#SBATCH --output=ril_rq3t/logs/%x_%j.out
# Leakage check of the oracle prompts and of the untrained prompts with the same code; reports only (digests).
set -uo pipefail
W=$HOME/ril_rq3t; E=$HOME/ril_e
PY=$E/venv_ril$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')/bin/python
PQ=$HOME/ril_rq3/data/verified.parquet
cd "$W"; export PYTHONPATH="$W"
O=${ORACLE_PREPARED:?}
$PY -I scripts/rq3_oracle_arm.py leak-check "$HOME/ril_rq3_driver/out/prepared_b8000_65086" "$PQ" "$O/../untrained_leak_baseline.json"; echo "baseline rc=$?"
