#!/bin/bash
#SBATCH --job-name=g1_stacked
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=03:00:00
#SBATCH --output=ril_aitems/logs/g1_stacked_%j.out
# CPU only. Stacked expansion and L3 edge-set measurement G1 (E-A-OWNER-ITEMS items 1 and 2) on the
# existing E3 cache and X2 dense scores, dev instances only; writes tables and run files with
# SHA-256. Resumable (evaluation files carry the configuration hash). Regression control against the
# stored S1 rows in every run.
#   rsync -a --exclude __pycache__ ril scripts configs ada:ril_aitems/
#   sbatch --export=ALL,RIL_COMMIT=<hash> ril_aitems/scripts/ada/g1_stacked.sbatch
set -euo pipefail
W=$HOME/ril_aitems
PY=$W/venv310/bin/python
CACHE=${CACHE:-$HOME/ril_t1/work/e3_cache}
DENSE=${DENSE:-$HOME/ril_x2/dense}
S1=${S1:-$HOME/ril_x2/s1}
cd "$W"
export PYTHONPATH="$W"
mkdir -p g1 results_g1
{ echo "host=$(hostname)"; echo "python=$($PY -V)"; echo "cpus=$(nproc)"; \
  echo "cpu_model=$(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2)"; \
  echo "ril_commit=${RIL_COMMIT:-none}"; } > g1/env.txt
for name in g1_cre g1_qwen3; do
  CFG=configs/experiments/$name.yaml
  sha256sum "$CFG" >> g1/config_hashes.txt
  S1D=$S1/s1_graph_role_${name#g1_}
  $PY scripts/g1_run.py eval "$CFG" "$CACHE" "$DENSE" "$W/g1/${name}_v2" --s1-dir "$S1D"
  $PY scripts/g1_run.py tables "$W/g1/${name}_v2" "$W/results_g1/${name}_v2"
  sha256sum results_g1/${name}_v2_*.csv >> g1/run_files.sha256
done
