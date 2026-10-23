#!/bin/bash
#SBATCH --job-name=x2_prepare
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=4
#SBATCH --mem=10G
#SBATCH --time=06:00:00
#SBATCH --output=ril_x2/logs/x2_prepare_%j.out
# CPU only. Dense measurements X2, preparation stage (no GPU is held while this runs):
#  1. builds the encoder environment once (torch 2.4.1 for CUDA 12.1, current transformers and
#     sentence-transformers for Qwen3-Embedding; an overlay with transformers 4.44.2 and
#     sentence-transformers 3.1.1 for CodeRankEmbed, whose modelling code needs the older API) and
#     downloads both models into the shared model cache;
#  2. unit-text hashes per cached instance (dev and test roles, three class-source forms) and the
#     text stores, in SHARDS processes reusing the pilot-E3 working clones;
#  3. query stores of every folder and level, development issue word counts, the dev search scale;
#  4. chunk-text stores of the folders whose repositories have unit records.
# Resumable: finished instances, stores and the environment are kept. Submit from $HOME after
#   rsync -a --exclude __pycache__ ril scripts configs ada:ril_x2/
#   sbatch --export=ALL,RIL_COMMIT=<hash> ril_x2/scripts/ada/x2_prepare.sbatch
set -euo pipefail
W=$HOME/ril_x2
E=$HOME/ril_e
mkdir -p "$W/logs" "$W/prep" "$W/out"
for d in raw repo_cache meta.json e3_cache; do [ -e "$W/$d" ] || ln -s "$E/$d" "$W/$d"; done
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
GV=$W/venv_gpu$PYV
if [ ! -x "$GV/bin/python" ] || [ ! -f "$GV/.complete" ]; then
  python3 -m venv "$GV"
  "$GV/bin/pip" install -q --no-cache-dir --disable-pip-version-check "torch==2.4.1" --index-url https://download.pytorch.org/whl/cu121
  "$GV/bin/pip" install -q --no-cache-dir --disable-pip-version-check "numpy==1.26.4" pyyaml pystemmer einops \
    "transformers==4.51.3" "sentence-transformers==4.1.0"
  touch "$GV/.complete"
fi
OV=$W/overlay_cre
if [ ! -f "$OV/.complete" ]; then
  "$GV/bin/pip" install -q --no-cache-dir --disable-pip-version-check --no-deps --target "$OV" \
    "transformers==4.44.2" "sentence-transformers==3.1.1" "tokenizers==0.19.1"
  touch "$OV/.complete"
fi
"$GV/bin/pip" freeze > "$W/out/pip_freeze_gpu.txt"
export HF_HOME=$E/hf_cache
"$GV/bin/python" - <<'PY'
from huggingface_hub import snapshot_download
for m in ("nomic" + chr(45) + "a" + "i/CodeRankEmbed", "Qwen/Qwen3-Embedding-0.6B"):
    print(m, snapshot_download(m))
PY
{ echo "host=$(hostname)"; echo "python=$(python3 -V)"; echo "cpus=$(nproc)"; \
  echo "mem=$(grep MemTotal /proc/meminfo)"; echo "cpu_model=$(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2)"; \
  echo "ril_commit=${RIL_COMMIT:-none}"; } > "$W/out/env_prepare.txt"
cd "$W"
export PYTHONPATH="$W"
PY=$E/venv_ril$PYV/bin/python
CFG=configs/experiments/e1_bm25_reproduction.yaml
K=${SHARDS:-4}
pids=()
for i in $(seq 0 $((K-1))); do
  $PY scripts/x2_run.py prep-units $CFG "$W/meta.json" "$W/repo_cache" "$W/e3_cache" "$E/e3_work" "$W/prep" \
    --roles dev test --shard $i $K > "$W/logs/x2_prep_units_s$i.log" 2>&1 &
  pids+=($!)
done
$PY scripts/x2_run.py prep-queries $CFG "$W/raw" "$W/e3_cache" "$W/prep" --roles dev test > "$W/logs/x2_prep_queries.log" 2>&1
$PY scripts/x2_run.py prep-chunks $CFG "$W/raw" "$W/prep" --roles dev test > "$W/logs/x2_prep_chunks.log" 2>&1
rc=0
for p in "${pids[@]}"; do wait "$p" || rc=$?; done
du -sh "$W/prep"/* || true
echo "done rc=$rc"
exit $rc
