#!/bin/bash
#SBATCH --job-name=ril_mine
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=12:00:00
#SBATCH --output=ril_mine/logs/mine_%j.out
# CPU only. PR-mined set (E-MINE-PILOT): list merged pull requests with their closing issues, mine a
# seeded sample (compare, base-commit snapshot, parse, hunk-to-unit mapping), write one directory per
# pull request. Resumable and idempotent: finished pull requests have a state row and are skipped.
# Needs GITHUB_TOKEN (read-only) in the job environment: presence is tested, the value is never printed.
# Without it the job stops at once with exit code 3 and fetches nothing (no unauthenticated fallback).
# Needs ~/ril_mine/{ril,scripts,configs}, the pool listing and the held-out files (see scripts/ada/README.md).
#   sbatch --export=ALL,CONFIG=configs/mining/pilot.yaml,RUN=pilot,CREATED=<YYYY-MM-DD> ril_mine/scripts/ada/mine_pilot.sbatch
# Optional: LIST_ONLY=1 SHARD="i n" (listing shards: three jobs list every third repository; the mining
# session then reuses the stored listings), REPOS=5 (validation stage M1), STOP_AFTER=N (bounded session), LOOKAHEAD=6 (base commits
# fetched ahead in background threads; a speed setting only, the outputs do not depend on it).
# DURABLE=<path> (the full run, D94): the run root is built on node-local disk and pushed to <path> (the
# de-duplicated store plus run state; a shared home) every SYNC_EVERY outcomes (default 25) or SYNC_SECONDS
# (default 600) and at the end; a job on a node with no run root restores it from <path> first
# (ril/data_mining/durable.py). Use one job per <path> at a time. Without DURABLE the run root is
# ~/ril_mine/runs/$RUN as before (directory layout).
# In-job relaunch (DEV-036): when the miner exits non-zero it is started again inside the same
# allocation, up to RELAUNCHES times (default 5), resuming from state.jsonl (a recorded pull request is
# never mined twice); STOP_AFTER counts what is still missing after the rows the failed run recorded.
# Exit codes 3 (no token), 4 (incomplete listing) and 5 (quarantine rate above the limit) end the job
# and, with DURABLE, leave a HALT file there: a later session (one released by `afterany`) refuses to
# start while it exists, so a systemic fault is not repeated by the next job. The engineer removes it.
# Disk: the base-commit working repositories live in node-local $TMPDIR (regenerable); the run root
# (~/ril_mine/runs/$RUN) holds the directories, listings and state. Estimate the added size first.
set -euo pipefail
cd "$HOME/ril_mine"
if [ -z "${GITHUB_TOKEN:-}" ]; then
  echo "BLOCKED: GITHUB_TOKEN is not set in the job environment; nothing fetched" >&2
  exit 3
fi
V="$HOME/ril_mine/venv_$(python3 -c 'import sys;print("%d%d" % sys.version_info[:2])')"
if [ ! -x "$V/bin/pip" ]; then python3 -m venv "$V" && "$V/bin/pip" install -q numpy pyyaml; fi
mkdir -p logs
if [ -n "${DURABLE:-}" ] && [ -f "$DURABLE/HALT" ]; then
  echo "BLOCKED: $DURABLE/HALT exists (an earlier session ended on exit code $(cat "$DURABLE/HALT")); nothing run" >&2
  exit 6
fi
[ -n "${DURABLE:-}" ] && mkdir -p "$DURABLE" || mkdir -p "runs/${RUN:-pilot}"
WORK=$(mktemp -d "${TMPDIR:-/tmp}/ril_mine_work.XXXXXX")
trap 'rm -rf "$WORK"' EXIT
EXTRA=""
[ -n "${REPOS:-}" ] && EXTRA="$EXTRA --repos $REPOS"
EXTRA="$EXTRA --lookahead ${LOOKAHEAD:-6}"
[ -n "${LIST_ONLY:-}" ] && EXTRA="$EXTRA --list-only"
[ -n "${SHARD:-}" ] && EXTRA="$EXTRA --shard $SHARD"
OUT="runs/${RUN:-pilot}"
if [ -n "${DURABLE:-}" ]; then
  OUT="$WORK/run"
  EXTRA="$EXTRA --store-layout dedup --durable $DURABLE --sync-every ${SYNC_EVERY:-25} --sync-seconds ${SYNC_SECONDS:-600}"
fi
state_rows() {  # rows of the run state that a run started now would resume from
  if [ -f "$OUT/state.jsonl" ]; then wc -l < "$OUT/state.jsonl"
  elif [ -n "${DURABLE:-}" ] && [ -f "$DURABLE/state.jsonl" ]; then wc -l < "$DURABLE/state.jsonl"
  else echo 0; fi
}
START_ROWS=$(state_rows)
attempt=0
while true; do
  STOP=""
  if [ -n "${STOP_AFTER:-}" ]; then
    LEFT=$(( STOP_AFTER - ($(state_rows) - START_ROWS) ))
    [ "$LEFT" -lt 1 ] && LEFT=1
    STOP="--stop-after $LEFT"
  fi
  if RIL_COMMIT=${RIL_COMMIT:-none} "$V/bin/python" -I scripts/mine_pilot.py run "${CONFIG:-configs/mining/pilot.yaml}" \
    "$OUT" --listing "$HOME/ril_s2/raw/ziplist_train.json" \
    --held-out data/held_out/held_out_repos.json --rename-cache data/held_out/rename_cache.json \
    --work "$WORK" --created "${CREATED:?set CREATED=YYYY-MM-DD}" $EXTRA $STOP; then
    break
  else
    rc=$?
  fi
  case "$rc" in
    3|4|5)
      echo "miner exit code $rc ends the job (no relaunch)" >&2
      [ -n "${DURABLE:-}" ] && echo "$rc" > "$DURABLE/HALT"
      exit "$rc" ;;
  esac
  attempt=$((attempt + 1))
  if [ "$attempt" -gt "${RELAUNCHES:-5}" ]; then
    echo "miner failed $attempt times (last exit code $rc); giving up" >&2
    exit "$rc"
  fi
  echo "miner exit code $rc; relaunch $attempt of ${RELAUNCHES:-5} from state.jsonl after $((30 * attempt)) s" >&2
  sleep $((30 * attempt))
done
echo done
