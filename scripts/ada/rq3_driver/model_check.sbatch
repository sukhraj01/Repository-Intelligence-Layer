#!/bin/bash
#SBATCH --job-name=ril_rq3_check
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=08:00:00
#SBATCH --output=ril_rq3_driver/logs/check_%j.out   # relative to the submit directory ($HOME)
# Graded model check (D112): one candidate model, one arm (default RRF at 8,000 tokens), once, on the
# held-out slice. MAKES PAID MODEL CALLS: needs billing with a provider-side hard cap, the key in
# ~/.ril_llm_env (mode 600) and a cap for this run. The driver refuses to start without --cap-usd and
# stops before a call that could pass it; the log and the result rows are resumable.
# Required environment: MODEL, CAP_USD, LIMITS (file with the billed-tier limits of MODEL), PREPARED
# (prepared directory of prepare.sbatch), UV_BIN_DIR (directory of the uv binary). Optional: ARM (rrf),
# THINKING (JSON for thinkingConfig), PROBE (default 1: run the cache probe first, D158; 0 skips it and the
# projection is then uncached), RUN_TAG (suffix of the output directory; a new configuration gets a new tag so the
# earlier rows stay as they are, D159), PROBE_CAP_USD (default 0.5; the probe's cost counts against CAP_USD of the check).
set -u
W=$HOME/ril_rq3_driver
X=$HOME/ril_rq3_exec
PY=$HOME/ril_e/venv_ril310/bin/python
: "${MODEL:?}" "${CAP_USD:?}" "${LIMITS:?}" "${PREPARED:?}"
ARM=${ARM:-rrf}
LOCAL=${TMPDIR:-/tmp}/ril_rq3_driver_${SLURM_JOB_ID}
RUN=$W/out/check_${MODEL}_${ARM}${RUN_TAG:+_$RUN_TAG}
mkdir -p "$LOCAL/work" "$LOCAL/cache" "$LOCAL/mirrors" "$RUN"
export PATH="${UV_BIN_DIR:?directory that holds the uv binary}:$PATH"
THINK=()
[ -n "${THINKING:-}" ] && THINK=(--thinking-config "$THINKING")
COUNT=()
if [ "${PROBE:-1}" = "1" ]; then
  # 10 held-out prompts sent twice back to back; writes $RUN/probe/cache_probe.json (run once; a repeat refuses)
  if [ ! -f "$RUN/probe/cache_probe.json" ]; then
    "$PY" -I "$W/code/scripts/rq3_driver.py" cache-probe "$PREPARED" "$RUN/probe" \
      --arm "$ARM" --instances "$PREPARED/ids_heldout.txt" --model "$MODEL" --n 10 \
      --cap-usd "${PROBE_CAP_USD:-0.5}" --limits "$LIMITS" "${THINK[@]}" --seed 0
    echo "== probe exit $? $(date -u +%FT%TZ)"
  fi
  COUNT=(--count-spent "$RUN/probe/cache_probe_calls.jsonl")
fi
"$PY" -I "$W/code/scripts/rq3_driver.py" run "$PREPARED" "$RUN/log" "$RUN/results" \
  --arm "$ARM" --run-index 0 --instances "$PREPARED/ids_heldout.txt" --model "$MODEL" \
  --cap-usd "$CAP_USD" --limits "$LIMITS" "${THINK[@]}" "${COUNT[@]}" \
  --specs "$X/data/specs_v1.jsonl" --work-root "$LOCAL/work" --cache-root "$LOCAL/cache" \
  --mirror-dir "$LOCAL/mirrors" --local-mirrors "$HOME/ril_e/repo_cache" \
  --subset "$W/in/executable_instances_v1.json" --workers 2 --seed 0
echo "== check exit $? $(date -u +%FT%TZ)"
