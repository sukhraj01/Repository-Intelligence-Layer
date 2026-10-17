#!/bin/bash
#SBATCH --job-name=e1_run
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=24G
#SBATCH --time=06:00:00
#SBATCH --output=ril_e/logs/e1_run_%j.out
# CPU only. Pilot E1/E2: STAGE=chunk runs BM25 over each configured CORE-Bench folder (protocol and
# filter-first ranks of every positive); STAGE=units checks out each instance's base commit and ranks
# its code units. Writes ranks, ids, paths and line numbers only (no text). Resumable: a finished
# item with the same configuration hash is read back. ONLY=<folder> limits the run to one folder.
# Needs ~/ril_e/raw (e_fetch_data.sbatch), ~/ril_e/repo_cache (e_clone_repos.sbatch) and ~/ril_e/meta.json.
# Submit from $HOME after  rsync -a --exclude __pycache__ ril scripts configs ada:ril_e/ :
#   sbatch --export=ALL,STAGE=chunk,RIL_COMMIT=<hash> ril_e/scripts/ada/e1_run.sbatch
set -euo pipefail
W=$HOME/ril_e
mkdir -p "$W/logs" "$W/out" "$W/work"
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
VENV=$W/venv_ril$PYV
if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q --disable-pip-version-check numpy pyyaml pyarrow pystemmer
fi
"$VENV/bin/pip" freeze > "$W/out/pip_freeze.txt"
{ echo "host=$(hostname)"; echo "python=$("$VENV/bin/python" -V)"; echo "cpus=$(nproc)"; \
  echo "git=$(git --version)"; echo "mem=$(grep MemTotal /proc/meminfo)"; \
  echo "ril_commit=${RIL_COMMIT:-none}"; echo "stage=${STAGE:?}"; } > "$W/out/env_${STAGE}.txt"
cd "$W"
export PYTHONPATH="$W"
ONLY_ARGS=()
if [ -n "${ONLY:-}" ]; then ONLY_ARGS=(--only "$ONLY"); fi
CFG=configs/experiments/e1_bm25_reproduction.yaml
if [ "$STAGE" = chunk ]; then
  "$VENV/bin/python" scripts/e1_run.py chunk "$CFG" "$W/raw" "$W/out" "${ONLY_ARGS[@]}"
else
  "$VENV/bin/python" scripts/e1_run.py units "$CFG" "$W/raw" "$W/meta.json" "$W/repo_cache" "$W/work" "$W/out" "${ONLY_ARGS[@]}"
fi
echo done
