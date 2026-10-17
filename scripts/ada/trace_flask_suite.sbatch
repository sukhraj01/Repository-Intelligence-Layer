#!/bin/bash
#SBATCH --job-name=p_trace_flask
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=ril_p/logs/p_trace_flask_%j.out
# CPU only. Runs the flask test suite at the pallets__flask-5014 base commit under the function-level
# tracer (ril/evaluation/dynamic_trace.py) and again under coverage.py for line coverage. The
# dependency pins are the repository's own (requirements/tests.txt) plus the runtime packages of the
# same period. Idempotent: finished outputs are skipped. Submit from $HOME after
#   rsync -a --exclude __pycache__ ril scripts ada:ril_p/      (copies the package and scripts)
#   sbatch ril_p/scripts/ada/trace_flask_suite.sbatch
set -euo pipefail
W=$HOME/ril_p
SHA=7ee9ceb71e868944a46e1ff00b506772a53a4f1d
mkdir -p "$W/logs" "$W/repos" "$W/out"
REPO=$W/repos/pallets__flask
if [ ! -d "$REPO/.git" ]; then
  git clone -q "$HOME/ril_s2/raw/repo_cache/pallets__flask.git" "$REPO"
fi
git -C "$REPO" checkout -q "$SHA"
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
VENV=$W/venv_flask$PYV
if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q --disable-pip-version-check -r "$REPO/requirements/tests.txt" \
    "werkzeug==2.2.3" "jinja2==3.1.2" "click==8.1.3" "itsdangerous==2.1.2" "markupsafe==2.1.2" coverage
  "$VENV/bin/pip" install -q --disable-pip-version-check --no-deps -e "$REPO"
fi
"$VENV/bin/pip" freeze > "$W/out/flask_pip_freeze.txt"
{ echo "host=$(hostname)"; echo "python=$("$VENV/bin/python" -V)"; echo "cpus=$(nproc)"; echo "commit=$(git -C "$REPO" rev-parse HEAD)"; } > "$W/out/flask_env.txt"
cd "$W"
if [ ! -s out/flask_trace.json ]; then
  "$VENV/bin/python" scripts/ada/trace_pytest.py "$REPO" out/flask_trace.json -p no:cacheprovider -W ignore -q tests \
    > logs/flask_trace_pytest.log 2>&1 || true
fi
if [ ! -s out/flask_coverage.json ]; then
  ( cd "$REPO" && "$VENV/bin/python" -m coverage run --branch --source="$REPO/src/flask" -m pytest -p no:cacheprovider -W ignore -q tests \
      > "$W/logs/flask_coverage_pytest.log" 2>&1 || true
    "$VENV/bin/python" -m coverage json -o "$W/out/flask_coverage.json" ) || true
fi
echo done
