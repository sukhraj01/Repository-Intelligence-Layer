#!/bin/bash
#SBATCH --job-name=ril_contam_scan
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=06:00:00
#SBATCH --output=ril_c/logs/contam_scan_%j.out
# CPU only. Scan of CoRNStack python shards (field "document") against ~/ril_c/out/probe_verified.json.
# Four worker processes; shards FIRST, FIRST+STRIDE, ... up to LAST; a shard with an output file is skipped.
# Slice run (every 10th shard, 24 of 240): sbatch --export=ALL,FIRST=0,LAST=239,STRIDE=10 ril_c/scripts/ada/contam_scan.sbatch
# Full scan (about 10 CPU-hours, 307 GB streamed): FIRST=0,LAST=239,STRIDE=1.
set -euo pipefail
cd "$HOME/ril_c"
# base URL from the tree listing of the dataset (field "source"), fetched earlier by hf_list_tree.py
P=$(python3 -c "import glob,json;print(json.load(open(glob.glob('$HOME/ril_s2/raw/listing_*cornstack-python-v1.json')[0]))['source'] + '/resolve/main')")
FIRST=${FIRST:-0}; LAST=${LAST:-239}; STRIDE=${STRIDE:-10}; W=4
worker() {
  for ((i=FIRST+$1*STRIDE; i<=LAST; i+=W*STRIDE)); do
    python3 -I scripts/ada/contam_probe.py scan out/probe_verified.json out/scan "$P" "$i" "$i" 0
  done
}
for ((w=0; w<W; w++)); do worker $w & done
wait
