#!/bin/bash
#SBATCH --job-name=rq2f_planonly
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=1
#SBATCH --mem=6G
#SBATCH --time=00:30:00
#SBATCH --output=ril_rq2f/logs/rq2f_planonly_%j.out
# CPU only, no GPU, nothing deleted, nothing submitted. Plan-only validation of the RQ2 final configurations and
# launch scripts on one account (docs/RQ2_LAUNCH_PLAN.md section 9): the 45 configurations are re-rendered and
# compared with the committed files, the plan (hashes, budget on both bases, job graph) is printed, the
# preflight is run for the account's family against the real directories (it is expected to report the items
# that wait for the prep job), the evaluation sets are checked against the stores on the account, and the
# script headers are read for the memory request; a rehearsal on a synthetic work directory passes every check,
# and the submit script is run to show its refusals (no preflight file, no confirmation, N not computed from a
# prepared store, D140): nothing is submitted. Memory estimate: a plan of 45 configurations, the evaluation
# store check reads unit-text shards line by line (gzipped parts too): under 2 GB peak; 6 GB asked.
#   sbatch --export=ALL,ACCT=A,FAMILY=injected,RIL_COMMIT=<hash> ril_rq2f/scripts/ada/rq2f_planonly.sbatch
set -uo pipefail
W=$HOME/ril_rq2f
ACCT=${ACCT:?set ACCT (A or C)}
FAMILY=${FAMILY:?set FAMILY (mined or injected)}
PY=$HOME/ril_x2/venv_gpu310/bin/python
OUT=$W/out/planonly_${ACCT}_${SLURM_JOB_ID}
mkdir -p "$OUT" "$W/logs" "$W/work"
cd "$W"
export PYTHONPATH="$W"
{ echo "host=$(hostname)"; echo "ril_commit=${RIL_COMMIT:-none}"; echo "account=$ACCT family=$FAMILY"; df -h "$HOME" | tail -1; } > "$OUT/env.txt"
step() { # name, command...
  local name=$1; shift
  local t0=$(date +%s)
  "$@" > "$OUT/$name.json" 2> "$OUT/$name.err"
  local rc=$?
  echo "$name rc=$rc seconds=$(( $(date +%s) - t0 ))" | tee -a "$OUT/steps.txt"
  return 0
}
step plan "$PY" -I scripts/rq2_plan.py plan --filter-size 3450 --pool-examples 5800 --queue-wait-hours 0.03
step plan_drop_conditional "$PY" -I scripts/rq2_plan.py plan --filter-size 3450 --pool-examples 5800 --drop-conditional
step render "$PY" -I scripts/rq2_plan.py render --out "$OUT/rendered"
diff -r -x '_template_*' "$OUT/rendered" configs/experiments/rq2_final > "$OUT/render_vs_committed.diff" 2>&1
echo "render vs committed diff rc=$? (0 = identical)" | tee -a "$OUT/steps.txt"
step eval_sets "$PY" -I scripts/rq2_plan.py eval --set \
  "dev=configs/experiments/e1_bm25_reproduction.yaml:$HOME/ril_x2/prep:dev:$HOME/ril_t1/work/e3_cache" \
  "eight=configs/experiments/eval_repos_v1_build.yaml:$HOME/ril_eval/prep:test:$HOME/ril_eval/e3_cache" \
  "verified_stored36=configs/experiments/e1_bm25_reproduction.yaml:$HOME/ril_x2/prep:test:$HOME/ril_t1/work/e3_cache" \
  "verified_built337=configs/experiments/rq3_units_v1.yaml:$HOME/ril_rq3u/prep:test:$HOME/ril_rq3u/e3_cache:gz" \
  "verified_xarray=configs/experiments/rq3_units_v1_xarray.yaml:$HOME/ril_rq3u_x/prep:test:$HOME/ril_rq3u_x/e3_cache:gz"
RETAIN=()
[ "$FAMILY" = mined ] && RETAIN=(--retain-dir "$HOME/ril_rq2f/retained")
step preflight "$PY" -I scripts/rq2_preflight.py --family "$FAMILY" --account "$ACCT" --work "$W/work" \
  --home "$HOME" --out "$OUT/preflight_${FAMILY}.json" "${RETAIN[@]}"
# Rehearsal on a synthetic work directory (node-local): the records are written by the record script, the prep
# summary and the empty input files are placeholders, so every check can pass; the preflight file is named
# rehearsal and is never accepted by a launch (its work directory is deleted with the node-local scratch).
T=${TMPDIR:-/tmp}/rq2f_rehearsal_${SLURM_JOB_ID}
mkdir -p "$T/work"
export RIL_COMMIT=${RIL_COMMIT:-rehearsal}
step rehearsal_registration "$PY" -I scripts/rq2_record.py registration --work "$T/work" --protocol docs/RQ2_PROTOCOL.md
echo "..........
41 passed in 1.00s" > "$T/pytest_output.txt"
step rehearsal_leakage "$PY" -I scripts/rq2_record.py leakage --work "$T/work" --pytest-output "$T/pytest_output.txt"
echo '{"examples": 5800, "filter_size": 3450, "held_out_rows": 0, "drop_list_applied": true}' > "$T/work/prep_summary.json"
touch "$T/work/mined.jsonl.gz" "$T/work/features_mined.csv"
# the launch step (D140): N from the prepared store, resolved configurations and their hashes (mined family)
if [ "$FAMILY" = mined ]; then
  step rehearsal_resolve "$PY" -I scripts/rq2_plan.py resolve --work "$T/work"
fi
step rehearsal_preflight "$PY" -I scripts/rq2_preflight.py --family "$FAMILY" --account "$ACCT" --work "$T/work" \
  --home "$HOME" --out "$OUT/preflight_rehearsal_${FAMILY}.json" "${RETAIN[@]}"
WORKARG=()
[ "$FAMILY" = mined ] && WORKARG=(--work "$T/work")
step submit_graph "$PY" -I scripts/rq2_submit.py --family "$FAMILY" --account "$ACCT" --date 2026-11-10 \
  --print-graph "${WORKARG[@]}"
# the refusal without a preflight file: exits 2 before any sbatch call (nothing is ever submitted here)
"$PY" -I scripts/rq2_submit.py --family "$FAMILY" --account "$ACCT" --date 2026-11-10 --confirm-launch \
  "${WORKARG[@]}" > "$OUT/submit_refusal.out" 2> "$OUT/submit_refusal.err"
echo "submit without preflight rc=$? (2 = refused)" | tee -a "$OUT/steps.txt"
"$PY" -I scripts/rq2_submit.py --family "$FAMILY" --account "$ACCT" --date 2026-11-10 "${WORKARG[@]}" \
  > /dev/null 2> "$OUT/submit_no_confirm.err"
echo "submit without --confirm-launch rc=$? (2 = refused)" | tee -a "$OUT/steps.txt"
if [ "$FAMILY" = mined ]; then
  # N not computed from a prepared store: an empty work directory has no rq2_updates.json
  mkdir -p "$T/empty"
  "$PY" -I scripts/rq2_submit.py --family mined --account "$ACCT" --date 2026-11-10 --print-graph --work "$T/empty" \
    > /dev/null 2> "$OUT/submit_no_updates.err"
  echo "submit with N not computed rc=$? (2 = refused)" | tee -a "$OUT/steps.txt"
fi
rm -rf "$T"
grep -n "mem=" scripts/ada/rq2f_*_run.sbatch scripts/ada/rq2f_final_sets.sbatch > "$OUT/mem_requests.txt"
quota -s > "$OUT/quota.txt" 2>&1 || true
df -h "$HOME" | tail -1 >> "$OUT/quota.txt"
echo done
