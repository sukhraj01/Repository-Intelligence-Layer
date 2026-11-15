#!/bin/bash
#SBATCH --job-name=rq3_arms_leakgate
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=ril_rq3t/logs/%x_%j.out
# Differential leakage check (the one of the oracle arm, D168) over the prompts of the three trained arms
# (RAW, FILTER-BM25, subsample); the untrained and oracle prompts were checked by the oracle gate job.
# Reports hold digests only. A finding makes the exit code non-zero.
#   sbatch --export=ALL ril_rq3t/scripts/ada/rq3_arms_leakgate.sbatch
set -uo pipefail
W=$HOME/ril_rq3t; E=$HOME/ril_e
PY=$E/venv_ril$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')/bin/python
PQ=$HOME/ril_rq3/data/verified.parquet
P=$W/out/prepared_trained_b8000_78233
OUT=$W/out/leak_arms; mkdir -p "$OUT"
TMPW=$(mktemp -d "${TMPDIR:-/tmp}/ril_rq3a_gate.XXXXXX"); trap 'rm -rf "$TMPW"' EXIT
mkdir -p "$TMPW/repo_cache"
for repo in django/django sympy/sympy pytest-dev/pytest sphinx-doc/sphinx pylint-dev/pylint astropy/astropy \
  pydata/xarray psf/requests mwaskom/seaborn pallets/flask scikit-learn/scikit-learn matplotlib/matplotlib; do
  name=${repo/\//__}
  if [ -d "$E/repo_cache/$name.git" ]; then ln -s "$E/repo_cache/$name.git" "$TMPW/repo_cache/$name.git"
  else git clone -q --bare "https://github.com/$repo.git" "$TMPW/repo_cache/$name.git" || echo "clone failed: $repo"; fi
done
cd "$W"; export PYTHONPATH="$W"
worst=0
for run in mined_raw_u100_s100 mined_filter_bm25_u100_s100 mined_sub_u100_s100; do
  $PY -I scripts/rq3_oracle_arm.py leak-check "$P/$run" "$PQ" "$OUT/leak_$run.json" --repo-cache "$TMPW/repo_cache"; rc=$?
  echo "$run rc=$rc"; [ $rc -gt $worst ] && worst=$rc
done
exit $worst
