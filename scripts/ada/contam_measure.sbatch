#!/bin/bash
#SBATCH --job-name=ril_contam_measure
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=6G
#SBATCH --time=01:30:00
#SBATCH --output=ril_c/logs/contam_measure_%j.out
# CPU only. Throughput of streaming the CoRNStack python shards: network read, inflate, JSON parse and
# hashing, on the first MB megabytes of shards 0, 120 and 239 (documents) and of shard 0 (documents and
# negatives). The probe set is empty (hashing cost does not depend on it). Counts and timings only.
# Submit from $HOME: sbatch --export=ALL,MB=200 ril_c/scripts/ada/contam_measure.sbatch
set -euo pipefail
cd "$HOME/ril_c"
mkdir -p out logs
# base URL from the tree listing of the dataset (field "source"), fetched earlier by hf_list_tree.py
P=$(python3 -c "import glob,json;print(json.load(open(glob.glob('$HOME/ril_s2/raw/listing_*cornstack-python-v1.json')[0]))['source'] + '/resolve/main')")
python3 -I -c "
import sys; sys.path.insert(0, '.')
from ril.training.contamination import ProbeSet
open('out/probe_empty.json', 'w').write(ProbeSet().to_json())"
for i in 00000 00120 00239; do
  python3 -I scripts/ada/contam_probe.py measure "$P/shard-$i.jsonl.gz" "${MB:-200}" out/probe_empty.json "out/measure_docs_$i.json"
done
python3 -I scripts/ada/contam_probe.py measure "$P/shard-00000.jsonl.gz" "${MB_NEG:-50}" out/probe_empty.json out/measure_negatives_00000.json --negatives
