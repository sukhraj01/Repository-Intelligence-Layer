#!/bin/bash
#SBATCH --job-name=assembly_cap
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=06:00:00
#SBATCH --output=ril_asm/logs/assembly_cap_%j.out
# CPU only. E-ASSEMBLY-CAP: gold in the assembled context by unit cap (500, 1000, 2000), budget and first stage,
# dev instances only, on the existing E3 cache and stored dense scores; every instance is checked out at its base commit on node-local disk
# and rebuilt (class units in header form), then tables. Resumable (one file per instance, keyed by
# the configuration hash). Output goes to its own directory (out_cap), apart from E-ASSEMBLY.
#   rsync -a --exclude __pycache__ ril scripts configs ada:ril_asm/
#   sbatch --export=ALL,RIL_COMMIT=<hash> ril_asm/scripts/ada/assembly_cap.sbatch
set -euo pipefail
W=$HOME/ril_asm
E=$HOME/ril_e
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=${PY:-$E/venv_ril$PYV/bin/python}
CACHE=${CACHE:-$HOME/ril_t1/work/e3_cache}
DENSE=${DENSE:-$HOME/ril_x2/dense}
REPOS=${REPOS:-$E/repo_cache}
LOCAL=${TMPDIR:-/tmp}/ril_asm_$SLURM_JOB_ID
mkdir -p "$W/logs" "$W/out_cap" "$LOCAL/work"
trap 'rm -rf "$LOCAL"' EXIT
cd "$W"
export PYTHONPATH="$W"
{ echo "host=$(hostname)"; echo "python=$($PY -V)"; echo "cpus=$(nproc)"; \
  echo "cpu_model=$(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2)"; \
  echo "mem=$(grep MemTotal /proc/meminfo)"; echo "ril_commit=${RIL_COMMIT:-none}"; \
  echo "tmp_free=$(df -h "$LOCAL" | tail -1)"; } > out_cap/env.txt
CFG=configs/experiments/assembly_cap.yaml
sha256sum "$CFG" > out_cap/config_hashes.txt
$PY scripts/assembly_run.py measure "$CFG" "$CACHE" "$DENSE" "$REPOS" "$LOCAL/work" "$W/out_cap/run"
$PY scripts/assembly_run.py cap_tables "$W/out_cap/run" "$W/out_cap/assembly_cap"
echo done
