#!/bin/bash
#SBATCH --job-name=rq3_trained_ctx
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --time=06:00:00
#SBATCH --output=ril_rq3t/logs/%x_%j.out
# CPU only. Contexts of the trained arms (E-RQ3-TRAINED-ARMS) for every model whose scores are finished (or the
# models named in MODELS, run ids joined by colons), at budgets 8,000 and 16,000, by the path of E-RQ3-CONTEXTS: each
# of the 377 instances is checked out at its base commit on node-local disk and parsed once for all models,
# assembly unchanged. Resumable per (model, instance): a file that carries the build's spec hash is kept. With
# CHECK=1 it first rebuilds 30 stored instances with the untrained arms through the same path and compares the
# bytes with the stored contexts ($HOME/ril_rq3c/out/ctx, account A; on another account set STORED_CTX): the
# build stops if any differ. Nothing is deleted; node-local scratch is removed at exit.
# Memory estimate (measured in E-RQ3-CONTEXTS, same code path: 4 shards, 12 GB, 8.8 CPU-hours summed for 341
# instances): the same request; a model adds one score array of at most 36,000 floats per instance.
#   sbatch --export=ALL,RIL_COMMIT=<hash>[,MODELS=<id:id>][,CHECK=1] ril_rq3t/scripts/ada/rq3_trained_contexts.sbatch
set -euo pipefail
W=${RQ3T_DIR:-$HOME/ril_rq3t}
E=$HOME/ril_e
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$E/venv_ril$PYV/bin/python
[ -x "$PY" ] || PY=$HOME/ril_x2/venv_gpu$PYV/bin/python   # account C has the GPU environment only
CFG=${RQ3T_CFG:-configs/experiments/rq3_contexts_v1.yaml}
STORED_CTX=${STORED_CTX:-$HOME/ril_rq3c/out/ctx}
FREE=$(df -Pm "$HOME" | awk 'NR==2{print $4}')
[ "$FREE" -gt 1500 ] || { echo "only $FREE MB free in HOME"; exit 3; }
NODE_FREE=$(df -Pm "${TMPDIR:-/tmp}" | awk 'NR==2{print $4}')
[ "$NODE_FREE" -gt 30000 ] || { echo "node-local space on $(hostname) has only $NODE_FREE MB free"; exit 4; }
TMPW=$(mktemp -d "${TMPDIR:-/tmp}/ril_rq3t_ctx.XXXXXX")
trap 'rm -rf "$TMPW"' EXIT
mkdir -p "$W/logs" "$W/out" "$W/ctx"
{ echo "host=$(hostname)"; echo "python=$($PY -V)"; echo "cpus=$(nproc)"; echo "mem=$(grep MemTotal /proc/meminfo)"; \
  echo "ril_commit=${RIL_COMMIT:-none}"; echo "job=${SLURM_JOB_ID:-none}"; echo "models=${MODELS:-all finished}"; } \
  > "$W/out/env_contexts_${SLURM_JOB_ID:-0}.txt"
sha256sum "$W/$CFG" > "$W/out/config_hash_contexts_${SLURM_JOB_ID:-0}.txt"
cd "$W"
export PYTHONPATH="$W"
# bare clones, node-local: a cached bare repository is linked, the others are cloned
mkdir -p "$TMPW/repo_cache"
for repo in django/django sympy/sympy pytest-dev/pytest sphinx-doc/sphinx pylint-dev/pylint astropy/astropy \
  pydata/xarray psf/requests mwaskom/seaborn pallets/flask; do
  name=${repo/\//__}
  if [ -d "$E/repo_cache/$name.git" ]; then ln -s "$E/repo_cache/$name.git" "$TMPW/repo_cache/$name.git"
  else git clone -q --bare "https://github.com/$repo.git" "$TMPW/repo_cache/$name.git"; fi
done
if [ "${CHECK:-0}" = "1" ]; then
  $PY scripts/rq3_trained_arm.py verify-untrained "$CFG" "$TMPW/repo_cache" "$TMPW/work_v" "$STORED_CTX" \
    "$W/out/untrained_equality" --n 30 > "$W/logs/verify_untrained_${SLURM_JOB_ID:-0}.log" 2>&1 \
    || { echo "the untrained arms built by this path differ from the stored contexts"; cat "$W/logs/verify_untrained_${SLURM_JOB_ID:-0}.log"; exit 5; }
  echo "untrained equality ok"
fi
MODELS_ARG=()
[ -z "${MODELS:-}" ] || MODELS_ARG=(--models ${MODELS//:/ })
K=4
rc=0
pids=()
for i in $(seq 0 $((K-1))); do
  $PY scripts/rq3_trained_arm.py contexts "$CFG" "$W/scores" "$TMPW/repo_cache" "$TMPW/work_s$i" "$W/ctx" \
    ${MODELS_ARG[@]+"${MODELS_ARG[@]}"} --shard $i $K > "$W/logs/contexts_s${i}_${SLURM_JOB_ID:-0}.log" 2>&1 &
  pids+=($!)
done
for p in "${pids[@]}"; do wait "$p" || rc=$?; done
echo "contexts rc=$rc"
for d in "$W"/ctx/*/; do echo "$(basename "$d") files=$(ls "$d/instances" | wc -l)"; done
du -sh "$W/ctx"
exit $rc
