#!/bin/bash
#SBATCH --job-name=ril_rq3_armrun
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=3-00:00:00
#SBATCH --output=ril_rq3_driver/logs/armrun_%j.out   # relative to the submit directory ($HOME)
# One arm, one run index, on the confirmatory instances (N = 327, D111) by default: an untrained arm or a trained
# arm (E-RQ3-TRAINED-ARMS) alike, the driver's own `run` unchanged. MAKES PAID MODEL CALLS: needs billing with a
# provider-side hard cap, the key in ~/.ril_llm_env (mode 600), the model chosen by the graded check (D112) and a
# cap for this run (D114: the driver refuses to start without --cap-usd and stops before a call that could pass it;
# a resumed run counts the cost already in its call log). Resumable: submit the same line again after a failure.
# Required environment: MODEL, CAP_USD, LIMITS (file with the billed-tier limits of MODEL), PREPARED (the prepared
# directory that holds the arm's prompts: the untrained set of prepare.sbatch for bm25, dense and rrf, or
# $W/out/prepared_trained_b8000_<job>/<run id> of rq3_trained_prepare.sbatch for tr_<run id>), ARM, RUN_INDEX,
# UV_BIN_DIR. Optional: INSTANCES (ids file, default the confirmatory list beside the prepared directory; the
# trained set of each model has its own copy of the same list), THINKING (JSON for thinkingConfig; the same for
# every arm of the study, recorded in meta.json), RQ3_OUT (result root, default $W/out/arms).
set -u
W=$HOME/ril_rq3_driver
X=$HOME/ril_rq3_exec
PY=$HOME/ril_e/venv_ril310/bin/python
: "${MODEL:?}" "${CAP_USD:?}" "${LIMITS:?}" "${PREPARED:?}" "${ARM:?}" "${RUN_INDEX:?}"
INSTANCES=${INSTANCES:-$PREPARED/ids_confirmatory.txt}
LOCAL=${TMPDIR:-/tmp}/ril_rq3_driver_${SLURM_JOB_ID}
RUN=${RQ3_OUT:-$W/out/arms}/${MODEL}/${ARM}_run${RUN_INDEX}
mkdir -p "$LOCAL/work" "$LOCAL/cache" "$LOCAL/mirrors" "$RUN"
export PATH="${UV_BIN_DIR:?directory that holds the uv binary}:$PATH"
THINK=()
[ -n "${THINKING:-}" ] && THINK=(--thinking-config "$THINKING")
"$PY" -I "$W/code/scripts/rq3_driver.py" run "$PREPARED" "$RUN/log" "$RUN/results" \
  --arm "$ARM" --run-index "$RUN_INDEX" --instances "$INSTANCES" --model "$MODEL" \
  --cap-usd "$CAP_USD" --limits "$LIMITS" "${THINK[@]}" \
  --specs "$X/data/specs_v1.jsonl" --work-root "$LOCAL/work" --cache-root "$LOCAL/cache" \
  --mirror-dir "$LOCAL/mirrors" --local-mirrors "$HOME/ril_e/repo_cache" \
  --subset "$W/in/executable_instances_v1.json" --workers 2 --seed 0
echo "== arm run exit $? $(date -u +%FT%TZ)"
