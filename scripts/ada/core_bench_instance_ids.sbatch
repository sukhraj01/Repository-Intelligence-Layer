#!/bin/bash
#SBATCH --job-name=ril_cb_ids
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=04:00:00
#SBATCH --output=ril_s2/logs/core_bench_instance_ids_%j.out
# CPU-only, streams (does not store) queries.jsonl and qrels.jsonl for every L2/L3/Rewrite folder.
# Needs ~/ril_s2/raw/listing_data.json (hf_list_tree.py on subpath data). Resumable: finished folders are skipped.
set -euo pipefail
cd "$HOME/ril_s2"
python3 scripts/core_bench_instance_ids.py raw/listing_data.json raw/ids 4
