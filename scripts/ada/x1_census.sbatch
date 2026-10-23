#!/bin/bash
#SBATCH --job-name=x1_census
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=08:00:00
#SBATCH --output=ril_x1/logs/x1_census_%j.out
# CPU only. L3 positive census beyond the pilot-E1 unit set: fetch the SWE-bench Pro ansible folders
# (L2, L3), bare clones of the seven repositories, then the pilot-E1 unit stage (checkout, locate each
# positive chunk, map to units, kind) per folder, one process per folder, four at a time. Records hold ids,
# paths, lines and kinds only. Needs ~/ril_x1/census_meta.json (built locally from the datasets' metadata,
# untracked) and configs/experiments/x1_l3_census.yaml. Resumable (finished records are kept; clones fetched).
# Submit from $HOME:  sbatch --export=ALL,RIL_COMMIT=<hash> ril_x1/scripts/ada/x1_census.sbatch
# (FOLDERS="a b" limits the run to those folders; the fetch and clone steps are skipped when done.)
set -euo pipefail
W=$HOME/ril_x1
E=$HOME/ril_e
RAW=$W/raw_census
RC=$W/repo_cache_census
mkdir -p "$W/logs" "$RAW/data/LEVEL-2/SWE-bench_Verified" "$RAW/data/LEVEL-3/SWE-bench_Verified" "$RC" "$W/out_census"
for lvl in LEVEL-2 LEVEL-3; do
  for f in django__django pylint pytest scikit sphinx sympy__sympy; do
    [ -e "$RAW/data/$lvl/SWE-bench_Verified/$f" ] || ln -s "$E/raw/data/$lvl/SWE-bench_Verified/$f" "$RAW/data/$lvl/SWE-bench_Verified/$f"
  done
done
( cd "$HOME/ril_s2" && python3 scripts/hf_fetch.py zhangfw123/CORE-Bench raw/listing_root.json "$RAW" \
    "data/LEVEL-2/SWE-bench_Pro/instance_ansible__ansible/" "data/LEVEL-3/SWE-bench_Pro/instance_ansible__ansible/" )
for repo in django/django pylint-dev/pylint pytest-dev/pytest scikit-learn/scikit-learn sphinx-doc/sphinx sympy/sympy ansible/ansible; do
  name=${repo/\//__}
  dest="$RC/$name.git"
  if [ ! -d "$dest" ]; then
    git clone -q --bare "https://github.com/$repo.git" "$dest.tmp" && mv "$dest.tmp" "$dest"
  fi
  du -sh "$dest"
done
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
VENV=$E/venv_ril$PYV
{ echo "host=$(hostname)"; echo "python=$("$VENV/bin/python" -V)"; echo "cpus=$(nproc)"; \
  echo "cpu_model=$(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2)"; \
  echo "mem=$(grep MemTotal /proc/meminfo)"; echo "ril_commit=${RIL_COMMIT:-none}"; } > "$W/out_census/env.txt"
cd "$W"
export PYTHONPATH="$W"
CFG=configs/experiments/x1_l3_census.yaml
run() {
  "$VENV/bin/python" scripts/e1_run.py units "$CFG" "$RAW" "$W/census_meta.json" "$RC" "$W/work_census_$1" \
    "$W/out_census/$1" --only "$1" > "$W/logs/x1_census_$1.log" 2>&1
}
if [ -n "${FOLDERS:-}" ]; then  # e.g. FOLDERS="sphinx pytest pylint": these folders only, in parallel
  for f in $FOLDERS; do run "$f" & done
  wait
else
  run django__django & run sympy__sympy & run instance_ansible__ansible & run scikit & wait
  run sphinx & run pytest & run pylint & wait
fi
echo done
