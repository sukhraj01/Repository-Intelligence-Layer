#!/bin/bash
#SBATCH --job-name=ril_cb_corpus
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=08:00:00
#SBATCH --output=ril_s2/logs/core_bench_corpus_stats_%j.out
# CPU-only, streams (does not store) every L2/L3 corpus.jsonl and keeps row and length counts only.
# Needs ~/ril_s2/raw/listing_data.json (hf_list_tree.py on subpath data). Resumable: finished folders are skipped.
set -euo pipefail
cd "$HOME/ril_s2"
python3 scripts/core_bench_corpus_stats.py raw/listing_data.json raw/corpus_stats 4
