#!/bin/bash
#SBATCH --job-name=rq3_gold_units
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=03:00:00
#SBATCH --output=ril_rq3g/logs/%x_%j.out
# CPU only, no model call, no GPU. Gold units (units edited by the reference patch) of the 377
# executable instances for the failure breakdown (E-RQ3-FAILURE-BREAKDOWN). Reads the patch column
# and the base-commit text of the edited files from the bare repository cache; parses only those
# files. Memory estimate: a few files per instance, the largest (a django module) is below 50 MB
# of syntax tree, so 4 GB leaves a wide margin.
#   sbatch ril_rq3g/scripts/ada/rq3_gold_units.sbatch
set -euo pipefail
W=${RQ3G_DIR:-$HOME/ril_rq3g}
E=$HOME/ril_e
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$E/venv_ril$PYV/bin/python
PQ=${VERIFIED_PARQUET:-$HOME/ril_rq3/data/verified.parquet}
SUBSET=${SUBSET:-$HOME/ril_rq3t/in/executable_instances_v1.json}
mkdir -p "$W/logs" "$W/out"
NODE_FREE=$(df -Pm "${TMPDIR:-/tmp}" | awk 'NR==2{print $4}')
[ "$NODE_FREE" -gt 8000 ] || { echo "node-local space on $(hostname) has only $NODE_FREE MB free"; exit 4; }
TMPW=$(mktemp -d "${TMPDIR:-/tmp}/ril_rq3g.XXXXXX")
trap 'rm -rf "$TMPW"' EXIT
# Bare repositories: the cached ones are linked, the others (django, sympy, pytest, sphinx, pylint)
# are cloned without file contents (blob-less) to node-local disk; the contents of the few edited files are fetched on demand by git show, and removed at exit.
mkdir -p "$TMPW/repo_cache"
for repo in django/django sympy/sympy pytest-dev/pytest sphinx-doc/sphinx pylint-dev/pylint astropy/astropy \
  pydata/xarray psf/requests mwaskom/seaborn pallets/flask; do
  name=${repo/\//__}
  if [ -d "$E/repo_cache/$name.git" ]; then ln -s "$E/repo_cache/$name.git" "$TMPW/repo_cache/$name.git"
  else git clone -q --bare --filter=blob:none "https://github.com/$repo.git" "$TMPW/repo_cache/$name.git"; fi
done
cd "$W"
export PYTHONPATH="$W"
$PY -I scripts/rq3_gold_units.py "$PQ" "$SUBSET" "$TMPW/repo_cache" "$W/out/gold_units.json" --seed 0
sha256sum "$W/out/gold_units.json"
