#!/bin/bash
#SBATCH --job-name=is_test_rule
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=ril_d/logs/is_test_rule-%j.out
# CPU only. Validates the D9 is_test path rule against pytest collection on flask, requests and
# seaborn (bare clones cached by core_bench_snapshot_check.sbatch). Idempotent: rebuilds the trees.
# Submit from $HOME:  sbatch ril_d/scripts/validate_is_test_rule.sbatch   (ril copied to ~/ril_d/ril)
set -euo pipefail
W=$HOME/ril_d
mkdir -p "$W/logs" "$W/trees"
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
VENV=$W/venv_pt$PYV
[ -x "$VENV/bin/python" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install -q --disable-pip-version-check pytest flask requests pytest-httpbin trustme seaborn pytest-mock || true
for n in pallets__flask psf__requests mwaskom__seaborn; do
  rm -rf "$W/trees/$n"; mkdir -p "$W/trees/$n"
  G=$HOME/ril_s2/raw/repo_cache/$n.git
  REV=HEAD; git --git-dir="$G" rev-parse -q --verify HEAD >/dev/null || REV=FETCH_HEAD
  git --git-dir="$G" archive "$REV" | tar -x -C "$W/trees/$n"
  echo "$n $(git --git-dir="$G" rev-parse "$REV")"
done
cd "$W"
"$VENV/bin/python" scripts/validate_is_test_rule.py logs/is_test_rule.json \
  flask=trees/pallets__flask requests=trees/psf__requests seaborn=trees/mwaskom__seaborn
