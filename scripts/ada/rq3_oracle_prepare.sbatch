#!/bin/bash
#SBATCH --job-name=rq3_oracle_prep
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --time=04:00:00
#SBATCH --output=ril_rq3t/logs/%x_%j.out
# CPU only, no network call to a model. Oracle calibration arm of RQ3 (E-RQ3-ORACLE, D168), in four steps:
#  1. gold files: the paths the gold patch modifies, per instance of the subset (paths only), from the
#     benchmark table's patch column;
#  2. contexts: units of the gold files first, then the untrained rrf ranking, assembly unchanged
#     (4 shards, each instance checked out at its base commit on node-local disk), to $W/ctx/oracle;
#  3. prepare: the driver's own `prepare` (pseudonymise, screen) with the arm name `oracle`, to
#     $W/out/prepared_oracle_b8000_<job>/oracle, with the held-out and confirmatory id lists of D111;
#  4. leakage check on every oracle prompt (exit code 6 and a failed job on any finding; the run job
#     refuses a directory without a clean report), and the same check on the untrained prompts of
#     the stored prepared set as a baseline (reported, not a gate).
# Nothing is deleted; node-local scratch is removed at exit. Memory estimate (measured in
# E-RQ3-CONTEXTS and E-RQ3-AGENT, same code path, one target instead of three): 4 shards, 12 GB.
#   sbatch --export=ALL,RIL_COMMIT=<hash> ril_rq3t/scripts/ada/rq3_oracle_prepare.sbatch
set -euo pipefail
W=${RQ3T_DIR:-$HOME/ril_rq3t}
E=$HOME/ril_e
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$E/venv_ril$PYV/bin/python
CFG=${RQ3T_CFG:-configs/experiments/rq3_contexts_v1.yaml}
VERIFIED_PARQUET=${VERIFIED_PARQUET:-$HOME/ril_rq3/data/verified.parquet}
BASELINE_PREPARED=${BASELINE_PREPARED:-$HOME/ril_rq3_driver/out/prepared_b8000_65086}
BUDGET=${BUDGET:-8000}
FREE=$(df -Pm "$HOME" | awk 'NR==2{print $4}')
[ "$FREE" -gt 1500 ] || { echo "only $FREE MB free in HOME"; exit 3; }
NODE_FREE=$(df -Pm "${TMPDIR:-/tmp}" | awk 'NR==2{print $4}')
[ "$NODE_FREE" -gt 30000 ] || { echo "node-local space on $(hostname) has only $NODE_FREE MB free"; exit 4; }
TMPW=$(mktemp -d "${TMPDIR:-/tmp}/ril_rq3o_ctx.XXXXXX")
trap 'rm -rf "$TMPW"' EXIT
mkdir -p "$W/logs" "$W/out" "$W/ctx"
OUT=$W/out/prepared_oracle_b${BUDGET}_${SLURM_JOB_ID:-0}
mkdir -p "$OUT"
{ echo "host=$(hostname)"; echo "python=$($PY -V)"; echo "cpus=$(nproc)"; echo "mem=$(grep MemTotal /proc/meminfo)"; \
  echo "ril_commit=${RIL_COMMIT:-none}"; echo "job=${SLURM_JOB_ID:-none}"; } > "$W/out/env_oracle_${SLURM_JOB_ID:-0}.txt"
sha256sum "$W/$CFG" > "$W/out/config_hash_oracle_${SLURM_JOB_ID:-0}.txt"
cd "$W"
export PYTHONPATH="$W"
echo "== 1. gold files $(date -u +%FT%TZ)"
$PY -I scripts/rq3_oracle_arm.py gold-files "$VERIFIED_PARQUET" "$W/in/executable_instances_v1.json" "$W/in/oracle_gold_files.json"
sha256sum "$W/in/oracle_gold_files.json" > "$OUT/gold_files.sha256"
echo "== 2. contexts $(date -u +%FT%TZ)"
mkdir -p "$TMPW/repo_cache"
for repo in django/django sympy/sympy pytest-dev/pytest sphinx-doc/sphinx pylint-dev/pylint astropy/astropy \
  pydata/xarray psf/requests mwaskom/seaborn pallets/flask; do
  name=${repo/\//__}
  if [ -d "$E/repo_cache/$name.git" ]; then ln -s "$E/repo_cache/$name.git" "$TMPW/repo_cache/$name.git"
  else git clone -q --bare "https://github.com/$repo.git" "$TMPW/repo_cache/$name.git"; fi
done
K=4
rc=0
pids=()
for i in $(seq 0 $((K-1))); do
  $PY -I scripts/rq3_oracle_arm.py contexts "$CFG" "$TMPW/repo_cache" "$TMPW/work_s$i" "$W/ctx/oracle" \
    --gold "$W/in/oracle_gold_files.json" --shard $i $K > "$W/logs/oracle_contexts_s${i}_${SLURM_JOB_ID:-0}.log" 2>&1 &
  pids+=($!)
done
for p in "${pids[@]}"; do wait "$p" || rc=$?; done
echo "contexts rc=$rc files=$(ls "$W/ctx/oracle/instances" | wc -l)"
[ "$rc" -eq 0 ] || exit "$rc"
echo "== 3. prepare $(date -u +%FT%TZ)"
"$PY" -I scripts/rq3_driver.py prepare "$W/ctx/oracle" "$OUT/oracle" \
  --raw "$HOME/ril_e/raw/data" --issues-parquet "$VERIFIED_PARQUET" \
  --subset "$W/in/executable_instances_v1.json" --heldout "$W/in/heldout_v1.json" \
  --budget "$BUDGET" --arms oracle --seed 0
sha256sum "$OUT/oracle/items.jsonl" > "$OUT/oracle/items.sha256"
echo "== 4. leakage check $(date -u +%FT%TZ)"
"$PY" -I scripts/rq3_oracle_arm.py leak-check "$OUT/oracle" "$VERIFIED_PARQUET" "$OUT/oracle/oracle_leak_report.json" --expect-arm oracle
if [ -d "$BASELINE_PREPARED" ]; then
  set +e
  "$PY" -I scripts/rq3_oracle_arm.py leak-check "$BASELINE_PREPARED" "$VERIFIED_PARQUET" "$OUT/untrained_leak_baseline.json"
  echo "baseline leak-check rc=$? (information only)"
  set -e
fi
echo "== prepare done $(date -u +%FT%TZ)"; ls "$OUT" "$OUT/oracle" | head -20
