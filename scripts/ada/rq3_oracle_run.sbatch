#!/bin/bash
#SBATCH --job-name=ril_rq3_oraclerun
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=3-00:00:00
#SBATCH --output=ril_rq3_driver/logs/oraclerun_%j.out   # relative to the submit directory ($HOME)
# Graded run of the oracle calibration arm (E-RQ3-ORACLE, D168): MAKES PAID MODEL CALLS. A guard in front
# of the shared arm runner (rq3_driver/arm_run.sbatch, unchanged): the prepared directory must hold a clean
# leakage report for this arm, and the run starts only with the pinned configuration hash, the shared locked
# ledger, the per-arm cap, the unusable-share stop and the projected-cost stop. Required environment: MODEL,
# CAP_USD, LIMITS, PREPARED, UV_BIN_DIR, SHARED_LEDGER, SHARED_CAP_USD, EXPECT_CONFIG_HASH, MAX_UNUSABLE,
# PROJECT_AFTER, RUN_INDICES, THINKING (the same values as the other arms; the adjacent repeats are 0 and 1).
set -u
: "${PREPARED:?}" "${CAP_USD:?}" "${EXPECT_CONFIG_HASH:?}" "${SHARED_LEDGER:?}" "${PROJECT_AFTER:?}"
REPORT=$PREPARED/oracle_leak_report.json
PY=$HOME/ril_e/venv_ril310/bin/python
[ -f "$REPORT" ] || { echo "no leakage report in $PREPARED: no call made"; exit 7; }
"$PY" -I -c "import json,sys; r=json.load(open(sys.argv[1])); sys.exit(0 if r['clean'] and r['prompts_checked']==377 else 1)" "$REPORT" \
  || { echo "leakage report is not clean for all 377 prompts: no call made"; exit 7; }
export ARM=oracle
exec bash "$HOME/ril_rq3_driver/code/scripts/ada/rq3_driver/arm_run.sbatch"
