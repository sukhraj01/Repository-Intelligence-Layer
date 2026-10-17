#!/bin/bash
#SBATCH --job-name=m_chunk_unit_reach
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --time=02:00:00
#SBATCH --output=ril_m/logs/m_chunk_unit_reach_%j.out
# CPU only. Pilot M: checks out the SWE-bench Verified base commit of every instance of flask,
# requests and seaborn that appears in the CORE-Bench L2 or L3 sample folders, locates each positive
# chunk in the files, maps it to units, builds the graph of the snapshot and measures graph reach with
# random controls (ril/evaluation/chunk_unit_pilot.py). Writes ids, paths, lines and unit ids only;
# no chunk text. Idempotent and resumable: a finished instance is read back from out/instances.
# Needs: ~/ril_s2/raw/core_bench_samples (fetch_core_bench_samples.sbatch), the bare clones in
# ~/ril_s2/raw/repo_cache (core_bench_snapshot_check.sbatch) and the Verified parquet.
# Submit from $HOME after rsync of ril and scripts:
#   rsync -a --exclude __pycache__ ril scripts ada:ril_m/ && sbatch ril_m/scripts/ada/m_chunk_unit_reach.sbatch
set -euo pipefail
W=$HOME/ril_m
mkdir -p "$W/logs" "$W/out" "$W/work"
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
VENV=$W/venv_ril$PYV
if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q --disable-pip-version-check numpy pyyaml pyarrow
fi
"$VENV/bin/pip" freeze > "$W/out/pip_freeze.txt"
{ echo "host=$(hostname)"; echo "python=$("$VENV/bin/python" -V)"; echo "cpus=$(nproc)"; \
  echo "git=$(git --version)"; echo "mem=$(grep MemTotal /proc/meminfo)"; \
  echo "ril_commit=${RIL_COMMIT:-none}"; } > "$W/out/env.txt"
cd "$W"
export PYTHONPATH="$W"
"$VENV/bin/python" scripts/m_chunk_unit_reach.py \
  "$HOME/ril_s2/raw/core_bench_samples" \
  "$HOME/ril_s2/raw/meta_sets/princeton-nlp_SWE-bench_Verified/data/test-00000-of-00001.parquet" \
  "$HOME/ril_s2/raw/repo_cache" "$W/work" "$W/out" \
  --seed 0 --draws 200 pallets__flask psf__requests mwaskom__seaborn
echo done
