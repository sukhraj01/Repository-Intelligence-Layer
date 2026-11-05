#!/bin/bash
#SBATCH --job-name=ril_mp_prep
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=1
#SBATCH --mem=12G
#SBATCH --time=12:00:00
#SBATCH --output=ril_mp/logs/mp_prep_%j.out
# CPU. Preparation of the mined-set integration pilot (E-MINED-PILOT): the pool-like reading of the mined
# pilot run (no test-file function in the corpora, no test positive) packed as a zip in node-local space
# (about 1.3 GB; $HOME has too little room for it), BM25 ranks of every directory, the exact comparison with
# the BM25 ranks of the first 300 directories measured earlier (the job stops here if one rank differs), the
# feature table, the held-out selection, the example cache, and the size FILTER K = 20 leaves. Resumable:
# the rank file is appended per directory; the other outputs are rewritten.
# Memory estimate: BM25 over one directory at a time (the earlier 300-directory job peaked below 3 GB);
# the cache is written as a stream; 12 GB requested is above the measured peak of the stored-text step.
#   sbatch --export=ALL,RIL_COMMIT=<hash> ril_mp/scripts/ada/mp_prep.sbatch
set -euo pipefail
M=$HOME/ril_mp
RUN=${RUN:-$HOME/ril_mine/runs/pilot}
OLD=${OLD:-$HOME/ril_mine/ranks/pilot/non_test/limit300/ranks_bm25.jsonl}
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$HOME/ril_x2/venv_gpu$PYV/bin/python
W=$M/work
T=${TMPDIR:-/tmp}/ril_mp_${SLURM_JOB_ID}
HELD=data/held_out/held_out_repos.json
REN=data/held_out/rename_cache.json
mkdir -p "$W" "$T" "$M/logs"
cd "$M"
export PYTHONPATH="$M"
{ echo "host=$(hostname)"; echo "ril_commit=${RIL_COMMIT:-none}"; df -h /tmp "$HOME" | tail -2; } > "$W/env_prep_${SLURM_JOB_ID}.txt"
$PY -I scripts/mine_pilot.py rank-prepare "$RUN" "$T/full" --drop-tests > "$W/prepare.json"
$PY -I scripts/mine_pilot.py rank-bm25 "$T/full" "$W/ranks_bm25.jsonl" > "$W/bm25_${SLURM_JOB_ID}.json"
$PY -I scripts/mine_pilot.py rank-reproduce "$OLD" --new "$W/ranks_bm25.jsonl" > "$W/reproduce.json"
$PY -I scripts/train.py features "$W/ranks_bm25.jsonl" --out "$W/features_mined.csv" --teachers bm25 \
  --held-out "$HELD" --rename-cache "$REN" > "$W/features.json"
$PY -I scripts/train.py select "$T/full/mined.listing.json" "$HELD" "$REN" "$W/selection_mined.json" \
  --feature-table "$W/features_mined.csv" --seed 0 > "$W/select.json"
$PY -I scripts/train.py cache "$T/full/mined.listing.json" "$W/selection_mined.json" "$T/mined.jsonl.gz" \
  --feature-table "$W/features_mined.csv" --form code --local > "$W/cache.json"
CACHE_BYTES=$(stat -c %s "$T/mined.jsonl.gz")
AVAIL=$(df --output=avail -B1 "$HOME" | tail -1)
echo "cache_bytes=$CACHE_BYTES home_avail_bytes=$AVAIL" > "$W/cache_space.txt"
$PY -I scripts/train.py filter-size "$T/mined.jsonl.gz" "$W/features_mined.csv" --teacher bm25 --k 20 \
  > "$W/filter_size.json"
# keep the cache in $HOME only if at least 1 GiB stays free afterwards; otherwise stop and report
if [ $((AVAIL - CACHE_BYTES)) -ge 1073741824 ]; then
  cp "$T/mined.jsonl.gz" "$W/mined.jsonl.gz.part" && mv "$W/mined.jsonl.gz.part" "$W/mined.jsonl.gz"
  cp "$T/mined.jsonl.gz.json" "$W/mined.jsonl.gz.json"
  echo "cache_kept=1" >> "$W/cache_space.txt"
else
  echo "cache_kept=0" >> "$W/cache_space.txt"
  rm -rf "$T"
  exit 5
fi
rm -rf "$T"
echo done
