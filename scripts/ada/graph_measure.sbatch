#!/bin/bash
#SBATCH --job-name=p_graph_measure
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=03:00:00
#SBATCH --output=ril_p/logs/p_graph_measure_%j.out
# CPU only. Builds the graph of flask, requests and django at their Verified base commits (full
# statistics through scripts/parse_repo.py), then runs the storage and expansion measurement through
# the latency harness (ril/bench/graph_measure.py) and a determinism rerun. Idempotent: it rebuilds
# everything it measures. Needs ril_p/repos/{pallets__flask,django__django} (trace_flask_suite.sbatch and
# clone_django.sbatch create them). Submit from $HOME after rsync of ril and scripts:
#   sbatch --export=ALL,RIL_COMMIT=<short hash>,RIL_DIRTY=1 ril_p/scripts/ada/graph_measure.sbatch
set -euo pipefail
W=$HOME/ril_p
mkdir -p "$W/logs" "$W/out" "$W/repos"
if [ ! -d "$W/repos/psf__requests/.git" ]; then
  git clone -q "$HOME/ril_s2/raw/repo_cache/psf__requests.git" "$W/repos/psf__requests"
fi
git -C "$W/repos/psf__requests" checkout -q 0192aac24123735b3eaf9b08df46429bb770c283
git -C "$W/repos/pallets__flask" checkout -q 7ee9ceb71e868944a46e1ff00b506772a53a4f1d
git -C "$W/repos/django__django" checkout -q 93d4c9ea1de24eb391cb2b3561b6703fd46374df
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
VENV=$W/venv_ril$PYV
if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q --disable-pip-version-check numpy pyyaml pyarrow networkx rustworkx kuzu
fi
"$VENV/bin/pip" freeze > "$W/out/graph_measure_pip_freeze.txt"
cd "$W"
export PYTHONPATH="$W"
{ echo "host=$(hostname)"; echo "python=$("$VENV/bin/python" -V)"; echo "cpus=$(nproc)"; \
  echo "mem=$(grep MemTotal /proc/meminfo)"; echo "ril_commit=${RIL_COMMIT:-none}"; } > out/graph_measure_env.txt
for spec in flask=pallets__flask=pallets/flask requests=psf__requests=psf/requests django=django__django=django/django; do
  label=${spec%%=*}; rest=${spec#*=}; dir=${rest%%=*}; rid=${rest#*=}
  "$VENV/bin/python" scripts/parse_repo.py "repos/$dir" --repo-id "$rid" --seed 0 \
    --stats-json "out/${label}_stats.json" > "logs/${label}_parse_repo.txt"
done
rm -rf gm out/log; mkdir -p out/log
"$VENV/bin/python" -m ril.bench.graph_measure all \
  --repo flask=repos/pallets__flask=pallets/flask --repo requests=repos/psf__requests=psf/requests \
  --repo django=repos/django__django=django/django \
  --work gm --log-dir out/log --out out/graph_measure_ada.json --seed 0
cp gm/*/queries.txt out/ 2>/dev/null || true
for l in flask requests django; do cp "gm/$l/queries.txt" "out/queries_$l.txt"; done
echo done
