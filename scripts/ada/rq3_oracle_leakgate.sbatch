#!/bin/bash
#SBATCH --job-name=rq3_oracle_leakgate
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=01:30:00
#SBATCH --output=ril_rq3t/logs/%x_%j.out
# Differential leakage gate of the oracle prompts (E-RQ3-ORACLE, D168). A match of patch text counts only
# when it is absent from the base-commit version of the file whose block holds it, and every context line must
# come from that file. Gate on the oracle prompts (exit 6 on a finding); the same check on the untrained
# prompts is reported as a baseline. The strict report of the build job is kept as oracle_leak_report_strict.json.
#   ORACLE_PREPARED=$HOME/ril_rq3t/out/prepared_oracle_b8000_<job>/oracle sbatch --export=ALL ril_rq3t/scripts/ada/rq3_oracle_leakgate.sbatch
set -uo pipefail
W=$HOME/ril_rq3t; E=$HOME/ril_e
PY=$E/venv_ril$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')/bin/python
PQ=$HOME/ril_rq3/data/verified.parquet
O=${ORACLE_PREPARED:?}
TMPW=$(mktemp -d "${TMPDIR:-/tmp}/ril_rq3o_gate.XXXXXX"); trap 'rm -rf "$TMPW"' EXIT
mkdir -p "$TMPW/repo_cache"
for repo in django/django sympy/sympy pytest-dev/pytest sphinx-doc/sphinx pylint-dev/pylint astropy/astropy \
  pydata/xarray psf/requests mwaskom/seaborn pallets/flask scikit-learn/scikit-learn matplotlib/matplotlib; do
  name=${repo/\//__}
  if [ -d "$E/repo_cache/$name.git" ]; then ln -s "$E/repo_cache/$name.git" "$TMPW/repo_cache/$name.git"
  else git clone -q --bare "https://github.com/$repo.git" "$TMPW/repo_cache/$name.git" || echo "clone failed: $repo"; fi
done
cd "$W"; export PYTHONPATH="$W"
[ -f "$O/oracle_leak_report_strict.json" ] || cp "$O/oracle_leak_report.json" "$O/oracle_leak_report_strict.json"
$PY -I scripts/rq3_oracle_arm.py leak-check "$HOME/ril_rq3_driver/out/prepared_b8000_65086" "$PQ" "$O/../untrained_leak_differential.json" --repo-cache "$TMPW/repo_cache"; echo "baseline rc=$?"
$PY -I scripts/rq3_oracle_arm.py leak-check "$O" "$PQ" "$O/oracle_leak_report.json" --expect-arm oracle --repo-cache "$TMPW/repo_cache"; rc=$?
echo "oracle gate rc=$rc"; exit $rc
