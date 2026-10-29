#!/bin/bash
#SBATCH --job-name=s1_graph_role
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=03:00:00
#SBATCH --output=ril_x2/logs/s1_graph_role_%j.out
# CPU only. Graph-role measurement S1: runs the four S1 configurations (two first stages, stated cell
# on dev and Verified-six; dev weight sensitivity) on the existing E3 cache and X2 dense scores, then
# writes the tables. Resumable (evaluation files carry the configuration hash).
#   rsync -a --exclude __pycache__ ril scripts configs ada:ril_x2/
#   sbatch --export=ALL,RIL_COMMIT=<hash> ril_x2/scripts/ada/s1_graph_role.sbatch
set -euo pipefail
W=$HOME/ril_x2
E=$HOME/ril_e
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$E/venv_ril$PYV/bin/python
# the cache with the D18 readings (the one the training stack evaluates on)
CACHE=${CACHE:-$HOME/ril_t1/work/e3_cache}
cd "$W"
export PYTHONPATH="$W"
mkdir -p s1 results_s1
{ echo "host=$(hostname)"; echo "python=$(python3 -V)"; echo "cpus=$(nproc)"; \
  echo "cpu_model=$(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2)"; \
  echo "ril_commit=${RIL_COMMIT:-none}"; } > s1/env.txt
for name in s1_graph_role_qwen3 s1_graph_role_cre s1_graph_role_qwen3_sens s1_graph_role_cre_sens; do
  CFG=configs/experiments/$name.yaml
  sha256sum "$CFG" >> s1/config_hashes.txt
  $PY scripts/s1_run.py eval "$CFG" "$CACHE" "$W/dense" "$W/s1/$name"
  $PY scripts/s1_run.py tables "$CFG" "$W/s1/$name" "$W/results_s1/$name"
done
