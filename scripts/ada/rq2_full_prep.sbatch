#!/bin/bash
#SBATCH --job-name=ril_prep
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=30G
#SBATCH --time=08:00:00
#SBATCH --exclude=gnode004,gnode044
#SBATCH --output=ril_prep/logs/prep_%j.out
# CPU only. E-RQ2-FULL-PREP (docs/RQ2_LAUNCH_PLAN.md stages 1 to 3): from a finished mined store to the
# mined example cache, as explicit stages with one entry point:
#   select, overlap (sharded, resumable), drop, materialise, inputs, teacher, features, cache, check
# Reads the store, never writes into it, deletes nothing. Outputs go to $HOME/ril_prep/runs/$RUN; the
# materialised directories, zips and listings go to node-local scratch ($TMPDIR, else /tmp), which is lost
# with the node: a resubmission with the same RUN skips finished stages and rebuilds what it needs.
# Submit from $HOME (the log path is relative):
#   sbatch --export=ALL,STORE=<store>,RUN=<name>[,LIMIT=N][,STAGES=a,b][,SHARDS=n][,READINGS=non_test:pool_aligned] \
#          [--mem=..G] ril_prep/code/scripts/ada/rq2_full_prep.sbatch
# Options (environment): LIMIT (the first N final mined directories; the trial), NAMES_FILE (a named
# subset, for scale probes), STAGES (default all),
# SHARDS (audit shards, default from configs/rq2_prep/full.yaml), READINGS (colon-separated, default
# non_test; pool_aligned is the sensitivity reading), DROP_LIST + DROP_SHA256 (a tracked, hashed drop list instead of this run's own
# audit), CLEAN_SCRATCH=1 (remove this job's scratch at the end; off by default), FORCE=1 (rerun finished
# stages), INDEX (held-out index, default $HOME/ril_prep/inputs/ril_ov/index/v1).
# Memory: the request is 30 GB because the chain's largest step at the full mined set reads the whole
# example cache into memory (filter-size; the same read as a training process): projected 17 GB decoded
# plus the encoder and evaluation in a run (docs/RQ2_LAUNCH_PLAN.md stage 3). A trial passes a smaller --mem.
# Wall time: see docs/RQ2_LAUNCH_PLAN.md stage 3 for the measured cost per directory.
set -euo pipefail
P=$HOME/ril_prep
CODE=${CODE:-$P/code}
RUN=${RUN:?set RUN}
STORE=${STORE:?set STORE}
OUT=$P/runs/$RUN
INDEX=${INDEX:-$P/inputs/ril_ov/index/v1}
HELD=${HELD:-$HOME/ril_mine/data/held_out/held_out_repos.json}
REN=${REN:-$HOME/ril_mine/data/held_out/rename_cache.json}
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=${PY:-$HOME/ril_x2/venv_gpu$PYV/bin/python}
SCR=${TMPDIR:-/tmp}/ril_prep_${RUN}_${SLURM_JOB_ID:-local}
mkdir -p "$P/logs" "$OUT" "$SCR"
cd "$CODE"
{
  echo "host=$(hostname)"; echo "ril_commit=${RIL_COMMIT:-none}"; "$PY" --version
  df -h "$SCR" "$HOME" | tail -2; free -g | head -2
  echo "scratch=$SCR (kept unless CLEAN_SCRATCH=1)"
} | tee "$OUT/env_${SLURM_JOB_ID:-local}.txt"
ARGS=(run --config configs/rq2_prep/full.yaml --store "$STORE" --out "$OUT" --scratch "$SCR"
      --index "$INDEX" --held-out "$HELD" --rename-cache "$REN" --python "$PY"
      --stages "${STAGES:-all}")
[ -n "${LIMIT:-}" ] && ARGS+=(--limit "$LIMIT")
[ -n "${NAMES_FILE:-}" ] && ARGS+=(--names-file "$NAMES_FILE")
[ -n "${SHARDS:-}" ] && ARGS+=(--shards "$SHARDS")
[ -n "${READINGS:-}" ] && ARGS+=(--readings ${READINGS//:/ })
[ -n "${DROP_LIST:-}" ] && ARGS+=(--drop-list "$DROP_LIST" --drop-sha256 "${DROP_SHA256:?set DROP_SHA256 with DROP_LIST}")
[ "${CLEAN_SCRATCH:-0}" = 1 ] && ARGS+=(--clean-scratch)
[ "${FORCE:-0}" = 1 ] && ARGS+=(--force)
"$PY" -I scripts/rq2_full_prep.py "${ARGS[@]}"
echo done
