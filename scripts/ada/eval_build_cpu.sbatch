#!/bin/bash
#SBATCH --job-name=eval_build_cpu
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --time=06:00:00
#SBATCH --output=ril_eval/logs/eval_build_cpu_%j.out
# CPU only. Build of the evaluation repositories of D100 (E-EVAL-REPOS-BUILD): raw L2 folders,
# bare clones, unit records (e1 units stage), instance caches (e3 prepare), unit-text and query
# stores (x2 prepare). Build only: no retrieval result is computed here.
# Bare and working clones live on node-local space and are removed at exit; only small outputs
# stay under ~/ril_eval. Resumable (finished items are read back). Submit from $HOME after
#   rsync -a --exclude __pycache__ ril scripts configs ada:ril_eval/
#   scp data/processed/eval_repos_v1_meta.json ada:ril_eval/meta.json
#   sbatch --export=ALL,RIL_COMMIT=<hash> ril_eval/scripts/ada/eval_build_cpu.sbatch
set -euo pipefail
W=$HOME/ril_eval
E=$HOME/ril_e
S2=$HOME/ril_s2
mkdir -p "$W/logs" "$W/out" "$W/e3_cache" "$W/e3_out" "$W/prep"
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$E/venv_ril$PYV/bin/python
CFG=configs/experiments/eval_repos_v1_build.yaml
FREE=$(df -Pm "$HOME" | awk 'NR==2{print $4}')
[ "$FREE" -gt 2000 ] || { echo "only $FREE MB free in HOME"; exit 3; }
TMPW=$(mktemp -d /tmp/ril_eval.XXXXXX)
trap 'rm -rf "$TMPW"' EXIT
{ echo "host=$(hostname)"; echo "python=$($PY -V)"; echo "cpus=$(nproc)"; \
  echo "mem=$(grep MemTotal /proc/meminfo)"; echo "cpu_model=$(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2)"; \
  echo "ril_commit=${RIL_COMMIT:-none}"; echo "job=${SLURM_JOB_ID:-none}"; } > "$W/out/env_build_${SLURM_JOB_ID:-0}.txt"
cd "$W"
export PYTHONPATH="$W"
# 1. raw folders (resumable, size-checked)
mapfile -t PREFIXES < <($PY -I - <<PY
import yaml
c = yaml.safe_load(open("$CFG"))
for f in c["folders"]:
    print("data/LEVEL-2/%s/%s/" % (f["dataset"], f["folder"]))
PY
)
(cd "$S2" && python3 scripts/hf_fetch.py zhangfw123/CORE-Bench raw/listing_root.json "$W/raw" "${PREFIXES[@]}")
# 2. bare clones on node-local space
mapfile -t REPOS < <($PY -I - <<PY
import yaml
c = yaml.safe_load(open("$CFG"))
print("\n".join(sorted({f["repo"] for f in c["folders"]})))
PY
)
mkdir -p "$TMPW/repo_cache" "$TMPW/work"
T_CLONE=$(date +%s)
for repo in "${REPOS[@]}"; do
  name=${repo/\//__}
  git clone -q --bare "https://github.com/$repo.git" "$TMPW/repo_cache/$name.git"
  du -sh "$TMPW/repo_cache/$name.git"
done
echo "clone_seconds=$(( $(date +%s) - T_CLONE ))"
# 3. unit records: one worker per repository (a repository's folders run one after the other)
unit_worker() {
  local repo=$1
  local name=${repo/\//__}
  mapfile -t ONLYS < <($PY -I - <<PY
import yaml
c = yaml.safe_load(open("$CFG"))
for f in c["folders"]:
    if f["repo"] == "$repo":
        print("%s/%s" % (f["dataset"], f["folder"]))
PY
)
  for only in "${ONLYS[@]}"; do
    $PY scripts/e1_run.py units "$CFG" "$W/raw" "$W/meta.json" "$TMPW/repo_cache" "$TMPW/work" "$W/out/$name" --only "$only"
  done
}
export -f unit_worker
export PY CFG W TMPW PYTHONPATH
printf '%s\n' "${REPOS[@]}" | xargs -P 4 -I{} bash -c 'unit_worker {} > "$W/logs/eval_units_$(echo {} | tr / _).log" 2>&1' || true
mkdir -p "$W/units"
cp -n "$W"/out/*/units/*.json "$W/units/"
echo "unit records: $(ls "$W/units" | wc -l)"
# 4. instance caches and text stores, K shards
K=4
pids=()
for i in $(seq 0 $((K-1))); do
  $PY scripts/e3_run.py prepare $CFG "$W/raw" "$W/meta.json" "$TMPW/repo_cache" "$W/e3_cache" "$TMPW/work" "$W/e3_out" "$W/units" \
    --roles test --shard $i $K > "$W/logs/eval_e3_shard$i.log" 2>&1 &
  pids+=($!)
done
rc=0
for p in "${pids[@]}"; do wait "$p" || rc=$?; done
echo "e3 prepare rc=$rc"
pids=()
for i in $(seq 0 $((K-1))); do
  $PY scripts/x2_run.py prep-units $CFG "$W/meta.json" "$TMPW/repo_cache" "$W/e3_cache" "$TMPW/work" "$W/prep" \
    --roles test --shard $i $K > "$W/logs/eval_prep_units_s$i.log" 2>&1 &
  pids+=($!)
done
for p in "${pids[@]}"; do wait "$p" || rc=$?; done
$PY scripts/x2_run.py prep-queries $CFG "$W/raw" "$W/e3_cache" "$W/prep" --roles test > "$W/logs/eval_prep_queries.log" 2>&1 || rc=$?
echo "prep rc=$rc"
du -sh "$W"/* || true
echo "done rc=$rc"
exit $rc
