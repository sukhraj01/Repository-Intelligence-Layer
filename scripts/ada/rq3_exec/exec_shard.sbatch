#!/bin/bash
#SBATCH --job-name=ril_rq3_exec
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --time=23:00:00
#SBATCH --output=ril_rq3_exec/logs/exec_%A_%a.out   # relative to the submit directory ($HOME)
# Gold-patch runs of D106 (docs/RQ3_PILOT.md). The submit limit is 5 jobs per user, so an array
# task t of T runs shards t, t+T, t+2T, ... of SHARDS one after another (TASKS = T):
# (from $HOME, so the log path resolves):
#   (set UV_BIN_DIR to the directory of the uv binary)
#   RUN=pilot SHARDS=5 TASKS=5 IDS=data/pilot25.txt sbatch --array=0-4 ril_rq3_exec/exec_shard.sbatch
#   RUN=full SHARDS=8 TASKS=4 sbatch --array=0-3 ril_rq3_exec/exec_shard.sbatch
# (two array tasks at a time: the per-user limit is 10 CPUs and Slurm counts hardware threads,
#  so --cpus-per-task=2 occupies 4)
# Work, package caches and repository mirrors live in node-local $TMPDIR; $HOME gets only the
# small results file. Resumable: the same command continues where the shard stopped.
set -u
cd ~/ril_rq3_exec
RUN=${RUN:?RUN name}; SHARDS=${SHARDS:?SHARDS count}; TASKS=${TASKS:?TASKS count}
IDS=${IDS:-}; WORKERS=${WORKERS:-3}
TASK=${SLURM_ARRAY_TASK_ID:?array task}
LOCAL=${TMPDIR:-/tmp}/ril_rq3_exec_${SLURM_JOB_ID}
mkdir -p "$LOCAL/work" "$LOCAL/cache"
echo "== node $(hostname) $(date -u +%FT%TZ) task $TASK of $TASKS, $SHARDS shards, run $RUN"
df -h "$LOCAL" | tail -1
export PATH="${UV_BIN_DIR:?directory that holds the uv binary}:$PATH"
rc=0
for SHARD in $(seq "$TASK" "$TASKS" $((SHARDS-1))); do
  ARGS=(data/specs_v1.jsonl data/gold_v1.jsonl "runs/$RUN/shard_$(printf %02d "$SHARD")"
        --shard "$SHARD" --count "$SHARDS" --runs 2 --workers "$WORKERS"
        --work-root "$LOCAL/work" --cache-root "$LOCAL/cache" --local-mirrors "$HOME/ril_e/repo_cache"
        --commit "$(cat code/COMMIT 2>/dev/null)")
  [ -n "$IDS" ] && ARGS+=(--ids "$IDS")
  # the job's own node-local caches (mirrors, packages) are removed with the last shard of the task
  [ $((SHARD + TASKS)) -gt $((SHARDS - 1)) ] && ARGS+=(--clean-cache)
  venv/bin/python code/rq3_exec.py run-shard "${ARGS[@]}"
  rc=$?
  echo "== shard $SHARD exit $rc $(date -u +%FT%TZ)"
  [ "$rc" -eq 75 ] && break   # node-local disk full: stop; resubmit with --exclude=<node>
done
# what is left after the executor's own cleanup (it removes each evaluation's scratch directory)
du -sh "$LOCAL" 2>/dev/null | tail -1
exit $rc
