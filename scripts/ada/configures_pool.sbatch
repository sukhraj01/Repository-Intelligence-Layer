#!/bin/bash
#SBATCH --job-name=p_cfg_pool
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=ril_p/logs/p_cfg_pool_%j.out
# CPU only. Shallow-fetches the SWE-bench Verified base commits of four more repositories (pytest,
# sphinx, pylint, seaborn; parsing only) and renders the exploratory `configures` edges of those
# and of flask, requests and django, so that the precision sample can reach n >= 50.
# Submit from $HOME after rsync of ril and scripts: sbatch ril_p/scripts/ada/configures_pool.sbatch
set -euo pipefail
W=$HOME/ril_p
mkdir -p "$W/logs" "$W/repos_extra" "$W/out"
fetch() {  # name url sha
  local d=$W/repos_extra/$1
  if [ ! -d "$d/.git" ]; then mkdir -p "$d"; git -C "$d" init -q; git -C "$d" remote add origin "$2"; fi
  git -C "$d" fetch -q --depth 1 origin "$3"
  git -C "$d" checkout -q FETCH_HEAD
}
fetch pytest-dev__pytest https://github.com/pytest-dev/pytest.git 3c1534944cbd34e8a41bc9e76818018fadefc9a1
fetch sphinx-doc__sphinx https://github.com/sphinx-doc/sphinx.git 6cb783c0024a873722952a67ebb9f41771c8eb6d
fetch pylint-dev__pylint https://github.com/pylint-dev/pylint.git 1f8c4d9eb185c16a2c1d881c054f015e1c2eb334
fetch mwaskom__seaborn https://github.com/mwaskom/seaborn.git 22cdfb0c93f8ec78492d87edb810f10cb7f57a31
cd "$W"
export PYTHONPATH="$W"
python3 scripts/ada/configures_pool.py out/configures_pool.json \
  flask=repos/pallets__flask=pallets/flask requests=repos/psf__requests=psf/requests \
  django=repos/django__django=django/django \
  pytest=repos_extra/pytest-dev__pytest=pytest-dev/pytest sphinx=repos_extra/sphinx-doc__sphinx=sphinx-doc/sphinx \
  pylint=repos_extra/pylint-dev__pylint=pylint-dev/pylint seaborn=repos_extra/mwaskom__seaborn=mwaskom/seaborn
echo done
