#!/bin/bash
#SBATCH --job-name=e_clone
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=04:00:00
#SBATCH --output=ril_e/logs/e_clone_%j.out
# CPU only. Bare clones of the repositories of pilot E into ~/ril_e/repo_cache (name owner__name.git).
# The three smallest Verified repositories already sit in ~/ril_s2/raw/repo_cache and are linked, not recloned.
# Idempotent: an existing clone is only fetched. Submit from $HOME.
set -euo pipefail
R=(pydata/xarray matplotlib/matplotlib astropy/astropy internetarchive/openlibrary \
   qutebrowser/qutebrowser conan-io/conan deepset-ai/haystack streamlink/streamlink)
mkdir -p "$HOME/ril_e/repo_cache"
for repo in "${R[@]}"; do
name=${repo/\//__}
dest="$HOME/ril_e/repo_cache/$name.git"
if [ -d "$dest" ]; then
  git --git-dir "$dest" fetch -q origin '+refs/heads/*:refs/heads/*' || true
else
  git clone -q --bare "https://github.com/$repo.git" "$dest.tmp" && mv "$dest.tmp" "$dest"
fi
git --git-dir "$dest" rev-parse --short HEAD
du -sh "$dest"
done
echo done
