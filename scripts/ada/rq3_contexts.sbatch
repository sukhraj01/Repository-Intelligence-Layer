#!/bin/bash
#SBATCH --job-name=rq3_contexts
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --time=06:00:00
#SBATCH --output=ril_rq3c/logs/rq3_contexts_%j.out
# CPU only. Retrieved contexts of the 377 executable instances (E-RQ3-CONTEXTS, D108): BM25, untrained
# dense and RRF at budgets 8,000 and 16,000, from the stored scores of E-RQ3-UNITS and the earlier
# builds; every instance is checked out at its base commit on node-local disk and parsed (class units in
# header form). Then the determinism check (30 instances built a second time), the tables and the
# 8,000-token archive. Resumable (a finished instance file is kept). Nothing is deleted.
#   rsync -a --exclude __pycache__ ril scripts configs ada:ril_rq3c/
#   scp results/rq3_exec/executable_instances_v1.json ada:ril_rq3c/results/rq3_exec/
#   sbatch --export=ALL,RIL_COMMIT=<hash> ril_rq3c/scripts/ada/rq3_contexts.sbatch
set -euo pipefail
W=${RQ3C_DIR:-$HOME/ril_rq3c}
E=$HOME/ril_e
mkdir -p "$W/logs" "$W/out" "$W/tables" "$W/archive"
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$E/venv_ril$PYV/bin/python
CFG=${RQ3C_CFG:-configs/experiments/rq3_contexts_v1.yaml}
FREE=$(df -Pm "$HOME" | awk 'NR==2{print $4}')
[ "$FREE" -gt 1500 ] || { echo "only $FREE MB free in HOME"; exit 3; }
NODE_FREE=$(df -Pm /tmp | awk 'NR==2{print $4}')
[ "$NODE_FREE" -gt 30000 ] || { echo "node-local /tmp on $(hostname) has only $NODE_FREE MB free"; exit 4; }
TMPW=$(mktemp -d /tmp/ril_rq3c.XXXXXX)
trap 'rm -rf "$TMPW"' EXIT
{ echo "host=$(hostname)"; echo "python=$($PY -V)"; echo "cpus=$(nproc)"; \
  echo "mem=$(grep MemTotal /proc/meminfo)"; echo "cpu_model=$(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2)"; \
  echo "ril_commit=${RIL_COMMIT:-none}"; echo "job=${SLURM_JOB_ID:-none}"; } > "$W/out/env_${SLURM_JOB_ID:-0}.txt"
sha256sum "$W/$CFG" > "$W/out/config_hash_${SLURM_JOB_ID:-0}.txt"
cd "$W"
export PYTHONPATH="$W"
# smoke first (no clone needed: flask is in the earlier repository cache); the instance file is kept
mkdir -p "$TMPW/repo_smoke"
ln -s "$E/repo_cache/pallets__flask.git" "$TMPW/repo_smoke/pallets__flask.git"
$PY scripts/rq3_contexts.py build "$CFG" "$TMPW/repo_smoke" "$TMPW/work_smoke" "$W/out/ctx" \
  --only pallets__flask-5014 > "$W/logs/rq3_contexts_smoke.log" 2>&1 || { echo "smoke failed"; cat "$W/logs/rq3_contexts_smoke.log"; exit 5; }
echo "smoke ok"
# bare clones: the five repositories without an earlier cache are cloned node-local, the others are linked
mkdir -p "$TMPW/repo_cache"
for repo in django/django sympy/sympy pytest-dev/pytest sphinx-doc/sphinx pylint-dev/pylint; do
  git clone -q --bare "https://github.com/$repo.git" "$TMPW/repo_cache/${repo/\//__}.git"
done
for name in astropy__astropy pydata__xarray psf__requests mwaskom__seaborn pallets__flask; do
  ln -s "$E/repo_cache/$name.git" "$TMPW/repo_cache/$name.git"
done
K=4
rc=0
pids=()
for i in $(seq 0 $((K-1))); do
  $PY scripts/rq3_contexts.py build "$CFG" "$TMPW/repo_cache" "$TMPW/work_s$i" "$W/out/ctx" \
    --shard $i $K > "$W/logs/rq3_contexts_build_s$i.log" 2>&1 &
  pids+=($!)
done
for p in "${pids[@]}"; do wait "$p" || rc=$?; done
echo "build rc=$rc files=$(ls "$W/out/ctx/instances" | wc -l)"
[ "$rc" -eq 0 ] || exit "$rc"
# determinism: 30 instances (seeded draw) built again into a second directory and compared
$PY scripts/rq3_contexts.py verify "$CFG" "$TMPW/repo_cache" "$TMPW/work_v" "$W/out/ctx" "$W/out/ctx_verify" \
  > "$W/logs/rq3_contexts_verify.log" 2>&1 || rc=$?
echo "verify rc=$rc"
$PY scripts/rq3_contexts.py tables "$W/out/ctx" "$W/tables/rq3_contexts" > "$W/logs/rq3_contexts_tables.log" 2>&1 || rc=$?
$PY scripts/rq3_contexts.py archive "$W/out/ctx" "$W/archive/rq3_contexts_b8000.tar.gz" --budget 8000 \
  > "$W/logs/rq3_contexts_archive.log" 2>&1 || rc=$?
ls -l "$W/archive"
du -sh "$W/out/ctx" "$W/out/ctx_verify"
echo "done rc=$rc"
exit $rc
