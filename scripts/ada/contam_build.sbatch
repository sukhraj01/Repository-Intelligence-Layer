#!/bin/bash
#SBATCH --job-name=ril_contam_build
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=04:00:00
#SBATCH --output=ril_c/logs/contam_build_%j.out
# CPU only. Probe set of the 12 SWE-bench Verified repositories: bare clones of the six not yet on
# the cluster, then every function and method of every Verified base commit, hashed (no text kept).
# Idempotent: an existing clone is only fetched, an existing probe set is rebuilt (minutes).
# Needs ~/ril_c/{ril,scripts} and ~/ril_pc/work/verified_ref.json. Submit from $HOME:
#   sbatch ril_c/scripts/ada/contam_build.sbatch
set -euo pipefail
cd "$HOME/ril_c"
mkdir -p repo_cache work out logs
for repo in django/django sympy/sympy scikit-learn/scikit-learn sphinx-doc/sphinx pylint-dev/pylint pytest-dev/pytest; do
  name=${repo/\//__}
  dest="repo_cache/$name.git"
  if [ -d "$dest" ]; then
    git --git-dir "$dest" fetch -q origin '+refs/heads/*:refs/heads/*' || true
  else
    git clone -q --bare "https://github.com/$repo.git" "$dest.tmp" && mv "$dest.tmp" "$dest"
  fi
done
for name in astropy__astropy matplotlib__matplotlib pydata__xarray; do
  [ -e "repo_cache/$name.git" ] || ln -s "$HOME/ril_e/repo_cache/$name.git" "repo_cache/$name.git"
done
for name in mwaskom__seaborn pallets__flask psf__requests; do
  [ -e "repo_cache/$name.git" ] || ln -s "$HOME/ril_s2/raw/repo_cache/$name.git" "repo_cache/$name.git"
done
python3 - <<'PY'
import json, os
d = os.path.expanduser("~/ril_c/repo_cache")
out = {n[:-4].replace("__", "/"): os.path.join(d, n) for n in sorted(os.listdir(d)) if n.endswith(".git")}
json.dump(out, open(os.path.expanduser("~/ril_c/work/clones.json"), "w"), indent=1)
print(len(out), "clones")
PY
python3 -I scripts/ada/contam_probe.py build "$HOME/ril_pc/work/verified_ref.json" work/clones.json "${PROBE_OUT:-out/probe_verified.json}" "${STATS_OUT:-out/probe_stats.json}"
