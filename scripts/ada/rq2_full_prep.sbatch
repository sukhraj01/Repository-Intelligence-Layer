#!/bin/bash
#SBATCH --job-name=ril_prep
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
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
#   sbatch --export=ALL,STORE=<store>,RUN=<name>[,LIMIT=N][,STAGES=a:b][,SHARDS=n][,READINGS=non_test:pool_aligned] \
#          [--mem=..G] ril_prep/code/scripts/ada/rq2_full_prep.sbatch
# Options (environment; lists use colons because --export splits on commas): LIMIT (the first N final mined
# directories: the trial), NAMES_FILE (a named subset, for scale probes), STAGES (default all), SHARDS (audit
# shards, default from configs/rq2_prep/full.yaml), READINGS (default non_test; pool_aligned is the sensitivity
# reading), DROP_LIST + DROP_SHA256 (a tracked, hashed drop list instead of this run's own audit), CLEAN_SCRATCH=1
# (remove this job's scratch at the end; off by default), FORCE=1 (rerun finished stages), INDEX (held-out
# index, default $HOME/ril_prep/inputs/ril_ov/index/v1).
# Memory: 12 GB is asked (Slurm allocates 5 to 6 CPUs for it: the cluster grants at most 3,000 MB per CPU and
# the account's limit is 10 CPUs, so a request above 30,000 MB cannot start and one of 30 GB is 11 CPUs).
# Measured on a 200-directory trial (peak 1.2 GB, the overlap audit of one shard) and on 201 directories of three
# large repositories (peak 1.7 GB, the cache read of filter-size with the earlier reader); projected at the full
# store: the largest repository decides the audit and materialise (4.8 GB on the pilot) and the example cache is
# read once, with equal strings shared, about 3 to 6 GB (17 GB with the earlier reader). See
# docs/RQ2_LAUNCH_PLAN.md stage 3. Check sacct MaxRSS after the full run.
# Wall time: projected 2.0 to 2.6 hours for the primary reading (measured per directory and per stage on the
# trial, linear, no interval; docs/RQ2_LAUNCH_PLAN.md stage 3); 8 hours are requested, finished stages are
# skipped on a resubmission and audit shards are resumable.
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
