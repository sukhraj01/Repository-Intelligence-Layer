#!/bin/bash
#SBATCH --job-name=e_fetch
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=03:00:00
#SBATCH --output=ril_e/logs/e_fetch_%j.out
# CPU only. Fetches the CORE-Bench folders used by pilot E: all twelve SWE-bench Verified folders at
# L2 and L3 (the reproduction of the paper's Verified BM25 row) and the development folders
# (Pro: openlibrary, qutebrowser at L2 and L3; Live: conan, deepset, streamlink at L2).
# Resumable and idempotent (hf_fetch.py skips files whose size matches). Needs
# ~/ril_s2/raw/listing_root.json and ~/ril_s2/scripts/hf_fetch.py.
# Submit from $HOME:  mkdir -p ril_e/logs && sbatch ril_e/scripts/ada/e_fetch_data.sbatch
set -euo pipefail
mkdir -p "$HOME/ril_e/logs" "$HOME/ril_e/data"
cd "$HOME/ril_s2"
P=()
for lvl in LEVEL-2 LEVEL-3; do
  for r in astropy__astropy django__django matplotlib__matplotlib mwaskom__seaborn pallets__flask \
           psf__requests pydata__xarray pylint pytest scikit sphinx sympy__sympy; do
    P+=("data/$lvl/SWE-bench_Verified/$r/")
  done
  for r in instance_internetarchive__openlibrary instance_qutebrowser__qutebrowser; do
    P+=("data/$lvl/SWE-bench_Pro/$r/")
  done
done
for r in conan deepset streamlink__streamlink; do
  P+=("data/LEVEL-2/SWE-bench-Live/$r/")
done
python3 scripts/hf_fetch.py zhangfw123/CORE-Bench raw/listing_root.json "$HOME/ril_e/raw" "${P[@]}"
echo done
