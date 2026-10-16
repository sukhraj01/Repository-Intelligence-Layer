#!/bin/bash
#SBATCH --job-name=ril_cb_samples
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=01:00:00
#SBATCH --output=ril_s2/logs/fetch_core_bench_samples_%j.out
# CPU-only. Fetches the three smallest SWE-bench Verified repositories at L2, L3 and Rewrite-L2
# (all files present: 4 per repo at L2/L3, 3 at Rewrite-L2). Submit from $HOME so the log path resolves.
# Needs ~/ril_s2/raw/listing_root.json from: python3 hf_list_tree.py zhangfw123/CORE-Bench "" listing_root.json
set -euo pipefail
cd "$HOME/ril_s2"
P=()
for lvl in LEVEL-2 LEVEL-3 Rewrite-LEVEL-2; do
  for r in pallets__flask psf__requests mwaskom__seaborn; do
    P+=("data/$lvl/SWE-bench_Verified/$r/")
  done
done
python3 scripts/hf_fetch.py zhangfw123/CORE-Bench raw/listing_root.json raw/core_bench_samples "${P[@]}"
