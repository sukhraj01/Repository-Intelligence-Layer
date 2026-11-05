#!/bin/sh
# Pre-commit step: run the latency regression check and record the row.
#
# Switch RIL_LATENCY_HOOK (environment variable):
#   strict   (default) every commit gets a fresh row and the regression check
#   relaxed  commits that stage nothing under ril/, scripts/ or configs/ skip the run
#   off      skip entirely
# Which of these the project uses is an open question (Q3); the default is the strict reading.
# RIL_LATENCY_DIR (default results/latency) names the directory of the two CSVs; workstreams A and C use their own.
# The appended rows are staged so they travel with the commit they describe.
set -e
mode="${RIL_LATENCY_HOOK:-strict}"
root="$(git rev-parse --show-toplevel)"
cd "$root"
case "$mode" in
  off) exit 0 ;;
  relaxed)
    if ! git diff --cached --name-only | grep -qE '^(ril|scripts|configs)/'; then
      echo "latency hook: relaxed mode, no code staged; skipped"
      exit 0
    fi
    ;;
  strict) ;;
  *) echo "latency hook: unknown RIL_LATENCY_HOOK=$mode (strict|relaxed|off)" >&2; exit 1 ;;
esac
make --no-print-directory bench-check
dir="${RIL_LATENCY_DIR:-results/latency}"
git add "$dir/latency_log.csv" "$dir/throughput_log.csv"
