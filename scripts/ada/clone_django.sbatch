#!/bin/bash
#SBATCH --job-name=p_clone_django
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=01:00:00
#SBATCH --output=ril_p/logs/p_clone_django_%j.out
# CPU only. Clones django/django (full history, needed for the history pass) and checks out the
# django__django-16145 base commit; prints counts of Python files and bytes. Idempotent: skipped if
# the checkout exists. Submit from $HOME:  sbatch ril_p/scripts/ada/clone_django.sbatch
set -euo pipefail
W=$HOME/ril_p
SHA=93d4c9ea1de24eb391cb2b3561b6703fd46374df
mkdir -p "$W/logs" "$W/repos"
REPO=$W/repos/django__django
if [ ! -d "$REPO/.git" ]; then
  git clone -q https://github.com/django/django.git "$REPO"
fi
git -C "$REPO" checkout -q "$SHA"
echo "commit=$(git -C "$REPO" rev-parse HEAD)"
echo "commits_reachable=$(git -C "$REPO" rev-list --count HEAD)"
echo "py_files=$(git -C "$REPO" ls-files '*.py' | wc -l)"
echo "py_bytes=$(git -C "$REPO" ls-files -z '*.py' | xargs -0 cat | wc -c)"
echo "py_lines=$(git -C "$REPO" ls-files -z '*.py' | xargs -0 cat | wc -l)"
du -sh "$REPO"
df -h "$HOME" | tail -1
