#!/bin/bash
#SBATCH --job-name=rq3_floor_prep
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:30:00
#SBATCH --output=ril_rq3t/logs/%x_%j.out
# CPU only, no model call. Floor reference arm of RQ3 (E-RQ3-FLOOR, D169): the prompt carries the issue and an
# empty excerpt section (no retrieved code; the reply parser's path filter is off for this arm).
#  1. prepare: the driver's own `prepare` with `--arms floor` (pseudonymise, screen) to
#     $W/out/prepared_floor_b<budget>_<job>/floor, with the held-out and confirmatory id lists of D111;
#  2. differential leakage check on every floor prompt (exit code 6 and a failed job on any finding; the run
#     job refuses a directory without a clean report for all 377 prompts). The context is empty, so the
#     check is vacuous by construction; it is run for the record.
# Nothing is deleted. Memory: 377 prompts of a few kilobytes, far below 4 GB.
#   sbatch ril_rq3t/scripts/ada/rq3_floor_prepare.sbatch
set -euo pipefail
W=${RQ3T_DIR:-$HOME/ril_rq3t}
E=$HOME/ril_e
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$E/venv_ril$PYV/bin/python
VERIFIED_PARQUET=${VERIFIED_PARQUET:-$HOME/ril_rq3/data/verified.parquet}
BUDGET=${BUDGET:-8000}
OUT=$W/out/prepared_floor_b${BUDGET}_${SLURM_JOB_ID:-0}
mkdir -p "$W/logs" "$OUT"
{ echo "host=$(hostname)"; echo "python=$($PY -V)"; echo "job=${SLURM_JOB_ID:-none}"; echo "ril_commit=${RIL_COMMIT:-none}"; } > "$W/out/env_floor_${SLURM_JOB_ID:-0}.txt"
cd "$W"
export PYTHONPATH="$W"
echo "== 1. prepare $(date -u +%FT%TZ)"
"$PY" -I scripts/rq3_driver.py prepare "$W/in" "$OUT/floor" \
  --raw "$E/raw/data" --issues-parquet "$VERIFIED_PARQUET" \
  --subset "$W/in/executable_instances_v1.json" --heldout "$W/in/heldout_v1.json" \
  --budget "$BUDGET" --arms floor --seed 0
sha256sum "$OUT/floor/items.jsonl" > "$OUT/floor/items.sha256"
echo "== 2. leakage check $(date -u +%FT%TZ)"
"$PY" -I scripts/rq3_oracle_arm.py leak-check "$OUT/floor" "$VERIFIED_PARQUET" "$OUT/floor/floor_leak_report.json" \
  --expect-arm floor --repo-cache "$E/repo_cache"
echo "== prepare done $(date -u +%FT%TZ)"; ls "$OUT" "$OUT/floor" | head -20
